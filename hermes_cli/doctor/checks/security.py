"""Security advisory checks."""

from __future__ import annotations

from hermes_cli.doctor._registry import register


@register("Security Advisories", "security-advisories", priority=10)
def check_security_advisories(report):
    from hermes_cli.security_advisories import (
        detect_compromised,
        filter_unacked,
        full_remediation_text,
        get_acked_ids,
    )

    all_hits = detect_compromised()
    fresh_hits = filter_unacked(all_hits)

    if not fresh_hits:
        report.ok("No active security advisories")
        return

    for hit in fresh_hits:
        report.fail(
            f"{hit.advisory.title}",
            f"({hit.package}=={hit.installed_version})",
        )
        for line in full_remediation_text(hit):
            if line:
                report.raw_print(f"    {report.color(line, report.YELLOW)}")
            else:
                report.raw_print()
        report.add_issue(
            f"Resolve security advisory {hit.advisory.id}: "
            f"uninstall {hit.package}=={hit.installed_version} and "
            f"rotate credentials, then run "
            f"`hermes doctor --ack {hit.advisory.id}`."
        )

    acked_ids = get_acked_ids()
    for h in all_hits:
        if h.advisory.id in acked_ids:
            report.warn(
                f"{h.package}=={h.installed_version} still installed "
                f"(advisory {h.advisory.id} acknowledged)",
            )
