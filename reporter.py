"""Report generator — Song Knowledge Report + Decision Profile + Behavioral Patterns + Proto-Twin."""
import os
from datetime import datetime
from pathlib import Path
from collections import Counter

from db import get_connection, query_stats
from analyzer import BehaviorAnalyzer


def generate_report_md(db_path: str) -> str:
    """Data inventory report (songos profile)."""
    conn = get_connection(db_path)
    stats = query_stats(conn)

    total = stats["total_notes"]
    daily = stats["daily_notes"]
    actions = stats["has_actions"]
    decisions = stats["has_decisions"]
    insights = stats["has_insights"]
    words = stats["total_words"]
    types = stats["note_types"]

    rows = conn.execute(
        "SELECT MIN(note_date), MAX(note_date) FROM notes "
        "WHERE note_date != '' AND note_date GLOB '[0-9][0-9][0-9][0-9]-*'"
    ).fetchone()
    date_range = f"{rows[0]} ~ {rows[1]}" if rows and rows[0] else "Unknown"

    tag_counts = dict(conn.execute("""
        SELECT t.name, COUNT(*) FROM tags t
        JOIN note_tags nt ON t.id=nt.tag_id
        GROUP BY t.name ORDER BY COUNT(*) DESC LIMIT 10
    """).fetchall())
    conn.close()

    lines = [
        f"# Song Knowledge Report v1",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Data Inventory",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total notes indexed | {total} |",
        f"| Daily notes | {daily} |",
        f"| Date range | {date_range} |",
        f"| Total words | {words:,} |",
        f"| Avg words/day | {words // max(daily, 1):,} |",
        "",
        "## Behavioral Data Available",
        f"| Section Type | Count |",
        f"|-------------|-------|",
        f"| Actions | {actions} |",
        f"| Decisions | {decisions} |",
        f"| Insights | {insights} |",
        "",
        "## Top Tags",
    ]
    for tag, cnt in tag_counts.items():
        lines.append(f"- `{tag}` — {cnt}")
    lines.append("")

    lines.append("## Note Types")
    for nt, cnt in sorted(types.items(), key=lambda x: -x[1]):
        lines.append(f"- {nt}: {cnt}")
    lines.append("")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# songos decision — Decision Analytics
# ═══════════════════════════════════════════════════════════════════════════

def generate_decision_report(db_path: str) -> str:
    """Decision Profile: how Song makes decisions."""
    a = BehaviorAnalyzer(db_path)
    d = a.decision_profile()
    a.close()

    lines = [
        f"# Song Decision Profile",
        f"**Period:** {d['period']}",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        '> 不是「你做了什么决定」，而是「你是怎么决定的」。',
        "",
        "---",
        "",
        "## Decision Summary",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total decisions (all notes) | {d['total_decisions_all']} |",
        f"| Decisions in daily journals | {d['total_decisions_daily']} |",
        f"| Execution rate (same-day action) | {d['execution_rate']} |",
        f"| Days with same-day action | {d['same_day_action']} |",
        f"| Days with next-day action | {d['next_day_action']} |",
        f"| Stranded decisions | {d['stranded']} |",
        f"| Avg decisions/day | {d['avg_per_day']} |",
        "",
        f"**Insight:** {d['insight']}",
        "",
    ]

    # Decision quality
    sp = d["structured_vs_prose"]
    lines += [
        "---",
        "",
        "## Decision Quality",
        "",
        "| Style | Count | Execution Rate |",
        "|-------|-------|----------------|",
        f"| Table-structured (表格化) | {sp['structured']['count']} | {sp['structured']['rate']} |",
        f"| Free-text (自由文本) | {sp['prose']['count']} | {sp['prose']['rate']} |",
        "",
    ]

    # Decision domains
    if d["domains"]:
        lines += [
            "## Decision Domains",
            "",
            "Decision headings that appear most in daily journals:",
            "",
        ]
        for dm in d["domains"][:8]:
            lines.append(f"- **{dm['heading']}** — {dm['count']} 次")
        lines.append("")

    # Anti-patterns
    if d["anti_patterns"]:
        lines += [
            "---",
            "",
            "## Co-occurring Themes in Decision Context",
            "",
            "Tag combinations that appear together when Song makes decisions:",
            "",
        ]
        for ap in d["anti_patterns"][:8]:
            lines.append(f"- `{ap['combo']}` — {ap['co_occurrence']} 次共现")
        lines.append("")

    # ── Decision Trajectory ──
    dt = d.get("trajectory", {})
    if dt and dt.get("total_trajectories", 0) > 0:
        lines += [
            "---",
            "",
            "## Decision Trajectory — 决策存活追踪",
            "",
            f"**{dt['insight']}**",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Decision themes tracked | {dt['total_trajectories']} |",
            f"| Avg persistence | {dt['avg_persistence_days']} days |",
            f"| Active (still relevant) | {dt['active_themes']} |",
            f"| Likely abandoned | {dt['abandoned_themes']} |",
            f"| No traction (same-day) | {dt['no_traction']} |",
            "",
        ]

        # Abandoned themes
        if dt.get("abandoned_themes", 0) > 0:
            lines.append("### ⚠️ Likely Abandoned Themes")
            for t in dt["trajectories"]:
                if t["status"] == "likely_abandoned":
                    themes = ", ".join(t["themes"][:3])
                    lines.append(
                        f"- **{t['date']}**: `{themes}` — "
                        f"survived {t['persistence_days']} days, "
                        f"last seen {t['last_seen']}"
                    )
            lines.append("")

        # Active themes
        if dt.get("active_themes", 0) > 0:
            lines.append("### ✅ Active Themes")
            for t in dt["trajectories"]:
                if t["status"] == "active":
                    themes = ", ".join(t["themes"][:3])
                    lines.append(
                        f"- **{t['date']}**: `{themes}` — "
                        f"persisting {t['persistence_days']} days"
                    )
            lines.append("")

        # Direction switches
        switches = dt.get("direction_switches", [])
        if switches:
            lines += [
                "### 🔄 Major Direction Switches",
                "",
                "Days when focus shifted significantly:",
                "",
            ]
            for sw in switches[:5]:
                incoming = ", ".join(sw["incoming"][:3]) if sw["incoming"] else "—"
                outgoing = ", ".join(sw["outgoing"][:3]) if sw["outgoing"] else "—"
                lines.append(
                    f"- **{sw['date']}**: ↗ {incoming}  |  ↘ {outgoing}"
                )
            lines.append("")

    # Readiness
    lines += [
        "---",
        "",
        "## Prediction Readiness",
        "",
        f"{'✅' if d['data_sufficient'] else '⚠️'} "
        f"{'Sufficient data for basic decision modeling' if d['data_sufficient'] else 'Need more daily journals (30+) for statistical significance'}",
        "",
    ]

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# songos pattern — Behavioral Patterns
# ═══════════════════════════════════════════════════════════════════════════

def generate_pattern_report(db_path: str) -> str:
    """Behavioral Patterns: what habits does Song have?"""
    a = BehaviorAnalyzer(db_path)
    p = a.behavioral_patterns()
    a.close()

    lines = [
        f"# Song Behavioral Patterns",
        f"**Period:** {p['period']}",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        '> 不是「你做了什么」，而是「你总是怎么做」。',
        "",
    ]

    # 1. Output Cycle
    oc = p["output_cycle"]
    lines += [
        "---",
        "",
        "## 1. Output Rhythm",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Avg daily output | {oc['avg_daily']} words |",
        f"| Consistency | {oc['consistency']} (CV={oc['cv']}) |",
        f"| Burst days | {oc['burst_days']} |",
        f"| Burst → burnout | {oc['burnout_after_burst']}/{oc['burst_days']} |",
        "",
        f"**{oc['insight']}**",
        "",
    ]
    if oc["samples"]:
        lines.append("**Burst details:**")
        for bs in oc["samples"][:3]:
            warn = " ⚠️ crash" if bs.get("burnout") else ""
            lines.append(
                f"- {bs['date']}: {bs['word_count']} words → "
                f"next day {bs['next_day_change']}{warn}"
            )
        lines.append("")

    # 2. Context Switching
    cs = p["context_switching"]
    lines += [
        "## 2. Context Switching Cost",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Avg domains touched/day | {cs['avg_domains_per_day']} |",
        f"| Highly fragmented days | {cs['fragmented_days']} |",
        f"| Output drops after fragmentation | {cs['drops_after_frag']}/{cs['fragmented_days']} |",
        "",
        f"**{cs['cost']}**",
        "",
    ]
    if cs["worst_days"]:
        lines.append("**Most fragmented:**")
        for fd in cs["worst_days"]:
            lines.append(
                f"- {fd['date']}: {fd['domain_count']} domains (score {fd['score']})"
            )
        lines.append("")

    # 3. Idea Pipeline
    ip = p["idea_pipeline"]
    lines += [
        "## 3. Idea-to-Output Pipeline",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total insights captured | {ip['total_insights']} |",
        f"| Insights → output | {ip['converted_to_output']} ({ip['linkage_rate']}) |",
        f"| Stuck ideas | {ip['stuck_count']} |",
        "",
        f"**{ip['insight']}**",
        "",
    ]
    if ip["recent_stuck"]:
        lines.append("**Recently stuck:**")
        for s in ip["recent_stuck"]:
            lines.append(f"- {s['date']} 「{s['heading']}」")
        lines.append("")

    # 4. Theme Migration
    tm = p["theme_migration"]
    lines += [
        "## 4. Theme Lifecycle",
        "",
        f"**{tm['insight']}**",
        "",
    ]
    if tm["emerging"]:
        lines.append("**📈 Emerging:**")
        for tag, cnt in tm["emerging"][:5]:
            lines.append(f"- `{tag}` ({cnt})")
        lines.append("")
    if tm["fading"]:
        lines.append("**📉 Fading:**")
        for tag, cnt in tm["fading"][:5]:
            lines.append(f"- `{tag}` ({cnt})")
        lines.append("")

    # 5. Automation
    au = p["automation"]
    lines += [
        "## 5. Automation Candidates",
        "",
        f"**{au['summary']}**",
        "",
    ]
    if au["templates"]:
        lines.append("**Template candidates:**")
        for t in au["templates"][:5]:
            lines.append(
                f"- 「{t['pattern']}」— {t['frequency']} ({t['structure']}, "
                f"potential: {t['automation_potential']})"
            )
        lines.append("")
    if au["table_schemas"]:
        lines.append("**Consistent table schemas (workflow candidates):**")
        for ts in au["table_schemas"][:3]:
            cols = " | ".join(ts["columns"])
            lines.append(f"- `{cols}` — {ts['count']} occurrences")
        lines.append("")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# songos twin — Proto Digital Twin
# ═══════════════════════════════════════════════════════════════════════════

def generate_twin_report(db_path: str) -> str:
    """Proto-Twin: what do we know about Song's behavior?"""
    a = BehaviorAnalyzer(db_path)
    t = a.proto_twin()
    a.close()

    rd = t["readiness"]
    kt = t["known_traits"]

    lines = [
        f"# Song Digital Twin — {t['stage']}",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        f"> Readiness: **{rd['level']}**",
        "",
        "> 数字分身的本质不是「聊天像你」，而是「做决定像你」。",
        "> 当前阶段：描述 Song。未来阶段：预测 Song → 替代 Song 的部分工作。",
        "",
        "---",
        "",
        "## Known Behavioral Traits",
        "",
        "| Trait | Profile |",
        "|-------|---------|",
        f"| Decision style | {kt['decision_style']} |",
        f"| Output style | {kt['output_style']} |",
        f"| Focus trajectory | {kt['focus_trajectory']} |",
        f"| Insight capture | {kt['insight_capture_rate']} insights/day |",
        f"| Decision velocity | {kt['decision_velocity']} |",
        "",
        "---",
        "",
        "## What We Can Predict",
        "",
    ]
    for item in rd["predictable"]:
        lines.append(f"- {item}")
    lines.append("")

    lines += [
        "---",
        "",
        "## What's Missing",
        "",
    ]
    for item in rd["missing"]:
        lines.append(f"- {item}")
    lines.append("")

    lines += [
        "---",
        "",
        "## Path to Full Twin",
        "",
        "```",
        "Proto-Twin (current)      → 描述 Song 的行为特征",
        "  ↓ 30+ daily journals",
        "Pattern Twin               → 发现 Song 没意识到的模式",
        "  ↓ 200+ decisions",
        "Predictive Twin            → 预测 Song 的下一步行为",
        "  ↓ 500+ decisions, 3+ months",
        "Autonomous Twin            → 代替 Song 执行部分决策",
        "```",
        "",
    ]

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# Write to vault
# ═══════════════════════════════════════════════════════════════════════════

def write_to_vault(report_md: str, vault_path: str) -> str:
    """Write report into vault's 00 Dashboard/ directory."""
    dashboard = Path(vault_path) / "00 Dashboard（总入口）"
    dashboard.mkdir(parents=True, exist_ok=True)
    outpath = dashboard / "Song Knowledge Report v1.md"
    outpath.write_text(report_md, encoding="utf-8")
    return str(outpath)
