"""Behavior Analysis Engine v2 — Cross-table correlation discovery.

Principle: Don't tell the user what they already know.
Find patterns invisible to the naked eye through cross-table correlation.

No keyword matching. No AI calls. Pure SQLite + Python statistics.
"""

import re
import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from db import get_connection

logger = logging.getLogger(__name__)

_EMOJI_RE = re.compile(
    r'[\U0001F300-\U0001F9FF\u2600-\u27BF\u2B50\u2705\u274C\u2795-\u2797\u23CF\u23E9-\u23F3\u23F8-\u23FA\u200D\uFE0F\u20E3]'
)


def _clean(s: str) -> str:
    """Strip emojis and leading symbols from a heading."""
    return _EMOJI_RE.sub("", s or "").strip().lstrip("#-*| ").strip()


class BehaviorAnalyzer:
    """Cross-table analysis engine. All methods read-only."""

    def __init__(self, db_path: str):
        self.conn = get_connection(db_path)

    def close(self):
        self.conn.close()

    # ═══════════════════════════════════════════════════════════════════════
    # Tier 1 — Known Facts (contextualized, not just dumped)
    # ═══════════════════════════════════════════════════════════════════════

    def baseline_stats(self) -> dict:
        """Data inventory with meaningful ratios, not raw counts."""
        total = self.conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
        daily = self.conn.execute(
            "SELECT COUNT(*) FROM notes WHERE note_type='DAILY'"
        ).fetchone()[0]
        total_words = self.conn.execute(
            "SELECT COALESCE(SUM(word_count),0) FROM notes"
        ).fetchone()[0]

        actions = self.conn.execute(
            "SELECT COUNT(*) FROM sections WHERE section_type='ACTION'"
        ).fetchone()[0]
        decisions = self.conn.execute(
            "SELECT COUNT(*) FROM sections WHERE section_type='DECISION'"
        ).fetchone()[0]
        insights = self.conn.execute(
            "SELECT COUNT(*) FROM sections WHERE section_type='INSIGHT'"
        ).fetchone()[0]

        # Section diversity — how many different section types per daily note?
        diversity = self.conn.execute("""
            SELECT n.id, COUNT(DISTINCT s.section_type) as type_count
            FROM notes n
            JOIN sections s ON n.id = s.note_id
            WHERE n.note_type = 'DAILY'
            GROUP BY n.id
        """).fetchall()
        avg_types = sum(r[1] for r in diversity) / max(len(diversity), 1)

        return {
            "total_notes": total,
            "daily_notes": daily,
            "total_words": total_words,
            "actions": actions,
            "decisions": decisions,
            "insights": insights,
            "avg_section_types_per_day": round(avg_types, 1),
            "action_per_day": round(actions / max(daily, 1), 1),
            "decision_per_day": round(decisions / max(daily, 1), 1),
            "insight_per_day": round(insights / max(daily, 1), 1),
        }

    # ═══════════════════════════════════════════════════════════════════════
    # Tier 2 — Correlational Discoveries
    # ═══════════════════════════════════════════════════════════════════════

    def decision_follow_through(self) -> dict:
        """How many decisions actually lead to actions?

        Two measures:
        - Same-day: decision + action in the same daily note
        - Next-day: decision today → action tomorrow
        """
        # Notes that have BOTH decision and action sections (same day)
        same_day = self.conn.execute("""
            SELECT COUNT(DISTINCT n.id)
            FROM notes n
            WHERE n.id IN (SELECT s.note_id FROM sections s WHERE s.section_type='DECISION')
              AND n.id IN (SELECT s.note_id FROM sections s WHERE s.section_type='ACTION')
              AND n.note_type = 'DAILY'
        """).fetchone()[0]

        # Notes with decisions only (no action section same day)
        decision_only = self.conn.execute("""
            SELECT COUNT(DISTINCT n.id)
            FROM notes n
            WHERE n.id IN (SELECT s.note_id FROM sections s WHERE s.section_type='DECISION')
              AND n.id NOT IN (SELECT s.note_id FROM sections s WHERE s.section_type='ACTION')
              AND n.note_type = 'DAILY'
        """).fetchone()[0]

        total_notes_with_decisions = same_day + decision_only

        # Next-day follow-through: notes that had decisions yesterday → actions today
        next_day = self.conn.execute("""
            SELECT COUNT(DISTINCT a.note_id)
            FROM sections a
            JOIN notes an ON a.note_id = an.id
            WHERE a.section_type = 'ACTION'
              AND an.note_type = 'DAILY'
              AND an.note_date != ''
              AND EXISTS (
                  SELECT 1 FROM sections d
                  JOIN notes dn ON d.note_id = dn.id
                  WHERE d.section_type = 'DECISION'
                    AND dn.note_type = 'DAILY'
                    AND dn.note_date != ''
                    AND date(dn.note_date) = date(an.note_date, '-1 day')
              )
        """).fetchone()[0]

        # Days where decisions had no same-day action AND no next-day action
        stranded = self.conn.execute("""
            SELECT dn.id, dn.note_date FROM sections d
            JOIN notes dn ON d.note_id = dn.id
            WHERE d.section_type = 'DECISION'
              AND dn.note_type = 'DAILY'
              AND dn.note_date != ''
              AND dn.id NOT IN (SELECT note_id FROM sections WHERE section_type='ACTION')
              AND NOT EXISTS (
                  SELECT 1 FROM sections a2
                  JOIN notes an2 ON a2.note_id = an2.id
                  WHERE a2.section_type = 'ACTION'
                    AND an2.note_type = 'DAILY'
                    AND date(an2.note_date) = date(dn.note_date, '+1 day')
              )
        """).fetchall()

        # Decision count from daily notes (for the follow-through analysis)
        decision_count_daily = self.conn.execute("""
            SELECT COUNT(*) FROM sections s
            JOIN notes n ON s.note_id = n.id
            WHERE s.section_type = 'DECISION' AND n.note_type = 'DAILY'
        """).fetchone()[0]

        same_day_rate = same_day / max(total_notes_with_decisions, 1)

        # Decision count from all notes (for context)
        total_all = self.conn.execute(
            "SELECT COUNT(*) FROM sections WHERE section_type='DECISION'"
        ).fetchone()[0]

        return {
            "total_decisions_all_notes": total_all,
            "total_decisions_daily": decision_count_daily,
            "days_with_decisions": total_notes_with_decisions,
            "same_day_action_pct": f"{same_day_rate * 100:.0f}%",
            "same_day_action_days": same_day,
            "decision_only_days": decision_only,
            "next_day_action_days": next_day,
            "stranded_days": [
                {"date": note_date} for _, note_date in stranded
            ],
            "stranded_count": len(stranded),
            "insight": self._interpret_conversion(
                same_day, same_day + decision_only, same_day_rate
            ),
        }

    @staticmethod
    def _interpret_conversion(followed, total, rate):
        """Interpret decision follow-through with nuance."""
        if total == 0:
            return "暂无足够数据。"
        stranded = total - followed
        if rate >= 0.8:
            return (
                f"执行力强：{rate*100:.0f}% 的决策日在同一天有行动记录。"
                f"决策和行动高度耦合。"
            )
        elif rate >= 0.5:
            return (
                f"中等：{rate*100:.0f}% 的决策日同天有行动。"
                f"{stranded}/{total} 天做了决策但当天未执行——这些决策可能停留在思考层。"
            )
        else:
            return (
                f"⚠️ 仅 {rate*100:.0f}% 的决策日同天有行动。"
                f"{stranded}/{total} 天做了决策却没有行动记录。大量'决策泡沫'——制定了但未推进。"
            )

    def attention_fragmentation(self) -> dict:
        """How many different contexts does Song switch between daily?

        Fragmented days → output quality drops next day.
        """
        # Per-day section type diversity + wikilink diversity
        daily_activity = self.conn.execute("""
            SELECT n.id, n.note_date, n.word_count,
                   COUNT(DISTINCT s.section_type) as section_types,
                   COUNT(s.id) as section_count
            FROM notes n
            LEFT JOIN sections s ON n.id = s.note_id
            WHERE n.note_type = 'DAILY' AND n.note_date != ''
            GROUP BY n.id
            ORDER BY n.note_date
        """).fetchall()

        # Per-day wikilink target diversity
        daily_links = defaultdict(set)
        link_rows = self.conn.execute("""
            SELECT n.note_date, l.target_path
            FROM links l
            JOIN notes n ON l.source_id = n.id
            WHERE n.note_type = 'DAILY' AND n.note_date != ''
        """).fetchall()
        for ndate, target in link_rows:
            # Normalize: first path component as domain
            domain = target.split("/")[0] if "/" in target else target
            daily_links[ndate].add(domain)

        # Build timeline: each day's fragmentation score
        timeline = []
        prev_wc = 0
        for row in daily_activity:
            nid, ndate, wc, stypes, scount = row
            link_domains = len(daily_links.get(ndate, set()))
            frag_score = stypes + min(link_domains, 10)  # cap at +10

            # Does prev day's fragmentation predict today's output drop?
            output_delta = wc - prev_wc if prev_wc else 0
            timeline.append({
                "date": ndate,
                "word_count": wc,
                "section_types": stypes,
                "link_domains": link_domains,
                "fragmentation_score": frag_score,
                "output_delta_vs_prev": output_delta,
            })
            prev_wc = wc

        # Correlation: high fragmentation → next day word count drops?
        fragmented_days = [d for d in timeline if d["fragmentation_score"] >= 5]
        drops_after_fragment = 0
        for i, day in enumerate(timeline):
            if i == 0:
                continue
            prev = timeline[i - 1]
            if prev["fragmentation_score"] >= 5 and day["output_delta_vs_prev"] < 0:
                drops_after_fragment += 1

        # Most fragmented days
        top_fragmented = sorted(timeline, key=lambda x: -x["fragmentation_score"])[:5]

        return {
            "total_daily_notes": len(timeline),
            "avg_fragmentation": round(
                sum(d["fragmentation_score"] for d in timeline) / max(len(timeline), 1), 1
            ),
            "high_frag_days_count": len(fragmented_days),
            "drops_after_high_frag": drops_after_fragment,
            "fragmentation_cost": (
                f"碎片化日（分数≥5）后，{drops_after_fragment}/{len(fragmented_days)} 天输出下降"
                if fragmented_days
                else "数据不足以计算"
            ),
            "most_fragmented_days": [
                {"date": d["date"], "score": d["fragmentation_score"],
                 "domain_count": d["link_domains"]}
                for d in top_fragmented
            ],
        }

    def idea_to_output_pipeline(self) -> dict:
        """Track how insights (认知收获) travel from capture → action → output.

        Identifies: ideas that are captured but never acted on.
        """
        # INSIGHT sections
        insights = self.conn.execute("""
            SELECT s.id, s.heading, s.content, n.note_date
            FROM sections s
            JOIN notes n ON s.note_id = n.id
            WHERE s.section_type = 'INSIGHT'
            ORDER BY n.note_date
        """).fetchall()

        # Find which insights have wikilinks to OUTPUT notes
        output_references = self.conn.execute("""
            SELECT l.source_id, l.target_path
            FROM links l
            WHERE l.target_path LIKE '%Output%' OR l.target_path LIKE '%05 %'
        """).fetchall()
        output_ref_ids = {row[0] for row in output_references}

        # Tag presence: which tags appear in OUTPUT notes
        output_tags = set()
        tag_rows = self.conn.execute("""
            SELECT DISTINCT t.name FROM tags t
            JOIN note_tags nt ON t.id = nt.tag_id
            JOIN notes n ON nt.note_id = n.id
            WHERE n.note_type = 'OUTPUT'
        """).fetchall()
        for (tn,) in tag_rows:
            output_tags.add(tn)

        # For each insight, check if related to any output note via tags
        insight_tag_map = defaultdict(set)
        ins_tag_rows = self.conn.execute("""
            SELECT nt.note_id, t.name FROM tags t
            JOIN note_tags nt ON t.id = nt.tag_id
            JOIN sections s ON nt.note_id = s.note_id
            WHERE s.section_type = 'INSIGHT'
        """).fetchall()
        for nid, tname in ins_tag_rows:
            insight_tag_map[nid].add(tname)

        linked_insights = 0
        stuck_insights = []
        for sid, heading, content, ndate in insights:
            # Filter malformed dates (e.g. frontmatter dict leaks)
            if not isinstance(ndate, str) or not ndate or ndate.startswith("{"):
                continue

            # Get note_id for this insight's section
            note_id = self.conn.execute(
                "SELECT note_id FROM sections WHERE id=?", (sid,)
            ).fetchone()[0]

            tags = insight_tag_map.get(note_id, set())
            has_output_link = tags & output_tags

            if has_output_link:
                linked_insights += 1
            else:
                clean_h = _clean(heading or "")
                snippet = (content or "")[:60].replace("\n", " ")
                stuck_insights.append({
                    "date": ndate,
                    "heading": clean_h[:50],
                    "snippet": snippet,
                })

        total = len(insights)

        return {
            "total_insights": total,
            "insights_linked_to_output": linked_insights,
            "linkage_rate": f"{linked_insights / max(total, 1) * 100:.0f}%",
            "stuck_ideas": stuck_insights[-10:],  # most recent stuck ideas
            "stuck_count": len(stuck_insights),
            "insight": self._interpret_pipeline(
                linked_insights, total, stuck_insights
            ),
        }

    def decision_quality_patterns(self) -> dict:
        """Do thorough decisions (with table structure) have better follow-through?

        Hypothesis: structured thinking → better execution.
        """
        # Categorize decisions: table-backed vs. prose
        decisions = self.conn.execute("""
            SELECT s.id, s.heading, s.content, s.word_count, n.note_date
            FROM sections s
            JOIN notes n ON s.note_id = n.id
            WHERE s.section_type = 'DECISION' AND n.note_date != ''
            ORDER BY n.note_date
        """).fetchall()

        table_decisions = []
        prose_decisions = []
        for did, heading, content, wc, ndate in decisions:
            entry = {"id": did, "heading": _clean(heading)[:60], "date": ndate, "wc": wc}
            if content and "|" in content:
                table_decisions.append(entry)
            else:
                prose_decisions.append(entry)

        # Action dates for follow-through check
        action_dates = set()
        for (nd,) in self.conn.execute(
            "SELECT DISTINCT n.note_date FROM sections s "
            "JOIN notes n ON s.note_id=n.id WHERE s.section_type='ACTION' AND n.note_date!=''"
        ).fetchall():
            action_dates.add(nd)

        def _followed_rate(dlist):
            if not dlist:
                return 0
            f = 0
            for d in dlist:
                try:
                    dt = datetime.fromisoformat(d["date"][:10])
                except ValueError:
                    continue
                for off in range(4):
                    if (dt + timedelta(days=off)).strftime("%Y-%m-%d") in action_dates:
                        f += 1
                        break
            return f / len(dlist)

        table_rate = _followed_rate(table_decisions)
        prose_rate = _followed_rate(prose_decisions)

        return {
            "total_decisions": len(decisions),
            "table_backed": len(table_decisions),
            "prose_decisions": len(prose_decisions),
            "table_follow_through": f"{table_rate * 100:.0f}%",
            "prose_follow_through": f"{prose_rate * 100:.0f}%",
            "insight": (
                f"结构化决策（表格）转化率 {table_rate*100:.0f}% vs "
                f"自由文本决策 {prose_rate*100:.0f}%"
                if table_decisions and prose_decisions
                else "数据不足以比较"
            ),
        }

    def output_momentum(self) -> dict:
        """Binge-bust cycle detection: do high-output days precede burnout?

        Also: which writing pattern (morning vs evening, burst vs steady) produces more?
        """
        daily = self.conn.execute("""
            SELECT n.id, n.note_date, n.word_count,
                   COUNT(s.id) as section_count
            FROM notes n
            LEFT JOIN sections s ON n.id = s.note_id
            WHERE n.note_type = 'DAILY' AND n.note_date != ''
            GROUP BY n.id
            ORDER BY n.note_date
        """).fetchall()

        if len(daily) < 5:
            return {"insight": "至少需要 5 天数据才能检测动量模式"}

        wc_values = [r[2] for r in daily]
        dates = [r[1] for r in daily]
        avg_wc = sum(wc_values) / len(wc_values)
        threshold = avg_wc * 1.5  # 50% above average = "burst"

        burst_info = []
        for i, (nid, ndate, wc, sc) in enumerate(daily):
            if wc >= threshold:
                next_wc = wc_values[i + 1] if i + 1 < len(wc_values) else wc
                delta = next_wc - wc
                burst_info.append({
                    "date": ndate,
                    "word_count": wc,
                    "next_day_change": f"{delta:+d}",
                    "burnout": delta < -wc * 0.3,
                })

        burnout_count = sum(1 for b in burst_info if b["burnout"])

        # Consistent vs erratic: calculate coefficient of variation
        mean = sum(wc_values) / len(wc_values)
        variance = sum((w - mean) ** 2 for w in wc_values) / len(wc_values)
        cv = (variance ** 0.5) / max(mean, 1)

        return {
            "daily_count": len(daily),
            "avg_words_per_day": round(avg_wc),
            "coeff_variation": round(cv, 2),
            "consistency": (
                "稳定" if cv < 0.5 else ("波动较大" if cv < 1.0 else "极不稳定")
            ),
            "burst_days": len(burst_info),
            "burst_led_to_burnout": burnout_count,
            "burst_samples": burst_info[:5],
            "insight": (
                f"{len(burst_info)} 天输出爆发，其中 {burnout_count} 天次日输出大幅下降"
                if burst_info
                else "无异常爆发日"
            ),
        }

    def tag_lifecycle(self) -> dict:
        """Which themes are emerging, stable, or fading?

        Split timeline into two halves; compare tag frequency.
        """
        tag_timeline = self.conn.execute("""
            SELECT t.name, n.note_date
            FROM tags t
            JOIN note_tags nt ON t.id = nt.tag_id
            JOIN notes n ON nt.note_id = n.id
            WHERE n.note_date != ''
            ORDER BY n.note_date
        """).fetchall()

        if not tag_timeline:
            return {"insight": "No dated tag data."}

        dates = sorted(set(d[1] for d in tag_timeline))
        mid = len(dates) // 2
        mid_date = dates[mid] if mid > 0 else dates[-1]

        first_half = Counter()
        second_half = Counter()
        for tname, ndate in tag_timeline:
            if ndate <= mid_date:
                first_half[tname] += 1
            else:
                second_half[tname] += 1

        emerging = []
        fading = []
        stable = []

        all_tags = set(list(first_half.keys()) + list(second_half.keys()))
        for tag in all_tags:
            f = first_half.get(tag, 0)
            s = second_half.get(tag, 0)
            if f == 0 and s > 0:
                emerging.append((tag, s))
            elif s == 0 and f > 0:
                fading.append((tag, f))
            elif f > 0 and s > 0:
                change = (s - f) / max(f, 1)
                if change > 0.5:
                    emerging.append((tag, s))
                elif change < -0.5:
                    fading.append((tag, f))
                else:
                    stable.append((tag, f + s))

        emerging.sort(key=lambda x: -x[1])
        fading.sort(key=lambda x: -x[1])
        stable.sort(key=lambda x: -x[1])

        emerging_f = [(t, c) for t, c in emerging if c >= 2]
        fading_f = [(t, c) for t, c in fading if c >= 2]
        stable_f = [(t, c) for t, c in stable[:6]]

        return {
            "midpoint_date": mid_date,
            "emerging": emerging_f[:8],
            "fading": fading_f[:8],
            "stable": stable_f,
            "insight": (
                f"上升期主题 {len(emerging_f)} 个，衰退中 {len(fading_f)} 个，稳定 {len(stable_f)} 个"
            ),
        }

    # ═══════════════════════════════════════════════════════════════════════
    # Tier 3 — Automation Signal
    # ═══════════════════════════════════════════════════════════════════════

    def automation_signal(self) -> dict:
        """Find repeated workflows: same structural pattern, different data.

        Three signals:
        - Same heading pattern appears ≥3 times → template candidate
        - Table structure + same columns → workflow candidate
        - Same wikilink target + repeated action → integration candidate
        """
        # Signal 1: Repeated heading prefixes (normalized)
        actions = self.conn.execute("""
            SELECT s.heading, s.content, n.note_date
            FROM sections s
            JOIN notes n ON s.note_id = n.id
            WHERE s.section_type = 'ACTION' AND s.heading != ''
            ORDER BY n.note_date
        """).fetchall()

        heading_normalized = defaultdict(list)
        for heading, content, ndate in actions:
            norm = _clean(heading)[:30]
            heading_normalized[norm].append({
                "date": ndate,
                "heading": _clean(heading),
                "has_table": "|" in (content or ""),
                "word_count": len((content or "").split()),
            })

        templates = []
        for norm, instances in heading_normalized.items():
            if len(instances) >= 2:
                table_count = sum(1 for i in instances if i["has_table"])
                avg_wc = sum(i["word_count"] for i in instances) / len(instances)
                templates.append({
                    "pattern": norm,
                    "count": len(instances),
                    "has_table": table_count >= len(instances) * 0.5,
                    "avg_word_count": round(avg_wc),
                    "repetition": "daily" if len(instances) >= len(set(i["date"] for i in instances)) * 0.7 else "occasional",
                })

        templates.sort(key=lambda x: -(x["count"] * 2 + (5 if x["has_table"] else 0)))

        # Signal 2: Cross-project repeated wikilink patterns
        repeated_links = self.conn.execute("""
            SELECT l.target_path, COUNT(DISTINCT l.source_id) as source_count,
                   COUNT(*) as total_refs
            FROM links l
            GROUP BY l.target_path
            HAVING source_count >= 3
            ORDER BY total_refs DESC
            LIMIT 15
        """).fetchall()

        # Signal 3: Table column consistency
        table_actions = [(h, c, d) for h, c, d in actions if c and "|" in c]
        table_columns = []
        for heading, content, ndate in table_actions:
            first_row = content.strip().split("\n")[0]
            cols = [c.strip() for c in first_row.split("|") if c.strip()]
            if cols:
                table_columns.append((_clean(heading), tuple(cols), ndate))

        col_counter = Counter()
        for h, cols, nd in table_columns:
            col_counter[cols] += 1

        consistent_tables = [
            {"columns": list(cols), "count": cnt}
            for cols, cnt in col_counter.most_common(5)
            if cnt >= 2
        ]

        return {
            "template_candidates": [
                {
                    "pattern": t["pattern"],
                    "frequency": f"{t['count']} 次 / {t['repetition']}",
                    "structure": "表格化" if t["has_table"] else "自由文本",
                    "automation_potential": (
                        "高" if t["count"] >= 3 and t["has_table"]
                        else "中" if t["count"] >= 2 and t["has_table"]
                        else "低"
                    ),
                }
                for t in templates[:10]
            ],
            "integration_hooks": [
                {"target": p, "sources": c, "total_refs": t}
                for p, c, t in repeated_links[:10]
            ],
            "consistent_table_schemas": consistent_tables,
            "summary": (
                f"模板候选 {len(templates)} 个，"
                f"被 ≥3 篇笔记引用的集成点 {len(repeated_links)} 个，"
                f"一致表格结构 {len(consistent_tables)} 种"
            ),
        }

    def decision_trajectories(self) -> dict:
        """Track each decision theme from formulation → persistence → outcome.

        Core commercial insight: not "you made X decisions" but
        "your decisions survive N days on average, and here's when they die."
        """
        # ── 1. Build daily theme fingerprints ──
        # For each daily note, collect its tags and wikilink targets as a "theme set"

        daily_tags = defaultdict(set)
        tag_rows = self.conn.execute("""
            SELECT n.note_date, t.name FROM tags t
            JOIN note_tags nt ON t.id = nt.tag_id
            JOIN notes n ON nt.note_id = n.id
            WHERE n.note_type = 'DAILY' AND n.note_date != ''
            ORDER BY n.note_date
        """).fetchall()
        for ndate, tname in tag_rows:
            daily_tags[ndate].add(tname)

        daily_links = defaultdict(set)
        link_rows = self.conn.execute("""
            SELECT n.note_date, l.target_path FROM links l
            JOIN notes n ON l.source_id = n.id
            WHERE n.note_type = 'DAILY' AND n.note_date != ''
        """).fetchall()
        for ndate, target in link_rows:
            domain = target.split("/")[0] if "/" in target else target
            daily_links[ndate].add(domain)

        # ── 2. Identify decision themes per day ──
        decision_rows = self.conn.execute("""
            SELECT DISTINCT n.note_date, s.heading
            FROM sections s
            JOIN notes n ON s.note_id = n.id
            WHERE s.section_type = 'DECISION' AND n.note_type = 'DAILY' AND n.note_date != ''
            ORDER BY n.note_date
        """).fetchall()

        # Build theme set for each decision day
        decision_themes: dict[str, set] = {}
        decision_headings: dict[str, list] = defaultdict(list)
        for ndate, heading in decision_rows:
            themes = set()
            themes.update(daily_tags.get(ndate, set()))
            themes.update(daily_links.get(ndate, set()))
            if themes:
                decision_themes[ndate] = themes
            decision_headings[ndate].append(_clean(heading)[:40])

        # ── 3. Calculate theme persistence ──
        all_dates = sorted(set(daily_tags.keys()) | set(daily_links.keys()))
        if len(all_dates) < 2:
            return {"insight": "Need at least 2 days of data for trajectory analysis."}

        trajectories = []
        for i, ddate in enumerate(all_dates):
            if ddate not in decision_themes:
                continue
            dthemes = decision_themes[ddate]

            # How many subsequent days contain ≥50% of the same themes?
            persistence = 0
            last_seen = ddate
            for j in range(i + 1, len(all_dates)):
                later_themes = daily_tags.get(all_dates[j], set()) | daily_links.get(
                    all_dates[j], set()
                )
                if not later_themes:
                    continue
                overlap = dthemes & later_themes
                if len(overlap) >= max(1, len(dthemes) * 0.3):
                    persistence += 1
                    last_seen = all_dates[j]
                else:
                    break  # theme chain broken

            # Status
            days_since_last = len(all_dates) - 1 - i
            if persistence >= days_since_last - 1 and i < len(all_dates) - 3:
                status = "active"
            elif persistence == 0:
                status = "no_traction"
            elif persistence <= 2 and i < len(all_dates) - 4:
                status = "likely_abandoned"
            else:
                status = "uncertain"

            trajectories.append({
                "date": ddate,
                "themes": sorted(dthemes)[:5],
                "headings": decision_headings.get(ddate, [])[:2],
                "persistence_days": persistence,
                "last_seen": last_seen,
                "status": status,
                "theme_count": len(dthemes),
            })

        # ── 4. Aggregate stats ──
        active = [t for t in trajectories if t["status"] == "active"]
        abandoned = [t for t in trajectories if t["status"] == "likely_abandoned"]
        no_traction = [t for t in trajectories if t["status"] == "no_traction"]

        persistences = [t["persistence_days"] for t in trajectories if t["persistence_days"] > 0]
        avg_persistence = sum(persistences) / max(len(persistences), 1)

        # ── 5. Direction switches ──
        switches = self._detect_direction_switches(all_dates, daily_tags, daily_links)

        return {
            "total_trajectories": len(trajectories),
            "active_themes": len(active),
            "abandoned_themes": len(abandoned),
            "no_traction": len(no_traction),
            "avg_persistence_days": round(avg_persistence, 1),
            "trajectories": trajectories,
            "direction_switches": switches,
            "insight": self._trajectory_insight(trajectories, switches),
        }

    def _detect_direction_switches(
        self, all_dates: list, daily_tags: dict, daily_links: dict
    ) -> list[dict]:
        """Detect when focus shifts: new theme cluster replaces old one."""
        if len(all_dates) < 4:
            return []

        switches = []
        prev_cluster = set()

        for i in range(len(all_dates)):
            current = daily_tags.get(all_dates[i], set()) | daily_links.get(all_dates[i], set())
            if not current:
                continue

            if prev_cluster and current:
                # New themes appearing, old themes disappearing
                new_arrivals = current - prev_cluster
                departures = prev_cluster - current

                if len(new_arrivals) >= 3 or len(departures) >= 3:
                    switches.append({
                        "date": all_dates[i],
                        "incoming": sorted(new_arrivals)[:5],
                        "outgoing": sorted(departures)[:5],
                        "magnitude": len(new_arrivals) + len(departures),
                    })

            prev_cluster = current

        switches.sort(key=lambda x: -x["magnitude"])
        return switches[:8]

    @staticmethod
    def _trajectory_insight(trajectories: list, switches: list) -> str:
        if not trajectories:
            return "暂无足够数据。"
        active = sum(1 for t in trajectories if t["status"] == "active")
        abandoned = sum(1 for t in trajectories if t["status"] == "likely_abandoned")
        avg_p = (
            sum(t["persistence_days"] for t in trajectories if t["persistence_days"] > 0)
            / max(sum(1 for t in trajectories if t["persistence_days"] > 0), 1)
        )
        parts = [f"决策主题平均存活 {avg_p:.1f} 天"]
        if abandoned:
            parts.append(f"{abandoned} 个主题可能已放弃")
        if switches:
            parts.append(f"检测到 {len(switches)} 次方向切换")
        if active:
            parts.append(f"{active} 个主题持续活跃")
        return "；".join(parts)

    # ═══════════════════════════════════════════════════════════════════════
    # Structured profiles (for CLI commands)
    # ═══════════════════════════════════════════════════════════════════════

    def decision_profile(self) -> dict:
        """songos decision — Decision Analytics.

        Answers: How does Song make decisions? What's the execution rate?
                How long do decisions survive? When does focus shift?
        """
        dft = self.decision_follow_through()
        dq = self.decision_quality_patterns()
        b = self.baseline_stats()
        dt = self.decision_trajectories()

        tag_combo_impact = self._tag_combo_decision_impact()
        domains = self._decision_domain_breakdown()

        return {
            "period": f"{b['daily_notes']} 天日记",
            "total_decisions_all": dft["total_decisions_all_notes"],
            "total_decisions_daily": dft["total_decisions_daily"],
            "execution_rate": dft["same_day_action_pct"],
            "same_day_action": dft["same_day_action_days"],
            "next_day_action": dft["next_day_action_days"],
            "stranded": dft["stranded_count"],
            "avg_per_day": b["decision_per_day"],
            "structured_vs_prose": {
                "structured": {"count": dq["table_backed"], "rate": dq["table_follow_through"]},
                "prose": {"count": dq["prose_decisions"], "rate": dq["prose_follow_through"]},
            },
            "domains": domains,
            "anti_patterns": tag_combo_impact,
            "insight": dft["insight"],
            "data_sufficient": b["daily_notes"] >= 30,
            # ── Decision Trajectory (new) ──
            "trajectory": dt,
        }

    def behavioral_patterns(self) -> dict:
        """songos pattern — Behavioral Patterns.

        Answers: What are Song's recurring habits? Time allocation?
                Context switching cost? Output rhythm? Idea pipeline?
        """
        af = self.attention_fragmentation()
        i2o = self.idea_to_output_pipeline()
        om = self.output_momentum()
        tl = self.tag_lifecycle()
        au = self.automation_signal()
        b = self.baseline_stats()

        return {
            "period": f"{b['daily_notes']} 天日记",
            "output_cycle": {
                "avg_daily": om["avg_words_per_day"],
                "consistency": om["consistency"],
                "cv": om["coeff_variation"],
                "burst_days": om["burst_days"],
                "burnout_after_burst": om["burst_led_to_burnout"],
                "samples": om.get("burst_samples", []),
                "insight": om["insight"],
            },
            "context_switching": {
                "avg_domains_per_day": af["avg_fragmentation"],
                "fragmented_days": af["high_frag_days_count"],
                "drops_after_frag": af["drops_after_high_frag"],
                "cost": af["fragmentation_cost"],
                "worst_days": af.get("most_fragmented_days", [])[:3],
            },
            "idea_pipeline": {
                "total_insights": i2o["total_insights"],
                "converted_to_output": i2o["insights_linked_to_output"],
                "linkage_rate": i2o["linkage_rate"],
                "stuck_count": i2o["stuck_count"],
                "recent_stuck": i2o.get("stuck_ideas", [])[-3:],
                "insight": i2o["insight"],
            },
            "theme_migration": {
                "emerging": tl["emerging"],
                "fading": tl["fading"],
                "stable": tl["stable"],
                "insight": tl["insight"],
            },
            "automation": {
                "templates": au["template_candidates"],
                "integrations": au["integration_hooks"],
                "table_schemas": au["consistent_table_schemas"],
                "summary": au["summary"],
            },
        }

    def proto_twin(self) -> dict:
        """songos twin — Proto Digital Twin.

        Answers: What do we know about Song's behavior?
                What can we predict? What's missing?
        """
        b = self.baseline_stats()
        dft = self.decision_follow_through()
        om = self.output_momentum()
        tl = self.tag_lifecycle()

        readiness = self._twin_readiness(b)

        return {
            "stage": "Proto-Twin v0.1",
            "readiness": readiness,
            "known_traits": {
                "decision_style": (
                    "决策-行动高度耦合（当天决策当天执行）"
                    if dft["same_day_action_days"] >= dft["days_with_decisions"] * 0.8
                    else "决策与行动存在延迟"
                ),
                "output_style": f"{om['consistency']}型（变异系数 {om['coeff_variation']}）",
                "focus_trajectory": _format_focus_shift(tl),
                "insight_capture_rate": b["insight_per_day"],
                "decision_velocity": f"日均 {b['decision_per_day']} 个决策",
            },
            "what_we_can_predict": readiness["predictable"],
            "whats_missing": readiness["missing"],
        }

    # ─── Helper: Twin readiness ───────────────────────────────────────────

    def _twin_readiness(self, baseline: dict) -> dict:
        daily = baseline["daily_notes"]
        decisions = baseline["decisions"]
        actions = baseline["actions"]

        predictable = []
        missing = []

        if daily >= 30:
            predictable.append("输出节奏预测（月度模式可识别）")
        else:
            missing.append(f"日记天数不足（{daily}/30），无法识别月度模式")

        if decisions >= 200:
            predictable.append("决策偏好预测（统计显著）")
        else:
            missing.append(f"决策数据不足（{decisions}/200），无法建模决策偏好")

        if actions >= 100:
            predictable.append("行动模式聚类")
        else:
            missing.append(f"行动数据不足（{actions}/100），无法聚类行为模式")

        if not predictable:
            predictable.append("暂无足够数据用于预测。持续记录每日日记以积累数据。")

        return {
            "level": (
                "🔴 数据积累期" if daily < 30
                else "🟡 模式识别期" if daily < 90
                else "🟢 预测就绪"
            ),
            "predictable": predictable,
            "missing": missing,
        }

    # ─── Helper: Decision domain breakdown ────────────────────────────────

    def _decision_domain_breakdown(self) -> list[dict]:
        """Cluster decision headings into domains."""
        rows = self.conn.execute("""
            SELECT s.heading, COUNT(*) as cnt
            FROM sections s
            JOIN notes n ON s.note_id = n.id
            WHERE s.section_type = 'DECISION' AND n.note_type = 'DAILY'
            GROUP BY s.heading
            ORDER BY cnt DESC
        """).fetchall()
        return [{"heading": _clean(h)[:60], "count": c} for h, c in rows[:10]]

    # ─── Helper: Tag combo → decision impact ──────────────────────────────

    def _tag_combo_decision_impact(self) -> list[dict]:
        """Find tag combinations that co-occur with decisions, then check
        if those combos correlate with low output days."""
        # Get tag pairs that appear in decision-laden notes
        pairs = self.conn.execute("""
            SELECT t1.name, t2.name, COUNT(DISTINCT nt1.note_id) as pair_count
            FROM note_tags nt1
            JOIN note_tags nt2 ON nt1.note_id = nt2.note_id AND nt1.tag_id < nt2.tag_id
            JOIN tags t1 ON nt1.tag_id = t1.id
            JOIN tags t2 ON nt2.tag_id = t2.id
            WHERE nt1.note_id IN (
                SELECT DISTINCT s.note_id FROM sections s
                WHERE s.section_type = 'DECISION'
            )
            GROUP BY t1.name, t2.name
            HAVING pair_count >= 2
            ORDER BY pair_count DESC
            LIMIT 10
        """).fetchall()

        return [
            {"combo": f"{t1} + {t2}", "co_occurrence": cnt}
            for t1, t2, cnt in pairs
        ]

    # ═══════════════════════════════════════════════════════════════════════
    # Full run (backward compatible)
    # ═══════════════════════════════════════════════════════════════════════

    def run_all(self) -> dict:
        return {
            "baseline": self.baseline_stats(),
            "decision": self.decision_profile(),
            "patterns": self.behavioral_patterns(),
            "twin": self.proto_twin(),
        }

    # ─── Interpreters ────────────────────────────────────────────────────

    @staticmethod
    def _interpret_pipeline(linked, total, stuck):
        rate = linked / max(total, 1)
        if rate < 0.2:
            return (
                f"⚠️ 仅 {rate*100:.0f}% 的认知收获转化为输出。"
                f"{len(stuck)} 条洞察被捕获但未落地。"
                f"最大的浪费不是没想法，而是想法停留在笔记里。"
            )
        return (
            f"认知→输出转化率 {rate*100:.0f}%。"
            f"{len(stuck)} 条洞察尚未关联产出。"
        )


def _format_focus_shift(tl: dict) -> str:
    emerging = [t for t, _ in tl["emerging"][:3]] if tl["emerging"] else []
    fading = [t for t, _ in tl["fading"][:3]] if tl["fading"] else []
    parts = []
    if emerging:
        parts.append(f"↗ {', '.join(emerging)}")
    if fading:
        parts.append(f"↘ {', '.join(fading)}")
    return " | ".join(parts) if parts else "暂无足够数据"
