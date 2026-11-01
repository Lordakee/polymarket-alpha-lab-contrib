"""WP-P1 W1 tests: Understat snapshot loading and goal-fit ratings.

Covers the frozen ``xg.py`` contracts (``load_xg_snapshot``,
``team_ratings``) plus the rating modes, registry, guarded lambda
construction and recent-form helper ported from the lineage
(``round15/soccer_tools/scan15.py`` -> ``round23/raw/model23.py``).

The synthetic two-league fixture below is hand-computable: prior-season
league base rates (bh, ba) = (1.5, 1.5), so blend multipliers reduce to
exact rationals. Regression against the frozen round-23 anchors lives in
``test_papersim_soccer_model.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from polymarket_alpha_lab.papersim import xg


def _synthetic_snapshot() -> dict[str, object]:
    """Hand-computable two-league snapshot (EPL + La_liga)."""
    return {
        "EPL_2025": {
            "dates": [
                {"isResult": True, "xG": {"h": 2.0, "a": 1.0}},
                {"isResult": True, "xG": {"h": 1.0, "a": 2.0}},
                {"isResult": False, "xG": {"h": 9.0, "a": 9.0}},
            ],
            "teams": {
                "1": {"title": "Alpha", "history": [{"xG": 1.5, "xGA": 1.5}]},
                "2": {"title": "Beta", "history": [{"xG": 2.0, "xGA": 1.0}]},
            },
        },
        "EPL_2026": {
            "dates": [],
            "teams": {
                "1": {
                    "title": "Alpha",
                    "history": [
                        {"xG": 2.0, "xGA": 1.0, "scored": 2, "missed": 1},
                        {"xG": 1.0, "xGA": 2.0, "scored": 0, "missed": 2},
                        {"xG": 1.5, "xGA": 1.5, "scored": 1, "missed": 1},
                    ],
                },
                "2": {
                    "title": "Beta",
                    "history": [
                        {"xG": 3.0, "xGA": 0.0},
                        {"xG": 1.0, "xGA": 2.0},
                    ],
                },
                "3": {"title": "Gamma", "history": [{"xG": 3.0, "xGA": 3.0}]},
                "4": {"title": "Delta", "history": []},
            },
        },
        "La_liga_2025": {
            "dates": [{"isResult": True, "xG": {"h": 1.4, "a": 1.2}}],
            "teams": {
                "5": {"title": "Real Epsilon", "history": [{"xG": 1.3, "xGA": 1.1}]},
            },
        },
        "La_liga_2026": {
            "dates": [],
            "teams": {
                "5": {"title": "Real Epsilon", "history": [{"xG": 1.3, "xGA": 1.1}]},
                "6": {"title": "Shared", "history": [{"xG": 1.0, "xGA": 1.0}]},
            },
        },
        "EPL_2026_extra": {"teams": {}, "dates": []},
    }


def test_load_xg_snapshot_preserves_raw_payload(tmp_path: Path) -> None:
    payload = {
        "EPL_2025": {
            "dates": [{"isResult": True, "xG": {"h": 1.6946258894736843, "a": 1.3643311084210525}}],
            "teams": {"244": {"id": "244", "title": "Brentford", "history": [{"xG": 4.04155, "xGA": 0.756284}]}},
        },
        "EPL_2026": {"dates": [], "teams": {}},
    }
    path = tmp_path / "xg_snapshot.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    loaded = xg.load_xg_snapshot(str(path))
    assert loaded == payload
    # Unrounded raw floats survive verbatim (no normalization on load).
    assert loaded["EPL_2025"]["dates"][0]["xG"]["h"] == 1.6946258894736843
    assert loaded["EPL_2025"]["teams"]["244"]["history"][0]["xGA"] == 0.756284


def test_load_xg_snapshot_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        xg.load_xg_snapshot(str(tmp_path / "absent.json"))


def test_season_keys_and_prior_season() -> None:
    assert xg.season_key("EPL", "2026") == "EPL_2026"
    assert xg.prior_season("2026") == "2025"
    with pytest.raises(ValueError):
        xg.prior_season("20x6")


def test_team_rows_normalize_verbatim() -> None:
    rows = xg.team_rows(_synthetic_snapshot(), "EPL", "2026")
    assert set(rows) == {"1", "2", "3", "4"}
    alpha = rows["1"]
    assert isinstance(alpha, xg.XgTeamRow)
    assert alpha.title == "Alpha"
    assert isinstance(alpha.history, tuple)
    assert alpha.history[0]["xG"] == 2.0
    with pytest.raises(KeyError):
        xg.team_rows(_synthetic_snapshot(), "Serie_A", "2026")


def test_league_goal_fit_uses_prior_season_completed_matches() -> None:
    snapshot = _synthetic_snapshot()
    fit = xg.league_goal_fit(snapshot, "EPL", "2025")
    assert fit.home_rate == pytest.approx(1.5)
    assert fit.away_rate == pytest.approx(1.5)
    assert fit.league_avg == pytest.approx(1.5)
    # isResult=False fixture rows must not leak into the base rates.
    with pytest.raises(ValueError):
        xg.league_goal_fit(snapshot, "EPL", "2026")
    with pytest.raises(KeyError):
        xg.league_goal_fit(snapshot, "Serie_A", "2025")


def test_ratings_for_blend_mode_exact_rationals() -> None:
    snapshot = _synthetic_snapshot()
    ratings = xg.ratings_for(snapshot, "EPL", "2026", last_weight=0.5, prior_games=8.0)
    assert ratings.goal_fit.league_avg == pytest.approx(1.5)
    teams = ratings.teams
    # Alpha: current = last = league average -> exactly average multipliers.
    assert teams["Alpha"] == (pytest.approx(1.0), pytest.approx(1.0))
    # Beta: f = (2*2 + 19*2 + 8*1.5)/29 = 54/29, a = (2*1 + 19*1 + 8*1.5)/29 = 33/29.
    assert teams["Beta"][0] == pytest.approx((54 / 29) / 1.5)
    assert teams["Beta"][1] == pytest.approx((33 / 29) / 1.5)
    # Gamma is absent from the prior season -> league-average fallback for
    # its last-season rate: f = a = (1*3 + 19*1.5 + 8*1.5)/28 = 43.5/28.
    assert teams["Gamma"] == (pytest.approx((43.5 / 28) / 1.5), pytest.approx((43.5 / 28) / 1.5))
    # Delta has no current-season history -> excluded from the table.
    assert "Delta" not in teams


def test_ratings_for_cur_and_last_modes() -> None:
    snapshot = _synthetic_snapshot()
    cur = xg.ratings_for(snapshot, "EPL", "2026", last_weight=0.5, prior_games=8.0, mode="cur")
    assert cur.teams["Alpha"] == (pytest.approx(1.0), pytest.approx(1.0))
    assert cur.teams["Beta"] == (pytest.approx(2.0 / 1.5), pytest.approx(1.0 / 1.5))
    last = xg.ratings_for(snapshot, "EPL", "2026", last_weight=0.5, prior_games=8.0, mode="last")
    assert last.teams["Beta"] == (pytest.approx(2.0 / 1.5), pytest.approx(1.0 / 1.5))
    # Gamma missing from prior season -> league-average multipliers in last mode.
    assert last.teams["Gamma"] == (pytest.approx(1.0), pytest.approx(1.0))
    with pytest.raises(ValueError):
        xg.ratings_for(snapshot, "EPL", "2026", last_weight=0.5, prior_games=8.0, mode="bogus")
    with pytest.raises(KeyError):
        xg.ratings_for(snapshot, "Serie_A", "2026", last_weight=0.5, prior_games=8.0)


def test_team_ratings_frozen_contract_returns_blend_dict() -> None:
    snapshot = _synthetic_snapshot()
    blended = xg.team_ratings(snapshot, "EPL", "2026", last_weight=0.5, prior_games=8.0)
    assert isinstance(blended, dict)
    assert blended == dict(
        xg.ratings_for(snapshot, "EPL", "2026", last_weight=0.5, prior_games=8.0).teams
    )
    assert blended["Beta"][0] == pytest.approx((54 / 29) / 1.5)


def test_team_league_registry() -> None:
    snapshot = dict(_synthetic_snapshot())
    snapshot["EPL_2026"]["teams"]["6"] = {"title": "Shared", "history": []}  # type: ignore[index]
    registry = xg.team_league_registry(snapshot)
    assert registry["Alpha"] == frozenset({"EPL"})
    assert registry["Real Epsilon"] == frozenset({"La_liga"})
    assert registry["Shared"] == frozenset({"EPL", "La_liga"})
    only_2026 = xg.team_league_registry(snapshot, season="2026")
    assert only_2026["Alpha"] == frozenset({"EPL"})


def test_pair_lambdas_formula_and_shrink() -> None:
    snapshot = _synthetic_snapshot()
    base = xg.pair_lambdas(
        snapshot, "Alpha", "EPL", "Beta", "EPL", last_weight=0.5, prior_games=8.0
    )
    assert base is not None
    # lh = bh * att_Alpha * def_Beta = 1.5 * 1 * (22/29); la = 1.5 * (36/29) * 1.
    assert base[0] == pytest.approx(33 / 29)
    assert base[1] == pytest.approx(54 / 29)
    flat = xg.pair_lambdas(
        snapshot, "Alpha", "EPL", "Beta", "EPL", last_weight=0.5, prior_games=8.0, shrink=0.0
    )
    assert flat == pytest.approx((1.5, 1.5))
    doubled = xg.pair_lambdas(
        snapshot, "Alpha", "EPL", "Beta", "EPL", last_weight=0.5, prior_games=8.0, shrink=2.0
    )
    assert doubled is not None
    assert doubled[0] == pytest.approx(1.5 * (22 / 29) ** 2)
    assert doubled[1] == pytest.approx(1.5 * (36 / 29) ** 2)
    cur = xg.pair_lambdas(
        snapshot, "Alpha", "EPL", "Beta", "EPL", last_weight=0.5, prior_games=8.0, mode="cur"
    )
    assert cur == pytest.approx((1.5 * (1.0 / 1.5), 1.5 * (2.0 / 1.5)))
    last = xg.pair_lambdas(
        snapshot, "Alpha", "EPL", "Beta", "EPL", last_weight=0.5, prior_games=8.0, mode="last"
    )
    assert last == pytest.approx((1.5 * (1.0 / 1.5), 1.5 * (2.0 / 1.5)))


def test_pair_lambdas_empty_history_team_uses_league_average() -> None:
    snapshot = _synthetic_snapshot()
    # Delta is in the current-season table but has no history: lineage
    # default (1.0, 1.0) multipliers -> league base rates.
    lam = xg.pair_lambdas(
        snapshot, "Delta", "EPL", "Delta", "EPL", last_weight=0.5, prior_games=8.0
    )
    assert lam == pytest.approx((1.5, 1.5))


def test_pair_lambdas_cross_league_guard_returns_none() -> None:
    snapshot = _synthetic_snapshot()
    assert (
        xg.pair_lambdas(
            snapshot, "Alpha", "EPL", "Real Epsilon", "La_liga", last_weight=0.5, prior_games=8.0
        )
        is None
    )
    # Guard fires before any data lookup: even unknown teams cannot bypass it.
    assert (
        xg.pair_lambdas(
            snapshot, "Ghost", "EPL", "Phantom", "La_liga", last_weight=0.5, prior_games=8.0
        )
        is None
    )


def test_pair_lambdas_missing_block_or_unknown_team_returns_none() -> None:
    snapshot = _synthetic_snapshot()
    assert (
        xg.pair_lambdas(
            snapshot, "Alpha", "EPL", "Serie_A Team", "Serie_A", last_weight=0.5, prior_games=8.0
        )
        is None
    )
    assert (
        xg.pair_lambdas(
            snapshot, "Alpha", "EPL", "Not Listed", "EPL", last_weight=0.5, prior_games=8.0
        )
        is None
    )
    prior_only = {"EPL_2026": snapshot["EPL_2026"]}
    assert (
        xg.pair_lambdas(prior_only, "Alpha", "EPL", "Beta", "EPL", last_weight=0.5, prior_games=8.0)
        is None
    )


def test_recent_form_aggregation() -> None:
    snapshot = _synthetic_snapshot()
    form = xg.recent_form(snapshot, "Alpha")
    assert form is not None
    assert (form.team, form.league, form.season) == ("Alpha", "EPL", "2026")
    assert form.games == 3
    assert form.goals_for == 3
    assert form.goals_against == 4
    assert form.goals_per_game == pytest.approx(2.33)
    assert form.xg_per_game == pytest.approx(3.0)
    assert form.over_2_5_hits == 1
    assert form.btts_hits == 2


def test_recent_form_prior_season_replacement() -> None:
    snapshot = _synthetic_snapshot()
    # Beta has only 2 current rows (< 3): lineage replaces with prior-season
    # history (one row: xG 2.0 / xGA 1.0, scored/missed unknown -> 0).
    form = xg.recent_form(snapshot, "Beta")
    assert form is not None
    assert form.season == "2025"  # the season the data actually came from
    assert form.games == 1
    assert form.goals_for == 0
    assert form.goals_against == 0
    assert form.xg_per_game == pytest.approx(3.0)
    # Gamma has 1 current row and no prior-season history: replaced by an
    # empty history -> no form context (None), as in the lineage.
    assert xg.recent_form(snapshot, "Gamma") is None
    # Unknown team -> None.
    assert xg.recent_form(snapshot, "Nobody") is None


def test_recent_form_window_truncation() -> None:
    snapshot = _synthetic_snapshot()
    long_history = [
        {"xG": 1.0, "xGA": 1.0, "scored": 1, "missed": 1},
        {"xG": 2.0, "xGA": 2.0, "scored": 2, "missed": 2},
        {"xG": 3.0, "xGA": 0.5, "scored": 3, "missed": 0},
        {"xG": 0.5, "xGA": 3.0, "scored": 0, "missed": 3},
        {"xG": 1.5, "xGA": 1.5, "scored": 1, "missed": 1},
        {"xG": 2.5, "xGA": 0.5, "scored": 2, "missed": 1},
    ]
    snapshot["EPL_2026"]["teams"]["7"] = {"title": "Longside", "history": long_history}  # type: ignore[index]
    form = xg.recent_form(snapshot, "Longside")
    assert form is not None
    assert form.games == 5  # last-5 window
    assert form.goals_for == 8  # 3 + 0 + 1 + 2 + ... last five scored: 2,3,0,1,2
    assert form.goals_against == 7  # missed: 2,0,3,1,1
