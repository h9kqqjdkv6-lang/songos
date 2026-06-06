# SongOS

**Understand Yourself. Predict Yourself. Upgrade Yourself.**

SongOS doesn't help you manage knowledge.
It helps you discover the behavior patterns hidden inside your knowledge.

---

## What SongOS Actually Does

You already know *what* you do. You don't know *why you keep doing it*.

SongOS reads your notes and tells you:

```
Your decision themes survive 2.4 days on average.
You switched direction 8 times in 20 days.
Your real pattern isn't "lack of execution" — it's "too-frequent direction switching."
```

This is not a summary. This is something you cannot see about yourself.

---

## How It Works

```bash
# 1. Point SongOS at your Obsidian vault
songos ingest

# 2. Get the one insight you don't know
songos

# 3. Dive deeper
songos decision    # How you make decisions
songos pattern     # Your recurring behavioral patterns
songos twin        # How close you are to a Digital Twin
```

- **Zero setup.** You already write notes. SongOS reads them.
- **Local only.** SQLite, no cloud, no API calls.
- **2 seconds.** 996 notes ingested in one command.

---

## Real Output (20 days of journaling)

```
Decision themes tracked: 16
Avg survival: 2.4 days
Likely abandoned: 4 themes
Direction switches detected: 8

Active themes: OPC, 变现, 一人公司 ↗
Fading themes: 机器人, 低空经济, 投资 ↘

Output pattern: 4 burst days → 3 led to next-day crash
Idea pipeline: 12% of insights become output. 61 ideas stuck in notes.
```

---

## Why Open Source

SongOS is not a startup yet. It's a hypothesis:

> **People will pay to discover behavior patterns they cannot see themselves.**

If this hypothesis is true, SongOS becomes a company.  
If false, it stays a useful open-source tool.

Either way — the code is free.

---

## Quick Start

```bash
git clone https://github.com/h9kqqjdkv6-lang/songos.git
cd songos
pip install -e .

# Point to your Obsidian vault
mkdir -p ~/.songos
echo "vault_path: ~/path/to/your/obsidian/vault" > ~/.songos/config.yaml
# Optional: set your name for personalized reports
echo "user_name: YourName" >> ~/.songos/config.yaml

# Ingest and analyze
songos ingest
songos
```

---

## Roadmap

| Phase | What | Status |
|-------|------|--------|
| `songos ingest` | Obsidian → SQLite pipeline | ✅ |
| `songos profile` | Data inventory — what's in the database | ✅ |
| `songos decision` | Decision trajectory, execution rate, abandonment signals | ✅ |
| `songos pattern` | Output rhythm, context switching, idea pipeline, theme lifecycle | ✅ |
| `songos twin` | Proto Digital Twin — what we know, what's missing | ✅ |
| Prediction Engine | "This project has 15% chance of surviving 7+ days" | ⬜ |
| Execution Agent | Auto-generate PRDs, task lists, reminders | ⬜ |
| Notion / GitHub / Linear support | Multi-source data ingestion | ⬜ |

See [docs/roadmap.md](docs/roadmap.md) for details.

---

## Who This Is For

- **Indie hackers** who start 10 projects and finish 2
- **Founders** who make 50 decisions a day and wonder which ones mattered
- **Knowledge workers** who have years of notes and zero insight from them

Not for people who don't write things down.

---

## FAQ

**Q: Does this only work with Obsidian?**  
A: Currently yes. Multi-source (Notion, GitHub, Linear) is on the roadmap.

**Q: Is my data safe?**  
A: Everything runs locally. SQLite database. No cloud. No API calls.

**Q: Do I need to change how I take notes?**  
A: No. SongOS reads whatever you already have. Structured daily journals work best.

**Q: When will the Prediction Engine be ready?**  
A: After collecting enough user data to build reliable models. Help by being a tester.

---

## License

MIT
