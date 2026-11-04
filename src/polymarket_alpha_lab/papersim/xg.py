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

Implementation notes (frozen arithmetic, do not tune):

- Snapshot wire format: one JSON object keyed ``"<League>_<season>"``
  (for example ``"EPL_2026"``); each block holds ``teams`` (id-keyed rows
  with ``title`` and per-match ``history``) and ``dates`` (league match
  rows with ``isResult`` and ``xG.h`` / ``xG.a``). The same shape is
  used by ``round23/raw/xg_epl_23.json`` and
  ``round22/raw/xg_understat_22.json``.
- League goal fit: mean home / away xG over the PRIOR season's completed
  (``isResult``) dates; ``league_avg = (home_rate + away_rate) / 2``.
- Shrinkage blend (per team and per side): the current-season mean gets
  weight ``n_games`` matches, the last-season rate weight
  ``last_weight * SEASON_GAMES`` pseudo-matches and the league average
  ``prior_games`` pseudo-matches. Attack / defense multipliers are the
  blended goal rates divided by the prior-season league average. Teams
  missing from the prior season (promoted sides) fall back to the league
  average for their last-season rate, exactly as the lineage did.
- Known domestic league registry: :data:`UNDERSTAT_LEAGUES` holds the
  Big-5 Understat snapshot keys of the lineage snapshots;
  :data:`DOMESTIC_LEAGUES` adds the FotMob-sourced ``"Championship"``
  key (WP-P3; adapter :mod:`polymarket_alpha_lab.papersim.fotmob`).
  The registry documents which domestic leagues have validated
  snapshot sources — it is NOT an allowlist: ``pair_lambdas`` resolves
  any league key present in the snapshot (synthetic lowercase test
  leagues included), and ``"Championship"`` pairs are ordinary
  same-league domestic fixtures on the standard 10-variant path.
- Cross-league guard: domestic multipliers from different leagues are
  not comparable; :func:`pair_lambdas` returns ``None`` whenever the two
  clubs' leagues differ. The guard is structural and unrelaxable (the
  HOF-LYO favorite-flip defect came from relaxing it). WP-P2a adds the
  one sanctioned cross-league path: an EXPLICIT league-strength κ
  bridge passed as ``bridge=`` (see ``league_strength``), which scales
  the home rate by the clamped strength ratio ``f`` and the away rate
  by ``1 / f``. Without a bridge the guard is byte-for-byte the
  lineage behavior, and the same-league path never consults the
  bridge argument at all.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Mapping

from polymarket_alpha_lab.papersim.league_strength import bridge_factor

__all__ = [
    "DOMESTIC_LEAGUES",
    "LeagueGoalFit",
    "LeagueRatings",
    "RATING_MODES",
    "RecentForm",
    "SEASON_GAMES",
    "UNDERSTAT_LEAGUES",
    "XgTeamRow",
    "league_goal_fit",
    "load_xg_snapshot",
    "pair_lambdas",
    "prior_season",
    "ratings_for",
    "recent_form",
    "season_key",
    "team_league_registry",
    "team_ratings",
    "team_rows",
]

#: One full league season of matches. The last-season per-team rate enters
#: the shrinkage blend with weight ``last_weight * SEASON_GAMES``
#: pseudo-matches (frozen from scan15.py / model23.py / model24.py).
#: The Championship (FotMob, WP-P3) is a 46-game, 24-team league but
#: runs the SAME frozen weight on the standard 10-variant path — the
#: WP-P3 Phase 1 walk-forward backtest (gate D, 2026-11-03) validated
#: exactly these constants; do not retune per league.
SEASON_GAMES = 38

#: The Big-5 Understat league keys present in the canonical lineage
#: snapshots (``round5/raw/xg_understat_5c.json``,
#: ``round13/raw/xg_understat_13.json`` and the r23 league files).
UNDERSTAT_LEAGUES = frozenset({"EPL", "La_liga", "Serie_A", "Bundesliga", "Ligue_1"})

#: Known domestic league keys with validated snapshot sources: the
#: Big-5 Understat set above plus the FotMob-sourced ``"Championship"``
#: (WP-P3 Phase 1, validated 2026-11-03; fetched through
#: :mod:`polymarket_alpha_lab.papersim.fotmob`). A documentation
#: registry, NOT an allowlist gate: :func:`pair_lambdas` accepts any
#: league key present in the snapshot, and Championship pairs are
#: same-league domestic fixtures on the standard 10-variant path.
DOMESTIC_LEAGUES = UNDERSTAT_LEAGUES | frozenset({"Championship"})

#: Rating modes: ``"blend"`` (current + last + league prior), ``"cur"``
#: (current-season rates only) and ``"last"`` (last-season rates only).
RATING_MODES = ("blend", "cur", "last")


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


@dataclass(frozen=True)
class LeagueGoalFit:
    """League base scoring rates from one season's completed matches."""

    home_rate: float
    away_rate: float
    league_avg: float


@dataclass(frozen=True)
class LeagueRatings:
    """Goal-fit ratings for one league-season.

    ``goal_fit`` carries the PRIOR season's league base rates (the
    ``bh`` / ``ba`` / ``lgf`` triple of the lineage) and ``teams`` maps
    each Understat team title with current-season history to
    ``(attack_multiplier, defense_multiplier)``: blended goal rates for
    and against, divided by the prior-season league average. Teams with
    no current-season history are absent from ``teams``; callers treat
    them as league-average (1.0, 1.0) multipliers, as the lineage did.
    """

    league: str
    season: str
    goal_fit: LeagueGoalFit
    teams: Mapping[str, tuple[float, float]]


@dataclass(frozen=True)
class RecentForm:
    """Recent actual-goal form context for one team.

    Field semantics follow the r15 ``recent_form`` helper: the last
    ``window`` matches of the current season (prior-season fallback when
    fewer than ``min_current`` current-season rows exist).
    ``goals_per_game`` and ``xg_per_game`` are team-inclusive rates
    (goals for + against per game) with the lineage's 2-decimal display
    rounding; ``over_2_5_hits`` counts matches with 3+ total goals and
    ``btts_hits`` matches where both sides scored.
    """

    team: str
    league: str
    season: str
    games: int
    goals_for: int
    goals_against: int
    goals_per_game: float
    xg_per_game: float
    over_2_5_hits: int
    btts_hits: int


def load_xg_payload(payload: object) -> dict[str, Mapping[str, object]]:
    """Validate an already-parsed Understat snapshot payload without file I/O.

    Same root-type contract as :func:`load_xg_snapshot`; lets read-only callers
    (e.g. ``papersim selfcheck``) feed an in-memory snapshot without writes.
    """
    if not isinstance(payload, dict):
        raise ValueError("xG snapshot root must be a JSON object")
    return payload


def load_xg_snapshot(path: str) -> dict[str, Mapping[str, object]]:
    """Load an Understat snapshot JSON from ``path`` without network access.

    Returns the raw ``{"<League>_<season>": {"teams": {...}, "dates": [...]}}``
    structure unmodified so raw payloads are preserved before normalization.
    """
    with open(path, "r", encoding="utf-8") as handle:
        return load_xg_payload(json.load(handle))


def season_key(league: str, season: str) -> str:
    """Snapshot block key for one league-season (``"EPL"``, ``"2026"`` -> ``"EPL_2026"``)."""
    return f"{league}_{season}"


def prior_season(season: str) -> str:
    """Snapshot season key of the season before ``season`` (``"2026"`` -> ``"2025"``)."""
    try:
        year = int(season)
    except ValueError as exc:
        raise ValueError(f"season must be an integer year string, got {season!r}") from exc
    return str(year - 1)


def _season_block(
    snapshot: Mapping[str, object],
    league: str,
    season: str,
) -> Mapping[str, object] | None:
    block = snapshot.get(season_key(league, season))
    return block if isinstance(block, Mapping) else None


def _latest_season(snapshot: Mapping[str, object], league: str) -> str | None:
    """Newest integer season present for ``league`` (the lineage pinned ``2026``)."""
    prefix = f"{league}_"
    years: list[int] = []
    for key in snapshot:
        if isinstance(key, str) and key.startswith(prefix):
            tail = key[len(prefix) :]
            try:
                years.append(int(tail))
            except ValueError:
                continue
    return str(max(years)) if years else None


def _team_history(block: Mapping[str, object], title: str) -> list[Mapping[str, object]] | None:
    teams = block.get("teams")
    if not isinstance(teams, Mapping):
        return None
    for row in teams.values():
        if isinstance(row, Mapping) and row.get("title") == title:
            history = row.get("history")
            if isinstance(history, list):
                return [entry for entry in history if isinstance(entry, Mapping)]
            return []
    return None


def team_rows(
    snapshot: Mapping[str, object],
    league: str,
    season: str,
) -> dict[str, XgTeamRow]:
    """Normalize one season block into :class:`XgTeamRow` values, verbatim.

    Raw history mappings (including unrounded xG floats) are preserved
    exactly; only the container shape is normalized.
    """
    block = _season_block(snapshot, league, season)
    if block is None:
        raise KeyError(f"missing xG snapshot block: {season_key(league, season)!r}")
    teams = block.get("teams")
    if not isinstance(teams, Mapping):
        raise ValueError(f"snapshot block {season_key(league, season)!r} has no teams mapping")
    rows: dict[str, XgTeamRow] = {}
    for team_id, row in teams.items():
        if not isinstance(row, Mapping):
            continue
        history = row.get("history")
        entries = tuple(history) if isinstance(history, list) else ()
        rows[str(team_id)] = XgTeamRow(
            team_id=str(team_id),
            title=str(row.get("title", "")),
            history=entries,
        )
    return rows


def league_goal_fit(
    snapshot: Mapping[str, object],
    league: str,
    season: str,
) -> LeagueGoalFit:
    """Mean home/away xG base rates over ``season``'s completed matches.

    Only ``dates`` rows with a truthy ``isResult`` contribute (the
    lineage's completed-match filter). Raises ``KeyError`` when the
    league-season block is missing and ``ValueError`` when it has no
    completed matches.
    """
    block = _season_block(snapshot, league, season)
    if block is None:
        raise KeyError(f"missing xG snapshot block: {season_key(league, season)!r}")
    dates = block.get("dates")
    results = [
        row
        for row in (dates if isinstance(dates, list) else [])
        if isinstance(row, Mapping) and row.get("isResult")
    ]
    if not results:
        raise ValueError(f"no completed matches in {season_key(league, season)!r}")
    home_rate = sum(float(row["xG"]["h"]) for row in results) / len(results)
    away_rate = sum(float(row["xG"]["a"]) for row in results) / len(results)
    return LeagueGoalFit(
        home_rate=home_rate,
        away_rate=away_rate,
        league_avg=(home_rate + away_rate) / 2.0,
    )


def ratings_for(
    snapshot: Mapping[str, object],
    league: str,
    season: str,
    *,
    last_weight: float,
    prior_games: float,
    mode: str = "blend",
) -> LeagueRatings:
    """Goal-fit attack / defense multipliers for ``league``'s ``season``.

    ``mode`` selects the rating dimension of the lineage sweep:
    ``"blend"`` (shrinkage blend of current-season games, the last-season
    rate weighted ``last_weight * SEASON_GAMES`` pseudo-matches and a
    ``prior_games``-match league-average prior), ``"cur"`` (current-season
    rates only) or ``"last"`` (last-season rates only). The league base
    rates always come from the PRIOR season's completed matches, in every
    mode, exactly as in the lineage.
    """
    if mode not in RATING_MODES:
        raise ValueError(f"unknown rating mode {mode!r}; expected one of {RATING_MODES}")
    current_block = _season_block(snapshot, league, season)
    if current_block is None:
        raise KeyError(f"missing xG snapshot block: {season_key(league, season)!r}")
    goal_fit = league_goal_fit(snapshot, league, prior_season(season))
    lgf = goal_fit.league_avg

    last_rates: dict[str, tuple[float, float]] = {}
    prior_block = _season_block(snapshot, league, prior_season(season))
    if prior_block is not None:
        prior_teams = prior_block.get("teams")
        if isinstance(prior_teams, Mapping):
            for row in prior_teams.values():
                if not isinstance(row, Mapping):
                    continue
                history = row.get("history")
                if not isinstance(history, list) or not history:
                    continue
                title = row.get("title")
                if not isinstance(title, str):
                    continue
                for_rate = sum(float(entry["xG"]) for entry in history) / len(history)
                against_rate = sum(float(entry["xGA"]) for entry in history) / len(history)
                last_rates[title] = (for_rate, against_rate)

    teams: dict[str, tuple[float, float]] = {}
    current_teams = current_block.get("teams")
    if isinstance(current_teams, Mapping):
        for row in current_teams.values():
            if not isinstance(row, Mapping):
                continue
            history = row.get("history")
            if not isinstance(history, list) or not history:
                continue
            title = row.get("title")
            if not isinstance(title, str):
                continue
            current_for = sum(float(entry["xG"]) for entry in history) / len(history)
            current_against = sum(float(entry["xGA"]) for entry in history) / len(history)
            games = len(history)
            if mode == "cur":
                blend_for, blend_against = current_for, current_against
            elif mode == "last":
                blend_for, blend_against = last_rates.get(title, (lgf, lgf))
            else:
                last_for, last_against = last_rates.get(title, (lgf, lgf))
                last_weighted = last_weight * SEASON_GAMES
                denom = games + last_weighted + prior_games
                blend_for = (games * current_for + last_weighted * last_for + prior_games * lgf) / denom
                blend_against = (
                    games * current_against + last_weighted * last_against + prior_games * lgf
                ) / denom
            teams[title] = (blend_for / lgf, blend_against / lgf)

    return LeagueRatings(league=league, season=season, goal_fit=goal_fit, teams=teams)


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
    return dict(ratings_for(snapshot, league, season, last_weight=last_weight, prior_games=prior_games).teams)


def team_league_registry(
    snapshot: Mapping[str, object],
    *,
    season: str | None = None,
) -> dict[str, frozenset[str]]:
    """Map each Understat team title to the leagues it appears in.

    With ``season`` unset every league-season block contributes (a team
    active in two leagues maps to both); with ``season`` set only that
    season's blocks contribute, mirroring the lineage registry that was
    built from the current season's team tables.
    """
    registry: dict[str, set[str]] = {}
    for key, block in snapshot.items():
        if not isinstance(key, str) or not isinstance(block, Mapping):
            continue
        if "_" not in key:
            continue
        league, _, key_season = key.rpartition("_")
        if season is not None and key_season != season:
            continue
        teams = block.get("teams")
        if not isinstance(teams, Mapping):
            continue
        for row in teams.values():
            if isinstance(row, Mapping) and isinstance(row.get("title"), str):
                registry.setdefault(row["title"], set()).add(league)
    return {title: frozenset(leagues) for title, leagues in registry.items()}


def _resolve_league_ratings(
    snapshot: Mapping[str, object],
    league: str,
    team: str,
    *,
    season: str | None,
    last_weight: float,
    prior_games: float,
    mode: str,
) -> LeagueRatings | None:
    """One league's ratings when its season blocks and ``team`` resolve.

    Mirrors the same-league guards of :func:`pair_lambdas` for one
    league: ``None`` when the league is absent from the snapshot, has
    no resolvable current season, lacks the current or prior season
    block, has no team table, or when ``team`` is not in it.
    """
    if season is None:
        resolved = _latest_season(snapshot, league)
        if resolved is None:
            return None
    else:
        resolved = season
    block = _season_block(snapshot, league, resolved)
    if block is None or _season_block(snapshot, league, prior_season(resolved)) is None:
        return None
    teams = block.get("teams")
    if not isinstance(teams, Mapping):
        return None
    titles = {
        str(row.get("title"))
        for row in teams.values()
        if isinstance(row, Mapping)
    }
    if team not in titles:
        return None
    return ratings_for(
        snapshot,
        league,
        resolved,
        last_weight=last_weight,
        prior_games=prior_games,
        mode=mode,
    )


def _cross_league_pair_lambdas(
    snapshot: Mapping[str, object],
    home_team: str,
    home_league: str,
    away_team: str,
    away_league: str,
    *,
    last_weight: float,
    prior_games: float,
    mode: str,
    shrink: float,
    season: str | None,
    factor: float,
) -> tuple[float, float] | None:
    """Bridged cross-league rates: the WP-P2a sanctioned path.

    Each side keeps its OWN league's base rate and multipliers
    (``ratings_X`` from the home league, ``ratings_Y`` from the away
    league) and the pair is tilted by the clamped league-strength
    factor ``f`` from :func:`polymarket_alpha_lab.papersim.league_strength.bridge_factor`
    — home rate ``* f``, away rate ``/ f`` — so the team from the
    stronger league is boosted on both sides of the ball. Returns
    ``None`` under the same per-league guards as the same-league path
    (missing blocks or unknown team in ITS league's table).
    """
    ratings_home = _resolve_league_ratings(
        snapshot,
        home_league,
        home_team,
        season=season,
        last_weight=last_weight,
        prior_games=prior_games,
        mode=mode,
    )
    if ratings_home is None:
        return None
    ratings_away = _resolve_league_ratings(
        snapshot,
        away_league,
        away_team,
        season=season,
        last_weight=last_weight,
        prior_games=prior_games,
        mode=mode,
    )
    if ratings_away is None:
        return None
    attack_home, defense_home = ratings_home.teams.get(home_team, (1.0, 1.0))
    attack_away, defense_away = ratings_away.teams.get(away_team, (1.0, 1.0))
    return (
        ratings_home.goal_fit.home_rate
        * (attack_home ** shrink)
        * (defense_away ** shrink)
        * factor,
        ratings_away.goal_fit.away_rate
        * (attack_away ** shrink)
        * (defense_home ** shrink)
        / factor,
    )


def pair_lambdas(
    snapshot: Mapping[str, object],
    home_team: str,
    home_league: str,
    away_team: str,
    away_league: str,
    *,
    last_weight: float,
    prior_games: float,
    mode: str = "blend",
    shrink: float = 1.0,
    season: str | None = None,
    bridge: Mapping[str, float] | None = None,
) -> tuple[float, float] | None:
    """Expected goal rates for one fixture, with the cross-league guard.

    Returns ``None`` when the clubs' leagues differ (``home_league !=
    away_league``) — the structural cross-league guard — UNLESS an
    explicit league-strength ``bridge`` table is supplied, in which
    case the WP-P2a bridged cross-league path applies: each side keeps
    its own league's base rate and multipliers and the pair is tilted
    by the clamped factor ``f = bridge_factor(bridge, home_league,
    away_league)`` (home ``* f``, away ``/ f``; ``None`` again when
    either league is missing from the bridge). The same-league path
    below is byte-identical regardless of ``bridge``: the argument is
    never consulted when ``home_league == away_league``.

    Also returns ``None`` when either league-season block is missing
    from the snapshot, or when either team is absent from the shared
    league's current-season team table. Otherwise computes
    ``lambda_home = home_rate * attack_home**shrink * defense_away**shrink``
    and ``lambda_away = away_rate * attack_away**shrink * defense_home**shrink``
    from the selected rating mode. ``"Championship"`` fixtures
    (FotMob-sourced, :data:`DOMESTIC_LEAGUES`) are ordinary domestic
    same-league pairs on this standard path (WP-P3). Teams present in
    the table but without current-season history use league-average
    (1.0, 1.0) multipliers, as in the lineage.
    """
    if home_league != away_league:
        if bridge is None:
            return None
        factor = bridge_factor(bridge, home_league, away_league)
        if factor is None:
            return None
        return _cross_league_pair_lambdas(
            snapshot,
            home_team,
            home_league,
            away_team,
            away_league,
            last_weight=last_weight,
            prior_games=prior_games,
            mode=mode,
            shrink=shrink,
            season=season,
            factor=factor,
        )
    league = home_league
    if season is None:
        season = _latest_season(snapshot, league)
        if season is None:
            return None
    current_block = _season_block(snapshot, league, season)
    if current_block is None or _season_block(snapshot, league, prior_season(season)) is None:
        return None
    teams = current_block.get("teams")
    if not isinstance(teams, Mapping):
        return None
    titles = {
        str(row.get("title"))
        for row in teams.values()
        if isinstance(row, Mapping)
    }
    if home_team not in titles or away_team not in titles:
        return None
    ratings = ratings_for(
        snapshot,
        league,
        season,
        last_weight=last_weight,
        prior_games=prior_games,
        mode=mode,
    )
    attack_home, defense_home = ratings.teams.get(home_team, (1.0, 1.0))
    attack_away, defense_away = ratings.teams.get(away_team, (1.0, 1.0))
    home_rate = ratings.goal_fit.home_rate
    away_rate = ratings.goal_fit.away_rate
    return (
        home_rate * (attack_home ** shrink) * (defense_away ** shrink),
        away_rate * (attack_away ** shrink) * (defense_home ** shrink),
    )


def recent_form(
    snapshot: Mapping[str, object],
    team: str,
    *,
    season: str | None = None,
    window: int = 5,
    min_current: int = 3,
) -> RecentForm | None:
    """Last-``window`` actual-goal form context for ``team``.

    Resolves the team's league through :func:`team_league_registry`
    (leagues scanned in sorted order for determinism), reads the
    current-season history and falls back to the prior season when fewer
    than ``min_current`` current-season rows exist. Returns ``None`` when
    the team is unknown or has no history in either season, exactly as
    the r15 helper did.
    """
    registry = team_league_registry(snapshot, season=season)
    leagues = registry.get(team)
    if not leagues:
        return None
    if season is None:
        candidates = [
            latest
            for latest in (_latest_season(snapshot, lg) for lg in sorted(leagues))
            if latest is not None
        ]
        if not candidates:
            return None
        resolved_season = str(max(int(candidate) for candidate in candidates))
    else:
        resolved_season = season
    history: list[Mapping[str, object]] | None = None
    used_league = ""
    used_season = resolved_season
    for league in sorted(leagues):
        block = _season_block(snapshot, league, resolved_season)
        if block is None:
            continue
        found = _team_history(block, team)
        if found is not None:
            used_league = league
            history = found
            break
    if history is None:
        return None
    if len(history) < min_current:
        # Lineage semantics: a short current-season history is REPLACED by
        # the prior-season history; when that is absent the team has no
        # form context at all (None).
        replacement: list[Mapping[str, object]] | None = None
        for league in sorted(leagues):
            block = _season_block(snapshot, league, prior_season(resolved_season))
            if block is None:
                continue
            found = _team_history(block, team)
            if found is not None:
                replacement = found
                used_league = league
                break
        history = replacement or []
        used_season = prior_season(resolved_season)
    if not history:
        return None
    recent = history[-window:]
    games = len(recent)
    goals_for = sum(int(entry.get("scored") or 0) for entry in recent)
    goals_against = sum(int(entry.get("missed") or 0) for entry in recent)
    xg_for = sum(float(entry.get("xG") or 0.0) for entry in recent)
    xg_against = sum(float(entry.get("xGA") or 0.0) for entry in recent)
    over_hits = sum(
        1
        for entry in recent
        if (int(entry.get("scored") or 0) + int(entry.get("missed") or 0)) >= 3
    )
    btts_hits = sum(
        1
        for entry in recent
        if int(entry.get("scored") or 0) >= 1 and int(entry.get("missed") or 0) >= 1
    )
    return RecentForm(
        team=team,
        league=used_league,
        season=used_season,
        games=games,
        goals_for=goals_for,
        goals_against=goals_against,
        goals_per_game=round((goals_for + goals_against) / games, 2),
        xg_per_game=round((xg_for + xg_against) / games, 2),
        over_2_5_hits=over_hits,
        btts_hits=btts_hits,
    )
