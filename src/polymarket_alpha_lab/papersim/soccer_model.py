"""10-variant xG-Poisson soccer match model.

Single responsibility: turn xG team ratings into per-market probabilities
and executable candidate quotes for a single fixture — O/U totals, BTTS,
team totals, 1X2 and spreads — across the ten shrinkage/rho variants, and
apply the cross-league guard. The model is deterministic and read-only.

Canonical lineage: ``r5c -> r15 -> r23`` (current head
``round23/raw/model23.py``). Policy carried from the head and from
``review/FIXES.md`` (2026-10-30):

- ``match_winner`` (1X2) is SUSPENDED — domestic eligible under tightened
  gates but deprioritized; cross-league (UCL/UEL/international) 1X2 is
  BANNED until a league-strength-bridged walk-forward backtest passes.
- Spreads are flagged-only (blowout-tail rule).
- The cross-league guard ``lgh != lga -> None`` must never be relaxed by
  callers or bespoke scripts; the HOF-LYO favorite-flip defect came from
  exactly that relaxation (see ``tests/fixtures/papersim/
  regression_banned_path.json``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class SoccerCandidate:
    """One priced candidate quote for a single market of one fixture."""

    match: str
    question: str
    kind: str
    side: int
    entry_ask_vwap250: float
    model_median: float
    model_range: tuple[float, float]
    qs_variants: tuple[float, ...]
    lambda_home: float
    lambda_away: float
    market_id: str


def match_lambdas(
    xg_snapshot: Mapping[str, object],
    home_team: str,
    home_league: str,
    away_team: str,
    away_league: str,
) -> tuple[float, float] | None:
    """Expected goal rates ``(lambda_home, lambda_away)`` for one fixture.

    Returns ``None`` when the two clubs' xG ratings come from different
    leagues (``home_league != away_league``): domestic multipliers are not
    cross-league comparable and combining them raw produced the confirmed
    HOF-LYO favorite-flip structural defect. This guard is mandatory and
    must not be relaxed.
    """
    raise NotImplementedError


def over_under_quote(
    lambdas: tuple[float, float],
    line: float,
    *,
    market: str,
    market_id: str,
    entry_ask_vwap250: float,
) -> SoccerCandidate:
    """Over/Under ``line`` candidate quote across the ten model variants.

    ``lambdas`` must come from :func:`match_lambdas` (same-league only).
    """
    raise NotImplementedError
