"""Python environment checks."""

from __future__ import annotations

import sys

from hermes_cli.doctor._registry import register


@register("Python Environment", "python-version", priority=10)
def check_python_version(report):
    py = sys.version_info
    if py >= (3, 11):
        report.ok(f"Python {py.major}.{py.minor}.{py.micro}")
    elif py >= (3, 10):
        report.ok(f"Python {py.major}.{py.minor}.{py.micro}")
        report.warn("Python 3.11+ recommended for RL Training tools (tinker requires >= 3.11)")
    else:
        report.fail(
            f"Python {py.major}.{py.minor}.{py.micro}",
            "(3.10+ required)",
            fix="Upgrade Python to 3.10+",
        )


@register("Python Environment", "venv-active", priority=20)
def check_venv_active(report):
    if sys.prefix != sys.base_prefix:
        report.ok("Virtual environment active")
    else:
        report.warn("Not in virtual environment", "(recommended)")


@register("Python Environment", "version-consistency", priority=30)
def check_version_consistency(report):
    """Verify pyproject.toml version matches hermes_cli.__version__."""
    from hermes_cli.doctor import PROJECT_ROOT
    from hermes_cli import __version__ as init_version

    pyproject = PROJECT_ROOT / "pyproject.toml"
    try:
        text = pyproject.read_text(encoding="utf-8")
    except OSError:
        return  # Installed wheel — nothing to cross-check

    in_project = False
    pyproject_version = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            in_project = line == "[project]"
            continue
        if in_project and line.startswith("version") and "=" in line:
            value = line.split("=", 1)[1].split("#", 1)[0].strip().strip("\"\'")
            pyproject_version = value or None
            break

    if pyproject_version is None:
        return

    if pyproject_version == init_version:
        report.ok("Version files consistent", f"({init_version})")
    else:
        report.fail(
            "Version mismatch between source files",
            f"(pyproject.toml {pyproject_version} != hermes_cli/__init__.py {init_version})",
            fix=(
                "Re-sync version files (e.g. run 'hermes update', or set "
                "hermes_cli/__init__.py __version__ to match pyproject.toml)"
            ),
        )
