"""Entry gates for paper candidates.

Single responsibility: decide whether a modeled candidate may become a
paper entry, from the frozen gate thresholds plus the arithmetic inputs
(variant spread, worst-variant edge, median exec edge at the $250 CLOB
VWAP ask, Gamma liquidity) and the fixture news check. Pure computation;
no I/O.

Canonical lineage: the thresholds were frozen in the soccer lineage
(``r5c -> r15 -> r23``; wording fixed in round23/epl_candidates.json
``rules.gates`` and re-verified in round24) and apply unchanged to crypto
candidates from the ``r19`` lineage. Threshold values are book-of-record
constants: changing one is a policy change requiring owner review, not a
tune-up.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

# Frozen entry-gate thresholds (book of record).
# var<=6c; worst-variant exec >= +4c; median exec >= +5c (CLOB $250-VWAP
# ask); liq >= $5k. Additional eligibility (entry .10-.92, book fills
# $250, eligible market kinds) is enforced by callers.
GATES: Mapping[str, float] = {
    "variant_spread_max": 0.06,
    "worst_edge_min": 0.04,
    "exec_edge_min": 0.05,
    "liq_min": 5000.0,
}


@dataclass(frozen=True)
class NewsCheck:
    """Lineup/injury concordance check for one fixture.

    ``delta`` is the time-to-kickoff bucket the check ran at (for example
    ``"48h"`` or ``"recheck T-1d"``); ``concordant`` is True when fresh
    news does not contradict the model's fragility assumptions;
    ``blockers`` lists exit conditions met (any entry block);
    ``sources`` lists press-conference / news citations.
    """

    fixture: str
    delta: str
    concordant: bool
    blockers: tuple[str, ...]
    sources: tuple[str, ...]


@dataclass(frozen=True)
class GateDecision:
    """Gate outcome for one candidate."""

    passed: bool
    failed: tuple[str, ...]


def evaluate_gates(
    *,
    variant_spread: float,
    worst_variant_edge: float,
    median_exec_edge: float,
    gamma_liquidity: float,
) -> GateDecision:
    """Evaluate the four frozen numeric gates for one candidate."""
    raise NotImplementedError


def check_news(fixture: str, delta: str) -> NewsCheck:
    """Assemble the news-concordance record for ``fixture`` at ``delta``."""
    raise NotImplementedError
