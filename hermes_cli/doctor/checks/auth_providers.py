"""Auth provider checks."""

from __future__ import annotations

from hermes_cli.doctor._registry import register
from hermes_cli.doctor.checks._helpers import _safe_which


@register("Auth Providers", "nous-auth", priority=10)
def check_nous_auth(report):
    from hermes_cli.auth import get_nous_auth_status
    status = get_nous_auth_status()
    if status.get("logged_in"):
        report.ok("Nous Portal auth", "(logged in)")
    else:
        report.warn("Nous Portal auth", "(not logged in)")


@register("Auth Providers", "codex-auth", priority=20)
def check_codex_auth(report):
    from hermes_cli.auth import get_codex_auth_status
    status = get_codex_auth_status()
    if status.get("logged_in"):
        report.ok("OpenAI Codex auth", "(logged in)")
    else:
        report.warn("OpenAI Codex auth", "(not logged in)")
        if status.get("error"):
            report.info(status["error"])
        if not _safe_which("codex"):
            report.info(
                "codex CLI not installed "
                "(optional — only required to import tokens from an existing Codex CLI login)"
            )


@register("Auth Providers", "gemini-oauth", priority=30)
def check_gemini_oauth(report):
    from hermes_cli.auth import get_gemini_oauth_auth_status
    status = get_gemini_oauth_auth_status()
    if status.get("logged_in"):
        pieces = [x for x in [status.get("email"), status.get("project_id") and f"project={status['project_id']}"] if x]
        suffix = f" ({', '.join(pieces)})" if pieces else ""
        report.ok("Google Gemini OAuth", f"(logged in{suffix})")
    else:
        report.warn("Google Gemini OAuth", "(not logged in)")


@register("Auth Providers", "minimax-oauth", priority=40)
def check_minimax_oauth(report):
    from hermes_cli.auth import get_minimax_oauth_auth_status
    status = get_minimax_oauth_auth_status()
    if status.get("logged_in"):
        report.ok("MiniMax OAuth", f"(logged in, region={status.get('region', 'global')})")
    else:
        report.warn("MiniMax OAuth", "(not logged in)")


@register("Auth Providers", "xai-oauth", priority=50)
def check_xai_oauth(report):
    from hermes_cli.auth import get_xai_oauth_auth_status
    status = get_xai_oauth_auth_status() or {}
    if status.get("logged_in"):
        report.ok("xAI OAuth", "(logged in)")
    else:
        report.warn("xAI OAuth", "(not logged in)")
        if status.get("error"):
            report.info(status["error"])
