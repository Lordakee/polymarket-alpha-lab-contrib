"""Command-line entry points for the paper-sim library.

Single responsibility: expose the library's read-only research flows
(load snapshots, price fixtures, evaluate gates, render reports, dump
regression comparisons against the frozen fixtures) as CLI subcommands.
Every subcommand is paper-only / report-only / readonly: none may place,
sign or submit real orders, authenticate accounts or handle credentials.

Canonical lineage: this CLI replaces the per-round bespoke scripts of the
soccer lineage (``r5c -> r15 -> r23``: discover/model/finalize per round)
and the crypto lineage (``r19``: fetch19/model19/finalize19) with one
consolidated, testable surface. Bespoke scripts may not relax model
guards (``review/FIXES.md`` scan-dispatch rule).
"""

from __future__ import annotations

from collections.abc import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    """Run the papersim CLI; returns a process exit code."""
    raise NotImplementedError
