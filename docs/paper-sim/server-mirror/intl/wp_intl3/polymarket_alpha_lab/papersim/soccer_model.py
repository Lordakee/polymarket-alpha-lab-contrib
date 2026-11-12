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
  regression_banned_path.json``). WP-P2a adds the one sanctioned
  cross-league path: an explicit league-strength κ ``bridge`` table
  (``polymarket_alpha_lab.papersim.league_strength``) threaded through
  ``fixture_variants`` / ``match_lambdas`` /
  ``candidate_from_variants`` into ``xg.pair_lambdas``; relaxation
  without a bridge remains banned, and cross-league 1X2 stays BANNED
  regardless (the suspension above is lifted only by the walk-forward
  backtest, not by the bridge alone).

Implementation notes (frozen arithmetic, do not tune):

- Score grid: independent Poisson PMFs on an 11x11 grid (0-10 goals per
  side). The Dixon-Coles tau multiplies ONLY the 0-0, 0-1, 1-0 and 1-1
  cells by ``(1 - lh*la*rho)``, ``(1 + lh*rho)``, ``(1 + la*rho)`` and
  ``(1 - rho)`` (each floored at ``DC_FLOOR``, the lineage safety clamp),
  then the grid renormalizes to sum 1. For independent Poisson cells the
  four tau deltas cancel exactly, so the correction preserves row and
  column marginals and total mass: team-total distributions are
  DC-invariant, and O/U probabilities for lines >= 2.0 are DC-invariant
  because every adjusted cell has total goals <= 2.
- Ten-variant sweep: :data:`SWEEPS` freezes the lineage set and order
  (blend w=.5 p=8 rho0 / DC, w=1.0, w=.25, p=16, p=4, current-only,
  last-only, cross-shrink .8 / 1.1). Rating modes and shrink exponents
  re-derive per-variant lambdas from the xG snapshot through
  :func:`polymarket_alpha_lab.papersim.xg.pair_lambdas`.
- Aggregation: median over the ten per-variant quotes (mean of the two
  middle order statistics for the even count), with min/max range.
- Candidate builders: :func:`candidate_from_variants` is the public,
  GATE-SAFE builder — it re-derives every variant's lambdas from the xG
  snapshot through :func:`fixture_variants`, so the candidate's fair
  range carries the true ten-variant uncertainty. :func:`over_under_quote`
  is the frozen pair-level stub: a bare lambda pair cannot re-derive the
  rating-blend / shrink dimensions, so its ten sweep slots coincide for
  O/U lines >= 2.0 — its range is NOT gate-safe evidence (codex review
  2026-10-30, finding 1; regression: BOU-LEE must gate-reject at 6.09c
  through the builder).
- ``over``/``under`` semantics follow the lineage push convention:
  ``over(line) = P(total >= floor(line) + 1)``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Mapping

from polymarket_alpha_lab.papersim.xg import pair_lambdas

__all__ = [
    "DC_FLOOR",
    "GRID_MAX_GOALS",
    "LINEAGE_EPS",
    "MatchOutputs",
    "RHO_DC",
    "SWEEPS",
    "SWEEP_NAMES",
    "SoccerCandidate",
    "VariantResult",
    "VariantSpec",
    "both_teams_to_score",
    "candidate_from_variants",
    "cover_probability",
    "dixon_coles_tau",
    "fixture_variants",
    "match_lambdas",
    "median",
    "over_probability",
    "over_under_quote",
    "poisson_pmf",
    "score_grid",
    "team_total_over",
    "variant_outputs",
]

#: Dixon-Coles rho frozen across the lineage (scan15.py / model23.py /
#: model24.py all pin -0.1). Refitting rho from O/U outcomes was
#: rejected by review (zero sensitivity above the tau cells).
RHO_DC = -0.1

#: Score-grid goals per side: 0..10 inclusive (11x11 grid).
GRID_MAX_GOALS = 10

#: Lineage epsilon guarding float lines in floor() and cover comparisons.
LINEAGE_EPS = 1e-9

#: Safety clamp: tau never multiplies a cell below this weight.
DC_FLOOR = 0.01


@dataclass(frozen=True)
class VariantSpec:
    """One sweep variant: rating weights, rho and shrink exponent."""

    name: str
    last_weight: float | None
    prior_games: float | None
    rho: float
    mode: str
    shrink: float


#: The ten-variant sweep, frozen in lineage order (names are regression
#: keys compared against the round-23 archives). ``last_weight`` /
#: ``prior_games`` are ``None`` for the pure current/last modes, which
#: ignore blend weights. The shrink exponent applies to the attack /
#: defense multipliers; the lineage encoded it in the variant name
#: prefix and kept the same values.
SWEEPS: tuple[VariantSpec, ...] = (
    VariantSpec("blend w=.5 p=8 rho0", 0.5, 8.0, 0.0, "blend", 1.0),
    VariantSpec("blend w=.5 p=8 DC", 0.5, 8.0, RHO_DC, "blend", 1.0),
    VariantSpec("blend w=1.0 p=8", 1.0, 8.0, 0.0, "blend", 1.0),
    VariantSpec("blend w=.25 p=8", 0.25, 8.0, 0.0, "blend", 1.0),
    VariantSpec("blend w=.5 p=16", 0.5, 16.0, 0.0, "blend", 1.0),
    VariantSpec("blend w=.5 p=4", 0.5, 4.0, 0.0, "blend", 1.0),
    VariantSpec("current-only", None, None, 0.0, "cur", 1.0),
    VariantSpec("last-only", None, None, 0.0, "last", 1.0),
    VariantSpec("cross-shrink .8", 0.5, 8.0, 0.0, "blend", 0.8),
    VariantSpec("cross-shrink 1.1", 0.5, 8.0, 0.0, "blend", 1.1),
)

SWEEP_NAMES: tuple[str, ...] = tuple(spec.name for spec in SWEEPS)


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


@dataclass(frozen=True)
class MatchOutputs:
    """Per-market probability outputs for one variant's score grid.

    ``totals[k]`` is P(total goals = k) for k in 0..2*max_goals;
    ``home_goals`` / ``away_goals`` are the per-side goal distributions;
    ``margins[m + max_goals]`` is P(home goals - away goals = m) for m in
    -max_goals..max_goals. ``away_win = 1 - home_win - draw`` exactly as
    the lineage computed it.
    """

    home_win: float
    draw: float
    away_win: float
    btts: float
    totals: tuple[float, ...]
    home_goals: tuple[float, ...]
    away_goals: tuple[float, ...]
    margins: tuple[float, ...]


@dataclass(frozen=True)
class VariantResult:
    """One evaluated sweep variant for a single fixture."""

    spec: VariantSpec
    lambdas: tuple[float, float]
    outputs: MatchOutputs


def poisson_pmf(rate: float, goals: int) -> float:
    """Poisson probability mass ``exp(-rate) * rate**goals / goals!``."""
    return math.exp(-rate) * rate ** goals / math.factorial(goals)


def dixon_coles_tau(
    lh: float,
    la: float,
    rho: float,
) -> tuple[float, float, float, float]:
    """Dixon-Coles tau factors for the (0-0, 0-1, 1-0, 1-1) cells.

    Each factor is floored at ``DC_FLOOR`` (the lineage's ``max(..., .01)``
    safety clamp). With independent Poisson cells and the floors not
    binding, the induced cell corrections cancel: row marginals, column
    marginals and total mass are all preserved.
    """
    return (
        max(1.0 - lh * la * rho, DC_FLOOR),
        max(1.0 + lh * rho, DC_FLOOR),
        max(1.0 + la * rho, DC_FLOOR),
        max(1.0 - rho, DC_FLOOR),
    )


def score_grid(
    lh: float,
    la: float,
    *,
    rho: float = 0.0,
    max_goals: int = GRID_MAX_GOALS,
) -> tuple[tuple[float, ...], ...]:
    """Normalized Poisson score grid with optional Dixon-Coles tau.

    Grid size is ``(max_goals + 1) x (max_goals + 1)`` (11x11 at the
    frozen default). When ``rho`` is nonzero the tau factors apply ONLY
    to the 0-0 / 0-1 / 1-0 / 1-1 cells, then the whole grid is divided
    by its total mass.
    """
    size = max_goals + 1
    grid = [
        [poisson_pmf(lh, i) * poisson_pmf(la, j) for j in range(size)]
        for i in range(size)
    ]
    if rho:
        tau_00, tau_01, tau_10, tau_11 = dixon_coles_tau(lh, la, rho)
        grid[0][0] *= tau_00
        grid[0][1] *= tau_01
        grid[1][0] *= tau_10
        grid[1][1] *= tau_11
    total = sum(sum(row) for row in grid)
    return tuple(tuple(value / total for value in row) for row in grid)


def variant_outputs(
    lh: float,
    la: float,
    *,
    rho: float = 0.0,
    max_goals: int = GRID_MAX_GOALS,
) -> MatchOutputs:
    """Derive every per-market output for one variant's score grid."""
    grid = score_grid(lh, la, rho=rho, max_goals=max_goals)
    size = max_goals + 1
    home_win = sum(grid[i][j] for i in range(size) for j in range(size) if i > j)
    draw = sum(grid[i][i] for i in range(size))
    away_win = 1.0 - home_win - draw
    totals = [0.0] * (2 * max_goals + 1)
    home_goals = [0.0] * size
    away_goals = [0.0] * size
    margins = [0.0] * (2 * max_goals + 1)
    btts = 0.0
    for i in range(size):
        for j in range(size):
            p = grid[i][j]
            totals[i + j] += p
            if i >= 1 and j >= 1:
                btts += p
            home_goals[i] += p
            away_goals[j] += p
            margins[i - j + max_goals] += p
    return MatchOutputs(
        home_win=home_win,
        draw=draw,
        away_win=away_win,
        btts=btts,
        totals=tuple(totals),
        home_goals=tuple(home_goals),
        away_goals=tuple(away_goals),
        margins=tuple(margins),
    )


def _over_index(line: float) -> int:
    return int(math.floor(line + LINEAGE_EPS)) + 1


def over_probability(outputs: MatchOutputs, line: float) -> float:
    """P(total goals strictly above ``line``), push-excluded (lineage tail)."""
    need = _over_index(line)
    return sum(outputs.totals[k] for k in range(need, len(outputs.totals)))


def both_teams_to_score(outputs: MatchOutputs) -> float:
    """P(both teams score at least one goal)."""
    return outputs.btts


def team_total_over(
    outputs: MatchOutputs,
    side: str,
    line: float,
) -> float:
    """P(one team's goals strictly above ``line``); ``side`` is home/away."""
    if side not in ("home", "away"):
        raise ValueError(f"side must be 'home' or 'away', got {side!r}")
    goals = outputs.home_goals if side == "home" else outputs.away_goals
    need = _over_index(line)
    return sum(goals[k] for k in range(need, len(goals)))


def cover_probability(
    outputs: MatchOutputs,
    side: str,
    line: float,
) -> float:
    """P(``side`` covers a Polymarket spread ``line``), pushes excluded.

    For ``side='home'`` the margin distribution is used directly; for
    ``side='away'`` it is negated. Covering needs margin strictly above
    ``-line`` (the lineage's ``need = -line`` comparison).
    """
    if side not in ("home", "away"):
        raise ValueError(f"side must be 'home' or 'away', got {side!r}")
    max_goals = len(outputs.margins) // 2
    need = -line
    probability = 0.0
    for index, p in enumerate(outputs.margins):
        margin = index - max_goals
        if side == "away":
            margin = -margin
        if margin > need + LINEAGE_EPS:
            probability += p
    return probability


def median(values: Sequence[float]) -> float:
    """Median: middle order statistic, mean of the middle pair when even."""
    ordered = sorted(values)
    count = len(ordered)
    if count == 0:
        raise ValueError("median of an empty sequence")
    if count % 2:
        return ordered[count // 2]
    return (ordered[count // 2 - 1] + ordered[count // 2]) / 2.0


def fixture_variants(
    xg_snapshot: Mapping[str, object],
    home_team: str,
    home_league: str,
    away_team: str,
    away_league: str,
    *,
    season: str | None = None,
    bridge: Mapping[str, float] | None = None,
) -> tuple[VariantResult, ...] | None:
    """Evaluate all ten sweep variants for one fixture.

    Returns ``None`` whenever :func:`polymarket_alpha_lab.papersim.xg.pair_lambdas`
    refuses the fixture (cross-league guard, missing season blocks or
    unknown teams); this is the snapshot-driven, gateable variance path.
    ``bridge`` is the optional league-strength κ table threaded into
    every variant's ``pair_lambdas`` call: without it the cross-league
    guard stands unchanged; with it the WP-P2a bridged cross-league
    path applies. Same-league fixtures are unaffected by ``bridge``.
    """
    results: list[VariantResult] = []
    for spec in SWEEPS:
        lambdas = pair_lambdas(
            xg_snapshot,
            home_team,
            home_league,
            away_team,
            away_league,
            last_weight=0.0 if spec.last_weight is None else spec.last_weight,
            prior_games=0.0 if spec.prior_games is None else spec.prior_games,
            mode=spec.mode,
            shrink=spec.shrink,
            season=season,
            bridge=bridge,
        )
        if lambdas is None:
            return None
        outputs = variant_outputs(lambdas[0], lambdas[1], rho=spec.rho)
        results.append(VariantResult(spec=spec, lambdas=lambdas, outputs=outputs))
    return tuple(results)


def match_lambdas(
    xg_snapshot: Mapping[str, object],
    home_team: str,
    home_league: str,
    away_team: str,
    away_league: str,
    *,
    bridge: Mapping[str, float] | None = None,
) -> tuple[float, float] | None:
    """Expected goal rates ``(lambda_home, lambda_away)`` for one fixture.

    Returns ``None`` when the two clubs' xG ratings come from different
    leagues (``home_league != away_league``): domestic multipliers are not
    cross-league comparable and combining them raw produced the confirmed
    HOF-LYO favorite-flip structural defect. This guard is mandatory and
    must not be relaxed — except through the sanctioned WP-P2a
    mechanism: pass an explicit league-strength κ ``bridge`` table and
    the bridged cross-league path of
    :func:`polymarket_alpha_lab.papersim.xg.pair_lambdas` applies
    (``None`` again when either league is missing from the bridge).
    Same-league fixtures never consult ``bridge``.

    Implementation: the per-side MEDIAN of the ten sweep variants' rates
    (the lineage's ``med([v['lh'] ...])`` / ``med([v['la'] ...])``).
    """
    variants = fixture_variants(
        xg_snapshot,
        home_team,
        home_league,
        away_team,
        away_league,
        bridge=bridge,
    )
    if variants is None:
        return None
    return (
        median([variant.lambdas[0] for variant in variants]),
        median([variant.lambdas[1] for variant in variants]),
    )


def candidate_from_variants(
    xg_snapshot: Mapping[str, object],
    home_team: str,
    home_league: str,
    away_team: str,
    away_league: str,
    line: float,
    market: str,
    market_id: str,
    entry_ask_vwap250: float,
    *,
    season: str | None = None,
    bridge: Mapping[str, float] | None = None,
) -> SoccerCandidate | None:
    """Snapshot-driven Over/Under ``line`` candidate quote — the public,
    GATE-SAFE builder.

    Evaluates all ten sweep variants through :func:`fixture_variants`
    (each variant re-derives its own lambdas from ``xg_snapshot``) and
    carries the TRUE per-variant quotes into the candidate's
    ``qs_variants`` / ``model_median`` / ``model_range``, so the variant
    spread and worst-variant edge seen by the entry gates reflect the
    full rating-blend / shrink / rho uncertainty. ``lambda_home`` /
    ``lambda_away`` are the per-side medians (identical to
    :func:`match_lambdas`).

    Returns ``None`` whenever the fixture is refused — cross-league
    guard, missing season blocks or unknown teams — exactly like
    :func:`fixture_variants` / :func:`match_lambdas`. The optional
    league-strength ``bridge`` κ table threads through to
    :func:`fixture_variants` (sanctioned WP-P2a cross-league path;
    same-league candidates are unaffected by it). Callers must NOT
    fall back to :func:`over_under_quote` on a ``None`` here: that stub
    collapses the sweep variance and would silently pass the variant
    gates (codex review 2026-10-30, finding 1).

    Frozen regression anchor (``tests/fixtures/papersim/
    regression_r23_soccer.json``): BOU-LEE O2.5 built here reproduces
    the true range 0.5714-0.6323 (spread 6.09c) and is the only
    documented workflow path allowed to face the gates.
    """
    variants = fixture_variants(
        xg_snapshot,
        home_team,
        home_league,
        away_team,
        away_league,
        season=season,
        bridge=bridge,
    )
    if variants is None:
        return None
    quotes = tuple(over_probability(variant.outputs, line) for variant in variants)
    return SoccerCandidate(
        match=market,
        question=f"{market}: O/U {line:g}",
        kind="total",
        side=0,
        entry_ask_vwap250=entry_ask_vwap250,
        model_median=median(quotes),
        model_range=(min(quotes), max(quotes)),
        qs_variants=quotes,
        lambda_home=median([variant.lambdas[0] for variant in variants]),
        lambda_away=median([variant.lambdas[1] for variant in variants]),
        market_id=market_id,
    )


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

    .. warning::

        Pair-level stub — NOT gate-safe. The rating-blend and shrink
        dimensions of the sweep vary team RATINGS, which cannot be
        re-derived from a bare lambda pair, so every variant slot here
        re-evaluates the SAME provided rates and only the rho dimension
        differentiates. For O/U lines >= 2.0 the Dixon-Coles tau is
        provably neutral, so all ten quotes coincide: the candidate's
        ``model_range`` collapses to a point and the variant-spread /
        worst-variant gates see fabricated certainty (a candidate truly
        rejected for var>6c — e.g. frozen BOU-LEE, true spread 6.09c —
        would pass the gates when built via this path). Use
        :func:`candidate_from_variants` on the xG snapshot for anything
        that faces the entry gates; this stub remains only for
        pair-level inspection of a single already-chosen lambda pair.
    """
    lh, la = lambdas
    quotes = tuple(
        over_probability(variant_outputs(lh, la, rho=spec.rho), line) for spec in SWEEPS
    )
    return SoccerCandidate(
        match=market,
        question=f"{market}: O/U {line:g}",
        kind="total",
        side=0,
        entry_ask_vwap250=entry_ask_vwap250,
        model_median=median(quotes),
        model_range=(min(quotes), max(quotes)),
        qs_variants=quotes,
        lambda_home=lh,
        lambda_away=la,
        market_id=market_id,
    )
