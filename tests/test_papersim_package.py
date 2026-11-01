"""WP-P1 P0 placeholder: package skeleton, stub contracts, frozen fixtures.

These tests pin the commit-1 surface of ``polymarket_alpha_lab.papersim``:
the package imports, every stub interface raises
``NotImplementedError`` until its implementation commit lands, the
frozen gate constants match the book of record, and every regression
fixture loads with its required keys. Numeric regression assertions
against the frozen bytes arrive with the model implementation commits.
"""

import json
from pathlib import Path

import pytest

from polymarket_alpha_lab import papersim
from polymarket_alpha_lab.papersim import cli, crypto_model, gates, ledger, risk_policy, soccer_model, xg

FIXTURES = Path(__file__).parent / "fixtures" / "papersim"


def test_package_imports_and_exports_stub_surface():
    assert papersim.GATES["variant_spread_max"] == 0.06
    assert papersim.GATES["worst_edge_min"] == 0.04
    assert papersim.GATES["exec_edge_min"] == 0.05
    assert papersim.GATES["liq_min"] == 5000.0
    for name in papersim.__all__:
        assert getattr(papersim, name) is not None


@pytest.mark.parametrize(
    "func,kwargs",
    [
        (xg.load_xg_snapshot, {"path": "xg_epl_23.json"}),
        (xg.team_ratings, {"snapshot": {}, "league": "EPL", "season": "2026", "last_weight": 0.5, "prior_games": 8.0}),
        (soccer_model.match_lambdas, {"xg_snapshot": {}, "home_team": "Brentford", "home_league": "EPL", "away_team": "Nottingham Forest", "away_league": "EPL"}),
        (soccer_model.over_under_quote, {"lambdas": (1.894, 1.364), "line": 2.5, "market": "q", "market_id": "5856164", "entry_ask_vwap250": 0.56}),
        (crypto_model.realized_vol_daily, {"closes": [100.0, 101.0]}),
        (crypto_model.touch_probability, {"spot": 2326.84, "sigma_daily": 0.02430307766195731, "barrier": 2000.0, "horizon_hours": 1595.12, "asset": "ETH"}),
        (gates.evaluate_gates, {"variant_spread": 0.0211, "worst_variant_edge": 0.0635, "median_exec_edge": 0.0742, "gamma_liquidity": 16859.8558}),
        (gates.check_news, {"fixture": "Brentford FC vs. Nottingham Forest FC", "delta": "recheck T-1d"}),
        (risk_policy.paper_stake, {"fixture": "f", "question": "q", "entry_price": 0.56}),
        (risk_policy.bankroll_available, {"bankroll": 10780.73, "cash": 7045.33, "reserved": 750.0}),
        (ledger.record_entry, {"position_id": "#48", "fixture": "f", "question": "q", "side": "Over", "notional": 250.0, "price": 0.56}),
        (ledger.mark_to_market, {"entry_price": 0.56, "exit_bid": 0.54}),
        (cli.main, {}),
    ],
)
def test_stubs_raise_not_implemented(func, kwargs):
    with pytest.raises(NotImplementedError):
        func(**kwargs)


def test_regression_r19_crypto_fixture_loads():
    data = json.loads((FIXTURES / "regression_r19_crypto.json").read_text(encoding="utf-8"))
    assert data["schema"] == "papersim.regression.r19_crypto.v1"
    assert data["inputs"]["spot"]["ETH"] == 2326.84
    assert data["inputs"]["realized_vol_daily"]["ETH"]["30d"] == 0.02430307766195731
    assert data["anchor"]["horizon_anchor_utc"] == "2026-10-26T12:58:37Z"
    cases = data["cases"]
    assert cases["ETH-2000"]["A"] == 0.4449 and cases["ETH-2000"]["B"] == 0.4788
    assert cases["ETH-2250"]["A"] == 0.8654 and cases["ETH-2250"]["B"] == 0.8795
    assert cases["BTC-65k"]["A"] == 0.1008 and cases["BTC-65k"]["B"] == 0.1119
    assert len(data["provenance"]["source_files"]) == 2


def test_regression_r23_soccer_fixture_loads():
    data = json.loads((FIXTURES / "regression_r23_soccer.json").read_text(encoding="utf-8"))
    assert data["schema"] == "papersim.regression.r23_soccer.v1"
    cases = data["cases"]
    assert cases["BOU-LEE_O2.5"]["model_median"] == 0.6096
    assert cases["BOU-LEE_O2.5"]["model_range"] == [0.5714, 0.6323]
    assert cases["BRE-FOR_O2.5"]["model_median"] == 0.6342
    assert cases["HUL-IPS_O2.5"]["model_median"] == 0.613
    assert cases["CHE-MUN_O3.5"]["model_median"] == 0.4514
    assert len(cases["BRE-FOR_O2.5"]["qs_variants"]) == 10
    excerpt = data["xg_snapshot_excerpt"]["teams"]
    assert data["xg_snapshot_excerpt"]["season_key"] == "EPL_2026"
    assert set(excerpt) == {"73", "80", "89", "91", "244", "245", "249", "285"}
    assert excerpt["244"]["title"] == "Brentford"
    assert excerpt["249"]["title"] == "Nottingham Forest"
    assert len(excerpt["244"]["history"]) == 8
    assert len(data["provenance"]["source_files"]) == 3


def test_regression_banned_path_fixture_loads():
    data = json.loads((FIXTURES / "regression_banned_path.json").read_text(encoding="utf-8"))
    assert data["schema"] == "papersim.regression.banned_path.v1"
    case = data["case"]
    assert case["home"]["league"] == "bundesliga"
    assert case["away"]["league"] == "ligue_1"
    assert case["expected_result"] is None
    assert case["expected_match_lambdas"] is None
    flip = data["historical_favorite_flip"]
    assert flip["model_1x2_away_win"]["rng"] == [0.375, 0.457]
    assert flip["model_1x2_home_win"]["ask"] == 0.48
    assert flip["model_lambdas"] == [1.6186145926927629, 1.666628617248003]


def test_regression_gate_arithmetic_fixture_loads():
    data = json.loads((FIXTURES / "regression_gate_arithmetic.json").read_text(encoding="utf-8"))
    assert data["schema"] == "papersim.regression.gate_arithmetic.v1"
    assert data["gates"]["variant_spread_max"] == 0.06
    assert data["gates"]["worst_edge_min"] == 0.04
    assert data["gates"]["exec_edge_min"] == 0.05
    assert data["gates"]["liq_min"] == 5000
    case = data["case"]
    assert case["position_id"] == "#48"
    assert case["entry_r23"]["entry_ask_vwap250"] == 0.56
    assert case["entry_r23"]["model_median"] == 0.6342
    assert case["r24_recheck"]["edge_exec_now"] == 0.0742
    assert case["r24_recheck"]["edge_worst_now"] == 0.0635
    assert case["r24_recheck"]["expected_edge_exec_cents"] == 7.4
    assert case["r24_recheck"]["expected_edge_worst_cents"] == 6.3
    assert case["r24_book_ladder"]["tok0_ask"]["vwap"] == 0.56
    assert case["r24_book_ladder"]["tok0_ask"]["depth_near2c"] == 16076.0
    # frozen gate arithmetic identities
    entry = case["entry_r23"]
    assert round(entry["model_median"] - entry["entry_ask_vwap250"], 4) == case["r24_recheck"]["edge_exec_now"]
    assert round(min(entry["qs_variants"]) - entry["entry_ask_vwap250"], 4) == case["r24_recheck"]["edge_worst_now"]
