"""Behavioral checks for the opt-in WP-P4 model; no database or network."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import math

import pytest

from polymarket_alpha_lab.papersim.recalib import Config, Fixture, History, Match, fit


START = datetime(2026, 1, 1, tzinfo=timezone.utc)
CUTOFF = START + timedelta(days=120)


def match(n: int, *, league: str = "EPL", season: str = "2026", **changes: object) -> Match:
    row = Match(f"source:{league}:{season}:{n}", league, season, n + 1,
                START + timedelta(days=n), "Alpha", "Beta", 1.0, 1.0, 1, 1)
    return replace(row, **changes)


def history(rows: tuple[Match, ...], *, as_of: datetime = CUTOFF, **changes: object) -> History:
    value = History(as_of, rows, frozenset((r.league, r.season, r.matchweek) for r in rows),
                    {r.league: "2026" for r in rows})
    return replace(value, **changes)


def fixture(*, league: str = "EPL", **changes: object) -> Fixture:
    value = Fixture(league, "2026", 200, CUTOFF, "Alpha", "Beta")
    return replace(value, **changes)


def unshrunk_league(**changes: object) -> Config:
    return replace(Config(), min_league_matches=1, min_league_weight=0.0,
                   league_prior_matches=0.0, **changes)


def test_completed_rounds_are_filtered_atomically_with_strict_lag_and_cutoff() -> None:
    cutoff = START + timedelta(days=10)
    old = match(0)
    partial_early = match(1, matchweek=2)
    partial_late = match(2, matchweek=2, kickoff=cutoff - timedelta(hours=3))
    future = match(3, kickoff=cutoff + timedelta(days=10), home_xg=80.0)
    undeclared = match(4)
    value = history((old, partial_early, partial_late, future, undeclared), as_of=cutoff,
                    completed_matchweeks=frozenset({("EPL", "2026", 1),
                                                   ("EPL", "2026", 2), ("EPL", "2026", 4)}))
    fitted = fit(value)
    assert fitted.training_match_ids == (old.match_id,)
    assert fitted.training_rounds == frozenset({("EPL", "2026", 1)})
    assert fitted.excluded_matches == 4
    baseline = fit(history((old,), as_of=cutoff))
    assert fitted.predict(fixture(kickoff=cutoff)) == baseline.predict(fixture(kickoff=cutoff))


def test_availability_is_not_invented_and_delayed_publication_excludes_round() -> None:
    missing = match(0)
    with pytest.raises(ValueError, match="requires available_at"):
        fit(history((missing,), information_mode="observed"))
    first = replace(missing, available_at=START + timedelta(hours=4))
    second = match(1, available_at=CUTOFF, matchweek=1)
    fitted = fit(history((first, second), information_mode="observed"))
    assert fitted.training_match_ids == ()
    assert fitted.predict(fixture()).parameters.information_mode == "observed"
    retrospective = fit(history((missing,)))
    assert retrospective.predict(fixture()).parameters.information_mode == "event_time_replay"


def test_prior_season_without_round_metadata_requires_explicit_warmup() -> None:
    prior = match(0, season="2025", matchweek=None)
    fitted = fit(history((prior,)))
    assert fitted.training_match_ids == (prior.match_id,)
    assert fitted.team_parameters[("EPL", "Alpha")].current_matches == 0
    assert fitted.team_parameters[("EPL", "Alpha")].prior_matches == 1
    assert fit(history((prior,), completed_matchweeks=frozenset())).training_match_ids == ()
    with pytest.raises(ValueError, match="prior-season warmup"):
        fit(history((replace(prior, season="2026"),)))


def test_duplicate_ids_and_duplicate_fixtures_are_rejected() -> None:
    row = match(0)
    with pytest.raises(ValueError, match="duplicate"):
        fit(history((row, replace(row, kickoff=START + timedelta(days=1)))))
    with pytest.raises(ValueError, match="duplicate"):
        fit(history((row, replace(row, match_id="second-provider:55"))))


def test_prediction_is_bound_to_cutoff_target_season_and_next_round() -> None:
    fitted = fit(history((match(0),)))
    assert fitted.predict(fixture(kickoff=CUTOFF)).lambda_home > 0.0
    with pytest.raises(ValueError, match="precedes fit cutoff"):
        fitted.predict(fixture(kickoff=CUTOFF - timedelta(microseconds=1)))
    with pytest.raises(ValueError, match="follow all fitted"):
        fitted.predict(fixture(matchweek=1))
    with pytest.raises(ValueError, match="target league-season"):
        fitted.predict(fixture(season="2027"))
    with pytest.raises(ValueError, match="target league-season"):
        fitted.predict(fixture(league="Other"))


def test_goal_levels_and_xg_strength_are_separate_and_totals_match_poisson() -> None:
    rows = tuple(match(n, home_goals=3, away_goals=1) for n in range(20))
    fitted = fit(history(rows), config=unshrunk_league())
    prediction = fitted.predict(fixture())
    assert prediction.parameters.league.home_xg == pytest.approx(1.0)
    assert prediction.parameters.league.away_xg == pytest.approx(1.0)
    assert prediction.parameters.home.attack == pytest.approx(1.0)
    assert prediction.parameters.away.defence == pytest.approx(1.0)
    assert (prediction.lambda_home, prediction.lambda_away) == pytest.approx((3.0, 1.0))
    assert prediction.rho == 0.0
    assert prediction.over_probability(2.5) == pytest.approx(1.0 - math.exp(-4.0) * 13.0, abs=2e-12)
    assert prediction.home_win > prediction.away_win
    assert sum((prediction.home_win, prediction.draw, prediction.away_win)) == pytest.approx(1.0)
    assert sum(prediction.totals) == pytest.approx(1.0)
    assert all(0.0 <= p <= 1.0 for p in prediction.totals)
    assert prediction.over_probability(2.0) == prediction.over_probability(2.5)


def test_recent_scoring_changes_move_short_half_life_more() -> None:
    old = tuple(match(n, home_goals=4, home_xg=4.0) for n in range(15))
    recent = tuple(match(n, home_goals=1, home_xg=1.0) for n in range(95, 110))
    data = history(old + recent)
    fast = fit(data, config=unshrunk_league(half_life_days=15.0))
    slow = fit(data, config=unshrunk_league(half_life_days=240.0))
    assert 1.0 < fast.league_parameters["EPL"].home_rate < slow.league_parameters["EPL"].home_rate < 4.0
    assert fast.team_parameters[("EPL", "Alpha")].effective_matches < slow.team_parameters[("EPL", "Alpha")].effective_matches


def test_small_league_uses_global_levels_and_unknown_team_uses_league_prior() -> None:
    broad = tuple(match(n, league="Large", home_goals=3) for n in range(40))
    small = tuple(match(n, league="Small", home_goals=0) for n in range(4))
    fitted = fit(history(broad + small))
    assert fitted.league_parameters["Small"].level_source == "global_fallback"
    assert fitted.league_parameters["Small"].home_rate == fitted.global_parameters.home_rate
    assert fitted.league_parameters["Large"].level_source == "league_shrunk"
    new = fitted.predict(fixture(league="Small", home_team="New A", away_team="New B"))
    assert new.parameters.home.attack == new.parameters.away.defence == 1.0
    assert new.lambda_home == fitted.global_parameters.home_rate


def test_balanced_opponent_adjustment_recovers_attack_and_defence_ordering() -> None:
    strengths = {"A": (1.6, 0.7), "B": (1.0, 1.0), "C": (0.65, 1.4)}
    rows = []
    for repeat in range(6):
        for home in strengths:
            for away in strengths:
                if home == away:
                    continue
                n = len(rows)
                hx = 1.6 * strengths[home][0] * strengths[away][1]
                ax = 1.2 * strengths[away][0] * strengths[home][1]
                rows.append(match(n, home_team=home, away_team=away,
                                  home_xg=hx, away_xg=ax, home_goals=round(hx), away_goals=round(ax)))
    fitted = fit(history(tuple(rows)), config=unshrunk_league(team_prior_matches=2.0))
    a, b, c = (fitted.team_parameters[("EPL", name)] for name in ("A", "B", "C"))
    assert a.attack > b.attack > c.attack
    assert a.defence < b.defence < c.defence
    assert fitted.league_parameters["EPL"].converged


def test_sparse_k_is_separate_from_general_prior_and_infinity_is_exact_prior() -> None:
    prior = tuple(match(n, season="2025", home_xg=2.0) for n in range(8))
    established = tuple(match(n, home_xg=2.0) for n in range(20, 30))
    sparse = tuple(match(n, home_team="New", away_team="Other", home_xg=4.0) for n in range(40, 42))
    data = history(prior + established + sparse)
    fitted = fit(data, config=replace(Config(), team_prior_matches=4.0, sparse_prior_matches=math.inf))
    old = fitted.team_parameters[("EPL", "Alpha")]
    new = fitted.team_parameters[("EPL", "New")]
    assert old.sparse is False and old.prior_strength == 4.0
    assert old.matches == 18 and old.current_matches == 10 and old.prior_matches == 8
    assert old.effective_matches == pytest.approx(sum(2 ** (-(CUTOFF - r.kickoff).total_seconds() / 86400 / 120)
                                                    for r in prior + established))
    assert new.sparse is True and new.prior_strength == math.inf
    assert new.attack == new.defence == 1.0
    unsmoothed = fit(data, config=replace(Config(), team_prior_matches=4.0, sparse_prior_matches=0.0))
    assert unsmoothed.team_parameters[("EPL", "New")].attack > 1.0
    for k in (0.0, 4.0, 8.0, 12.0, 16.0, math.inf):
        output = fit(data, config=replace(Config(), sparse_prior_matches=k)).predict(fixture())
        assert sum((output.home_win, output.draw, output.away_win)) == pytest.approx(1.0)


def test_rho_uses_actual_low_scores_even_when_all_ou_25_labels_are_identical() -> None:
    diagonal = tuple(match(n, home_goals=n % 2, away_goals=n % 2) for n in range(90))
    off_diagonal = tuple(match(n, home_goals=n % 2, away_goals=1 - n % 2) for n in range(90))
    assert all(row.home_goals + row.away_goals <= 2 for row in diagonal + off_diagonal)
    correlated = fit(history(diagonal)).predict(fixture())
    anticorrelated = fit(history(off_diagonal)).predict(fixture())
    assert correlated.parameters.league.rho_source == "league"
    assert anticorrelated.parameters.league.rho_source == "league"
    assert correlated.rho < 0.0 < anticorrelated.rho
    assert correlated.draw > anticorrelated.draw


def test_rho_global_fallback_and_insufficient_low_score_independence() -> None:
    large = tuple(match(n, league="Large", home_goals=n % 2, away_goals=n % 2) for n in range(90))
    small = tuple(match(n, league="Small", home_goals=1, away_goals=0) for n in range(10))
    fitted = fit(history(large + small))
    assert fitted.league_parameters["Large"].rho_source == "league"
    assert fitted.league_parameters["Small"].rho_source == "global_fallback"
    assert fitted.league_parameters["Small"].rho == fitted.global_parameters.rho
    high = tuple(match(n, home_goals=3, away_goals=2) for n in range(90))
    independent = fit(history(high))
    assert independent.league_parameters["EPL"].rho == 0.0
    assert independent.league_parameters["EPL"].rho_source == "independence_insufficient_data"


def test_empty_training_has_explicit_configured_prior_and_numerically_valid_tails() -> None:
    empty = History(CUTOFF, (), frozenset(), {"EPL": "2026"})
    fitted = fit(empty, config=replace(Config(), global_home_rate=80.0, global_away_rate=60.0))
    output = fitted.predict(fixture())
    assert output.parameters.league.level_source == "configured_prior"
    assert output.rho == 0.0
    assert output.home_win + output.draw + output.away_win == pytest.approx(1.0)
    assert sum(output.totals) == pytest.approx(1.0)
    assert output.over_probability(2.5) == pytest.approx(1.0)


def test_symmetric_prior_is_symmetric_and_infinite_sparse_prior_is_reported() -> None:
    empty = History(CUTOFF, (), frozenset(), {"EPL": "2026"})
    config = replace(Config(), global_home_rate=1.0, global_away_rate=1.0,
                     sparse_prior_matches=math.inf)
    output = fit(empty, config=config).predict(fixture())
    assert output.lambda_home == output.lambda_away == 1.0
    assert output.home_win == output.away_win
    assert output.totals[0] == pytest.approx(math.exp(-2.0), abs=2e-12)
    assert output.parameters.home.prior_strength == math.inf


def test_new_pair_projects_rho_to_positive_support_without_changing_high_totals() -> None:
    rows = []
    for n in range(100):
        home, away, xg = (("Neutral A", "Neutral B", 1.0) if n < 60 else
                          ("A", "Neutral A", 4.0) if n < 80 else ("B", "Neutral B", 4.0))
        if n % 2:
            home, away = away, home
        rows.append(match(n, home_team=home, away_team=away, home_xg=xg, away_xg=xg))
    fitted = fit(history(tuple(rows)), config=replace(Config(), team_prior_matches=4.0))
    output = fitted.predict(fixture(home_team="A", away_team="B"))
    assert output.parameters.league.converged
    assert output.parameters.rho_projected
    assert output.rho > output.parameters.fitted_rho
    assert all(p >= 0.0 for p in output.totals)
    assert sum(output.totals) == pytest.approx(1.0)
    total_rate = output.lambda_home + output.lambda_away
    independent_over = 1.0 - math.exp(-total_rate) * (1.0 + total_rate + total_rate ** 2 / 2.0)
    assert output.over_probability(2.5) == pytest.approx(independent_over, abs=2e-12)


def test_input_order_cannot_change_fit_and_fitted_mappings_are_immutable() -> None:
    rows = tuple(match(n, home_xg=1.0 + n % 3, away_xg=0.5 + n % 2,
                       home_goals=n % 4, away_goals=n % 3) for n in range(25))
    first = fit(history(rows))
    second = fit(history(tuple(reversed(rows))))
    assert first.predict(fixture()) == second.predict(fixture())
    assert first.training_match_ids == second.training_match_ids
    with pytest.raises(TypeError):
        first.target_seasons["EPL"] = "2027"  # type: ignore[index]
    with pytest.raises(TypeError):
        first.team_parameters[("EPL", "Alpha")] = first.team_parameters[("EPL", "Beta")]  # type: ignore[index]


@pytest.mark.parametrize("field,value", [("home_xg", math.nan), ("away_xg", math.inf),
                                          ("home_xg", -1.0), ("away_xg", True),
                                          ("home_goals", True), ("away_goals", 1.5),
                                          ("home_goals", -1), ("matchweek", True)])
def test_malformed_match_numbers_fail_closed(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        fit(history((replace(match(0), **{field: value}),)))


@pytest.mark.parametrize("field,value", [("half_life_days", 0.0), ("team_prior_matches", -1),
                                          ("sparse_prior_matches", -math.inf),
                                          ("sparse_prior_matches", True),
                                          ("completion_lag_hours", 0), ("rho_bound", 1.0),
                                          ("fit_iterations", True), ("min_rho_matches", 0)])
def test_invalid_config_is_rejected(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        fit(history((match(0),)), config=replace(Config(), **{field: value}))


def test_naive_timestamps_and_impossible_publication_time_are_rejected() -> None:
    with pytest.raises(ValueError, match="aware datetime"):
        fit(history((match(0, kickoff=START.replace(tzinfo=None)),)))
    with pytest.raises(ValueError, match="precede kickoff"):
        fit(history((match(0, available_at=START - timedelta(seconds=1)),)))
    with pytest.raises(ValueError, match="aware datetime"):
        fit(history((match(0),), as_of=CUTOFF.replace(tzinfo=None)))
