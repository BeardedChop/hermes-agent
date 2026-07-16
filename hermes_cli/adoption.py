"""Legacy install detection for the adoption funnel.

This is a minimal stub — the full implementation (task 2.3) will replace
the ``detect_legacy_install`` function with the complete cohort detection
logic (pristine/dirty/fork, canonical remote check, branch ahead check).

See ``docs/plans/updater-rework/03-phase2-compat-and-adoption.md`` task 2.3.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class LegacyInfo:
    """Result of legacy-install detection.

    Attributes:
        pristine: True if the checkout is a clean upstream install on the
            expected branch with no local commits ahead of origin.
        reasons: Human-readable list of why the tree is NOT pristine
            (empty when ``pristine`` is True).
    """
    pristine: bool
    reasons: List[str] = field(default_factory=list)


def detect_legacy_install(
    project_root: Path,
    hermes_home: Path,
) -> Optional[LegacyInfo]:
    """Detect whether *project_root* is a legacy (non-slot) install.

    Returns ``None`` when running from a slot (root under ``versions/``),
    docker/nixos/homebrew, or pip installs.  Returns ``LegacyInfo`` for git
    checkouts.

    This is a stub — always returns ``None`` (no legacy detected) so the
    adoption flow proceeds without a dirty-tree guard.  The full
    implementation from task 2.3 will replace this.
    """
    return None
