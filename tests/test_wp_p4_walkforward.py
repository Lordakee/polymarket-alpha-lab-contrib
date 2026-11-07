"""Tests that target nested-validation leakage and proper scoring, not fit internals."""
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace

import pytest

from tools import wp_p4_history as history
from tools import wp_p4_walkforward as wf
from tests.test_wp_p4_history import mini_audit  # shared declared synthetic fixture


def test_raw_production_medians_retained_and_normalized_only_for_scoring():
    score = wf.score_forecast((.5, .2, .2), {1.5: .7, 2.5: .5, 3.5: .3}, 2, 0)
    assert score["raw_1x2"] == (.5, .2, .2)
    assert score["raw_1x2_sum"] == pytest.approx(.9)
    assert sum(score["scoring_1x2"]) == pytest.approx(1)
    assert score["logloss_1x2"] != score["raw_median_logloss_1x2"]
    assert len(score["totals_logloss_by_line"]) == 3


def test_config_fallback_cannot_see_outer_outcomes(mini_audit):
    fold = history.build_folds(mini_audit)[0][0]
    config, meta = wf.select_config(mini_audit, fold)
    changed = replace(mini_audit, matches=tuple(replace(m, home_goals=99, away_goals=0)
                      if m.match_id in {t.match_id for t in fold.test} else m for m in mini_audit.matches))
    other, other_meta = wf.select_config(changed, fold)
    assert config == other
    assert meta == other_meta
    assert config.half_life_days == 120
    assert config.team_prior_matches == 8
    assert meta["inner_fixture_ids"] == []


def test_late_inner_result_is_excluded_even_when_caller_includes_its_id(mini_audit):
    folds = history.build_folds(mini_audit)[0]
    inner, outer = folds
    future_test = tuple(replace(m, kickoff=outer.cutoff - timedelta(hours=1)) for m in inner.test)
    future_inner = replace(inner, test=future_test)
    _, metadata = wf.select_config(mini_audit, outer, folds=(future_inner, outer))
    assert metadata["inner_fold_count"] == 0


def test_nested_selector_uses_only_earlier_training_members(mini_audit, monkeypatch):
    from polymarket_alpha_lab.papersim import recalib
    inner, outer = history.build_folds(mini_audit)[0]
    calls = []
    class Prediction:
        home_win, draw, away_win = .5, .25, .25
        def over_probability(self, line):
            return .5
    class Estimator:
        league_parameters = {"EPL": SimpleNamespace(converged=True)}
        def predict(self, fixture):
            return Prediction()
    def fake_fit(model_history, *, config):
        calls.append((model_history, config))
        return Estimator()
    monkeypatch.setattr(recalib, "fit", fake_fit)
    config, metadata = wf.select_config(mini_audit, outer, min_inner_folds=1,
                                        half_lives=(60, 120), team_priors=(4, 8))
    assert len(calls) == 4
    assert metadata["inner_fixture_ids"] == [m.match_id for m in inner.test]
    assert all({m.match_id for m in model_history.matches} <= {m.match_id for m in outer.train}
               for model_history, _ in calls)
    assert all(not ({m.match_id for m in model_history.matches} & {m.match_id for m in inner.test})
               for model_history, _ in calls)
    assert (config.half_life_days, config.team_prior_matches) == (60, 4)  # declared tie order


def test_paired_bootstrap_drops_unpaired_and_resamples_whole_rounds():
    rows = [{"block_id": "r1", "forecasts": {"a": {"ll": .2}, "b": {"ll": .4}}},
            {"block_id": "r1", "forecasts": {"a": {"ll": .3}, "b": {"ll": .5}}},
            {"block_id": "r2", "forecasts": {"a": {"ll": .4}, "b": {"ll": .6}}},
            {"block_id": "r3", "forecasts": {"a": {"ll": 100}}}]
    result = wf.paired_block_interval(rows, "a", "b", "ll", repetitions=100)
    assert result["n_fixtures"] == 3
    assert result["n_blocks"] == 2
    assert result["mean_delta"] == pytest.approx(-.2)
    assert result["ci95"] == pytest.approx([-.2, -.2])


def test_zero_probability_is_finite_and_invalid_probability_rejected():
    score = wf.score_forecast((0, .5, .5), {1.5: 0, 2.5: 0, 3.5: 0}, 4, 0)
    assert score["logloss_1x2"] > 20
    assert score["totals_logloss"] > 20
    with pytest.raises(ValueError):
        wf.score_forecast((float('nan'), .5, .5), {1.5: .5, 2.5: .5, 3.5: .5}, 0, 0)
