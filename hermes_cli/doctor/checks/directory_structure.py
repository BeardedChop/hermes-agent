"""Directory structure and state file checks."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from hermes_cli.doctor._registry import register


@register("Directory Structure", "hermes-home", priority=10)
def check_hermes_home_dir(report):
    from hermes_cli.doctor import HERMES_HOME, _DHH

    if not HERMES_HOME.exists():
        def _fix(r):
            HERMES_HOME.mkdir(parents=True, exist_ok=True)
            r.ok(f"Created {_DHH} directory")
        report.warn(f"{_DHH} not found", "(will be created on first use)")
        report.add_issue(f"{_DHH} directory missing", fix_fn=_fix)
    else:
        report.ok(f"{_DHH} directory exists")

    for subdir in ("cron", "sessions", "logs", "skills", "memories"):
        p = HERMES_HOME / subdir
        if not p.exists():
            def _fix(r, _p=p, _s=subdir):
                _p.mkdir(parents=True, exist_ok=True)
                r.ok(f"Created {_DHH}/{_s}/")
            report.warn(f"{_DHH}/{subdir}/ not found", "(will be created on first use)")
            report.add_issue(f"{_DHH}/{subdir}/ missing", fix_fn=_fix)
        else:
            report.ok(f"{_DHH}/{subdir}/ exists")


@register("Directory Structure", "soul-md", priority=20)
def check_soul_md(report):
    from hermes_cli.doctor import HERMES_HOME, _DHH

    soul_path = HERMES_HOME / "SOUL.md"
    if soul_path.exists():
        content = soul_path.read_text(encoding="utf-8").strip()
        lines = [l for l in content.splitlines()
                 if l.strip() and not l.strip().startswith(("<!--", "-->", "#"))]
        if lines:
            report.ok(f"{_DHH}/SOUL.md exists (persona configured)")
        else:
            report.info(f"{_DHH}/SOUL.md exists but is empty — edit it to customize personality")
    else:
        def _fix(r):
            soul_path.parent.mkdir(parents=True, exist_ok=True)
            soul_path.write_text(
                "# Hermes Agent Persona\n\n"
                "<!-- Edit this file to customize how Hermes communicates. -->\n\n"
                "You are Hermes, a helpful AI assistant.\n",
                encoding="utf-8",
            )
            r.ok(f"Created {_DHH}/SOUL.md with basic template")

        report.warn(f"{_DHH}/SOUL.md not found", "(create it to give Hermes a custom personality)")
        report.add_issue(f"{_DHH}/SOUL.md missing", fix_fn=_fix)


@register("Directory Structure", "memories-dir", priority=30)
def check_memories_dir(report):
    from hermes_cli.doctor import HERMES_HOME, _DHH

    memories_dir = HERMES_HOME / "memories"
    if not memories_dir.exists():
        def _fix(r):
            memories_dir.mkdir(parents=True, exist_ok=True)
            r.ok(f"Created {_DHH}/memories/")
        report.warn(f"{_DHH}/memories/ not found", "(will be created on first use)")
        report.add_issue(f"{_DHH}/memories/ missing", fix_fn=_fix)
        return

    report.ok(f"{_DHH}/memories/ directory exists")
    for fname in ("MEMORY.md", "USER.md"):
        fpath = memories_dir / fname
        if fpath.exists():
            size = len(fpath.read_text(encoding="utf-8").strip())
            report.ok(f"{fname} exists ({size} chars)")
        else:
            report.info(f"{fname} not created yet (will be created when the agent first writes a memory)")


@register("Directory Structure", "state-db", priority=40)
def check_state_db(report):
    from hermes_cli.doctor import HERMES_HOME, _DHH

    db_path = HERMES_HOME / "state.db"
    if not db_path.exists():
        report.info(f"{_DHH}/state.db not created yet (will be created on first session)")
        return

    try:
        conn = sqlite3.connect(str(db_path))
        count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        conn.close()
        report.ok(f"{_DHH}/state.db exists ({count} sessions)")
    except Exception as e:
        from hermes_state import is_malformed_db_error, repair_state_db_schema
        if is_malformed_db_error(e):
            def _fix(r):
                db_report = repair_state_db_schema(db_path)
                if not db_report.get("repaired"):
                    raise RuntimeError(
                        f"{db_report.get('error')}; backup at {db_report.get('backup_path')}"
                    )
                try:
                    conn = sqlite3.connect(str(db_path))
                    count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
                    conn.close()
                except Exception:
                    count = "?"
                backup = Path(db_report["backup_path"]).name if db_report.get("backup_path") else "n/a"
                r.ok(
                    f"Repaired state.db schema ({count} sessions recovered)",
                    f"(strategy: {db_report.get('strategy')}; backup: {backup})",
                )

            report.warn(
                f"{_DHH}/state.db schema is malformed (sessions hidden until repaired)",
                f"({e})",
            )
            report.add_issue("state.db schema malformed", fix_fn=_fix)
        else:
            report.warn(f"{_DHH}/state.db exists but has issues: {e}")


@register("Directory Structure", "wal-file", priority=50)
def check_wal_file(report):
    from hermes_cli.doctor import HERMES_HOME, _DHH

    db_path = HERMES_HOME / "state.db"
    wal_path = HERMES_HOME / "state.db-wal"
    if not wal_path.exists() or not db_path.exists():
        return

    wal_size = wal_path.stat().st_size
    if wal_size > 50 * 1024 * 1024:
        def _fix(r):
            conn = sqlite3.connect(str(db_path))
            conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
            conn.close()
            new_size = wal_path.stat().st_size if wal_path.exists() else 0
            r.ok(f"WAL checkpoint performed ({wal_size // 1024}K → {new_size // 1024}K)")

        report.warn(
            f"WAL file is large ({wal_size // (1024 * 1024)} MB)",
            "(may indicate missed checkpoints)",
        )
        report.add_issue("large WAL file — checkpoint needed", fix_fn=_fix)
    elif wal_size > 10 * 1024 * 1024:
        report.info(f"WAL file is {wal_size // (1024 * 1024)} MB (normal for active sessions)")
