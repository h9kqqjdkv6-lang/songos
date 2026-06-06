"""Vault scanner — walk .md files, parse, write to SQLite."""
import os

import logging
from pathlib import Path

from md_parser import parse_file
from db import (get_connection, init_db, compute_file_hash, note_id_from_path,
                upsert_note, insert_section, insert_link, upsert_tag,
                link_note_tag, get_db_hashes, delete_notes_by_ids, query_stats)

logger = logging.getLogger(__name__)




def get_dirty_files(vault: Path, db_hashes: dict[str, str]) -> tuple[list[Path], list[str]]:
    """Compare vault files vs DB. Return (new_or_modified, deleted_note_ids)."""
    vault_files: dict[str, Path] = {}
    for root, dirs, files in os.walk(vault):
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for f in files:
            if f.endswith(".md"):
                fp = Path(root) / f
                rel = str(fp.relative_to(vault))
                vault_files[rel] = fp

    to_ingest = []
    for rel, fp in vault_files.items():
        if rel not in db_hashes or compute_file_hash(str(fp)) != db_hashes[rel]:
            to_ingest.append(fp)

    to_delete = [
        note_id_from_path(path)
        for path in db_hashes
        if path not in vault_files
    ]

    return to_ingest, to_delete


def run(vault_path: str, db_path: str) -> dict:
    """Scan vault, parse all .md files, write to SQLite. Returns stats dict."""
    vault = Path(vault_path).expanduser().resolve()
    if not vault.exists():
        raise FileNotFoundError(f"Vault not found: {vault}")

    init_db(db_path)
    conn = get_connection(db_path)

    logger.info(f"📂 Scanning: {vault}")
    db_hashes = get_db_hashes(conn)
    to_ingest, to_delete = get_dirty_files(vault, db_hashes)

    # Handle deletions
    if to_delete:
        delete_notes_by_ids(conn, to_delete)
        logger.info(f"🗑  {len(to_delete)} deleted notes removed")

    # Ingest new/modified
    ingested = 0
    skipped = 0
    for fp in to_ingest:
        try:
            parsed = parse_file(fp, vault_path)
        except UnicodeDecodeError:
            logger.warning(f"⚠ Skipping non-UTF8 file: {fp}")
            skipped += 1
            continue
        except Exception as e:
            logger.warning(f"⚠ Parse error {fp}: {e}")
            skipped += 1
            continue

        file_path = str(fp)
        file_hash = compute_file_hash(file_path)
        file_mtime = os.path.getmtime(file_path)

        note_id = upsert_note(
            conn, parsed["path"], vault_path, file_hash, file_mtime,
            parsed["note_type"], parsed["title"], parsed["note_date"],
            parsed["word_count"], parsed["frontmatter"]
        )

        # Sections
        for sec in parsed["sections"]:
            insert_section(conn, note_id, sec["heading"], sec["heading_level"],
                           sec["section_type"], sec["content"], sec["position"],
                           sec["word_count"])

        # Wikilinks
        for wl in parsed["wikilinks"]:
            insert_link(conn, note_id, wl["target"], None, wl.get("alias"), wl.get("context"))

        # Tags
        all_tags = set(parsed.get("frontmatter_tags", []) + parsed.get("inline_tags", []))
        for tag_name in all_tags:
            tid = upsert_tag(conn, str(tag_name), "frontmatter")
            if tid:
                link_note_tag(conn, note_id, tid)

        ingested += 1

    conn.commit()

    # Stats
    # modified = files in to_ingest that already existed in DB (updates, not new)
    modified_count = sum(
        1 for fp in to_ingest if str(fp.relative_to(vault)) in db_hashes
    )
    stats = query_stats(conn)
    stats["files_ingested"] = ingested
    stats["files_skipped"] = skipped
    stats["files_unchanged"] = len(db_hashes) - len(to_delete) - modified_count
    stats["files_deleted"] = len(to_delete)

    logger.info(f"✅ Ingest complete: {ingested} new/updated, "
                f"{stats['files_unchanged']} unchanged, {len(to_delete)} deleted")
    conn.close()
    return stats
