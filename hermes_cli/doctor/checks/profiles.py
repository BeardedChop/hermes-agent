"""Named profiles check."""

from __future__ import annotations

import re

from hermes_cli.doctor._registry import register


@register("Profiles", "named-profiles", priority=10)
def check_profiles(report):
    from hermes_cli.profiles import list_profiles, _get_wrapper_dir, profile_exists

    named = [p for p in list_profiles() if not p.is_default]
    if not named:
        return

    report.ok(f"{len(named)} profile(s) found")
    wrapper_dir = _get_wrapper_dir()
    for p in named:
        parts = []
        if p.gateway_running:
            parts.append("gateway running")
        if p.model:
            parts.append(p.model[:30])
        if not (p.path / "config.yaml").exists():
            parts.append("⚠ missing config")
        if not (p.path / ".env").exists():
            parts.append("no .env")
        if not (wrapper_dir / p.name).exists():
            parts.append("no alias")
        report.ok(f"  {p.name}: {', '.join(parts) if parts else 'configured'}")

    if wrapper_dir.is_dir():
        for wrapper in wrapper_dir.iterdir():
            if not wrapper.is_file():
                continue
            content = wrapper.read_text()
            if "hermes -p" in content:
                m = re.search(r"hermes -p (\S+)", content)
                if m and not profile_exists(m.group(1)):
                    report.warn(f"Orphan alias: {wrapper.name} → profile '{m.group(1)}' no longer exists")
