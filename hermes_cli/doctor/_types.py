"""Core types for the doctor diagnostic framework.

Pure stdlib — no external dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


class Severity(Enum):
    """Diagnostic severity levels."""
    OK = "ok"
    INFO = "info"
    WARN = "warn"
    FAIL = "fail"


@dataclass
class Finding:
    """A single diagnostic finding from a check."""
    severity: Severity
    text: str
    detail: str = ""
    fix: str = ""  # Fix instruction for the summary
    auto_fixable: bool = False


# Convenience constructors
def ok(text: str, detail: str = "") -> Finding:
    """Create an OK finding."""
    return Finding(Severity.OK, text, detail)


def info(text: str) -> Finding:
    """Create an informational finding."""
    return Finding(Severity.INFO, text)


def warn(text: str, detail: str = "") -> Finding:
    """Create a warning finding."""
    return Finding(Severity.WARN, text, detail)


def fail(text: str, detail: str = "", fix: str = "") -> Finding:
    """Create a failure finding with optional fix instruction."""
    return Finding(Severity.FAIL, text, detail, fix)


@dataclass
class CheckResult:
    """Result from running a single check function."""
    section: str
    findings: list[Finding] = field(default_factory=list)


@dataclass
class Check:
    """A registered diagnostic check."""
    name: str
    section: str
    fn: Callable  # (ctx: DoctorContext, report: DiagnosticReport) -> None
    priority: int = 0  # Ordering within section (lower = earlier)
