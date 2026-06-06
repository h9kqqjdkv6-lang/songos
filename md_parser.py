"""Obsidian-aware Markdown parser per PARSER_SPEC.md."""
import re
import json
from datetime import date, datetime
from pathlib import Path
import yaml


# ───────── 1. YAML Frontmatter ─────────

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_frontmatter(content: str) -> dict:
    """Extract YAML frontmatter. Return {} if none found."""
    m = _FM_RE.match(content)
    if not m:
        return {}
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {}
    # Convert non-serializable types (date, datetime) to strings
    return _make_json_safe(data)


def _make_json_safe(obj):
    """Recursively convert datetime/date objects to strings so JSON can serialize."""
    if isinstance(obj, dict):
        return {k: _make_json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_make_json_safe(v) for v in obj]
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return obj


def strip_frontmatter(content: str) -> str:
    """Return body without frontmatter."""
    m = _FM_RE.match(content)
    if m:
        return content[m.end():]
    return content


# ───────── 2. Wikilinks ─────────

_WIKILINK_RE = re.compile(r"!?\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")


def parse_wikilinks(content: str) -> list[dict]:
    """Extract [[wikilinks]]. Embedded ![[files]] are excluded."""
    results = []
    for m in _WIKILINK_RE.finditer(content):
        full = m.group(0)
        if full.startswith("!"):
            continue  # embedded file, not a wikilink
        target = m.group(1).strip()
        alias = m.group(2).strip() if m.group(2) else None
        start = max(0, m.start() - 30)
        end = min(len(content), m.end() + 30)
        context = content[start:end].replace("\n", " ").strip()
        results.append({"target": target, "alias": alias, "context": context})
    return results


# ───────── 3. Inline Tags ─────────

_INLINE_TAG_RE = re.compile(r"(?:^|\s)#([^\s#]+)")


def parse_inline_tags(content: str) -> list[str]:
    """Extract #inlineTags (not inside code blocks or frontmatter)."""
    return [m.group(1) for m in _INLINE_TAG_RE.finditer(content)]


# ───────── 4. Comments ─────────

_COMMENT_RE = re.compile(r"%%.*?%%", re.DOTALL)

def strip_comments(content: str) -> str:
    return _COMMENT_RE.sub("", content)


# ───────── 5. Section Splitting ─────────

SECTION_HEADING_RE = re.compile(r"^## (.+)$", re.MULTILINE)

# Per PARSER_SPEC §9 — heading keyword → section_type mapping
_SECTION_TYPE_MAP = [
    ("行动", "ACTION"),
    ("决策", "DECISION"),
    ("认知", "INSIGHT"),
    ("收获", "INSIGHT"),
    ("复盘", "REVIEW"),
    ("待办", "TODO"),
    ("线索", "TODO"),
    ("总结", "SUMMARY"),
]


def classify_section_type(heading: str) -> str:
    for keyword, stype in _SECTION_TYPE_MAP:
        if keyword in heading:
            return stype
    return "OTHER"


def parse_sections(content: str) -> list[dict]:
    """Split body by '## heading' lines. Returns [{heading, heading_level, section_type, content, position}, ...]."""
    lines = content.split("\n")
    sections = []
    current_heading = ""
    current_body: list[str] = []
    position = 0

    for line in lines:
        m = re.match(r"^## (.+)$", line)
        if m:
            if current_body:
                section_content = "\n".join(current_body).strip()
                sections.append({
                    "heading": current_heading,
                    "heading_level": 2,
                    "section_type": classify_section_type(current_heading),
                    "content": section_content,
                    "word_count": len(section_content.split()),
                    "position": position,
                })
                position += 1
            current_heading = m.group(1).strip()
            current_body = []
        else:
            current_body.append(line)

    # Last section
    if current_body:
        section_content = "\n".join(current_body).strip()
        sections.append({
            "heading": current_heading,
            "heading_level": 2,
            "section_type": classify_section_type(current_heading),
            "content": section_content,
            "word_count": len(section_content.split()),
            "position": position,
        })

    return sections


# ───────── 6. Markdown Table ─────────

def extract_actions_table(section_body: str) -> list[dict]:
    """Parse |-separated markdown table. First row = header."""
    lines = [l.strip() for l in section_body.strip().split("\n")
             if l.strip().startswith("|") and not l.strip().startswith("|-")]
    if len(lines) < 2:
        return []
    headers = [h.strip() for h in lines[0].split("|") if h.strip()]
    rows = []
    for line in lines[1:]:
        cells = [c.strip() for c in line.split("|") if c.strip()]
        if len(cells) >= len(headers):
            row = dict(zip(headers, cells[:len(headers)]))
            rows.append(row)
    return rows


# ───────── 7. Note Type Classification ─────────

def classify_note_type(filepath: str, frontmatter: dict) -> str:
    """Classify note by path and frontmatter per PARSER_SPEC §11."""
    p = str(filepath)
    if "Daily_Notes" in p:
        return "DAILY"
    if "Weekly_Review" in p:
        return "WEEKLY_REVIEW"
    if "Monthly_Review" in p:
        return "MONTHLY_REVIEW"
    if "04 Project System" in p:
        return "PROJECT"
    if "05 Output System" in p:
        return "OUTPUT"
    if "03 Knowledge System" in p:
        return "KNOWLEDGE"
    if "99 Templates" in p:
        return "TEMPLATE"
    ft = frontmatter.get("type", "").lower()
    if "daily" in ft:
        return "DAILY"
    if "weekly" in ft:
        return "WEEKLY_REVIEW"
    if "monthly" in ft:
        return "MONTHLY_REVIEW"
    return "UNKNOWN"


# ───────── 8. Top-level Parse ─────────

def parse_file(filepath: Path, vault_path: str) -> dict:
    """Parse a single .md file and return a ParsedNote dict."""
    raw = filepath.read_text(encoding="utf-8")
    fm = parse_frontmatter(raw)
    body = strip_frontmatter(raw)
    body_clean = strip_comments(body)

    rel_path = str(filepath.relative_to(Path(vault_path)))

    return {
        "path": rel_path,
        "note_type": classify_note_type(rel_path, fm),
        "title": fm.get("title", filepath.stem),
        "note_date": str(fm.get("created", "")),
        "word_count": len(body_clean.split()),
        "frontmatter": fm,
        "sections": parse_sections(body_clean),
        "wikilinks": parse_wikilinks(body_clean),
        "inline_tags": parse_inline_tags(body_clean),
        "frontmatter_tags": fm.get("tags", []) if isinstance(fm.get("tags"), list) else [],
    }
