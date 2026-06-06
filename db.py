"""SQLite database module — full 6-table + 9-index schema with CASCADE."""
import sqlite3
import hashlib
import os
import json
from datetime import datetime


def get_connection(db_path: str) -> sqlite3.Connection:
    """Open a WAL-mode connection with foreign keys enabled."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(db_path: str):
    """Create all 6 tables + 9 indexes. Idempotent (CREATE TABLE IF NOT EXISTS)."""
    conn = get_connection(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS notes (
            id TEXT PRIMARY KEY,
            path TEXT UNIQUE NOT NULL,
            vault_path TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            file_mtime REAL NOT NULL,
            note_type TEXT NOT NULL,
            title TEXT,
            note_date TEXT,
            word_count INTEGER DEFAULT 0,
            frontmatter TEXT,
            ingested_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sections (
            id TEXT PRIMARY KEY,
            note_id TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            heading TEXT,
            heading_level INTEGER,
            section_type TEXT,
            content TEXT NOT NULL,
            word_count INTEGER,
            position INTEGER
        );
        CREATE TABLE IF NOT EXISTS links (
            id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            target_path TEXT NOT NULL,
            target_id TEXT,
            alias TEXT,
            context TEXT
        );
        CREATE TABLE IF NOT EXISTS entities (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            first_seen TEXT,
            last_seen TEXT
        );
        CREATE TABLE IF NOT EXISTS entity_mentions (
            note_id TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
            context TEXT,
            PRIMARY KEY (note_id, entity_id)
        );
        CREATE TABLE IF NOT EXISTS tags (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            tag_type TEXT DEFAULT 'inline'
        );
        CREATE TABLE IF NOT EXISTS note_tags (
            note_id TEXT NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            tag_id TEXT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
            PRIMARY KEY (note_id, tag_id)
        );
        CREATE INDEX IF NOT EXISTS idx_notes_type        ON notes(note_type);
        CREATE INDEX IF NOT EXISTS idx_notes_date        ON notes(note_date);
        CREATE INDEX IF NOT EXISTS idx_notes_vault       ON notes(vault_path);
        CREATE INDEX IF NOT EXISTS idx_sections_note     ON sections(note_id);
        CREATE INDEX IF NOT EXISTS idx_sections_type     ON sections(section_type);
        CREATE INDEX IF NOT EXISTS idx_links_source      ON links(source_id);
        CREATE INDEX IF NOT EXISTS idx_links_target      ON links(target_id);
        CREATE INDEX IF NOT EXISTS idx_entity_mentions_e ON entity_mentions(entity_id);
        CREATE INDEX IF NOT EXISTS idx_note_tags_tag     ON note_tags(tag_id);
    """)
    conn.commit()
    conn.close()


def compute_file_hash(filepath: str) -> str:
    """SHA256 of raw file bytes."""
    with open(filepath, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def note_id_from_path(rel_path: str) -> str:
    return hashlib.sha256(rel_path.encode()).hexdigest()


def upsert_note(conn: sqlite3.Connection, rel_path: str, vault_path: str,
                file_hash: str, file_mtime: float, note_type: str,
                title: str, note_date: str | None, word_count: int,
                frontmatter: dict):
    note_id = note_id_from_path(rel_path)
    now = datetime.now().isoformat()
    conn.execute("""
        INSERT INTO notes (id, path, vault_path, file_hash, file_mtime,
                           note_type, title, note_date, word_count, frontmatter,
                           ingested_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(id) DO UPDATE SET
            file_hash=excluded.file_hash, file_mtime=excluded.file_mtime,
            note_type=excluded.note_type, title=excluded.title,
            note_date=excluded.note_date, word_count=excluded.word_count,
            frontmatter=excluded.frontmatter, updated_at=excluded.updated_at
    """, (note_id, rel_path, vault_path, file_hash, file_mtime,
          note_type, title, note_date, word_count,
          json.dumps(frontmatter, ensure_ascii=False), now, now))
    return note_id


def insert_section(conn: sqlite3.Connection, note_id: str, heading: str,
                   heading_level: int, section_type: str, content: str,
                   position: int, word_count: int = 0):
    sid = hashlib.sha256(f"{note_id}{heading}{position}".encode()).hexdigest()
    conn.execute("""
        INSERT OR REPLACE INTO sections (id, note_id, heading, heading_level,
                                         section_type, content, word_count, position)
        VALUES (?,?,?,?,?,?,?,?)
    """, (sid, note_id, heading, heading_level, section_type, content, word_count, position))


def insert_link(conn: sqlite3.Connection, source_id: str, target_path: str,
                target_id: str | None = None, alias: str | None = None,
                context: str | None = None):
    lid = hashlib.sha256(f"{source_id}{target_path}".encode()).hexdigest()
    conn.execute("""
        INSERT OR REPLACE INTO links (id, source_id, target_path, target_id, alias, context)
        VALUES (?,?,?,?,?,?)
    """, (lid, source_id, target_path, target_id, alias, context))


def upsert_tag(conn: sqlite3.Connection, name: str, tag_type: str = "frontmatter") -> str | None:
    """Insert or get existing tag. Returns tag_id or None if name is empty."""
    name = str(name).strip()
    if not name:
        return None
    tid = hashlib.sha256(name.encode()).hexdigest()
    conn.execute(
        "INSERT OR IGNORE INTO tags (id, name, tag_type) VALUES (?,?,?)",
        (tid, name, tag_type))
    return tid


def link_note_tag(conn: sqlite3.Connection, note_id: str, tag_id: str):
    conn.execute("""
        INSERT OR IGNORE INTO note_tags (note_id, tag_id) VALUES (?,?)
    """, (note_id, tag_id))


def get_db_hashes(conn: sqlite3.Connection) -> dict:
    """Return {rel_path: file_hash} for dirty-check."""
    rows = conn.execute("SELECT path, file_hash FROM notes").fetchall()
    return {row[0]: row[1] for row in rows}


def delete_notes_by_ids(conn: sqlite3.Connection, note_ids: list[str]):
    """Delete notes by ID list. CASCADE handles cleanup of sections/links/tags."""
    conn.executemany("DELETE FROM notes WHERE id = ?", [(nid,) for nid in note_ids])


def query_stats(conn: sqlite3.Connection) -> dict:
    """Aggregate stats for report generation."""
    return {
        "total_notes": conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0],
        "daily_notes": conn.execute(
            "SELECT COUNT(*) FROM notes WHERE note_type='DAILY'").fetchone()[0],
        "has_actions": conn.execute(
            "SELECT COUNT(*) FROM sections WHERE section_type='ACTION'").fetchone()[0],
        "has_decisions": conn.execute(
            "SELECT COUNT(*) FROM sections WHERE section_type='DECISION'").fetchone()[0],
        "has_insights": conn.execute(
            "SELECT COUNT(*) FROM sections WHERE section_type='INSIGHT'").fetchone()[0],
        "total_words": conn.execute(
            "SELECT COALESCE(SUM(word_count),0) FROM notes").fetchone()[0],
        "tags": [row[0] for row in conn.execute(
            "SELECT DISTINCT t.name FROM tags t "
            "JOIN note_tags nt ON t.id=nt.tag_id ORDER BY t.name").fetchall()],
        "note_types": dict(conn.execute(
            "SELECT note_type, COUNT(*) FROM notes GROUP BY note_type").fetchall()),
    }
