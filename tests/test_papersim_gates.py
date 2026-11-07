"""WP-P1 gates tests: ladder walk, frozen gate arithmetic, haircut order,
under_risk screen, news concordance, suspension registry, ranking, and
the 2026-11-05 fee-accounting fix (net-edge exec bar).

Regression anchors:
- ``tests/fixtures/papersim/regression_gate_arithmetic.json`` (the frozen
  #48 Brentford-Forest O2.5 record: entry 0.560, exec +7.4c / worst +6.3c);
- the r15 finalize haircut/under_risk semantics and the r24 book-walk
  arithmetic from the canonical lineage;
- the WP-P1 codex-review fixes (F2 hardcoded $250 ask acceptance walk,
  F3 finite gate inputs, F6 survivors-only ranking) in the closing
  section;
- the fee model (rate 0.07 crypto / 0.05 sports, per-share cost
  ``rate * p * (1 - p)``): the frozen +5c/+8c exec bars apply to the
  NET edge (gross minus fee); frozen threshold VALUES are unchanged.
"""

from __future__ import annotations

import dataclasses
import inspect
import json
from pathlib import Path

import pytest

from polymarket_alpha_lab.papersim.gates import (
    CROSS_LEAGUE_MW_WORST_EDGE_MIN,
    DEPTH_NEAR_BAND,
    ENTRY_WINDOW,
    FEE_RATE_CRYPTO,
    FEE_RATE_SPORTS,
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
    check_cross_league_mw,
    check_news,
    evaluate_candidate,
    evaluate_gates,
    fee_cost,
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
    # Fee-accounting fix (2026-11-05): two optional keyword-only fee
    # parameters joined the frozen numeric surface; the four frozen
    # numeric inputs keep their names and keyword-only kind, and callers
    # omitting the fee pair get the old as-supplied comparison.
    # Order-centralization fix (2026-11-07, codex finding 5): one more
    # optional keyword-only parameter (model_median) joined so the
    # library applies the 50-50 haircut in the canonical fee-then-haircut
    # position; callers omitting it are unaffected.
    assert list(sig.parameters) == [
        "variant_spread",
        "worst_variant_edge",
        "median_exec_edge",
        "gamma_liquidity",
        "fee_rate",
        "entry_price",
        "model_median",
    ]
    assert all(p.kind is inspect.Parameter.KEYWORD_ONLY for p in sig.parameters.values())
    assert sig.parameters["fee_rate"].default is None
    assert sig.parameters["entry_price"].default is None
    assert sig.parameters["model_median"].default is None
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
    assert report.exec_edge_gross == 0.0742
    # Fee accounting (2026-11-05 fix): sports fee 0.05 * 0.56 * 0.44
    # = 1.23c per share -> +7.42c gross = +6.19c net, still over +5c.
    assert report.exec_edge == 0.0619
    assert report.worst_variant_edge == 0.0635  # worst margin stays GROSS
    assert report.variant_spread == 0.0211
    assert report.haircut == 1.0  # median 0.6342 outside the 50-50 band
    assert report.exec_edge_haircut == 0.0619  # haircut acts on the NET edge
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
    # gross exec edge +7c: net of the sports fee (~+5.7c) it would pass
    # the +5c bar, but halved (~2.9c) it fails. Fee-adjustment note
    # (2026-11-05): pre-fee this test asserted a 3.5c halved edge; the
    # bar semantics are unchanged, only the edge is now net.
    quote = dict(model_median=median, qs_variants=(median + 0.035, median + 0.055))
    vwap = round(median - 0.07, 4)
    book = [(vwap, 5000.0)]  # vwap -> gross exec edge 0.07
    report = evaluate_candidate(
        quote, book, gamma_liquidity=20000.0, news=_concordant_news()
    )
    net = round(0.07 - round(fee_cost(vwap, FEE_RATE_SPORTS), 4), 4)
    assert report.exec_edge_gross == pytest.approx(0.07)
    assert report.exec_edge == pytest.approx(net)
    assert report.haircut == 0.5
    assert report.exec_edge_haircut == pytest.approx(round(net / 2, 4))
    assert report.exec_edge_haircut < GATES["exec_edge_min"]
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
    # gross 11.19c at a 0.50 median; sports fee at the 0.3881 entry is
    # 1.19c -> net 10.00c, halved to exactly 5.00c = the +5c bar.
    # (Pre-fee this boundary was 10.1c gross -> 5.05c halved; the
    # exactly-on-bar intent is preserved under the net definition.)
    quote = dict(model_median=0.50, qs_variants=(0.535, 0.555))
    report = evaluate_candidate(
        quote, [(0.3881, 5000.0)], gamma_liquidity=20000.0, news=_concordant_news()
    )
    assert report.exec_edge_gross == pytest.approx(0.1119)
    assert report.exec_edge == pytest.approx(0.1000, abs=1e-4)
    assert report.exec_edge_haircut == pytest.approx(0.0500, abs=1e-4)
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
    # Fee-adjusted numbers (2026-11-05): sports fee at the 0.56 entry is
    # 1.23c, so gross 8.0c -> net 6.77c (was gross/net 6c pre-fee):
    # clears the +5c bar, fails the +8c screen.
    quote = dict(model_median=0.64, qs_variants=(0.60, 0.63))
    book = [(0.56, 5000.0)]  # gross exec edge 0.08 -> net 0.0677, worst 0.04
    common = dict(gamma_liquidity=20000.0, news=_concordant_news())
    plain = evaluate_candidate(quote, book, **common)
    assert plain.checks["exec>=+5c"] is True and plain.decision.passed is True
    risky = evaluate_candidate(quote, book, under_risk=True, **common)
    assert risky.checks["exec>=+8c"] is False
    assert "exec>=+5c" not in risky.checks
    assert risky.decision.failed == ("exec_edge",)
    edge_pass = evaluate_candidate(
        dict(model_median=0.66, qs_variants=(0.62, 0.67)),
        [(0.56, 5000.0)],
        under_risk=True,
        **common,
    )
    assert edge_pass.checks["exec>=+8c"] is True  # net 8.77c clears the screen
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
    # fails, exec 0.06 gross / 0.0475 net fails the +5c bar (fee
    # accounting, 2026-11-05: sports fee at p=0.5 is exactly 1.25c),
    # liq 3000 fails. evaluate_gates nets its supplied edge only when
    # the fee_rate+entry_price pair is passed, so both doors agree.
    report = evaluate_candidate(
        dict(model_median=0.56, qs_variants=(0.53, 0.59)),
        [(0.50, 5000.0)],
        gamma_liquidity=3000.0,
        news=_concordant_news(),
    )
    frozen = evaluate_gates(
        variant_spread=0.06,
        worst_variant_edge=0.03,
        median_exec_edge=0.06,
        gamma_liquidity=3000.0,
        fee_rate=FEE_RATE_SPORTS,
        entry_price=0.50,
    )
    numeric_ids = tuple(
        gate_id
        for gate_id in ("variant_spread", "worst_edge", "exec_edge", "liq")
        if gate_id in report.decision.failed
    )
    assert report.variant_spread == 0.06
    assert report.worst_variant_edge == 0.03
    assert report.exec_edge_gross == 0.06
    assert report.exec_edge == 0.0475
    assert report.exec_edge_haircut == 0.0475
    assert numeric_ids == frozen.failed == ("worst_edge", "exec_edge", "liq")


# ---------------------------------------------------------------------------
# Suspension-policy registry
# ---------------------------------------------------------------------------


def test_suspension_registry_policies():
    cross_lg = suspension_policy("match_winner", cross_league=True)
    assert cross_lg.policy == POLICY_ELIGIBLE_DEPRIORITIZED
    assert cross_lg.eligible is True
    assert "bridge" in cross_lg.reason.lower()
    assert "T4" in cross_lg.reason
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
    assert suspension_policy("ml", cross_league=True).policy == POLICY_ELIGIBLE_DEPRIORITIZED
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
    assert [r.exec_edge_gross for r in ranked] == [0.15, 0.10, 0.09, 0.08]
    # net exec edges (sports fee at each entry: 0.55 -> 1.24c, the
    # 0.51/0.52 entries -> 1.25c); ordering is unchanged by the fee.
    assert [r.exec_edge for r in ranked] == [0.1376, 0.0875, 0.0775, 0.0675]


def test_rank_candidates_uses_haircut_edge_as_tiebreak():
    # same worst margin (0.05), one inside the 50-50 band: the halved
    # edge ranks lower. Fee-adjusted numbers (2026-11-05): outside nets
    # 8.75c at the 0.50 entry; inside keeps worst margin 0.05 at the
    # 0.40 entry and needs gross 11.5c (fee 1.20c -> net 10.3c) so its
    # halved NET edge (5.15c) still clears the +5c bar and stays
    # rankable (pre-fee this was 10c gross -> 5c halved exactly on the
    # bar).
    outside = _report(0.60, 0.55, 0.61, 0.50)  # net 0.0875 unhalved
    inside = _report(0.515, 0.45, 0.51, 0.40)  # net 0.103 -> haircut edge 0.0515
    ranked = rank_candidates([inside, outside])
    assert ranked[0] is outside
    assert ranked[0].worst_variant_edge == ranked[1].worst_variant_edge == 0.05
    assert ranked[0].exec_edge_haircut == pytest.approx(0.0875)
    assert ranked[1].exec_edge_haircut == pytest.approx(0.0515)


def test_rank_candidates_drops_unrankable_reports():
    empty = evaluate_candidate(
        dict(model_median=0.60, qs_variants=(0.58, 0.62)),
        [],
        gamma_liquidity=20000.0,
        news=_concordant_news(),
    )
    good = _report(0.60, 0.57, 0.61, 0.52)
    assert rank_candidates([empty, good]) == [good]


# ---------------------------------------------------------------------------
# WP-P1 codex-review fixes: F2 acceptance walk, F3 finite inputs, F6 survivors
# ---------------------------------------------------------------------------


def test_f2_thin_book_with_caller_notional_50_still_fails():
    # codex F2 counterexample 1: notional=50 over a $50 book. The
    # caller-configured walk fills, but acceptance must come from the
    # hardcoded $250 ask walk, which cannot fill -> fill_250 fails.
    quote = dict(model_median=0.60, qs_variants=(0.58, 0.62))
    book = [(0.50, 100.0)]  # $50 resting
    report = evaluate_candidate(
        quote, book, notional=50.0, gamma_liquidity=20000.0, news=_concordant_news()
    )
    assert (report.walk.side, report.walk.notional) == ("ask", 250.0)
    assert report.walk.filled is False
    assert report.checks["fill_250"] is False
    assert report.decision.passed is False
    assert "fill_250" in report.decision.failed
    # the caller's $50 walk survives only as supplementary valuation info
    assert report.valuation_walk is not None
    assert (report.valuation_walk.notional, report.valuation_walk.filled) == (
        50.0,
        True,
    )


def test_f2_bid_walk_bypass_counterexample_rejected():
    # codex F2 counterexample 2, original input preserved (review round 2):
    # side="bid" against a deep bid ladder at .56 while the executable ask
    # sits at .64. The single-ladder entry API is now ASK-ONLY, so a bid
    # request is rejected outright instead of manufacturing a pseudo-ask
    # walk over bids (which previously established false entry eligibility
    # at .56). Bid-side valuation is walk_book's job, not the entry gate's.
    deep_bid = walk_book([(0.56, 5000.0)], "bid")
    assert (deep_bid.vwap, deep_bid.filled) == (0.56, True)  # the old bypass
    quote = dict(model_median=0.62, qs_variants=(0.60, 0.63))  # passes at .56 only
    bid_ladder = [(0.56, 5000.0)]  # the original codex input: a bid ladder
    with pytest.raises(ValueError, match="ask-only"):
        evaluate_candidate(
            quote, bid_ladder, "bid", gamma_liquidity=20000.0, news=_concordant_news()
        )
    # and the genuinely executable .64 ask ladder still fails the edges
    report = evaluate_candidate(
        quote, [(0.64, 5000.0)], gamma_liquidity=20000.0, news=_concordant_news()
    )
    assert report.decision.passed is False
    assert (report.walk.side, report.walk.vwap) == ("ask", 0.64)
    assert report.decision.failed == ("worst_edge", "exec_edge")


def test_n1_composite_rejects_nonfinite_model_evidence():
    # codex round-2 N1: evaluate_candidate must validate every variant, the
    # median and liquidity BEFORE reductions -- min()/max() silently skip a
    # non-leading NaN, and infinities pass threshold comparisons outright.
    base_book = [(0.56, 5000.0)]
    nan_variant = dict(model_median=0.62, qs_variants=(0.60, float("nan"), 0.63))
    with pytest.raises(ValueError, match="qs_variants\[1\]"):
        evaluate_candidate(
            nan_variant, base_book, gamma_liquidity=20000.0, news=_concordant_news()
        )
    inf_median = dict(model_median=float("inf"), qs_variants=(0.60, 0.63))
    with pytest.raises(ValueError, match="model_median"):
        evaluate_candidate(
            inf_median, base_book, gamma_liquidity=20000.0, news=_concordant_news()
        )
    with pytest.raises(ValueError, match="gamma_liquidity"):
        evaluate_candidate(
            dict(model_median=0.62, qs_variants=(0.60, 0.63)),
            base_book,
            gamma_liquidity=float("inf"),
            news=_concordant_news(),
        )


def test_f2_default_call_records_no_supplementary_walk():
    # normal path still passes: the acceptance walk is exactly the
    # historical default walk and no supplementary walk is recorded.
    # Fee-adjusted numbers (2026-11-05): median raised 0.62 -> 0.64 so
    # the net edge (8c gross - 1.23c fee = 6.77c) clears the +5c bar
    # (the old 6c gross would now net 4.77c and fail).
    report = evaluate_candidate(
        dict(model_median=0.64, qs_variants=(0.60, 0.63)),
        [(0.56, 5000.0)],
        gamma_liquidity=20000.0,
        news=_concordant_news(),
    )
    assert report.decision.passed is True
    assert report.walk == walk_book([(0.56, 5000.0)], "ask")
    assert report.valuation_walk is None


def test_f2_invalid_side_or_notional_still_raise():
    # the caller-configured walk no longer feeds acceptance, but invalid
    # side/notional values must still raise (supplementary walk validation).
    quote = dict(model_median=0.62, qs_variants=(0.60, 0.63))
    common = dict(gamma_liquidity=20000.0, news=_concordant_news())
    with pytest.raises(ValueError):
        evaluate_candidate(quote, [(0.56, 5000.0)], "mid", **common)
    with pytest.raises(ValueError):
        evaluate_candidate(quote, [(0.56, 5000.0)], notional=0.0, **common)


def test_evaluate_gates_rejects_all_nan_inputs():
    # codex F3: NaN compares False against every threshold, so all-NaN
    # inputs previously returned GateDecision(passed=True).
    nan = float("nan")
    with pytest.raises(ValueError, match="non-finite"):
        evaluate_gates(
            variant_spread=nan,
            worst_variant_edge=nan,
            median_exec_edge=nan,
            gamma_liquidity=nan,
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("variant_spread", float("nan")),
        ("worst_variant_edge", float("nan")),
        ("median_exec_edge", float("nan")),
        ("gamma_liquidity", float("nan")),
        ("variant_spread", float("inf")),
        ("worst_variant_edge", float("-inf")),
        ("gamma_liquidity", float("inf")),
    ],
)
def test_evaluate_gates_rejects_single_non_finite_input(field, value):
    base = dict(
        variant_spread=0.05,
        worst_variant_edge=0.05,
        median_exec_edge=0.06,
        gamma_liquidity=6000.0,
    )
    with pytest.raises(ValueError, match="non-finite"):
        evaluate_gates(**{**base, field: value})


def test_rank_candidates_orders_survivors_only():
    # codex F6: ranking "orders the survivors" (docs/paper-sim/usage.md).
    # High-edge candidates rejected on news (or liquidity) must not rank
    # at all, let alone first.
    rejected_news = evaluate_candidate(
        dict(model_median=0.70, qs_variants=(0.67, 0.72)),
        [(0.55, 5000.0)],
        gamma_liquidity=20000.0,
        news=check_news("F", "48h", news_delta=NEWS_WORSE),
    )
    assert rejected_news.decision.passed is False
    assert rejected_news.checks["news_concordant"] is False
    assert rejected_news.worst_variant_edge == 0.12  # highest margin in the pool
    rejected_liq = evaluate_candidate(
        dict(model_median=0.70, qs_variants=(0.67, 0.72)),
        [(0.55, 5000.0)],
        gamma_liquidity=100.0,  # liq>=5k fails
        news=_concordant_news(),
    )
    assert rejected_liq.decision.passed is False
    good_low = _report(0.60, 0.57, 0.61, 0.52)  # worst 0.05, exec 0.08
    good_high = _report(0.70, 0.67, 0.72, 0.55)  # same edges as the rejected pair
    ranked = rank_candidates([rejected_news, rejected_liq, good_low, good_high])
    assert ranked == [good_high, good_low]
    assert rejected_news not in ranked
    assert rejected_liq not in ranked


# ---------------------------------------------------------------------------
# Fee accounting (2026-11-05 review fix): the exec bar is a NET-edge bar
# ---------------------------------------------------------------------------


def test_fee_cost_model_constants_and_values():
    assert FEE_RATE_CRYPTO == 0.07
    assert FEE_RATE_SPORTS == 0.05
    # p=0.5, sports rate -> 1.25c per share (the fee maximum).
    assert fee_cost(0.5, FEE_RATE_SPORTS) == pytest.approx(0.0125)
    # p=0.3, crypto rate -> 1.47c per share.
    assert fee_cost(0.3, FEE_RATE_CRYPTO) == pytest.approx(0.0147)
    # symmetric around 0.5, zero at the endpoints.
    assert fee_cost(0.3, 0.05) == pytest.approx(fee_cost(0.7, 0.05))
    assert fee_cost(0.0, 0.07) == pytest.approx(0.0)
    assert fee_cost(1.0, 0.07) == pytest.approx(0.0)


def test_five_and_half_cent_gross_edge_now_fails_the_net_bar():
    # The headline finding of the 2026-11-05 review: a 5.5c GROSS edge
    # at a p=0.5 entry passed the old gross +5c bar but nets only 4.25c
    # (5.5c - 1.25c sports fee) and must FAIL the net bar. The frozen
    # threshold itself is unchanged -- only the edge definition moved
    # from gross to net.
    report = evaluate_candidate(
        dict(model_median=0.555, qs_variants=(0.545, 0.565)),
        [(0.50, 5000.0)],
        gamma_liquidity=20000.0,
        news=_concordant_news(),
    )
    assert report.exec_edge_gross == 0.055
    assert report.exec_edge == 0.0425
    assert report.checks["exec>=+5c"] is False
    assert report.decision.failed == ("exec_edge",)


def test_seven_cent_gross_edge_passes_the_net_bar():
    # 7c gross at a p=0.5 entry nets 5.75c -> passes.
    report = evaluate_candidate(
        dict(model_median=0.57, qs_variants=(0.555, 0.58)),
        [(0.50, 5000.0)],
        gamma_liquidity=20000.0,
        news=_concordant_news(),
    )
    assert report.exec_edge_gross == 0.07
    assert report.exec_edge == 0.0575
    assert report.checks["exec>=+5c"] is True
    assert report.decision.passed is True


def test_crypto_fee_rate_is_stricter_than_sports():
    # 6.5c gross at p=0.5: passes on the sports net (5.25c) but fails on
    # the crypto net (6.5c - 1.75c = 4.75c).
    quote = dict(model_median=0.565, qs_variants=(0.555, 0.575))
    common = dict(gamma_liquidity=20000.0, news=_concordant_news())
    sports = evaluate_candidate(
        quote, [(0.50, 5000.0)], fee_rate=FEE_RATE_SPORTS, **common
    )
    crypto = evaluate_candidate(
        quote, [(0.50, 5000.0)], fee_rate=FEE_RATE_CRYPTO, **common
    )
    assert sports.exec_edge == pytest.approx(0.0525)
    assert sports.checks["exec>=+5c"] is True and sports.decision.passed is True
    assert crypto.exec_edge == pytest.approx(0.0475)
    assert crypto.checks["exec>=+5c"] is False
    assert crypto.decision.failed == ("exec_edge",)


def test_zero_fee_rate_restores_the_gross_bar():
    # fee_rate=0 documents the fee-free escape hatch (replaying frozen
    # gross records): the 5.5c gross edge passes again.
    report = evaluate_candidate(
        dict(model_median=0.555, qs_variants=(0.545, 0.565)),
        [(0.50, 5000.0)],
        fee_rate=0.0,
        gamma_liquidity=20000.0,
        news=_concordant_news(),
    )
    assert report.exec_edge == report.exec_edge_gross == 0.055
    assert report.decision.passed is True


def test_fee_is_charged_at_the_walked_vwap_not_the_best_quote():
    # $50 at 0.50 then $200 at 0.60 -> vwap 0.5769, not the 0.50 best;
    # the fee and the net identity must use the walked entry price.
    report = evaluate_candidate(
        dict(model_median=0.70, qs_variants=(0.68, 0.72)),
        [(0.60, 1000.0), (0.50, 100.0)],
        gamma_liquidity=20000.0,
        news=_concordant_news(),
    )
    assert report.entry_price == pytest.approx(0.5769, abs=1e-4)
    fee = round(fee_cost(report.entry_price, FEE_RATE_SPORTS), 4)
    assert report.exec_edge == round(report.exec_edge_gross - fee, 4)
    assert report.decision.passed is True


def test_evaluate_candidate_rejects_invalid_fee_rate():
    common = dict(gamma_liquidity=20000.0, news=_concordant_news())
    for bad in (-0.01, float("nan"), float("inf")):
        with pytest.raises(ValueError, match="fee_rate"):
            evaluate_candidate(
                dict(model_median=0.57, qs_variants=(0.555, 0.58)),
                [(0.50, 5000.0)],
                fee_rate=bad,
                **common,
            )


def test_evaluate_gates_fee_pair_nets_the_supplied_edge():
    # Without the fee pair the frozen surface compares as supplied
    # (gross); with the pair the supplied GROSS edge is netted first:
    # 5.5c at p=0.5 -> 4.25c fails, 7c -> 5.75c passes.
    base = dict(variant_spread=0.05, worst_variant_edge=0.05, gamma_liquidity=6000.0)
    gross_pass = evaluate_gates(median_exec_edge=0.055, **base)
    assert gross_pass.passed is True  # as-supplied comparison, no fee
    netted_fail = evaluate_gates(
        median_exec_edge=0.055, fee_rate=FEE_RATE_SPORTS, entry_price=0.50, **base
    )
    assert netted_fail.passed is False and netted_fail.failed == ("exec_edge",)
    netted_pass = evaluate_gates(
        median_exec_edge=0.07, fee_rate=FEE_RATE_SPORTS, entry_price=0.50, **base
    )
    assert netted_pass.passed is True and netted_pass.failed == ()


def test_evaluate_gates_fee_pair_must_be_complete_and_finite():
    base = dict(
        variant_spread=0.05,
        worst_variant_edge=0.05,
        median_exec_edge=0.06,
        gamma_liquidity=6000.0,
    )
    with pytest.raises(ValueError, match="both fee_rate and entry_price"):
        evaluate_gates(**base, fee_rate=FEE_RATE_SPORTS)
    with pytest.raises(ValueError, match="both fee_rate and entry_price"):
        evaluate_gates(**base, entry_price=0.5)
    with pytest.raises(ValueError, match="fee_rate"):
        evaluate_gates(**base, fee_rate=-0.01, entry_price=0.5)
    with pytest.raises(ValueError, match="fee_rate"):
        evaluate_gates(**base, fee_rate=float("nan"), entry_price=0.5)
    with pytest.raises(ValueError, match="entry_price"):
        evaluate_gates(**base, fee_rate=FEE_RATE_SPORTS, entry_price=float("nan"))


# ---------------------------------------------------------------------------
# Fee-then-haircut canonical order (codex-review finding 5, 2026-11-07):
# one shared helper, both doors, identical numbers. The pre-fix contract
# let evaluate_gates callers halve the GROSS edge before the fee was
# subtracted while evaluate_candidate always subtracted the fee first
# and halved the NET edge; reversing the order shifts the barred edge
# by fee/2 -- up to 0.625c per share at the sports-rate maximum (fee
# 1.25c at p=0.5) -- enough to flip near-bar decisions.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("median", [0.30, 0.44, 0.50, 0.70])
def test_gate_apis_produce_identical_net_numbers(median):
    # Same raw inputs through both doors: evaluate_candidate walks the
    # book itself; evaluate_gates receives the SAME gross edge + fee
    # pair + model_median, so the shared canonical chain (fee first,
    # haircut second) yields identical numbers and identical exec-gate
    # outcomes. p=0.50 sits inside the 50-50 band (net edge halved),
    # p=0.30/0.44/0.70 outside it; p=0.44 pins the band's lower edge.
    gross = 0.07
    vwap = round(median - gross, 4)
    quote = dict(
        model_median=median,
        qs_variants=(round(median - 0.01, 4), round(median + 0.0111, 4)),
    )
    report = evaluate_candidate(
        quote, [(vwap, 5000.0)], gamma_liquidity=20000.0, news=_concordant_news()
    )
    assert report.exec_edge_gross == gross
    # canonical order through the public composition: net the fee ...
    net = round(gross - round(fee_cost(vwap, FEE_RATE_SPORTS), 4), 4)
    assert report.exec_edge == net
    # ... THEN halve the net edge inside the band.
    assert report.haircut == cancellation_haircut(median)
    assert report.exec_edge_haircut == haircut_edge(net, median)
    frozen = evaluate_gates(
        variant_spread=report.variant_spread,
        worst_variant_edge=report.worst_variant_edge,
        median_exec_edge=report.exec_edge_gross,
        gamma_liquidity=20000.0,
        fee_rate=FEE_RATE_SPORTS,
        entry_price=vwap,
        model_median=median,
    )
    assert report.checks["exec>=+5c"] is ("exec_edge" not in frozen.failed)
    # full numeric parity: every frozen numeric gate agrees between doors.
    numeric_ids = tuple(
        gate_id
        for gate_id in ("variant_spread", "worst_edge", "exec_edge", "liq")
        if gate_id in report.decision.failed
    )
    assert numeric_ids == frozen.failed


def test_net_bar_boundary_gross_exactly_625c_at_p50():
    # gross exactly 6.25c at a p=0.50 entry (sports fee exactly 1.25c)
    # nets to exactly 5.00c -- exactly on the frozen +5c net bar, passes
    # (epsilon convention); one tick lower (6.24c -> 4.99c net) fails.
    # Outside the 50-50 band both application orders coincide; the
    # fee/2 = 0.625c divergence exists only inside the band.
    common = dict(gamma_liquidity=20000.0, news=_concordant_news())
    report = evaluate_candidate(
        dict(model_median=0.5625, qs_variants=(0.5425, 0.5825)),
        [(0.50, 5000.0)],
        **common,
    )
    assert report.exec_edge_gross == 0.0625
    assert report.exec_edge == 0.05
    assert report.haircut == 1.0
    assert report.exec_edge_haircut == 0.05
    assert report.checks["exec>=+5c"] is True
    assert report.decision.passed is True
    frozen = evaluate_gates(
        variant_spread=report.variant_spread,
        worst_variant_edge=report.worst_variant_edge,
        median_exec_edge=report.exec_edge_gross,
        gamma_liquidity=20000.0,
        fee_rate=FEE_RATE_SPORTS,
        entry_price=0.50,
    )
    assert frozen.passed is True and frozen.failed == ()
    next_tick = evaluate_candidate(
        dict(model_median=0.5624, qs_variants=(0.5425, 0.5824)),
        [(0.50, 5000.0)],
        **common,
    )
    assert next_tick.exec_edge == 0.0499
    assert next_tick.checks["exec>=+5c"] is False
    assert next_tick.decision.failed == ("exec_edge",)


def test_haircut_adjusted_5c_bar_gross_1125c_order_parity():
    # Inside the 50-50 band the order matters. Median 0.50, entry 0.3881
    # (fee 1.19c): gross 11.19c -> net 10.00c -> halved exactly 5.00c,
    # exactly on the +5c bar. The pre-fix reversed flow (caller halves
    # the GROSS edge first: 5.60c - 1.19c = 4.41c) FAILS -- that
    # fee/2 shift is the max order-reversal delta (0.625c at the p=0.5
    # sports maximum) flipping exactly this kind of near-bar decision.
    report = evaluate_candidate(
        dict(model_median=0.50, qs_variants=(0.49, 0.51)),
        [(0.3881, 5000.0)],
        gamma_liquidity=20000.0,
        news=_concordant_news(),
    )
    assert report.exec_edge_gross == pytest.approx(0.1119, abs=1e-4)
    assert report.exec_edge == pytest.approx(0.1000, abs=1e-4)
    assert report.haircut == 0.5
    assert report.exec_edge_haircut == pytest.approx(0.0500, abs=1e-4)
    assert report.checks["exec>=+5c"] is True
    # canonical door: fee pair + model_median applies fee first, halving
    # the NET edge -- identical outcome.
    frozen = evaluate_gates(
        variant_spread=0.02,
        worst_variant_edge=0.147,
        median_exec_edge=0.1119,
        gamma_liquidity=20000.0,
        fee_rate=FEE_RATE_SPORTS,
        entry_price=0.3881,
        model_median=0.50,
    )
    assert frozen.passed is True and frozen.failed == ()
    # the pre-fix caller contract (pre-halved GROSS edge + fee pair)
    # bars 0.056 - 0.0119 = 4.41c and fails -- the documented delta.
    pre_halved = evaluate_gates(
        variant_spread=0.02,
        worst_variant_edge=0.147,
        median_exec_edge=round(0.1119 * 0.5, 4),
        gamma_liquidity=20000.0,
        fee_rate=FEE_RATE_SPORTS,
        entry_price=0.3881,
    )
    assert pre_halved.passed is False and pre_halved.failed == ("exec_edge",)
    assert round(fee_cost(0.50, FEE_RATE_SPORTS) / 2, 6) == pytest.approx(0.00625)


def test_haircut_adjusted_8c_bar_boundary_under_risk():
    # under_risk + 50-50 band: gross 17.05c at a p=0.30 entry (sports
    # fee 1.05c) nets to 16.00c, halved to exactly 8.00c -- exactly on
    # the +8c screen bar, passes; one tick lower fails. The reversed
    # order (halve gross first: ~8.52c - 1.05c = 7.47c) fails both.
    common = dict(under_risk=True, gamma_liquidity=20000.0, news=_concordant_news())
    report = evaluate_candidate(
        dict(model_median=0.4705, qs_variants=(0.4305, 0.4905)),
        [(0.30, 5000.0)],
        **common,
    )
    assert report.exec_edge_gross == 0.1705
    assert report.exec_edge == 0.16
    assert report.haircut == 0.5
    assert report.exec_edge_haircut == 0.08
    assert report.checks["exec>=+8c"] is True
    assert report.decision.passed is True
    next_tick = evaluate_candidate(
        dict(model_median=0.4700, qs_variants=(0.4300, 0.4900)),
        [(0.30, 5000.0)],
        **common,
    )
    assert next_tick.exec_edge == pytest.approx(0.1595, abs=1e-4)
    assert next_tick.exec_edge_haircut == pytest.approx(0.0798, abs=1e-4)
    assert next_tick.checks["exec>=+8c"] is False
    assert next_tick.decision.failed == ("exec_edge",)


def test_evaluate_gates_model_median_requires_fee_pair_and_finite():
    base = dict(
        variant_spread=0.05,
        worst_variant_edge=0.05,
        median_exec_edge=0.07,
        gamma_liquidity=6000.0,
    )
    with pytest.raises(ValueError, match="model_median requires the fee pair"):
        evaluate_gates(**base, model_median=0.50)
    with pytest.raises(ValueError, match="model_median must be a finite"):
        evaluate_gates(
            **base,
            fee_rate=FEE_RATE_SPORTS,
            entry_price=0.50,
            model_median=float("nan"),
        )


# ---------------------------------------------------------------------------
# Cross-league match_winner enforcement (codex-review finding 4,
# 2026-11-07): the suspension registry stays descriptive; this check is
# what makes the book-of-record requirements (explicit bridge +
# worst-variant >= +5c extra margin) binding on the evaluate path.
# ---------------------------------------------------------------------------


def test_cross_league_mw_without_bridge_rejected():
    decision = check_cross_league_mw(
        "match_winner", worst_variant_edge=0.055, cross_league=True, bridge_present=False
    )
    assert decision.passed is False
    assert decision.failed == ("cross_league_bridge",)


def test_cross_league_mw_with_bridge_but_45c_worst_edge_rejected():
    decision = check_cross_league_mw(
        "match_winner", worst_variant_edge=0.045, cross_league=True, bridge_present=True
    )
    assert decision.passed is False
    assert decision.failed == ("cross_league_worst_edge",)


def test_cross_league_mw_with_bridge_and_55c_worst_edge_accepted():
    decision = check_cross_league_mw(
        "match_winner", worst_variant_edge=0.055, cross_league=True, bridge_present=True
    )
    assert decision.passed is True and decision.failed == ()
    # boundary: worst exactly +5c passes, next tick fails (round-24
    # epsilon convention, same as the frozen gates).
    on_bar = check_cross_league_mw(
        "match_winner", worst_variant_edge=0.05, cross_league=True, bridge_present=True
    )
    assert on_bar.passed is True and on_bar.failed == ()
    next_tick = check_cross_league_mw(
        "match_winner", worst_variant_edge=0.0499, cross_league=True, bridge_present=True
    )
    assert next_tick.passed is False
    assert next_tick.failed == ("cross_league_worst_edge",)
    assert CROSS_LEAGUE_MW_WORST_EDGE_MIN == 0.05


def test_cross_league_mw_missing_both_requirements_lists_both():
    # lineage aliases (ml/1x2) scope into the same rule.
    decision = check_cross_league_mw(
        "ml", worst_variant_edge=0.03, cross_league=True, bridge_present=False
    )
    assert decision.passed is False
    assert decision.failed == ("cross_league_bridge", "cross_league_worst_edge")


def test_cross_league_mw_domestic_and_other_kinds_pass_through():
    # domestic match_winner: unchanged -- no bridge/extra-margin rule is
    # added (the frozen worst>=+4c gate and the deprioritized sizing
    # keep applying exactly as before).
    domestic = check_cross_league_mw(
        "match_winner",
        worst_variant_edge=0.045,
        cross_league=False,
        bridge_present=False,
    )
    assert domestic.passed is True and domestic.failed == ()
    # other market kinds are untouched even when cross_league is set.
    for kind in ("total", "btts", "spread", "team_total"):
        passthrough = check_cross_league_mw(
            kind, worst_variant_edge=0.0, cross_league=True, bridge_present=False
        )
        assert passthrough.passed is True and passthrough.failed == ()


def test_cross_league_mw_rejects_non_finite_worst_edge():
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError, match="worst_variant_edge"):
            check_cross_league_mw(
                "match_winner", worst_variant_edge=bad, cross_league=True, bridge_present=True
            )


def test_cross_league_mw_enforces_the_registry_wording_on_the_evaluate_path():
    # composition: suspension_policy stays descriptive (the KIND is
    # ELIGIBLE_DEPRIORITIZED); this check is what makes the documented
    # requirements binding before any sizing happens.
    policy = suspension_policy("match_winner", cross_league=True)
    assert policy.eligible is True
    rejected = check_cross_league_mw(
        "match_winner", worst_variant_edge=0.045, cross_league=True, bridge_present=False
    )
    assert rejected.passed is False
    assert set(rejected.failed) == {"cross_league_bridge", "cross_league_worst_edge"}
