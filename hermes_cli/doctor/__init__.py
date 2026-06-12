"""hermes_cli.doctor — diagnostic checks for Hermes Agent setup.

This module is the public face of the doctor package.  It exposes the same
names the old flat doctor.py did so all existing imports and monkeypatches
in tests keep working without change:

    from hermes_cli.doctor import run_doctor, HERMES_HOME, PROJECT_ROOT, _DHH
    from hermes_cli.doctor import _has_provider_env_config, _PROVIDER_ENV_HINTS
    from hermes_cli.doctor import _apply_doctor_tool_availability_overrides
    from hermes_cli.doctor import _honcho_is_configured_for_doctor
    from hermes_cli.doctor import _doctor_tool_availability_detail
    from hermes_cli.doctor import _has_healthy_oauth_fallback_for_apikey_provider
    from hermes_cli.doctor import _build_apikey_providers_list
    from hermes_cli.doctor import shutil           # tests patch shutil.which via doctor_mod.shutil
    import hermes_cli.doctor as doctor_mod         # monkeypatching PROJECT_ROOT, HERMES_HOME etc.

Internal layout
---------------
hermes_cli/doctor/
    __init__.py          ← you are here
    _output.py           ← ANSI rendering helpers (no external deps)
    _registry.py         ← register() decorator, DiagnosticReport, run_checks()
    checks/
        __init__.py      ← imports all check modules (registers side-effects)
        _helpers.py      ← shared utils (safe_which, is_termux, …)
        python_env.py
        security.py
        dep_mgmt.py
        config_files.py
        xai_retirement.py
        auth_providers.py
        directory_structure.py
        gateway_service.py
        command_install.py
        external_tools.py
        api_connectivity.py
        tool_availability.py
        skills_hub.py
        memory_provider.py
        profiles.py
"""

from __future__ import annotations

import os
import shutil  # noqa: F401 — tests monkeypatch hermes_cli.doctor.shutil
import sys
from pathlib import Path

# ── Module-level globals (monkeypatched in tests) ─────────────────────────
# These are the same names the flat doctor.py exposed.

from hermes_cli.config import get_hermes_home, get_env_path
from hermes_constants import display_hermes_home, get_hermes_source_root

PROJECT_ROOT = get_hermes_source_root()
HERMES_HOME = get_hermes_home()
_DHH = display_hermes_home()

# ── Lazy env bootstrap — same as old doctor.py top-level code ─────────────
_env_path = get_env_path()
try:
    from hermes_cli.env_loader import load_hermes_dotenv
    load_hermes_dotenv(hermes_home=_env_path.parent, project_env=PROJECT_ROOT / ".env")
except Exception:
    pass

# ── Backward-compat re-exports from sub-modules ───────────────────────────
# Import these after the globals so sub-modules can `from hermes_cli.doctor import HERMES_HOME`

from hermes_cli.doctor.checks.config_files import (  # noqa: F401
    _PROVIDER_ENV_HINTS,
    _has_provider_env_config,
)
from hermes_cli.doctor.checks.tool_availability import (  # noqa: F401
    _apply_doctor_tool_availability_overrides,
    _honcho_is_configured_for_doctor,
    _doctor_tool_availability_detail,
)
from hermes_cli.doctor.checks.api_connectivity import (  # noqa: F401
    _has_healthy_oauth_fallback as _has_healthy_oauth_fallback_for_apikey_provider,
    _build_apikey_providers_list,
    _APIKEY_PROVIDERS_CACHE,
)

# Termux helpers (some tests import directly)
from hermes_cli.doctor.checks._helpers import (  # noqa: F401
    is_termux as _is_termux,
    python_install_cmd as _python_install_cmd,
    system_package_install_cmd as _system_package_install_cmd,
)

# ── Platform check ────────────────────────────────────────────────────────

def _check_unsupported_platform() -> None:
    if sys.platform == "darwin" and os.uname().machine == "x86_64":
        from hermes_cli.doctor._output import color, _Ansi
        print(color(
            "⚠️ WARNING: macOS x86_64 (Intel) is explicitly unsupported.\n"
            "We no longer accept PRs or provide fixes for this platform.\n"
            "Consider migrating to a supported platform (macOS arm64 / Apple Silicon).",
            _Ansi.YELLOW,
        ))
        print()


# ── run_doctor entry point ────────────────────────────────────────────────

def run_doctor(args) -> None:
    """Run all registered diagnostic checks.

    Called by ``hermes doctor`` (via ``hermes_cli/main.py``) and also
    directly by tests.  ``args`` is an ``argparse.Namespace`` with at least:
        args.fix    — bool, whether to attempt auto-fixes
        args.ack    — str | None, advisory ID to acknowledge
    """
    should_fix = getattr(args, "fix", False)
    ack_target = getattr(args, "ack", None)

    os.environ.setdefault("HERMES_INTERACTIVE", "1")

    # Fast path: `hermes doctor --ack <id>`
    if ack_target:
        _handle_ack(ack_target)
        return

    # Trigger all @register() decorators by importing the checks package
    import hermes_cli.doctor.checks  # noqa: F401

    from hermes_cli.doctor._output import print_banner, color, _Ansi
    from hermes_cli.doctor._registry import DiagnosticReport, run_checks

    print_banner()
    _check_unsupported_platform()

    report = DiagnosticReport(should_fix=should_fix)
    run_checks(report)
    report.print_summary()


def _handle_ack(ack_target: str) -> None:
    from hermes_cli.doctor._output import color, _Ansi
    from hermes_cli.security_advisories import ADVISORIES, ack_advisory

    valid_ids = {a.id for a in ADVISORIES}
    if ack_target not in valid_ids:
        print(color(
            f"Unknown advisory ID: {ack_target!r}. Known IDs: "
            f"{', '.join(sorted(valid_ids)) or '(none)'}",
            _Ansi.RED,
        ))
        sys.exit(2)
    if ack_advisory(ack_target):
        print(color(
            f"  ✓ Acknowledged advisory {ack_target}. "
            f"It will no longer trigger startup banners.",
            _Ansi.GREEN,
        ))
    else:
        print(color(
            f"  ✗ Failed to persist ack for {ack_target}. "
            f"Check ~/.hermes/config.yaml is writable.",
            _Ansi.RED,
        ))
        sys.exit(1)
