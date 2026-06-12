"""xAI model retirement check."""

from __future__ import annotations

from hermes_cli.doctor._registry import register


@register("xAI Model Retirement (May 15, 2026)", "xai-retirement", priority=10)
def check_xai_retirement(report):
    from hermes_cli.config import load_config
    from hermes_cli.xai_retirement import MIGRATION_GUIDE_URL, find_retired_xai_refs, format_issue

    cfg = load_config()
    retired_refs = find_retired_xai_refs(cfg)
    if not retired_refs:
        report.ok("No retired xAI models in config")
        return
    for ref in retired_refs:
        report.warn(format_issue(ref))
    report.info(f"Migration guide: {MIGRATION_GUIDE_URL}")
    report.add_issue(
        f"Update {len(retired_refs)} retired xAI model reference(s) "
        f"in config.yaml — see {MIGRATION_GUIDE_URL}"
    )
