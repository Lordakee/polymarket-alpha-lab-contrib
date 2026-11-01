"""Understat xG snapshot loading and team-rating extraction.

Single responsibility: read pre-fetched Understat per-league / per-season
xG snapshot files (the ``xg_epl_23.json`` wire format) and derive the
per-team attack / defense multiplier rows the soccer model consumes. This
module performs no network access: snapshots are local files fetched by
separate research tooling and frozen as test fixtures.

Canonical lineage: ``r5c -> r15 -> r23``. The corrected round-5c pull
established the snapshot format (``round5/raw/xg_understat_5c.json``),
r15 standardized the shrinkage-blend rating derivation, and r23 is the
current head (``round23/raw/xg_epl_23.json`` and sibling league files).
The r12/r13/r15 snapshot builders are superseded; do not copy logic from
them. The r23 refresh path (``xg_refresh23.py``) is the one to migrate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class XgTeamRow:
    """One Understat team row exactly as frozen in the snapshot.

    ``history`` holds per-match mappings with at least ``h_a``, ``xG``,
    ``xGA``, ``npxG`` and ``npxGA`` keys; values are kept verbatim from
    the raw payload (unrounded) so ratings reproduce bit-for-bit.
    """

    team_id: str
    title: str
    history: tuple[Mapping[str, object], ...]


def load_xg_snapshot(path: str) -> dict[str, Mapping[str, object]]:
    """Load an Understat snapshot JSON from ``path`` without network access.

    Returns the raw ``{"<League>_<season>": {"teams": {...}, "dates": [...]}}``
    structure unmodified so raw payloads are preserved before normalization.
    """
    raise NotImplementedError


def team_ratings(
    snapshot: Mapping[str, object],
    league: str,
    season: str,
    *,
    last_weight: float,
    prior_games: float,
) -> dict[str, tuple[float, float]]:
    """Return ``{team_title: (attack_multiplier, defense_multiplier)}``.

    Multiplies each team's blended xG for / xG against by the league goal
    average, using the r23 shrinkage blend of current-season games,
    last-season rates and a league-average prior (weights ``last_weight``
    and ``prior_games``). Cross-league comparability is NOT provided here;
    combining ratings across leagues is banned (see ``soccer_model``).
    """
    raise NotImplementedError
