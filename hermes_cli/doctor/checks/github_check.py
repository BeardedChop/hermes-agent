"""GitHub auth check."""

from __future__ import annotations

import subprocess

from hermes_cli.doctor._registry import register


@register("Skills Hub", priority=20)
def check_github_auth(report):
    """Check GitHub authentication status."""
    from hermes_cli.doctor import _DHH

    try:
        from hermes_cli.config import get_env_value
    except Exception:
        return

    def _gh_authenticated() -> bool:
        try:
            result = subprocess.run(
                ["gh", "auth", "status", "--json", "authenticated"],
                capture_output=True, timeout=10,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    github_token = get_env_value("GITHUB_TOKEN") or get_env_value("GH_TOKEN")
    if github_token:
        report.ok("GitHub token configured (authenticated API access)")
    elif _gh_authenticated():
        report.ok("GitHub authenticated via gh CLI", "(full API access — no GITHUB_TOKEN needed)")
    else:
        report.warn("No GITHUB_TOKEN", f"(60 req/hr rate limit — set in {_DHH}/.env for better rates)")
