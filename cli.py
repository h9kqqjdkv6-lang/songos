"""SongOS CLI — Personal Work Intelligence Engine.

Commands:
    songos              → One insight you don't know about yourself
    songos ingest       → Activate historical data (Obsidian → SQLite)
    songos profile      → Data inventory
    songos decision     → Decision Analytics (how you make decisions)
    songos pattern      → Behavioral Patterns (what you habitually do)
    songos twin         → Proto Digital Twin (what we know, what's missing)
"""
import os
import typer

from config import load_config, ensure_config_dir, get_user_name
from ingest import run as ingest_run
from analyzer import BehaviorAnalyzer
from reporter import (
    generate_report_md,
    generate_decision_report,
    generate_pattern_report,
    generate_twin_report,
    write_to_vault,
)

app = typer.Typer(
    name="songos",
    help="Personal Work Intelligence Engine — build your Digital Twin",
    invoke_without_command=True,
)


@app.callback()
def _default(ctx: typer.Context):
    """Show one insight you don't know about yourself."""
    if ctx.invoked_subcommand is not None:
        return

    ensure_config_dir()
    config = load_config()

    if not config.get("vault_path"):
        typer.echo(
            "👋 Welcome to SongOS!\n\n"
            "First, tell SongOS where your notes are:\n\n"
            f"  mkdir -p ~/.songos\n"
            f"  echo 'vault_path: ~/path/to/your/obsidian/vault' > ~/.songos/config.yaml\n\n"
            "Then run:\n"
            "  songos ingest   # import your notes\n"
            "  songos          # get your first insight\n"
        )
        return

    db_path = config["db_path"]
    if not os.path.exists(db_path):
        typer.echo(
            "👋 Welcome to SongOS!\n\n"
            "Run `songos ingest` first to import your Obsidian vault.\n"
            "Then run `songos` again to see your first insight.\n"
        )
        return

    try:
        a = BehaviorAnalyzer(db_path)
        b = a.baseline_stats()
        dt = a.decision_trajectories()
        tl = a.tag_lifecycle()
        a.close()
    except Exception:
        import logging
        logging.exception("Analysis error — run 'songos ingest' if this persists")
        typer.echo(
            "⚠️  No data found. Run `songos ingest` first to import your notes.\n"
        )
        return

    if b["daily_notes"] == 0:
        typer.echo(
            "📭 No daily journals found. SongOS works best with daily notes.\n"
            "Run `songos ingest` to re-scan your vault."
        )
        return

    # ── One surprise insight ──
    traj = dt.get("insight", "")
    active = tl.get("emerging", [])
    fading = tl.get("fading", [])

    user = get_user_name() or "Friend"
    lines = [
        "",
        f"{user}, {b['daily_notes']} days of journaling:",
        "",
    ]

    if traj:
        lines.append(f"  {traj}。")

    if active:
        rising = ", ".join(t for t, _ in active[:3])
        lines.append(f"  ↗ Rising: {rising}")
    if fading:
        falling = ", ".join(t for t, _ in fading[:3])
        lines.append(f"  ↘ Fading: {falling}")

    # Abandonment count
    ab = dt.get("abandoned_themes", 0)
    if ab:
        lines.append(f"  ⚠️ {ab} decision themes may have been abandoned.")

    lines += [
        "",
        f"  → songos decision    See your full decision profile",
        f"  → songos pattern     Discover your behavioral patterns",
        f"  → songos twin        Check your Digital Twin progress",
        "",
    ]

    typer.echo("\n".join(lines))


# ── Shared options ─────────────────────────────────────────────────────────

def _get_db():
    ensure_config_dir()
    return load_config()["db_path"]


def _get_vault():
    ensure_config_dir()
    return load_config()["vault_path"]


def _handle_output(report: str, write_vault: bool):
    if write_vault:
        outpath = write_to_vault(report, _get_vault())
        typer.echo(f"📄 Written to: {outpath}")
    else:
        typer.echo(report)


# ── Commands ───────────────────────────────────────────────────────────────

@app.command()
def ingest(
    vault_path: str = typer.Option(
        "", "--vault", help="Obsidian vault path (default: ~/.songos/config.yaml)"
    ),
    db_path: str = typer.Option(
        "", "--db", help="SQLite DB path (default: ~/.songos/config.yaml)"
    ),
):
    """Scan Obsidian vault, parse Markdown, write to SQLite."""
    ensure_config_dir()
    config = load_config()
    vp = vault_path or config["vault_path"]
    if not vp:
        typer.echo(
            "❌ No vault path configured.\n\n"
            "Set it in ~/.songos/config.yaml:\n"
            "  vault_path: ~/path/to/your/obsidian/vault\n\n"
            "Or pass it directly:\n"
            "  songos ingest --vault ~/path/to/your/vault\n"
        )
        raise typer.Exit(code=1)
    dp = db_path or config["db_path"]

    typer.echo(f"📂 Vault: {vp}")
    typer.echo(f"🗄  DB:    {dp}")

    stats = ingest_run(vp, dp)
    typer.echo(f"\n📊 Ingest complete:")
    typer.echo(f"   Ingested:    {stats['files_ingested']}")
    typer.echo(f"   Unchanged:   {stats['files_unchanged']}")
    typer.echo(f"   Deleted:     {stats['files_deleted']}")
    typer.echo(f"   Skipped:     {stats['files_skipped']}")
    typer.echo(f"   Total in DB: {stats['total_notes']} ({stats['daily_notes']} daily)")


@app.command()
def profile(
    write_vault: bool = typer.Option(
        False, "--write-vault", help="Write to Obsidian Dashboard"
    ),
):
    """Data inventory — what's in the database."""
    report = generate_report_md(_get_db())
    _handle_output(report, write_vault)


@app.command()
def decision(
    write_vault: bool = typer.Option(
        False, "--write-vault", help="Write to Obsidian Dashboard"
    ),
):
    """Decision Analytics — how Song makes decisions.

    Execution rate, structured vs prose, decision domains, anti-patterns.
    """
    typer.echo("🧠 Analyzing decision patterns...")
    report = generate_decision_report(_get_db())
    _handle_output(report, write_vault)


@app.command()
def pattern(
    write_vault: bool = typer.Option(
        False, "--write-vault", help="Write to Obsidian Dashboard"
    ),
):
    """Behavioral Patterns — what Song habitually does.

    Output rhythm, context switching cost, idea pipeline, theme lifecycle, automation candidates.
    """
    typer.echo("🔍 Discovering behavioral patterns...")
    report = generate_pattern_report(_get_db())
    _handle_output(report, write_vault)


@app.command()
def twin(
    write_vault: bool = typer.Option(
        False, "--write-vault", help="Write to Obsidian Dashboard"
    ),
):
    """Proto Digital Twin — what we know about Song, what's missing.

    Current stage: describing Song's behavioral traits.
    Next stages: predicting → simulating → acting on Song's behalf.
    """
    typer.echo("🪞 Building proto-twin...")
    report = generate_twin_report(_get_db())
    _handle_output(report, write_vault)


if __name__ == "__main__":
    app()
