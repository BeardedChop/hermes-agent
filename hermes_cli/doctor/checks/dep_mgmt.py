"""Dependency management checks: venv integrity, uv, required packages."""

from __future__ import annotations

import shutil

from hermes_cli.doctor._registry import register
from hermes_cli.doctor.checks._helpers import python_install_cmd


@register("Virtual Environment Integrity", "venv-structure", priority=10)
def check_venv_integrity(report):
    from hermes_cli.managed_uv import get_venv_path, resolve_uv

    venv_path = get_venv_path()
    if not venv_path.exists():
        report.warn("Venv directory missing", "(will be recreated on next install/update)")
        return

    has_uv = bool(resolve_uv() or shutil.which("uv"))
    if not has_uv:
        def _fix(r):
            r.raw_print("  -> Attempting atomic venv recreation...")
            from hermes_cli.managed_uv import recreate_venv_atomically, get_venv_path as _gvp
            if recreate_venv_atomically(_gvp().parent, group="all"):
                r.ok("Venv successfully recreated and swapped to uv-native state")
            else:
                raise RuntimeError("Recreation failed — please run the Hermes installer")

        report.fail(
            "Legacy pip venv detected (uv missing)",
            "(dependency management will fail)",
            fix="run `hermes doctor --fix` to recreate",
            fix_fn=_fix,
        )
    else:
        report.ok("Venv structure valid and uv-native")


@register("Dependency Management", "uv-available", priority=10)
def check_uv_available(report):
    from hermes_cli.managed_uv import resolve_uv
    uv_bin = resolve_uv()
    if uv_bin:
        report.ok(f"Managed uv available ({uv_bin})")
    else:
        path_uv = shutil.which("uv")
        if path_uv:
            report.ok(f"System uv available ({path_uv})")
        else:
            report.fail(
                "uv is missing",
                "(dependency installation will fail. Install uv via the Hermes installer, or `pkg install uv` on Termux)",
            )


@register("Required Packages", "required-packages", priority=10)
def check_required_packages(report):
    required = [
        ("openai", "OpenAI SDK"),
        ("rich", "Rich (terminal UI)"),
        ("dotenv", "python-dotenv"),
        ("yaml", "PyYAML"),
        ("httpx", "HTTPX"),
    ]
    optional = [
        ("croniter", "Croniter (cron expressions)"),
        ("telegram", "python-telegram-bot"),
        ("discord", "discord.py"),
    ]
    install_cmd = python_install_cmd()

    for module, name in required:
        try:
            __import__(module)
            report.ok(name)
        except ImportError:
            report.fail(name, "(missing)", fix=f"Install: {install_cmd} {module}")

    for module, name in optional:
        try:
            __import__(module)
            report.ok(name, "(optional)")
        except ImportError:
            report.warn(name, "(optional, not installed)")
