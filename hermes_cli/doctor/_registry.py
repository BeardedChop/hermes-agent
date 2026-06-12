"""Check registration and diagnostic reporting framework.

Pure stdlib — no external dependencies.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Callable

from hermes_cli.doctor._output import (
    check_ok,
    check_warn,
    check_fail,
    check_info,
    section as _print_section,
    color,
    _Ansi,
)


# ── Registry ──────────────────────────────────────────────────────────────

@dataclass
class RegisteredCheck:
    section: str
    name: str
    fn: Callable
    priority: int = 0


_CHECKS: list[RegisteredCheck] = []


def register(section: str, name: str = "", priority: int = 0) -> Callable:
    """Decorator to register a diagnostic check.

    Args:
        section:  Section heading this check appears under.
        name:     Short identifier for this specific sub-check.
                  Used in the auto-caught exception message.
                  Defaults to the function name.
        priority: Run order within the section — lower runs first (default 0).

    The decorated function receives a single ``DiagnosticReport`` argument.
    Any uncaught exception is caught by the runner, which emits a ⚠ warning
    and continues — checks don't need defensive blanket try/except.

    Example::

        @register("Python Environment", "python-version")
        def check_python_version(report):
            py = sys.version_info
            if py >= (3, 11):
                report.ok(f"Python {py.major}.{py.minor}.{py.micro}")
            else:
                report.fail(
                    "Python too old",
                    detail="(3.11+ required)",
                    fix="Upgrade Python to 3.10+",
                )

    For auto-fixable issues pass a ``fix_fn`` callable to ``report.fail`` or
    ``report.add_issue``::

        @register("Config Files", "env-file")
        def check_env_file(report):
            if not env_path.exists():
                def _fix(report):
                    env_path.touch()
                    report.ok("Created empty .env")
                report.fail(".env missing", fix="run hermes setup", fix_fn=_fix)
    """
    def decorator(fn: Callable) -> Callable:
        _CHECKS.append(RegisteredCheck(
            section=section,
            name=name or fn.__name__,
            fn=fn,
            priority=priority,
        ))
        return fn
    return decorator


def get_registered_checks() -> list[RegisteredCheck]:
    """Return all registered checks in run order."""
    seen: dict[str, int] = {}
    order = 0
    for c in _CHECKS:
        if c.section not in seen:
            seen[c.section] = order
            order += 1
    return sorted(_CHECKS, key=lambda c: (seen[c.section], c.priority, c.name))


# ── Issue record ──────────────────────────────────────────────────────────

@dataclass
class _Issue:
    """An issue collected during a check run."""
    text: str
    fix_fn: Callable | None = None  # None → manual-only
    section: str = ""
    check: str = ""


@dataclass
class _Warning:
    """A warning collected during a check run."""
    text: str
    section: str = ""
    check: str = ""


# ── Diagnostic Report ────────────────────────────────────────────────────

class DiagnosticReport:
    """Passed to every check function.

    Section headers are deferred: a header only prints when the first
    finding (ok/warn/fail/info) is emitted under it, so checks that
    return early without output never print stray banners.

    Fix model
    ---------
    Every ``fail()`` and ``add_issue()`` call accepts an optional
    ``fix_fn`` and an optional human-readable ``fix`` string.

    * ``fix_fn``  — zero-arg callable executed when ``--fix`` is active.
                    It receives the report so it can emit ok/warn/fail/info
                    lines describing what it did.
    * ``fix``     — short instruction shown in the issue summary when
                    ``--fix`` is NOT active or when no ``fix_fn`` was given.

    In ``--fix`` mode:
      - issues *with* a ``fix_fn`` are executed immediately; the issue
        is removed from the summary if the fn succeeds.
      - issues *without* a ``fix_fn`` remain in the summary as manual.

    In normal mode:
      - issues *with*  a ``fix_fn`` are shown as "✦ fixable — re-run with --fix"
      - issues *without* a ``fix_fn`` are shown as "✗ manual"
    """

    def __init__(self, should_fix: bool = False) -> None:
        self._should_fix = should_fix
        self._issues: list[_Issue] = []
        self._fixed_issues: list[_Issue] = []
        self._warnings: list[_Warning] = []
        self._fixed: int = 0
        self._pending_section: str | None = None
        self._printed_section: str | None = None
        # Set by the runner before each check so findings know their origin
        self._current_section: str = ""
        self._current_check: str = ""

    # ── Section management ────────────────────────────────────────────────

    def section(self, title: str) -> None:
        """Declare the current section (header is deferred until first output)."""
        self._pending_section = title
        self._current_section = title

    def _flush_section(self) -> None:
        if self._pending_section and self._pending_section != self._printed_section:
            _print_section(self._pending_section)
            self._printed_section = self._pending_section

    # ── Finding emitters ─────────────────────────────────────────────────

    def ok(self, text: str, detail: str = "") -> None:
        self._flush_section()
        check_ok(text, detail)

    def warn(self, text: str, detail: str = "") -> None:
        self._flush_section()
        check_warn(text, detail)
        label = text + (f" {detail}" if detail else "")
        self._warnings.append(_Warning(label, self._current_section, self._current_check))

    def fail(
        self,
        text: str,
        detail: str = "",
        *,
        fix: str = "",
        fix_fn: Callable | None = None,
    ) -> None:
        """Emit a ✗ failure line and record the issue.

        Args:
            text:    Primary description of the problem.
            detail:  Optional dim detail suffix on the same line.
            fix:     Short human-readable instruction shown in the summary.
            fix_fn:  Zero-arg callable that auto-fixes the problem when
                     called.  It receives this report for output.  If
                     ``--fix`` is active it is called immediately;
                     otherwise the issue is annotated as auto-fixable.
        """
        self._flush_section()
        check_fail(text, detail)
        self._record_issue(fix or text, fix_fn)

    def info(self, text: str) -> None:
        self._flush_section()
        check_info(text)

    def add_issue(
        self,
        text: str,
        *,
        fix_fn: Callable | None = None,
    ) -> None:
        """Add an issue to the summary without printing a fail line.

        Use when a check wants to register a problem that was already
        surfaced via warn() but still deserves a summary entry.

        Args:
            text:   Issue description for the summary.
            fix_fn: Optional auto-fix callable (same semantics as fail).
        """
        self._record_issue(text, fix_fn)

    # ── Internal ─────────────────────────────────────────────────────────

    def _record_issue(self, text: str, fix_fn: Callable | None) -> None:
        issue = _Issue(text, fix_fn, self._current_section, self._current_check)
        if self._should_fix and fix_fn is not None:
            try:
                fix_fn(self)
                self._fixed += 1
                self._fixed_issues.append(issue)
                return
            except Exception as exc:
                check_warn(f"Auto-fix failed", f"({type(exc).__name__}: {exc})")
                # Fall through and add to remaining issues
        self._issues.append(issue)

    # ── Colour helpers ────────────────────────────────────────────────────

    def color(self, text: str, *codes: str) -> str:
        return color(text, *codes)

    GREEN  = _Ansi.GREEN
    YELLOW = _Ansi.YELLOW
    RED    = _Ansi.RED
    CYAN   = _Ansi.CYAN
    DIM    = _Ansi.DIM
    BOLD   = _Ansi.BOLD

    def raw_print(self, text: str = "") -> None:
        self._flush_section()
        print(text)

    # ── Summary ───────────────────────────────────────────────────────────

    def print_summary(self) -> None:
        fixable = [i for i in self._issues if i.fix_fn is not None]
        manual  = [i for i in self._issues if i.fix_fn is None]

        print()

        # ── --fix mode: report what was done, then leftover sections ─────
        if self._should_fix and self._fixed > 0:
            if not self._issues:
                print(color("─" * 60, _Ansi.GREEN))
                print(color(
                    f"  ✓ Fixed {self._fixed} issue(s). All checks passed! 🎉",
                    _Ansi.GREEN, _Ansi.BOLD,
                ))
                print()
                _render_grouped(self._fixed_issues, bullet="✓")
                print()
                return
            print(color("─" * 60, _Ansi.YELLOW))
            print(
                color(f"  ✓ Fixed {self._fixed} issue(s).", _Ansi.GREEN, _Ansi.BOLD)
                + color(f"  {len(self._issues)} still require attention.", _Ansi.YELLOW)
            )
            print()
            _render_grouped(self._fixed_issues, bullet="✓")
            print()

        # ── All-clear ────────────────────────────────────────────────────
        elif not self._issues:
            print(color("─" * 60, _Ansi.GREEN))
            print(color("  All checks passed! 🎉", _Ansi.GREEN, _Ansi.BOLD))
            print()
            return

        # ── Header (no-fix mode) ─────────────────────────────────────────
        else:
            print(color("─" * 60, _Ansi.YELLOW))

        # ── Auto-fixable issues ──────────────────────────────────────────
        if fixable:
            print(color(
                f"  ✦ {len(fixable)} auto-fixable issue{"" if len(fixable) == 1 else "s"}"
                + (" — run `hermes doctor --fix` to resolve:" if not self._should_fix else ":"),
                _Ansi.CYAN, _Ansi.BOLD,
            ))
            _render_grouped(fixable)
            print()

        # ── Manual issues ────────────────────────────────────────────────
        if manual:
            print(color(f"  ✗ {len(manual)} issue{"" if len(manual) == 1 else "s"} require manual attention:", _Ansi.RED, _Ansi.BOLD))
            _render_grouped(manual)
            print()

        # ── Warnings (informational, not blocking) ───────────────────────
        if self._warnings:
            print(color(f"  ⚠ {len(self._warnings)} warning{"" if len(self._warnings) == 1 else "s"}:", _Ansi.YELLOW, _Ansi.BOLD))
            _render_grouped(self._warnings)
            print()



def _fmt_label(section: str, check: str) -> str:
    """Unused — kept for any external callers; grouping is now done in print_summary."""
    return ""


def _render_grouped(items: list, bullet: str = "•") -> None:
    """Render a list of _Issue or _Warning grouped by section, with sub-headers."""
    # Preserve insertion order of sections
    seen: dict[str, list] = {}
    for item in items:
        key = item.section or ""
        seen.setdefault(key, []).append(item)

    for section_name, group in seen.items():
        if section_name:
            print(f"    {color(section_name, _Ansi.DIM)}")
        for item in group:
            text = item.text if hasattr(item, "text") else item
            print(f"      {bullet} {text}")


# ── Runner ────────────────────────────────────────────────────────────────

def run_checks(report: DiagnosticReport) -> None:
    """Run all registered checks, catching any unexpected exceptions."""
    for check in get_registered_checks():
        report.section(check.section)
        report._current_section = check.section
        report._current_check = check.name
        try:
            check.fn(report)
        except Exception as exc:
            report.warn(
                f"Check '{check.name}' failed unexpectedly",
                f"({type(exc).__name__}: {exc})",
            )
