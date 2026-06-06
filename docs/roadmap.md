# SongOS Roadmap

## Phase 0 — Data Pipeline ✅

- [x] Obsidian vault → SQLite ingestion
- [x] Incremental sync (SHA256 dirty-check)
- [x] Obsidian-native parser (wikilinks, embeds, callouts, inline tags, dataview, tables)
- [x] 6-table schema + 9 indexes + ON DELETE CASCADE

## Phase 1 — Analysis Engine ✅

- [x] `songos` (default): One insight you don't know
- [x] `songos decision`: Decision trajectory, execution rate, abandonment signals, direction switches
- [x] `songos pattern`: Output rhythm, context switching cost, idea pipeline, theme lifecycle, automation candidates
- [x] `songos twin`: Proto Digital Twin — traits, readiness, what's missing

## Phase 2 — Multi-Source v0.2

- [ ] Notion integration (via official API)
- [ ] GitHub commits + issues → behavioral signals
- [ ] Linear / Jira → task completion patterns
- [ ] Standardized data schema for multi-source

## Phase 3 — Prediction Engine v0.3

- [ ] Project survival probability model
- [ ] Direction switch predictor
- [ ] Output crash early warning
- [ ] Requires 200+ decisions and 90+ journaling days for model training

## Phase 4 — Execution Agent v0.4

- [ ] `songos predict`: CLI for survival probability and risk scoring
- [ ] `songos recommend`: Suggested next actions based on behavioral patterns
- [ ] `songos alert`: Proactive warnings (e.g. "You've switched direction 3 times this week")
- [ ] Auto-generated task lists, PRDs, reminders

## Phase 5 — SongOS Cloud v1.0

- [ ] SaaS: upload anonymous data, get cloud-powered analysis
- [ ] Team/company mode
- [ ] Paid tiers: $9/mo (Decision), $39/mo (Prediction), $99/mo (Enterprise)

---

**Current focus:** Phase 2 (multi-source) → Phase 3 (prediction engine).  
**Engage:** Open a GitHub issue to request data source support.
