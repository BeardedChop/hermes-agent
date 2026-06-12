"""External tool checks: git, ripgrep, docker, ssh, daytona, node, npm audit."""

from __future__ import annotations

import os
import subprocess
import sys

from hermes_cli.doctor._registry import register
from hermes_cli.doctor.checks._helpers import (
    _safe_which,
    is_termux,
    system_package_install_cmd,
    termux_browser_setup_steps,
    termux_install_all_fallback_notes,
)


@register("External Tools", "git", priority=10)
def check_git(report):
    if _safe_which("git"):
        report.ok("git")
    else:
        report.warn("git not found", "(hermes update cannot work)")


@register("External Tools", "ripgrep", priority=20)
def check_ripgrep(report):
    if _safe_which("rg"):
        report.ok("ripgrep (rg)", "(faster file search)")
    else:
        report.warn("ripgrep (rg) not found", "(file search uses grep fallback)")
        report.info(f"Install for faster search: {system_package_install_cmd('ripgrep')}")


@register("External Tools", "docker", priority=30)
def check_docker(report):
    from hermes_cli.doctor import PROJECT_ROOT

    terminal_env = os.getenv("TERMINAL_ENV", "local")
    running_in_container = False
    try:
        from hermes_constants import is_container as _is_container
        running_in_container = _is_container()
    except Exception:
        pass

    if running_in_container and terminal_env != "docker":
        report.info(
            "Running inside a container — using local terminal backend "
            "(docker-in-docker is not configured by default)"
        )
        return

    if terminal_env == "docker":
        if not _safe_which("docker"):
            report.fail(
                "docker not found",
                "(required for TERMINAL_ENV=docker)",
                fix="Install Docker or change TERMINAL_ENV",
            )
            return
        try:
            res = subprocess.run(["docker", "info"], capture_output=True, timeout=10)
        except subprocess.TimeoutExpired:
            res = None
        if res is not None and res.returncode == 0:
            report.ok("docker", "(daemon running)")
        else:
            report.fail("docker daemon not running", "", fix="Start Docker daemon")
    elif _safe_which("docker"):
        report.ok("docker", "(optional)")
    elif is_termux():
        report.info("Docker backend is not available inside Termux (expected on Android)")
    else:
        report.warn("docker not found", "(optional)")


@register("External Tools", "ssh-backend", priority=40)
def check_ssh_backend(report):
    terminal_env = os.getenv("TERMINAL_ENV", "local")
    if terminal_env != "ssh":
        return

    ssh_host = os.getenv("TERMINAL_SSH_HOST")
    if not ssh_host:
        report.fail(
            "TERMINAL_SSH_HOST not set",
            "(required for TERMINAL_ENV=ssh)",
            fix="Set TERMINAL_SSH_HOST in .env",
        )
        return

    ssh_user = os.getenv("TERMINAL_SSH_USER")
    ssh_port = os.getenv("TERMINAL_SSH_PORT")
    ssh_key = os.getenv("TERMINAL_SSH_KEY")
    target = f"{ssh_user}@{ssh_host}" if ssh_user else ssh_host
    cmd = ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes"]
    if ssh_port:
        cmd += ["-p", ssh_port]
    if ssh_key:
        cmd += ["-i", os.path.expanduser(ssh_key)]
    cmd += [target, "echo ok"]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except subprocess.TimeoutExpired:
        res = None

    if res is not None and res.returncode == 0:
        report.ok(f"SSH connection to {ssh_host}")
    else:
        report.fail(
            f"SSH connection to {ssh_host}", "",
            fix=f"Check SSH configuration for {ssh_host}",
        )


@register("External Tools", "daytona-backend", priority=50)
def check_daytona_backend(report):
    if os.getenv("TERMINAL_ENV", "local") != "daytona":
        return

    if not os.getenv("DAYTONA_API_KEY"):
        report.fail(
            "DAYTONA_API_KEY not set",
            "(required for TERMINAL_ENV=daytona)",
            fix="Set DAYTONA_API_KEY environment variable",
        )
    else:
        report.ok("Daytona API key", "(configured)")

    try:
        from daytona import Daytona  # noqa: F401
        report.ok("daytona SDK", "(installed)")
    except ImportError:
        report.fail(
            "daytona SDK not installed",
            "(pip install daytona)",
            fix="Install daytona SDK: pip install daytona",
        )


@register("External Tools", "node-and-browser", priority=60)
def check_node_and_browser(report):
    from hermes_cli.doctor import PROJECT_ROOT

    if not _safe_which("node"):
        if is_termux():
            report.info("Node.js not found (browser tools are optional in the tested Termux path)")
            report.info("Install Node.js on Termux with: pkg install nodejs")
            report.info("Termux browser setup:")
            for step in termux_browser_setup_steps(node_installed=False):
                report.info(step)
        else:
            report.warn("Node.js not found", "(optional, needed for browser tools)")
        return

    report.ok("Node.js")

    agent_browser_ok = False
    if (PROJECT_ROOT / "node_modules" / "agent-browser").exists():
        report.ok("agent-browser (Node.js)", "(browser automation)")
        agent_browser_ok = True
    elif _safe_which("agent-browser"):
        report.ok("agent-browser", "(browser automation)")
        agent_browser_ok = True
    elif is_termux():
        report.info("agent-browser is not installed (expected in the tested Termux path)")
        report.info("Install it manually later with: npm install -g agent-browser && agent-browser install")
        report.info("Termux browser setup:")
        for step in termux_browser_setup_steps(node_installed=True):
            report.info(step)
    else:
        report.warn("agent-browser not installed", "(run: npm install)")

    if agent_browser_ok and not is_termux():
        from tools.browser_tool import (
            _chromium_installed,
            _is_camofox_mode,
            _get_cloud_provider,
            _get_cdp_override,
            _using_lightpanda_engine,
        )
        skip = (
            _is_camofox_mode()
            or bool(_get_cdp_override())
            or _get_cloud_provider() is not None
            or _using_lightpanda_engine()
        )
        if not skip:
            if _chromium_installed():
                report.ok("Playwright Chromium", "(browser engine)")
            else:
                report.warn(
                    "Playwright Chromium not installed",
                    "(browser_* tools will be hidden from the agent)",
                )
                install_cmd = (
                    f"cd {PROJECT_ROOT} && npx playwright install chromium"
                    if sys.platform == "win32"
                    else f"cd {PROJECT_ROOT} && npx playwright install --with-deps chromium"
                )
                report.info(f"Install with: {install_cmd}")


@register("External Tools", "npm-audit", priority=70)
def check_npm_audit(report):
    import json
    from hermes_cli.doctor import PROJECT_ROOT

    npm_bin = _safe_which("npm")
    if not npm_bin:
        return

    audit_targets = [
        (PROJECT_ROOT, "Browser tools (agent-browser)", ["--workspaces=false"]),
        (PROJECT_ROOT, "web workspace", ["--workspace", "web"]),
        (PROJECT_ROOT, "ui-tui workspace", ["--workspace", "ui-tui"]),
        (PROJECT_ROOT / "scripts" / "whatsapp-bridge", "WhatsApp bridge", []),
    ]
    for npm_dir, label, extra in audit_targets:
        check_dir = PROJECT_ROOT if extra else npm_dir
        if not (check_dir / "node_modules").exists():
            continue
        # best-effort: failures are silently ignored
        try:
            res = subprocess.run(
                [npm_bin, "audit", "--json", *extra],
                cwd=str(npm_dir),
                capture_output=True, text=True, timeout=30,
            )
            data = json.loads(res.stdout) if res.stdout.strip() else {}
        except Exception:
            continue

        vc = data.get("metadata", {}).get("vulnerabilities", {})
        critical = vc.get("critical", 0)
        high = vc.get("high", 0)
        moderate = vc.get("moderate", 0)
        total = critical + high + moderate

        if extra and extra[0] == "--workspace":
            fix_cmd = f"cd {npm_dir} && npm audit fix {' '.join(extra)}"
        elif extra == ["--workspaces=false"]:
            fix_cmd = f"cd {npm_dir} && npm audit fix --workspaces=false"
        else:
            fix_cmd = f"cd {npm_dir} && npm audit fix"

        if total == 0:
            report.ok(f"{label} deps", "(no known vulnerabilities)")
        elif critical > 0 or high > 0:
            report.warn(
                f"{label} deps",
                f"({critical} critical, {high} high, {moderate} moderate — run: {fix_cmd})",
            )
            report.add_issue(
                f"{label} has {total} npm "
                f"{'vulnerability' if total == 1 else 'vulnerabilities'}"
            )
        else:
            report.ok(
                f"{label} deps",
                f"({moderate} moderate {'vulnerability' if moderate == 1 else 'vulnerabilities'})",
            )


@register("External Tools", "termux-notes", priority=80)
def check_termux_notes(report):
    if not is_termux():
        return
    report.info("Termux compatibility fallbacks:")
    for note in termux_install_all_fallback_notes():
        report.info(note)
