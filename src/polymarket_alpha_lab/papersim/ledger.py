"""Paper position ledger records.

Single responsibility: build and mark the paper ledger entries (open,
hold, exit, realized/unrealized) for gated paper positions, and compute
the per-position marks used in reports. This module defines the record
shapes and the arithmetic only. Durable persistence of these records is
project-private native PostgreSQL (Project Iron Rule 1) via the store
adapters elsewhere in this package; this module must not create
file-backed journals (legacy file surfaces are frozen).

Canonical lineage: coordinator-maintained ledger practice from the soccer
lineage (``r5c -> r15 -> r23``; position ids such as ``#48
Brentford-Forest O2.5 Over $250 @ 0.560`` with r24 recheck blocks) and the
crypto lineage (``r19`` positions-MTM table). Paper-only: entries record
simulated fills, never real orders.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PaperLedgerEntry:
    """One immutable paper ledger event for a single position."""

    position_id: str
    fixture: str
    question: str
    side: str
    notional: float
    price: float
    event: str  # "entry" | "recheck" | "exit"
    evidence: tuple[str, ...]


def record_entry(
    position_id: str,
    fixture: str,
    question: str,
    side: str,
    notional: float,
    price: float,
    *,
    evidence: tuple[str, ...] = (),
) -> PaperLedgerEntry:
    """Build an entry event for a newly gated paper position."""
    raise NotImplementedError


def mark_to_market(entry_price: float, exit_bid: float) -> float:
    """Mark-to-market delta of a paper position versus its entry price."""
    raise NotImplementedError
