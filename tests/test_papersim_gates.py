"""WP-P1 gates tests: ladder walk, frozen gate arithmetic, haircut order,
under_risk screen, news concordance, suspension registry, ranking.

Regression anchors:
- ``tests/fixtures/papersim/regression_gate_arithmetic.json`` (the frozen
  #48 Brentford-Forest O2.5 record: entry 0.560, exec +7.4c / worst +6.3c);
- the r15 finalize haircut/under_risk semantics and the r24 book-walk
  arithmetic from the canonical lineage.
"""

from __future__ import annotations

import dataclasses
import inspect
import json
from pathlib import Path

import pytest

from polymarket_alpha_lab.papersim.gates import (
    DEPTH_NEAR_BAND,
    ENTRY_WINDOW,
    GATES,
    GATE_EPSILON,
    NEWS_BETTER,
    NEWS_UNCHANGED,
    NEWS_UNKNOWN,
    NEWS_WORSE,
    POLICY_BANNED,
    POLICY_ELIGIBLE,
    POLICY_ELIGIBLE_DEPRIORITIZED,
    POLICY_FLAGGED_ONLY,
    SUSPENSION_REGISTRY,
    UNDER_RISK_EXEC_EDGE_MIN,
    BookWalk,
    GateDecision,
    GateReport,
    NewsCheck,
    cancellation_haircut,
    check_news,
    evaluate_candidate,
    evaluate_gates,
    haircut_edge,
    news_concordance,
    rank_candidates,
    suspension_policy,
    under_risk_check,
    walk_book,
)
from polymarket_alpha_lab.papersim.soccer_model import SoccerCandidate

FIXTURES = Path(__file__).parent / "fixtures" / "papersim"

# Reconstructed representative ladders for market 5856164 (#48
# Brentford-Forest O2.5) that reproduce the frozen r24 book-ladder
# summary (round24/raw/books24.json stores the walk summary, not the raw
# levels): ask best/vwap 0.56 filled depth_near2c $16,076; bid
# best/vwap 0.54 filled depth_near2c $13,759.
ASK_LADDER_5856164 = [
    (0.56, 1000.0),
    (0.57, 14000.0),
    (0.58, 12993.0),
    (0.60, 30000.0),
]
BID_LADDER_5856164 = [
    (0.54, 800.0),
    (0.53, 15000.0),
    (0.52, 10340.0),
    (0.51, 20000.0),
]


def _concordant_news() -> NewsCheck:
    return check_news(
        "Brentford FC vs. Nottingham Forest FC",
        "recheck T-1d",
        news_delta=NEWS_UNCHANGED,
        sources=("bbc.com",),
    )


def _fixture_case() -> dict:
    data = json.loads(
        (FIXTURES / "regression_gate_arithmetic.json").read_text(encoding="utf-8")
    )
    assert data["schema"] == "papersim.regression.gate_arithmetic.v1"
    return data


def entry_variants() -> tuple[float, ...]:
    return tuple(_fixture_case()["case"]["entry_r23"]["qs_variants"])


# ---------------------------------------------------------------------------
# Frozen interfaces
# ---------------------------------------------------------------------------


def test_frozen_stub_surfaces_preserved():
    assert [f.name for f in dataclasses.fields(NewsCheck)] == [
        "fixture",
        "delta",
        "concordant",
        "blockers",
        "sources",
    ]
    assert [f.name for f in dataclasses.fields(GateDecision)] == ["passed", "failed"]
    sig = inspect.signature(evaluate_gates)
    assert list(sig.parameters) == [
        "variant_spread",
        "worst_variant_edge",
        "median_exec_edge",
        "gamma_liquidity",
    ]
    assert all(p.kind is inspect.Parameter.KEYWORD_ONLY for p in sig.parameters.values())
    assert list(inspect.signature(check_news).parameters)[:2] == ["fixture", "delta"]
    assert GATES == {
        "variant_spread_max": 0.06,
        "worst_edge_min": 0.04,
        "exec_edge_min": 0.05,
        "liq_min": 5000.0,
    }


def test_fixture_gates_block_matches_frozen_constants():
    case = _fixture_case()
    assert case["gates"]["variant_spread_max"] == GATES["variant_spread_max"]
    assert case["gates"]["worst_edge_min"] == GATES["worst_edge_min"]
    assert case["gates"]["exec_edge_min"] == GATES["exec_edge_min"]
    assert case["gates"]["liq_min"] == GATES["liq_min"]


# ---------------------------------------------------------------------------
# $250-VWAP ladder walks
# ---------------------------------------------------------------------------


def test_walk_book_single_level_fills_at_level_price():
    walk = walk_book([(0.56, 5000.0)])
    assert walk.best == pytest.approx(0.56)
    assert walk.vwap == pytest.approx(0.56)
    assert walk.filled is True
    assert walk.filled_notional == pytest.approx(250.0)
    assert walk.depth_near2c == pytest.approx(0.56 * 5000.0)


def test_walk_book_ladder_blends_levels():
    walk = walk_book([(0.60, 1000.0), (0.50, 100.0)])
    # $50 at 0.50, then $200 at 0.60 -> 100 + 333.33 shares.
    assert DEPTH_NEAR_BAND == 0.02
    assert walk.best == pytest.approx(0.50)
    assert walk.vwap == pytest.approx(250.0 / (100.0 + 200.0 / 0.60), abs=1e-4)
    assert walk.vwap == pytest.approx(0.5769, abs=1e-4)
    assert walk.filled is True
    # depth within 2c of best 0.50: only the 0.50 level.
    assert walk.depth_near2c == pytest.approx(50.0)


def test_walk_book_partial_fill_flagged():
    walk = walk_book([(0.50, 100.0)])
    assert walk.filled is False
    assert walk.filled_notional == pytest.approx(50.0)
    assert walk.shares == pytest.approx(100.0)
    assert walk.vwap == pytest.approx(0.50)


def test_walk_book_levels_normalized_and_sorted():
    shuffled = list(reversed(ASK_LADDER_5856164))
    walk = walk_book(shuffled)
    assert walk.best == 0.56
    assert (walk.best, walk.vwap, walk.filled, walk.depth_near2c) == (0.56, 0.56, True, 16076.0)
    dict_levels = [{"price": p, "size": s} for p, s in BID_LADDER_5856164]
    bid = walk_book(dict_levels, "bid")
    assert (bid.best, bid.vwap, bid.filled, bid.depth_near2c) == (0.54, 0.54, True, 13759.0)


def test_walk_book_bid_side_walks_dearest_first():
    bid = walk_book(BID_LADDER_5856164, "bid")
    assert bid.side == "bid"
    assert bid.best == 0.54
    assert bid.vwap == 0.54  # 800 shares at 0.54 alone cover $250
    assert bid.filled is True
    # depth within 2c of best 0.54: levels 0.54, 0.53, 0.52.
    assert bid.depth_near2c == pytest.approx(
        0.54 * 800 + 0.53 * 15000 + 0.52 * 10340, abs=1.0
    )
    assert bid.depth_near2c == 13759.0


def test_walk_book_bid_partial_fill_flagged():
    bid = walk_book([(0.52, 100.0), (0.51, 100.0)], "bid")
    assert bid.best == 0.52
    assert bid.filled is False
    assert bid.filled_notional == pytest.approx(103.0)


def test_walk_book_empty_and_invalid():
    empty = walk_book([])
    assert (empty.best, empty.vwap, empty.filled, empty.depth_near2c) == (None, None, False, 0.0)
    assert isinstance(empty, BookWalk)
    with pytest.raises(ValueError):
        walk_book([(0.5, 100.0)], "mid")
    with pytest.raises(ValueError):
        walk_book([(0.5, 100.0)], notional=0.0)
    # zero-size and non-positive levels are ignored, not walked.
    assert walk_book([(0.5, 0.0), (0.6, 1000.0)]).best == 0.6


# ---------------------------------------------------------------------------
# Frozen numeric gates
# ---------------------------------------------------------------------------


def test_evaluate_gates_boundaries_pass():
    decision = evaluate_gates(
        variant_spread=0.06,
        worst_variant_edge=0.04,
        median_exec_edge=0.05,
        gamma_liquidity=5000.0,
    )
    assert decision == GateDecision(passed=True, failed=())


@pytest.mark.parametrize(
    "kwargs,expected_failed",
    [
        (
            dict(variant_spread=0.0601, worst_variant_edge=0.05, median_exec_edge=0.06, gamma_liquidity=6000.0),
            ("variant_spread",),
        ),
        (
            dict(variant_spread=0.05, worst_variant_edge=0.0399, median_exec_edge=0.06, gamma_liquidity=6000.0),
            ("worst_edge",),
        ),
        (
            dict(variant_spread=0.05, worst_variant_edge=0.05, median_exec_edge=0.0499, gamma_liquidity=6000.0),
            ("exec_edge",),
        ),
        (
            dict(variant_spread=0.05, worst_variant_edge=0.05, median_exec_edge=0.06, gamma_liquidity=4999.99),
            ("liq",),
        ),
        (
            dict(variant_spread=0.0701, worst_variant_edge=0.039, median_exec_edge=0.049, gamma_liquidity=4999.0),
            ("variant_spread", "worst_edge", "exec_edge", "liq"),
        ),
    ],
)
def test_evaluate_gates_each_failure_dimension(kwargs, expected_failed):
    decision = evaluate_gates(**kwargs)
    assert decision.passed is False
    assert decision.failed == expected_failed


def test_evaluate_gates_epsilon_matches_round24_finalize():
    # round24/raw/finalize24.py: var > 6c + 1e-9 fails, worst < 4c - 1e-9
    # fails, exec < 5c - 1e-9 fails.
    assert evaluate_gates(
        variant_spread=0.06 + GATE_EPSILON / 2,
        worst_variant_edge=0.04 - GATE_EPSILON / 2,
        median_exec_edge=0.05 - GATE_EPSILON / 2,
        gamma_liquidity=5000.0,
    ).passed is True


# ---------------------------------------------------------------------------
# #48 regression fixture
# ---------------------------------------------------------------------------


def test_regression_48_book_ladder_and_edge_identities():
    case = _fixture_case()["case"]
    entry = case["entry_r23"]
    recheck = case["r24_recheck"]
    ladder = case["r24_book_ladder"]

    ask = walk_book(ASK_LADDER_5856164, "ask")
    assert (ask.best, ask.vwap, ask.filled, ask.depth_near2c) == (
        ladder["tok0_ask"]["best"],
        ladder["tok0_ask"]["vwap"],
        ladder["tok0_ask"]["filled"],
        ladder["tok0_ask"]["depth_near2c"],
    )
    bid = walk_book(BID_LADDER_5856164, "bid")
    assert (bid.best, bid.vwap, bid.filled, bid.depth_near2c) == (
        ladder["tok0_bid"]["best"],
        ladder["tok0_bid"]["vwap"],
        ladder["tok0_bid"]["filled"],
        ladder["tok0_bid"]["depth_near2c"],
    )

    # frozen edge identities: exec = median - vwap250, worst = min(qs) - vwap250
    assert round(entry["model_median"] - ask.vwap, 4) == recheck["edge_exec_now"] == 0.0742
    variants = entry["qs_variants"]
    assert round(min(variants) - ask.vwap, 4) == recheck["edge_worst_now"] == 0.0635
    assert round(max(variants) - min(variants), 4) == entry["var_spread"] == 0.0211
    # cents reproduction: exec +7.4c / worst +6.3c.
    assert round(recheck["edge_exec_now"] * 100, 1) == recheck["expected_edge_exec_cents"] == 7.4
    assert round(recheck["edge_worst_now"] * 100, 1) == recheck["expected_edge_worst_cents"] == 6.3
    # exit mark: bid 0.54 vs entry 0.560 -> -2.0c.
    assert round(bid.best - entry["entry_ask_vwap250"], 4) == recheck["mark_bid_vs_entry"] == -0.02

    decision = evaluate_gates(
        variant_spread=round(max(variants) - min(variants), 4),
        worst_variant_edge=round(min(variants) - ask.vwap, 4),
        median_exec_edge=round(entry["model_median"] - ask.vwap, 4),
        gamma_liquidity=ladder["liq"],
    )
    assert decision.passed is True and decision.failed == ()


def test_regression_48_evaluate_candidate_full_pass():
    case = _fixture_case()["case"]
    entry = case["entry_r23"]
    candidate = SoccerCandidate(
        match="Brentford FC vs. Nottingham Forest FC",
        question=entry["question"],
        kind="total",
        side=0,
        entry_ask_vwap250=entry["entry_ask_vwap250"],
        model_median=entry["model_median"],
        model_range=tuple(entry["model_range"]),
        qs_variants=tuple(entry["qs_variants"]),
        lambda_home=entry["lambda_home"],
        lambda_away=entry["lambda_away"],
        market_id=case["market_id"],
    )
    report = evaluate_candidate(
        candidate,
        ASK_LADDER_5856164,
        "ask",
        gamma_liquidity=case["r24_book_ladder"]["liq"],
        news=_concordant_news(),
    )
    assert isinstance(report, GateReport)
    assert report.decision.passed is True
    assert all(report.checks.values())
    assert set(report.checks) == {
        "variant_spread<=6c",
        "worst>=+4c",
        "exec>=+5c",
        "liq>=5k",
        "fill_250",
        "entry_window",
        "news_concordant",
    }
    assert report.entry_price == 0.56
    assert report.exec_edge == 0.0742
    assert report.worst_variant_edge == 0.0635
    assert report.variant_spread == 0.0211
    assert report.haircut == 1.0  # median 0.6342 outside the 50-50 band
    assert report.walk.depth_near2c == 16076.0

    # a plain mapping quote evaluates identically.
    mapping_report = evaluate_candidate(
        dict(model_median=entry["model_median"], qs_variants=entry["qs_variants"]),
        ASK_LADDER_5856164,
        gamma_liquidity=16859.8558,
        news=_concordant_news(),
    )
    assert mapping_report.decision == report.decision
    assert mapping_report.exec_edge == report.exec_edge


# ---------------------------------------------------------------------------
# 50-50 cancellation haircut: halved BEFORE the bar
# ---------------------------------------------------------------------------


def test_haircut_band_and_factor():
    assert cancellation_haircut(0.45) == 0.5
    assert cancellation_haircut(0.50) == 0.5
    assert cancellation_haircut(0.55) == 0.5
    assert cancellation_haircut(0.4499) == 1.0
    assert cancellation_haircut(0.5501) == 1.0
    assert cancellation_haircut(0.6342) == 1.0
    assert haircut_edge(0.0742, 0.50) == pytest.approx(0.0371)
    assert haircut_edge(0.0742, 0.6342) == pytest.approx(0.0742)


@pytest.mark.parametrize("median", [0.45, 0.50, 0.55])
def test_haircut_applied_before_exec_bar(median):
    # exec edge +7c: passes the +5c bar unhalved, fails halved (3.5c).
    quote = dict(model_median=median, qs_variants=(median + 0.035, median + 0.055))
    book = [(round(median - 0.07, 4), 5000.0)]  # vwap -> exec edge 0.07
    report = evaluate_candidate(
        quote, book, gamma_liquidity=20000.0, news=_concordant_news()
    )
    assert report.exec_edge == pytest.approx(0.07)
    assert report.haircut == 0.5
    assert report.exec_edge_haircut == pytest.approx(0.035)
    assert report.checks["exec>=+5c"] is False
    assert report.decision.failed == ("exec_edge",)


@pytest.mark.parametrize("median", [0.4499, 0.5501])
def test_no_haircut_outside_band_same_edge_passes(median):
    quote = dict(model_median=median, qs_variants=(median + 0.02, median + 0.04))
    book = [(round(median - 0.07, 4), 5000.0)]
    report = evaluate_candidate(
        quote, book, gamma_liquidity=20000.0, news=_concordant_news()
    )
    assert report.haircut == 1.0
    assert report.checks["exec>=+5c"] is True
    assert report.decision.passed is True


def test_haircut_boundary_edge_exactly_on_bar_after_halving():
    # 10.1c at a 0.50 median -> 5.05c halved, clears the +5c bar.
    quote = dict(model_median=0.50, qs_variants=(0.535, 0.555))
    report = evaluate_candidate(
        quote, [(0.399, 5000.0)], gamma_liquidity=20000.0, news=_concordant_news()
    )
    assert report.exec_edge == pytest.approx(0.101)
    assert report.exec_edge_haircut == pytest.approx(0.0505)
    assert report.checks["exec>=+5c"] is True


# ---------------------------------------------------------------------------
# under_risk 8c screen
# ---------------------------------------------------------------------------


def test_under_risk_check_over_total_flags():
    flagged, why = under_risk_check(
        kind="total",
        side="Over/Yes(side0)",
        o25_hits=3,
        lambda_total=2.5,
        lambda_home=1.4,
        lambda_away=1.1,
        line=2.5,
    )
    assert flagged is True
    assert "2.75" in why and "3/10" in why


def test_under_risk_check_clean_over_not_flagged():
    flagged, why = under_risk_check(
        kind="total",
        side="Over/Yes(side0)",
        o25_hits=6,
        lambda_total=3.26,
        lambda_home=1.894,
        lambda_away=1.364,
        line=2.5,
    )
    assert flagged is False and why == ""


def test_under_risk_check_btts_yes_min_lambda():
    flagged, why = under_risk_check(
        kind="btts",
        side="Yes",
        o25_hits=6,
        lambda_total=3.0,
        lambda_home=0.6,
        lambda_away=1.2,
    )
    assert flagged is True and "0.75" in why and "3/10" not in why
    clean, _ = under_risk_check(
        kind="btts", side="Yes", o25_hits=6, lambda_total=3.0, lambda_home=0.9, lambda_away=1.2
    )
    assert clean is False


def test_under_risk_check_ignores_other_sides_and_kinds():
    for kind, side in (("total", "Under/No(side1)"), ("spread", "Over/Yes(side0)"), ("match_winner", "Yes")):
        assert under_risk_check(
            kind=kind, side=side, o25_hits=0, lambda_total=0.0, lambda_home=0.0, lambda_away=0.0
        ) == (False, "")


def test_under_risk_raises_exec_bar_to_8c():
    quote = dict(model_median=0.62, qs_variants=(0.60, 0.63))
    book = [(0.56, 5000.0)]  # exec edge 0.06, worst 0.04
    common = dict(gamma_liquidity=20000.0, news=_concordant_news())
    plain = evaluate_candidate(quote, book, **common)
    assert plain.checks["exec>=+5c"] is True and plain.decision.passed is True
    risky = evaluate_candidate(quote, book, under_risk=True, **common)
    assert risky.checks["exec>=+8c"] is False
    assert "exec>=+5c" not in risky.checks
    assert risky.decision.failed == ("exec_edge",)
    edge_pass = evaluate_candidate(
        dict(model_median=0.65, qs_variants=(0.61, 0.66)),
        [(0.56, 5000.0)],
        under_risk=True,
        **common,
    )
    assert edge_pass.checks["exec>=+8c"] is True  # 9c clears the screen
    assert UNDER_RISK_EXEC_EDGE_MIN == 0.08


# ---------------------------------------------------------------------------
# NewsCheck concordance
# ---------------------------------------------------------------------------


def test_news_concordance_helper():
    assert news_concordance(NEWS_BETTER) is True
    assert news_concordance(NEWS_UNCHANGED) is True
    assert news_concordance(NEWS_WORSE) is False
    assert news_concordance(NEWS_UNKNOWN) is False
    assert news_concordance(None) is False
    assert news_concordance("  BETTER ") is True


def test_check_news_assembly_and_blockers():
    nc = check_news("F", "48h", news_delta=NEWS_BETTER, sources=("s1", "s2"))
    assert nc == NewsCheck(
        fixture="F", delta="48h", concordant=True, blockers=(), sources=("s1", "s2")
    )
    worse = check_news("F", "recheck T-1d", news_delta=NEWS_WORSE)
    assert worse.concordant is False
    assert "news_worse_than_model" in worse.blockers
    unknown = check_news("F", "48h")  # no evidence supplied
    assert unknown.concordant is False
    assert unknown.blockers == ("news_unknown",)
    blocked = check_news("F", "48h", news_delta=NEWS_UNCHANGED, blockers=("exit_condition_met",))
    assert blocked.concordant is False
    assert "exit_condition_met" in blocked.blockers


def test_evaluate_candidate_requires_concordant_news():
    quote = dict(model_median=0.6342, qs_variants=entry_variants())
    common = dict(gamma_liquidity=45453.1189)
    no_news = evaluate_candidate(quote, ASK_LADDER_5856164, **common)
    assert no_news.checks["news_concordant"] is False
    assert no_news.decision.failed == ("news_concordant",)
    worse = evaluate_candidate(
        quote,
        ASK_LADDER_5856164,
        news=check_news("F", "48h", news_delta=NEWS_WORSE),
        **common,
    )
    assert worse.decision.failed == ("news_concordant",)
    good = evaluate_candidate(quote, ASK_LADDER_5856164, news=_concordant_news(), **common)
    assert good.decision.passed is True


# ---------------------------------------------------------------------------
# Entry window, fill flag, missing inputs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("price", [0.05, 0.93])
def test_entry_window_rejects_outside_band(price):
    report = evaluate_candidate(
        dict(model_median=0.60, qs_variants=(0.58, 0.62)),
        [(price, 5000.0)],
        gamma_liquidity=20000.0,
        news=_concordant_news(),
    )
    assert report.checks["entry_window"] is False
    assert "entry_window" in report.decision.failed
    assert ENTRY_WINDOW == (0.10, 0.92)


@pytest.mark.parametrize("price", [0.10, 0.92])
def test_entry_window_accepts_band_edges(price):
    median = min(round(price + 0.10, 4), 0.99)
    report = evaluate_candidate(
        dict(model_median=median, qs_variants=(round(price + 0.05, 4), round(price + 0.09, 4))),
        [(price, 5000.0)],
        gamma_liquidity=20000.0,
        news=_concordant_news(),
    )
    assert report.checks["entry_window"] is True


def test_thin_book_fails_real_depth_intent():
    report = evaluate_candidate(
        dict(model_median=0.60, qs_variants=(0.58, 0.62)),
        [(0.50, 100.0)],  # only $50 resting: cannot fill $250
        gamma_liquidity=20000.0,
        news=_concordant_news(),
    )
    assert report.walk.filled is False
    assert report.checks["fill_250"] is False
    assert "fill_250" in report.decision.failed
    assert report.decision.passed is False


def test_missing_liquidity_fails_liq_gate_like_lineage():
    report = evaluate_candidate(
        dict(model_median=0.60, qs_variants=(0.58, 0.62)),
        [(0.50, 5000.0)],
        news=_concordant_news(),
    )
    assert report.gamma_liquidity == 0.0
    assert report.checks["liq>=5k"] is False
    assert report.decision.failed == ("liq",)


def test_quote_fallback_fields_for_liquidity():
    for field in ("gamma_liquidity", "liq_gamma", "liq"):
        report = evaluate_candidate(
            dict(model_median=0.60, qs_variants=(0.58, 0.62), **{field: 6000.0}),
            [(0.50, 5000.0)],
            news=_concordant_news(),
        )
        assert report.checks["liq>=5k"] is True


def test_evaluate_candidate_input_errors():
    with pytest.raises(ValueError):
        evaluate_candidate(dict(qs_variants=(0.5, 0.6)), [(0.5, 100.0)])
    with pytest.raises(ValueError):
        evaluate_candidate(dict(model_median=0.6, qs_variants=()), [(0.5, 100.0)])
    empty = evaluate_candidate(
        dict(model_median=0.60, qs_variants=(0.58, 0.62)),
        [],
        gamma_liquidity=20000.0,
        news=_concordant_news(),
    )
    assert empty.exec_edge is None and empty.worst_variant_edge is None
    assert empty.decision.passed is False
    assert set(empty.decision.failed) == {"exec_edge", "worst_edge", "entry_window", "fill_250"}


def test_evaluate_candidate_numeric_failed_matches_frozen_evaluate_gates():
    # Same numeric inputs through both doors: book at 0.50, median 0.56
    # (no haircut), variants (0.53, 0.59) -> var 0.06 passes, worst 0.03
    # fails, exec 0.06 passes, liq 3000 fails.
    report = evaluate_candidate(
        dict(model_median=0.56, qs_variants=(0.53, 0.59)),
        [(0.50, 5000.0)],
        gamma_liquidity=3000.0,
        news=_concordant_news(),
    )
    frozen = evaluate_gates(
        variant_spread=0.06, worst_variant_edge=0.03, median_exec_edge=0.06, gamma_liquidity=3000.0
    )
    numeric_ids = tuple(
        gate_id
        for gate_id in ("variant_spread", "worst_edge", "exec_edge", "liq")
        if gate_id in report.decision.failed
    )
    assert report.variant_spread == 0.06
    assert report.worst_variant_edge == 0.03
    assert report.exec_edge_haircut == 0.06
    assert numeric_ids == frozen.failed == ("worst_edge", "liq")


# ---------------------------------------------------------------------------
# Suspension-policy registry
# ---------------------------------------------------------------------------


def test_suspension_registry_policies():
    banned = suspension_policy("match_winner", cross_league=True)
    assert banned.policy == POLICY_BANNED
    assert banned.eligible is False
    assert "structural" in banned.reason.lower()
    domestic = suspension_policy("match_winner", cross_league=False)
    assert domestic.policy == POLICY_ELIGIBLE_DEPRIORITIZED
    assert domestic.eligible is True
    spreads = suspension_policy("spreads")
    assert spreads.policy == POLICY_FLAGGED_ONLY
    assert spreads.eligible is False
    totals = suspension_policy("total")
    assert totals.policy == POLICY_ELIGIBLE
    assert totals.eligible is True
    # aliases seen in the lineage records
    assert suspension_policy("ml", cross_league=True).policy == POLICY_BANNED
    assert suspension_policy("1x2").policy == POLICY_ELIGIBLE_DEPRIORITIZED
    assert suspension_policy("handicap").policy == POLICY_FLAGGED_ONLY


def test_suspension_registry_matches_lookup():
    for (kind, cross_league), (policy, eligible, reason) in SUSPENSION_REGISTRY.items():
        decision = suspension_policy(kind, cross_league=cross_league)
        assert decision.policy == policy
        assert decision.eligible is eligible
        assert decision.reason == reason
    assert ("match_winner", True) in SUSPENSION_REGISTRY
    assert SUSPENSION_REGISTRY[("match_winner", False)][0] == POLICY_ELIGIBLE_DEPRIORITIZED


# ---------------------------------------------------------------------------
# Ranking: worst-variant margin first, then exec edge
# ---------------------------------------------------------------------------


def _report(median: float, worst: float, best: float, vwap: float) -> GateReport:
    return evaluate_candidate(
        dict(model_median=median, qs_variants=(worst, best)),
        [(vwap, 5000.0)],
        gamma_liquidity=20000.0,
        news=_concordant_news(),
    )


def test_rank_candidates_worst_variant_first_then_exec():
    a = _report(0.60, 0.57, 0.61, 0.52)  # worst 0.05, exec 0.08
    b = _report(0.60, 0.57, 0.63, 0.51)  # worst 0.06, exec 0.09
    b2 = _report(0.61, 0.57, 0.63, 0.51)  # worst 0.06, exec 0.10
    c = _report(0.70, 0.67, 0.72, 0.55)  # worst 0.12, exec 0.15
    ranked = rank_candidates([a, b, c, b2])
    assert [r.worst_variant_edge for r in ranked] == [0.12, 0.06, 0.06, 0.05]
    assert [r.exec_edge for r in ranked] == [0.15, 0.10, 0.09, 0.08]


def test_rank_candidates_uses_haircut_edge_as_tiebreak():
    # same worst margin, one inside the 50-50 band: the halved edge ranks lower.
    outside = _report(0.60, 0.55, 0.61, 0.50)  # exec 0.10 unhalved
    inside = _report(0.50, 0.45, 0.51, 0.40)  # exec 0.10 -> haircut edge 0.05
    ranked = rank_candidates([inside, outside])
    assert ranked[0] is outside
    assert ranked[0].exec_edge_haircut == pytest.approx(0.10)
    assert ranked[1].exec_edge_haircut == pytest.approx(0.05)


def test_rank_candidates_drops_unrankable_reports():
    empty = evaluate_candidate(
        dict(model_median=0.60, qs_variants=(0.58, 0.62)),
        [],
        gamma_liquidity=20000.0,
        news=_concordant_news(),
    )
    good = _report(0.60, 0.57, 0.61, 0.52)
    assert rank_candidates([empty, good]) == [good]
