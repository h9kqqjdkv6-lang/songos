"""
Schema validation: create 6 tables + 9 indexes + CASCADE,
insert 3 real Daily Notes, verify CASCADE delete works.
Run this BEFORE writing ingest.py.
"""
import sqlite3
import hashlib
import json
import os

DB_PATH = os.path.expanduser("~/.songos/songos.db")

def init_db(db):
    db.executescript("""
        CREATE TABLE notes (
            id TEXT PRIMARY KEY, path TEXT UNIQUE NOT NULL, vault_path TEXT NOT NULL,
            file_hash TEXT NOT NULL, file_mtime REAL NOT NULL, note_type TEXT NOT NULL,
            title TEXT, note_date TEXT, word_count INTEGER DEFAULT 0, frontmatter TEXT,
            ingested_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE sections (
            id TEXT PRIMARY KEY, note_id TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            heading TEXT, heading_level INTEGER, section_type TEXT, content TEXT NOT NULL,
            word_count INTEGER, position INTEGER
        );
        CREATE TABLE links (
            id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            target_path TEXT NOT NULL, target_id TEXT, alias TEXT, context TEXT
        );
        CREATE TABLE entities (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, entity_type TEXT NOT NULL,
            first_seen TEXT, last_seen TEXT
        );
        CREATE TABLE entity_mentions (
            note_id TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
            context TEXT, PRIMARY KEY (note_id, entity_id)
        );
        CREATE TABLE tags (
            id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL, tag_type TEXT DEFAULT 'inline'
        );
        CREATE TABLE note_tags (
            note_id TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            tag_id TEXT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
            PRIMARY KEY (note_id, tag_id)
        );
        CREATE INDEX idx_notes_type        ON notes(note_type);
        CREATE INDEX idx_notes_date        ON notes(note_date);
        CREATE INDEX idx_notes_vault       ON notes(vault_path);
        CREATE INDEX idx_sections_note     ON sections(note_id);
        CREATE INDEX idx_sections_type     ON sections(section_type);
        CREATE INDEX idx_links_source      ON links(source_id);
        CREATE INDEX idx_links_target      ON links(target_id);
        CREATE INDEX idx_entity_mentions_e ON entity_mentions(entity_id);
        CREATE INDEX idx_note_tags_tag     ON note_tags(tag_id);
    """)


def test_insert():
    """Insert 3 simulated notes from real vault data."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA journal_mode = WAL")
    init_db(db)

    vault = "obsidian知识库/我的数字花园"
    now = "2026-06-06T00:00:00"

    notes = [
        {
            "id": hashlib.sha256(b"2026-05-27").hexdigest(),
            "path": "00 Dashboard/Daily_Notes/2026-05-27.md",
            "vault_path": vault,
            "file_hash": "abc123",
            "file_mtime": 1716810000.0,
            "note_type": "DAILY",
            "title": "2026-05-27 每日记录",
            "note_date": "2026-05-27",
            "word_count": 850,
            "frontmatter": json.dumps({"tags": ["daily","面试","智远无人机","深圳"]}),
            "ingested_at": now,
            "updated_at": now,
        },
        {
            "id": hashlib.sha256(b"2026-05-28").hexdigest(),
            "path": "00 Dashboard/Daily_Notes/2026-05-28.md",
            "vault_path": vault,
            "file_hash": "def456",
            "file_mtime": 1716896400.0,
            "note_type": "DAILY",
            "title": "2026-05-28 每日记录",
            "note_date": "2026-05-28",
            "word_count": 920,
            "frontmatter": json.dumps({"tags": ["daily","回青岛","求职","Claude Code"]}),
            "ingested_at": now,
            "updated_at": now,
        },
        {
            "id": hashlib.sha256(b"weekly-review").hexdigest(),
            "path": "00 Dashboard/01 Weekly_Review.md",
            "vault_path": vault,
            "file_hash": "ghi789",
            "file_mtime": 1716900000.0,
            "note_type": "WEEKLY_REVIEW",
            "title": "每周复盘",
            "note_date": "2026-05-26",
            "word_count": 200,
            "frontmatter": json.dumps({"tags": ["weekly","review"]}),
            "ingested_at": now,
            "updated_at": now,
        },
    ]

    # Insert notes
    for n in notes:
        db.execute(
            """INSERT INTO notes VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (n["id"],n["path"],n["vault_path"],n["file_hash"],n["file_mtime"],
             n["note_type"],n["title"],n["note_date"],n["word_count"],n["frontmatter"],
             n["ingested_at"],n["updated_at"])
        )

    # Insert sections
    note1_id = notes[0]["id"]
    sections = [
        (note1_id, "📋 今日行动", 2, "ACTION", "下午3:30 智远无人机面试", 5, 1),
        (note1_id, "💡 认知收获", 2, "INSIGHT", "这场面试和云世纪被拒之间隔了20天", 12, 2),
        (note1_id, "🧠 关键决策", 2, "DECISION", "接受你太菜了不防御", 8, 3),
    ]
    for i, s in enumerate(sections):
        sid = f"{note1_id}_s{i}"
        db.execute(
            "INSERT INTO sections VALUES (?,?,?,?,?,?,?,?)",
            (sid, s[0], s[1], 2, s[3], s[4], s[5], s[6])
        )

    # Insert tags
    tag_daily = "tag_daily"
    tag_interview = "tag_interview"
    db.execute("INSERT INTO tags VALUES (?,?,?)", (tag_daily, "daily", "frontmatter"))
    db.execute("INSERT INTO tags VALUES (?,?,?)", (tag_interview, "面试", "frontmatter"))

    # Insert note_tags
    db.execute("INSERT INTO note_tags VALUES (?,?)", (note1_id, tag_daily))
    db.execute("INSERT INTO note_tags VALUES (?,?)", (note1_id, tag_interview))

    # Insert entity
    entity_id = "entity_zhiyuan"
    db.execute("INSERT INTO entities VALUES (?,?,?,?,?)",
               (entity_id, "智远无人机", "PROJECT", "2026-05-27", "2026-05-27"))

    # Insert entity_mention
    db.execute("INSERT INTO entity_mentions VALUES (?,?,?)",
               (note1_id, entity_id, "下午3:30 智远无人机面试（盐田）"))

    db.commit()
    print("✅ 3 notes + 3 sections + 2 tags + 1 entity + 2 join-table records inserted.")

    # ── Verify CASCADE delete ──
    # Count before
    sec_before = db.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
    tag_before = db.execute("SELECT COUNT(*) FROM note_tags").fetchone()[0]
    em_before = db.execute("SELECT COUNT(*) FROM entity_mentions").fetchone()[0]

    print(f"Before CASCADE: sections={sec_before}, note_tags={tag_before}, entity_mentions={em_before}")

    # Delete note 1
    db.execute("DELETE FROM notes WHERE id = ?", (note1_id,))
    db.commit()

    # Count after
    sec_after = db.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
    tag_after = db.execute("SELECT COUNT(*) FROM note_tags").fetchone()[0]
    em_after = db.execute("SELECT COUNT(*) FROM entity_mentions").fetchone()[0]
    notes_after = db.execute("SELECT COUNT(*) FROM notes").fetchone()[0]

    print(f"After CASCADE: sections={sec_after}, note_tags={tag_after}, entity_mentions={em_after}, notes={notes_after}")

    # Assertions
    assert sec_after == 0,  f"FAIL: sections not cascaded ({sec_after})"
    assert tag_after == 0,  f"FAIL: note_tags not cascaded ({tag_after})"
    assert em_after == 0,   f"FAIL: entity_mentions not cascaded ({em_after})"
    assert notes_after == 2, f"FAIL: wrong note count ({notes_after})"

    print("\n🎉 ALL CHECKS PASSED: CASCADE deletes work across sections, note_tags, entity_mentions.")
    print(f"   Remaining notes: {notes_after} (2 weekly reviews + 1 daily untouched)")
    db.close()


def verify_indexes():
    """Verify all 9 indexes exist."""
    db = sqlite3.connect(DB_PATH)
    indexes = [row[1] for row in db.execute("SELECT * FROM sqlite_master WHERE type='index'")]
    required = [
        "idx_notes_type", "idx_notes_date", "idx_notes_vault",
        "idx_sections_note", "idx_sections_type",
        "idx_links_source", "idx_links_target",
        "idx_entity_mentions_e", "idx_note_tags_tag"
    ]
    missing = [ix for ix in required if ix not in indexes]
    if missing:
        print(f"❌ Missing indexes: {missing}")
    else:
        print(f"✅ All 9 indexes verified.")
    db.close()


if __name__ == "__main__":
    test_insert()
    verify_indexes()
