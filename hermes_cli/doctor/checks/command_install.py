"""Command installation checks."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from hermes_cli.doctor._registry import register


@register("Command Installation", "symlink-check", priority=10)
def check_command_installation(report):
    if sys.platform == "win32":
        return

    from hermes_cli.doctor import PROJECT_ROOT

    venv_bin = None
    for venv_name in ("venv", ".venv"):
        c = PROJECT_ROOT / venv_name / "bin" / "hermes"
        if c.exists():
            venv_bin = c
            break

    prefix = os.environ.get("PREFIX", "")
    is_termux = bool(os.environ.get("TERMUX_VERSION")) or "com.termux/files/usr" in prefix
    if is_termux and prefix:
        cmd_dir = Path(prefix) / "bin"
        cmd_display = "$PREFIX/bin"
    else:
        cmd_dir = Path.home() / ".local" / "bin"
        cmd_display = "~/.local/bin"
    cmd_link = cmd_dir / "hermes"

    if venv_bin is None:
        report.warn(
            "Venv entry point not found",
            "(hermes not in venv/bin/ or .venv/bin/ — reinstall with pip install -e '.[all]')",
        )
        report.add_issue(
            f"reinstall entry point: cd {PROJECT_ROOT} && source venv/bin/activate && pip install -e '.[all]'"
        )
        return

    report.ok(f"Venv entry point exists ({venv_bin.relative_to(PROJECT_ROOT)})")

    if cmd_link.is_symlink():
        target = cmd_link.resolve()
        expected = venv_bin.resolve()
        if target == expected:
            report.ok(f"{cmd_display}/hermes → correct target")
        else:
            def _fix(r):
                cmd_link.unlink()
                cmd_link.symlink_to(venv_bin)
                r.ok(f"Fixed symlink: {cmd_display}/hermes → {venv_bin}")

            report.warn(
                f"{cmd_display}/hermes points to wrong target",
                f"(→ {target}, expected → {expected})",
            )
            report.add_issue(f"broken symlink at {cmd_display}/hermes", fix_fn=_fix)
    elif cmd_link.exists():
        report.ok(f"{cmd_display}/hermes exists (non-symlink)")
    else:
        def _fix(r):
            cmd_dir.mkdir(parents=True, exist_ok=True)
            cmd_link.symlink_to(venv_bin)
            r.ok(f"Created symlink: {cmd_display}/hermes → {venv_bin}")
            path_dirs = os.environ.get("PATH", "").split(os.pathsep)
            if str(cmd_dir) not in path_dirs:
                r.warn(
                    f"{cmd_display} is not on your PATH",
                    '(add it to your shell config: export PATH="$HOME/.local/bin:$PATH")',
                )
                r.add_issue(f"add {cmd_display} to your PATH")

        report.fail(
            f"{cmd_display}/hermes not found",
            "(hermes command may not work outside the venv)",
            fix=f"run `hermes doctor --fix` to create symlink",
            fix_fn=_fix,
        )
