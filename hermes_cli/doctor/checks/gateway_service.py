"""Gateway service checks."""

from __future__ import annotations

import os

from hermes_cli.doctor._registry import register


@register("Gateway Service", "linger-check", priority=10)
def check_gateway_service_linger(report):
    from hermes_cli.gateway import get_systemd_linger_status, get_systemd_unit_path, is_linux
    from hermes_cli.service_manager import detect_service_manager

    if not is_linux() or detect_service_manager() == "s6":
        return

    unit_path = get_systemd_unit_path()
    if not unit_path.exists():
        return

    linger_enabled, linger_detail = get_systemd_linger_status()
    if linger_enabled is True:
        report.ok("Systemd linger enabled", "(gateway service survives logout)")
    elif linger_enabled is False:
        report.warn("Systemd linger disabled", "(gateway may stop after logout)")
        report.info("Run: sudo loginctl enable-linger $USER")
        report.add_issue("Enable linger for the gateway user service: sudo loginctl enable-linger $USER")
    else:
        report.warn("Could not verify systemd linger", f"({linger_detail})")


@register("s6 Supervision", "s6-supervision", priority=10)
def check_s6_supervision(report):
    from hermes_cli.service_manager import S6ServiceManager, detect_service_manager

    if detect_service_manager() != "s6":
        return

    mgr = S6ServiceManager()
    for static in ("main-hermes", "dashboard"):
        if mgr.is_running(static):
            report.ok(f"{static}: up")
        else:
            report.info(f"{static}: down (expected if not enabled via env)")

    profiles = mgr.list_profile_gateways()
    if not profiles:
        report.info("No per-profile gateways registered yet — create one with `hermes profile create <name>`")
        return

    up = sum(1 for p in profiles if mgr.is_running(f"gateway-{p}"))
    suffix = f" ({', '.join(sorted(profiles))})" if len(profiles) <= 8 else ""
    report.ok(f"Per-profile gateways: {up}/{len(profiles)} supervised up{suffix}")
