"""Paper sizing and bankroll policy.

Single responsibility: convert gated candidates into paper stake amounts
under the unit-size and cash-availability rules, and answer whether the
bankroll can absorb a new entry. Pure arithmetic on caller-supplied
state; this module never touches real money, real accounts or orders
(paper-only boundary).

Canonical lineage: sizing discipline stabilized in the soccer lineage
(``r5c -> r15 -> r23``; e.g. round23 ``bankroll_context`` with
``3 x $250`` paper entries) and the crypto lineage (``r19``, team-at-cap
monitoring mode). The r24 head adds max-new-candidates-per-round caps.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PaperStake:
    """One paper stake decision for a gated candidate."""

    fixture: str
    question: str
    notional: float
    entry_price: float
    currency: str


def paper_stake(
    fixture: str,
    question: str,
    entry_price: float,
    *,
    unit_notional: float = 250.0,
) -> PaperStake:
    """Size a paper entry as whole units of ``unit_notional`` (default $250)."""
    raise NotImplementedError


def bankroll_available(
    bankroll: float,
    cash: float,
    reserved: float,
) -> float:
    """Cash available for new paper entries after reserved commitments."""
    raise NotImplementedError
