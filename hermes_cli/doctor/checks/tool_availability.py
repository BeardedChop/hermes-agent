"""Tool availability checks using model_tools."""

from __future__ import annotations

import os

from hermes_cli.doctor._registry import register


def _is_kanban_worker_env_gate(item: dict) -> bool:
    if item.get("name") != "kanban":
        return False
    if os.environ.get("HERMES_KANBAN_TASK"):
        return False
    tools = item.get("tools") or []
    return bool(tools) and all(str(t).startswith("kanban_") for t in tools)


def _honcho_is_configured_for_doctor() -> bool:
    try:
        from plugins.memory.honcho.client import HonchoClientConfig
        cfg = HonchoClientConfig.from_global_config()
        return bool(cfg.enabled and (cfg.api_key or cfg.base_url))
    except Exception:
        return False


def _doctor_tool_availability_detail(toolset: str) -> str:
    if toolset == "kanban" and not os.environ.get("HERMES_KANBAN_TASK"):
        return "(runtime-gated; loaded only for dispatcher-spawned workers)"
    return ""


def _apply_doctor_tool_availability_overrides(available, unavailable):
    """Adjust runtime-gated tool availability for doctor diagnostics.

    Indirects through the hermes_cli.doctor module so that monkeypatching
    doctor._honcho_is_configured_for_doctor in tests works as expected.
    """
    import hermes_cli.doctor as _doctor_mod
    updated = list(available)
    remaining = []
    for item in unavailable:
        name = item.get("name")
        if _is_kanban_worker_env_gate(item):
            if "kanban" not in updated:
                updated.append("kanban")
            continue
        if name == "honcho" and _doctor_mod._honcho_is_configured_for_doctor():
            if "honcho" not in updated:
                updated.append("honcho")
            continue
        remaining.append(item)
    return updated, remaining


@register("Tool Availability", "tool-availability", priority=10)
def check_tool_availability(report):
    from hermes_cli.doctor import PROJECT_ROOT
    import sys
    sys.path.insert(0, str(PROJECT_ROOT))
    from model_tools import check_tool_availability as _cta, TOOLSET_REQUIREMENTS

    available, unavailable = _apply_doctor_tool_availability_overrides(*_cta())

    for tid in available:
        info = TOOLSET_REQUIREMENTS.get(tid, {})
        report.ok(info.get("name", tid), _doctor_tool_availability_detail(tid))

    for item in unavailable:
        env_vars = item.get("missing_vars") or item.get("env_vars") or []
        if env_vars:
            report.warn(item["name"], f"(missing {', '.join(env_vars)})")
        else:
            report.warn(item["name"], "(system dependency not met)")

    if any(u.get("missing_vars") or u.get("env_vars") for u in unavailable):
        report.add_issue("Run 'hermes setup' to configure missing API keys for full tool access")
