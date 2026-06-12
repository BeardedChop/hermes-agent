"""Shared utility functions for doctor checks.

Pure stdlib — no external dependencies.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def _safe_which(cmd: str) -> str | None:
    """shutil.which wrapper resilient to platform monkeypatching in tests."""
    try:
        return shutil.which(cmd)
    except Exception:
        return None


def is_termux() -> bool:
    """Return True when running inside Termux on Android."""
    return bool(
        os.environ.get("TERMUX_VERSION")
        or "com.termux/files" in os.environ.get("PREFIX", "")
    )


# Re-export as the private name tests expect
_is_termux = is_termux


def python_install_cmd() -> str:
    """Return the pip install command appropriate for the platform."""
    return "python -m pip install" if is_termux() else "uv pip install"


def system_package_install_cmd(pkg: str) -> str:
    """Return the package manager install command for the given package."""
    if is_termux():
        return f"pkg install {pkg}"
    if sys.platform == "darwin":
        return f"brew install {pkg}"
    return f"sudo apt install {pkg}"


def termux_browser_setup_steps(node_installed: bool) -> list[str]:
    """Return ordered setup steps for browser tools on Termux."""
    steps: list[str] = []
    step = 1
    if not node_installed:
        steps.append(f"{step}) pkg install nodejs")
        step += 1
    steps.append(f"{step}) npm install -g agent-browser")
    steps.append(f"{step + 1}) agent-browser install")
    return steps


def termux_install_all_fallback_notes() -> list[str]:
    """Return informational notes for Termux compatibility."""
    return [
        "Termux install profile: use .[termux-all] for broad compatibility (installer default on Termux).",
        "Matrix E2EE extra is excluded on Termux (python-olm currently fails to build).",
        "Local faster-whisper extra is excluded on Termux (ctranslate2/av build path unavailable).",
        "STT fallback: use Groq Whisper (set GROQ_API_KEY) or OpenAI Whisper (set VOICE_TOOLS_OPENAI_KEY).",
    ]


def resolve_project_root() -> Path:
    """Resolve the hermes-agent project root directory.

    Lightweight stdlib-only resolution: walks up from this file to find
    pyproject.toml, which marks the project root.
    """
    # This file is at hermes_cli/doctor/checks/_helpers.py
    # Project root is 4 levels up
    here = Path(__file__).resolve()
    candidate = here.parent.parent.parent.parent  # hermes_cli/doctor/checks/_helpers.py -> hermes_cli -> project root
    # Verify by checking pyproject.toml or setup.py exists
    if (candidate / "pyproject.toml").exists() or (candidate / "setup.py").exists():
        return candidate
    # Fallback: try parent.parent.parent (if the file moved)
    for parent in here.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    # Last resort
    return candidate


def resolve_hermes_home() -> Path:
    """Resolve the Hermes home directory.

    Reads HERMES_HOME env var, falls back to platform-native default.
    Lightweight stdlib-only implementation.
    """
    val = os.environ.get("HERMES_HOME", "").strip()
    if val:
        return Path(val)
    if sys.platform == "win32":
        local_appdata = os.environ.get("LOCALAPPDATA", "").strip()
        base = Path(local_appdata) if local_appdata else Path.home() / "AppData" / "Local"
        return base / "hermes"
    # Check for active profile
    default_home = Path.home() / ".hermes"
    try:
        active_path = default_home / "active_profile"
        active = active_path.read_text().strip() if active_path.exists() else ""
    except (OSError, UnicodeDecodeError):
        active = ""
    if active and active != "default":
        return default_home / "profiles" / active
    return default_home


def resolve_display_hermes_home() -> str:
    """Return a user-friendly display path for HERMES_HOME."""
    home = resolve_hermes_home()
    try:
        rel = home.relative_to(Path.home())
        return f"~/{rel}"
    except ValueError:
        return str(home)
