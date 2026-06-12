"""Terminal output rendering for doctor diagnostics.

Pure stdlib — uses inline ANSI codes instead of importing hermes_cli.colors.
"""

from __future__ import annotations

import os
import sys


def _should_use_color() -> bool:
    """Return True when colored output is appropriate.

    Respects NO_COLOR (https://no-color.org/) and TERM=dumb.
    """
    if os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    try:
        if not sys.stdout.isatty():
            return False
    except (AttributeError, ValueError):
        return False
    return True


class _Ansi:
    """ANSI escape code constants."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"


def color(text: str, *codes: str) -> str:
    """Apply ANSI color codes to text (only when color output is appropriate)."""
    if not _should_use_color():
        return text
    return "".join(codes) + text + _Ansi.RESET


def check_ok(text: str, detail: str = "") -> None:
    """Print an OK check line."""
    glyph = color("✓", _Ansi.GREEN)
    line = f"  {glyph} {text}"
    if detail:
        line += f" {color(detail, _Ansi.DIM)}"
    print(line)


def check_warn(text: str, detail: str = "") -> None:
    """Print a warning check line."""
    glyph = color("⚠", _Ansi.YELLOW)
    line = f"  {glyph} {text}"
    if detail:
        line += f" {color(detail, _Ansi.DIM)}"
    print(line)


def check_fail(text: str, detail: str = "") -> None:
    """Print a failure check line."""
    glyph = color("✗", _Ansi.RED)
    line = f"  {glyph} {text}"
    if detail:
        line += f" {color(detail, _Ansi.DIM)}"
    print(line)


def check_info(text: str) -> None:
    """Print an informational check line."""
    glyph = color("→", _Ansi.CYAN)
    print(f"    {glyph} {text}")


def section(title: str) -> None:
    """Print a section banner: blank line + bold cyan ◆ title."""
    print()
    print(color(f"◆ {title}", _Ansi.CYAN, _Ansi.BOLD))


def print_banner() -> None:
    """Print the doctor header banner."""
    print()
    print(color("┌─────────────────────────────────────────────────────────┐", _Ansi.CYAN))
    print(color("│                 🩺 Hermes Doctor                        │", _Ansi.CYAN))
    print(color("└─────────────────────────────────────────────────────────┘", _Ansi.CYAN))
    print()
