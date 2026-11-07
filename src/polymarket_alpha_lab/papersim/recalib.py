"""Opt-in WP-P4 soccer recalibration research, entirely in memory.

Nothing in the production model or its gate facade imports this module.  A
caller supplies completed, deduplicated match records and an audited schedule:
``completed_matchweeks`` is an explicit assertion about COMPLETE rounds, not a
round number inferred from the last result.  A whole round is excluded if any
of its supplied records is too recent.  ``matchweek=None`` is permitted only
for an explicitly completed prior-season warmup whose round metadata is absent.
Season labels must sort chronologically, e.g. the retained ``"2025"`` labels.

The default ``event_time_replay`` mode uses kickoff plus a conservative three
hour completion lag.  It does NOT establish historical publication time or
exclude subsequent source revisions.  ``observed`` additionally requires an
explicit ``available_at`` for every record.  No availability time is invented.
The caller must select decay/shrinkage inside training-only expanding windows;
the defaults below are research starting points, not validated selections.

Each historical match contributes once.  Exponential recency weights fit
league home/away GOAL levels, shrunk toward pooled global levels, and separate
xG levels.  Opponent-adjusted team xG attack/defence multipliers have Gamma
priors centred on one, expressed as pseudo-matches.  There is no second
current/fallback-last channel.  A separate sparse-team prior override permits
the predeclared k={0,4,8,12,16,infinity} study.  "Sparse" means fewer than eight
current-season training matches OR no prior same-league season in training;
absence of prior history alone is not proof that a club was promoted.

League levels need >=12 matches and >=6 recency-weighted matches; otherwise
they use the global prior.  Dixon-Coles rho needs >=80 positive-weight matches,
>=20 positive-weight low-score matches and >=20 weighted matches, locally or
globally; otherwise independence is explicit.  A numerically flat rho
likelihood is also insufficient.  Rho fits actual-score likelihood, not O/U.
Its feasible interval keeps every low-score cell positive without a tau floor.
All these minima are explicit Config fields.  Refit once per completed round;
predict refuses a target round at or before any fitted round in that season.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
from types import MappingProxyType
from typing import Mapping

__all__ = [
    "Config", "Estimator", "Fixture", "History", "LeagueParameters", "Match",
    "Prediction", "PredictionParameters", "TeamParameters", "fit",
]

RoundKey = tuple[str, str, int | None]
_EPS = 1e-10


@dataclass(frozen=True)
class Match:
    match_id: str
    league: str
    season: str
    matchweek: int | None
    kickoff: datetime
    home_team: str
    away_team: str
    home_xg: float
    away_xg: float
    home_goals: int
    away_goals: int
    available_at: datetime | None = None


@dataclass(frozen=True)
class Fixture:
    league: str
    season: str
    matchweek: int
    kickoff: datetime
    home_team: str
    away_team: str


@dataclass(frozen=True)
class History:
    as_of: datetime
    matches: tuple[Match, ...]
    completed_matchweeks: frozenset[RoundKey]
    target_seasons: Mapping[str, str]
    information_mode: str = "event_time_replay"


@dataclass(frozen=True)
class Config:
    half_life_days: float = 120.0
    team_prior_matches: float = 8.0
    sparse_prior_matches: float | None = None
    sparse_below_matches: int = 8
    league_prior_matches: float = 20.0
    global_prior_matches: float = 20.0
    global_home_rate: float = 1.5
    global_away_rate: float = 1.2
    min_league_matches: int = 12
    min_league_weight: float = 6.0
    min_rho_matches: int = 80
    min_rho_low_scores: int = 20
    min_rho_weight: float = 20.0
    rho_bound: float = 0.3
    completion_lag_hours: float = 3.0
    fit_iterations: int = 80
    fit_tolerance: float = 1e-9


@dataclass(frozen=True)
class TeamParameters:
    attack: float
    defence: float
    matches: int
    effective_matches: float
    current_matches: int
    prior_matches: int
    prior_strength: float
    sparse: bool


@dataclass(frozen=True)
class LeagueParameters:
    home_rate: float
    away_rate: float
    home_xg: float
    away_xg: float
    matches: int
    effective_matches: float
    level_source: str
    rho: float
    rho_source: str
    rho_low_score_matches: int
    fit_iterations: int
    converged: bool


@dataclass(frozen=True)
class PredictionParameters:
    as_of: datetime
    config: Config
    information_mode: str
    league: LeagueParameters
    home: TeamParameters
    away: TeamParameters
    fitted_rho: float
    rho_projected: bool


@dataclass(frozen=True)
class Prediction:
    home_win: float
    draw: float
    away_win: float
    totals: tuple[float, ...]
    lambda_home: float
    lambda_away: float
    rho: float
    parameters: PredictionParameters

    def over_probability(self, line: float) -> float:
        """P(total > line); integer-line pushes are not included."""
        _number(line, "line", lower=0.0)
        return math.fsum(self.totals[math.floor(line) + 1:])


@dataclass(frozen=True)
class Estimator:
    as_of: datetime
    config: Config
    information_mode: str
    training_match_ids: tuple[str, ...]
    training_rounds: frozenset[RoundKey]
    excluded_matches: int
    target_seasons: Mapping[str, str]
    league_parameters: Mapping[str, LeagueParameters]
    team_parameters: Mapping[tuple[str, str], TeamParameters]
    global_parameters: LeagueParameters

    def predict(self, fixture: Fixture) -> Prediction:
        """Predict a future domestic fixture from this immutable round fit."""
        if not isinstance(fixture, Fixture):
            raise TypeError("fixture must be Fixture")
        _identity(fixture)
        _positive_int(fixture.matchweek, "fixture matchweek")
        if _utc(fixture.kickoff, "fixture kickoff") < self.as_of:
            raise ValueError("fixture kickoff precedes fit cutoff")
        if self.target_seasons.get(fixture.league) != fixture.season:
            raise ValueError("fixture does not match an explicit target league-season")
        rounds = [r for league, season, r in self.training_rounds
                  if league == fixture.league and season == fixture.season and r is not None]
        if rounds and fixture.matchweek <= max(rounds):
            raise ValueError("fixture must follow all fitted current-season rounds")
        league = self.league_parameters.get(fixture.league, self.global_parameters)
        neutral_prior = (self.config.team_prior_matches if self.config.sparse_prior_matches is None
                         else self.config.sparse_prior_matches)
        neutral = TeamParameters(1.0, 1.0, 0, 0.0, 0, 0, neutral_prior, True)
        home = self.team_parameters.get((fixture.league, fixture.home_team), neutral)
        away = self.team_parameters.get((fixture.league, fixture.away_team), neutral)
        lh, la = league.home_rate * home.attack * away.defence, league.away_rate * away.attack * home.defence
        lower, upper = _rho_interval(((lh, la),), self.config.rho_bound)
        rho = min(upper, max(lower, league.rho))
        home_win, draw, away_win, totals = _probabilities(lh, la, rho)
        return Prediction(home_win, draw, away_win, totals, lh, la, rho,
                          PredictionParameters(self.as_of, self.config, self.information_mode,
                                               league, home, away, league.rho, rho != league.rho))


def _number(value: object, name: str, *, lower: float, strictly: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    number = float(value)
    if not math.isfinite(number) or number < lower or (strictly and number == lower):
        raise ValueError(f"{name} must be finite and {'greater than' if strictly else 'at least'} {lower}")
    return number


def _positive_int(value: object, name: str, *, zero: bool = False) -> None:
    if type(value) is not int or value < (0 if zero else 1):
        raise ValueError(f"{name} must be a {'nonnegative' if zero else 'positive'} integer")


def _utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be an aware datetime")
    return value.astimezone(timezone.utc)


def _identity(row: Match | Fixture) -> None:
    for name in ("league", "season", "home_team", "away_team"):
        value = getattr(row, name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a nonempty string")
    if row.home_team == row.away_team:
        raise ValueError("home and away teams must differ")


def _validate_config(config: Config) -> None:
    if not isinstance(config, Config):
        raise TypeError("config must be Config")
    for name in ("half_life_days", "global_prior_matches", "global_home_rate", "global_away_rate",
                 "rho_bound", "fit_tolerance"):
        _number(getattr(config, name), name, lower=0.0, strictly=True)
    for name in ("team_prior_matches", "league_prior_matches", "min_league_weight", "min_rho_weight"):
        _number(getattr(config, name), name, lower=0.0)
    _number(config.completion_lag_hours, "completion_lag_hours", lower=3.0)
    for name in ("sparse_below_matches", "min_league_matches", "min_rho_matches",
                 "min_rho_low_scores", "fit_iterations"):
        _positive_int(getattr(config, name), name)
    if config.rho_bound >= 1.0:
        raise ValueError("rho_bound must be below one")
    if config.sparse_prior_matches is not None:
        if isinstance(config.sparse_prior_matches, bool):
            raise ValueError("sparse_prior_matches must be nonnegative or positive infinity")
        if config.sparse_prior_matches != math.inf:
            _number(config.sparse_prior_matches, "sparse_prior_matches", lower=0.0)


def _training_rows(history: History, config: Config) -> tuple[tuple[Match, ...], frozenset[RoundKey]]:
    as_of = _utc(history.as_of, "as_of")
    if history.information_mode not in ("observed", "event_time_replay"):
        raise ValueError("information_mode must be observed or event_time_replay")
    targets = history.target_seasons
    if not isinstance(targets, Mapping) or any(not isinstance(k, str) or not k or
                                             not isinstance(v, str) or not v for k, v in targets.items()):
        raise ValueError("target_seasons must map league names to season labels")
    completed: set[RoundKey] = set()
    for key in history.completed_matchweeks:
        if not isinstance(key, tuple) or len(key) != 3:
            raise ValueError("completed_matchweeks must contain (league, season, round) tuples")
        league, season, week = key
        if league not in targets or not isinstance(season, str) or season > targets[league]:
            raise ValueError("completed round has no valid target league-season")
        if week is None:
            if season >= targets[league]:
                raise ValueError("round=None is prior-season warmup only")
        else:
            _positive_int(week, "completed matchweek")
        completed.add(key)
    groups: dict[RoundKey, list[Match]] = defaultdict(list)
    ids: set[tuple[str, str, str]] = set()
    fixtures: set[tuple[object, ...]] = set()
    for row in history.matches:
        if not isinstance(row, Match):
            raise TypeError("history matches must be Match records")
        _identity(row)
        if not isinstance(row.match_id, str) or not row.match_id:
            raise ValueError("match_id must be a nonempty source-qualified identifier")
        if row.league not in targets or row.season > targets[row.league]:
            raise ValueError("match has no valid target league-season")
        if row.matchweek is None:
            if row.season >= targets[row.league]:
                raise ValueError("current-season matches require official matchweek numbers")
        else:
            _positive_int(row.matchweek, "matchweek")
        kickoff = _utc(row.kickoff, "match kickoff")
        for name in ("home_xg", "away_xg"):
            _number(getattr(row, name), name, lower=0.0)
        for name in ("home_goals", "away_goals"):
            _positive_int(getattr(row, name), name, zero=True)
        if row.available_at is None:
            if history.information_mode == "observed":
                raise ValueError("observed mode requires available_at on every match")
        elif _utc(row.available_at, "available_at") < kickoff:
            raise ValueError("available_at cannot precede kickoff")
        identifier = (row.league, row.season, row.match_id)
        natural_key = (row.league, row.season, kickoff, row.home_team, row.away_team)
        if identifier in ids or natural_key in fixtures:
            raise ValueError("duplicate match or unresolved source revision")
        ids.add(identifier)
        fixtures.add(natural_key)
        groups[(row.league, row.season, row.matchweek)].append(row)
    selected: list[Match] = []
    admitted: set[RoundKey] = set()
    lag = timedelta(hours=config.completion_lag_hours)
    for key, rows in groups.items():
        if key not in completed:
            continue
        if any(_utc(row.kickoff, "kickoff") + lag >= as_of or
               (row.available_at is not None and _utc(row.available_at, "available_at") >= as_of)
               for row in rows):
            continue
        admitted.add(key)
        selected.extend(rows)
    selected.sort(key=lambda r: (_utc(r.kickoff, "kickoff"), r.league, r.season, r.match_id))
    return tuple(selected), frozenset(admitted)


def _levels(rows: tuple[tuple[Match, float], ...], prior: tuple[float, ...], strength: float) -> tuple[float, ...]:
    mass = math.fsum(weight for _, weight in rows)
    names = ("home_goals", "away_goals", "home_xg", "away_xg")
    return tuple(max(_EPS, (math.fsum(weight * getattr(row, name) for row, weight in rows) +
                            strength * fallback) / (mass + strength))
                 for name, fallback in zip(names, prior))


def _teams(rows: tuple[tuple[Match, float], ...], season: str,
           levels: tuple[float, ...], config: Config) -> tuple[dict[str, TeamParameters], int, bool]:
    # Conditional Gamma-Poisson MAP updates, using xG as fractional counts.
    # Every team has one attack and one concession multiplier, adjusted for
    # opponent strength and the xG baseline at the venue where it played.
    per_team: dict[str, list[tuple[Match, float, bool]]] = defaultdict(list)
    for row, weight in rows:
        per_team[row.home_team].append((row, weight, True))
        per_team[row.away_team].append((row, weight, False))
    names = sorted(per_team)
    priors: dict[str, float] = {}
    metadata: dict[str, tuple[int, float, int, int, float, bool]] = {}
    targets: dict[str, tuple[float, float]] = {}
    for team in names:
        games = per_team[team]
        current = sum(row.season == season for row, _, _ in games)
        previous = sum(row.season < season for row, _, _ in games)
        sparse = current < config.sparse_below_matches or previous == 0
        k = config.sparse_prior_matches if sparse and config.sparse_prior_matches is not None else config.team_prior_matches
        priors[team] = k * (levels[2] + levels[3]) / 2.0
        metadata[team] = (len(games), math.fsum(w for _, w, _ in games), current, previous, k, sparse)
        targets[team] = (math.fsum(w * (row.home_xg if home else row.away_xg) for row, w, home in games),
                         math.fsum(w * (row.away_xg if home else row.home_xg) for row, w, home in games))
    attacks = dict.fromkeys(names, 1.0)
    defences = dict.fromkeys(names, 1.0)
    converged = not names
    iterations = 0
    for iterations in range(1, config.fit_iterations + 1):
        next_attacks: dict[str, float] = {}
        next_defences: dict[str, float] = {}
        for team in names:
            prior = priors[team]
            exposure = math.fsum(w * (levels[2] if home else levels[3]) *
                                  defences[row.away_team if home else row.home_team]
                                  for row, w, home in per_team[team])
            next_attacks[team] = 1.0 if math.isinf(prior) else max(_EPS, (targets[team][0] + prior) / max(_EPS, exposure + prior))
        for team in names:
            prior = priors[team]
            exposure = math.fsum(w * (levels[3] if home else levels[2]) *
                                  next_attacks[row.away_team if home else row.home_team]
                                  for row, w, home in per_team[team])
            next_defences[team] = 1.0 if math.isinf(prior) else max(_EPS, (targets[team][1] + prior) / max(_EPS, exposure + prior))
        change = max((max(abs(next_attacks[t] - attacks[t]), abs(next_defences[t] - defences[t])) for t in names), default=0.0)
        attacks, defences = next_attacks, next_defences
        if change <= config.fit_tolerance:
            converged = True
            break
    return ({team: TeamParameters(attacks[team], defences[team], *metadata[team]) for team in names},
            iterations if names else 0, converged)


def _rho_interval(rates: tuple[tuple[float, float], ...], bound: float) -> tuple[float, float]:
    lower, upper = -bound, bound
    for lh, la in rates:
        if not math.isfinite(lh) or not math.isfinite(la) or lh < 0.0 or la < 0.0:
            raise ValueError("expected goal rates must be finite and nonnegative")
        if lh > 0.0:
            lower = max(lower, -(1.0 - _EPS) / lh)
        if la > 0.0:
            lower = max(lower, -(1.0 - _EPS) / la)
        if lh * la > 0.0:
            upper = min(upper, (1.0 - _EPS) / (lh * la))
    return lower, min(upper, 1.0 - _EPS)


def _rho_fit(rows: tuple[tuple[Match, float, float, float], ...], config: Config) -> tuple[float, bool, int]:
    # Decay can underflow: zero-weight rows are absent from the likelihood,
    # its sample-size checks, and its positivity constraints.
    rows = tuple(item for item in rows if item[1] > 0.0)
    low = sum(row.home_goals <= 1 and row.away_goals <= 1 for row, _, _, _ in rows)
    eligible = (len(rows) >= config.min_rho_matches and low >= config.min_rho_low_scores and
                math.fsum(w for _, w, _, _ in rows) >= config.min_rho_weight)
    if not eligible:
        return 0.0, False, low
    lower, upper = _rho_interval(tuple((lh, la) for _, _, lh, la in rows), config.rho_bound)
    terms: list[tuple[float, float]] = []
    for row, weight, lh, la in rows:
        score = (row.home_goals, row.away_goals)
        coefficient = {(0, 0): -lh * la, (0, 1): lh, (1, 0): la, (1, 1): -1.0}.get(score)
        if coefficient is not None and weight * coefficient != 0.0:
            terms.append((weight, coefficient))
    if not terms:
        return 0.0, False, low
    # The score-dependent log likelihood is sum w*log(1+c*rho), concave.
    def derivative(rho: float) -> float:
        return math.fsum(w * c / (1.0 + c * rho) for w, c in terms)
    if derivative(lower) <= 0.0:
        return lower, True, low
    if derivative(upper) >= 0.0:
        return upper, True, low
    for _ in range(70):
        midpoint = (lower + upper) / 2.0
        if derivative(midpoint) > 0.0:
            lower = midpoint
        else:
            upper = midpoint
    return (lower + upper) / 2.0, True, low


def fit(history: History, *, config: Config | None = None) -> Estimator:
    """Fit one audited cutoff; this function performs no I/O or model search."""
    if not isinstance(history, History):
        raise TypeError("history must be History")
    config = Config() if config is None else config
    _validate_config(config)
    rows, rounds = _training_rows(history, config)
    as_of = _utc(history.as_of, "as_of")
    weighted = tuple((r, math.exp2(-(as_of - _utc(r.kickoff, "kickoff")).total_seconds() /
                                  (86400.0 * config.half_life_days))) for r in rows)
    prior = (config.global_home_rate, config.global_away_rate) * 2
    global_levels = _levels(weighted, prior, config.global_prior_matches)
    grouped: dict[str, list[tuple[Match, float]]] = defaultdict(list)
    for row, weight in weighted:
        grouped[row.league].append((row, weight))
    league_data: dict[str, tuple[tuple[float, ...], str, int, bool]] = {}
    teams: dict[tuple[str, str], TeamParameters] = {}
    score_rows: dict[str, tuple[tuple[Match, float, float, float], ...]] = {}
    for league in sorted(grouped):
        games = tuple(grouped[league])
        mass = math.fsum(w for _, w in games)
        enough = len(games) >= config.min_league_matches and mass >= config.min_league_weight
        levels = _levels(games, global_levels, config.league_prior_matches) if enough else global_levels
        ratings, iterations, converged = _teams(games, history.target_seasons[league], levels, config)
        teams.update({(league, name): rating for name, rating in ratings.items()})
        league_data[league] = (levels, "league_shrunk" if enough else "global_fallback", iterations, converged)
        score_rows[league] = tuple((row, w,
                                   levels[0] * ratings[row.home_team].attack * ratings[row.away_team].defence,
                                   levels[1] * ratings[row.away_team].attack * ratings[row.home_team].defence)
                                  for row, w in games)
    global_scores = tuple(item for league in sorted(score_rows) for item in score_rows[league])
    global_rho, global_ok, global_low = _rho_fit(global_scores, config)
    global_parameters = LeagueParameters(*global_levels, len(rows), math.fsum(w for _, w in weighted),
                                          "global_shrunk" if rows else "configured_prior", global_rho,
                                          "global" if global_ok else "independence_insufficient_data",
                                          global_low, 0, True)
    leagues: dict[str, LeagueParameters] = {}
    for league, (levels, source, iterations, converged) in league_data.items():
        rho, enough, low = _rho_fit(score_rows[league], config)
        rho_source = "league" if enough else ("global_fallback" if global_ok else "independence_insufficient_data")
        leagues[league] = LeagueParameters(*levels, len(grouped[league]), math.fsum(w for _, w in grouped[league]),
                                           source, rho if enough else global_rho, rho_source, low, iterations, converged)
    return Estimator(as_of, config, history.information_mode, tuple(r.match_id for r in rows), rounds,
                     len(history.matches) - len(rows), MappingProxyType(dict(history.target_seasons)),
                     MappingProxyType(leagues), MappingProxyType(teams), global_parameters)


def _poisson(rate: float) -> tuple[float, ...]:
    # Finite support is expanded per fixture; truncation is below 1e-12.
    # Rates beyond 100 goals are rejected rather than silently clamped.
    if not math.isfinite(rate) or not 0.0 <= rate <= 100.0:
        raise ValueError("expected goal rate outside supported range [0, 100]")
    masses = [math.exp(-rate)]
    ceiling = max(16, math.ceil(rate + 12.0 * math.sqrt(rate + 1.0) + 10.0))
    for goal in range(1, ceiling + 1):
        masses.append(masses[-1] * rate / goal)
        if goal >= 2 and math.fsum(masses) >= 1.0 - 1e-12:
            break
    return tuple(masses)


def _probabilities(lh: float, la: float, rho: float) -> tuple[float, float, float, tuple[float, ...]]:
    home, away = _poisson(lh), _poisson(la)
    totals = [0.0] * (len(home) + len(away) - 1)
    wins, draws, losses = [], [], []
    taus = {(0, 0): 1.0 - lh * la * rho, (0, 1): 1.0 + lh * rho,
            (1, 0): 1.0 + la * rho, (1, 1): 1.0 - rho}
    for h, hp in enumerate(home):
        for a, ap in enumerate(away):
            p = hp * ap * taus.get((h, a), 1.0)
            totals[h + a] += p
            (wins if h > a else draws if h == a else losses).append(p)
    mass = math.fsum(totals)
    return (math.fsum(wins) / mass, math.fsum(draws) / mass, math.fsum(losses) / mass,
            tuple(p / mass for p in totals))
