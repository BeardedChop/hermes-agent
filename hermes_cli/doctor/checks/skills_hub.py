"""Skills Hub and GitHub auth checks."""

from __future__ import annotations

import json
import subprocess

from hermes_cli.doctor._registry import register


@register("Skills Hub", "skills-hub-dir", priority=10)
def check_skills_hub(report):
    from hermes_cli.doctor import HERMES_HOME

    hub_dir = HERMES_HOME / "skills" / ".hub"
    if not hub_dir.exists():
        report.warn("Skills Hub directory not initialized", "(run: hermes skills list)")
        return

    report.ok("Skills Hub directory exists")
    lock_file = hub_dir / "lock.json"
    if lock_file.exists():
        lock_data = json.loads(lock_file.read_text())
        count = len(lock_data.get("installed", {}))
        report.ok(f"Lock file OK ({count} hub-installed skill(s))")
    else:
        report.warn("Lock file", "(corrupted or unreadable)")

    quarantine = hub_dir / "quarantine"
    q_count = sum(1 for d in quarantine.iterdir() if d.is_dir()) if quarantine.exists() else 0
    if q_count > 0:
        report.warn(f"{q_count} skill(s) in quarantine", "(pending review)")


@register("Skills Hub", "github-auth", priority=20)
def check_github_auth(report):
    from hermes_cli.doctor import _DHH
    from hermes_cli.config import get_env_value

    def _gh_authenticated() -> bool:
        try:
            res = subprocess.run(
                ["gh", "auth", "status", "--json", "authenticated"],
                capture_output=True, timeout=10,
            )
            return res.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    github_token = get_env_value("GITHUB_TOKEN") or get_env_value("GH_TOKEN")
    if github_token:
        report.ok("GitHub token configured (authenticated API access)")
    elif _gh_authenticated():
        report.ok("GitHub authenticated via gh CLI", "(full API access — no GITHUB_TOKEN needed)")
    else:
        report.warn("No GITHUB_TOKEN", f"(60 req/hr rate limit — set in {_DHH}/.env for better rates)")
