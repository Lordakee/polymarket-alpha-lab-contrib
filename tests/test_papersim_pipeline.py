"""FX-08 tests: the ``decide_entry`` single entry point and its reasons.

Regression anchors preserved through the new entry point (numbers
byte-frozen from the same fixtures the existing suites pin):

- ``#48`` Brentford-Forest O2.5 (``regression_gate_arithmetic.json``):
  entry VWAP 0.560, exec +7.42c gross / +6.19c net, worst +6.35c,
  spread 2.11c -- ACCEPTED at the $250 FULL_EDGE unit;
- ``BOU-LEE`` O2.5 (``regression_r23_soccer.json``): rejected for the
  true 6.09c variant spread;
- ``HOF-LYO`` (``regression_banned_path.json`` + the WP-P2a bridge
  fixtures): rejected without a bridge, conditionally eligible with
  the validated bridge at a fixed $150 (``CROSS_LEAGUE_ML_CLASS``).

FX-13 additions: terminal/touch record-type consistency, mandatory
``yes_when`` through ``conservative_edges_for_terminal``, the
above-YES / below-NO mirror under symmetric quotes, replay-preserving
original-direction evidence, and the three frozen r19 touch anchors
passing through the touch path unchanged.

Exhaustiveness: the parametrized rejection matrix mutates one accepted
base per known reason id and proves the decision is never accepted
with that reason present -- together with the structure property
(accepted <=> reasons empty AND every step pass) this covers "any
required check failing forces rejection".
"""

from __future__ import annotations

import dataclasses
import datetime
import json
import math
from pathlib import Path

import pytest

from polymarket_alpha_lab.papersim import crypto_model, fees, gates, pipeline, risk_policy
from polymarket_alpha_lab.papersim.crypto_model import (
    TerminalProbability,
    TerminalYesProbability,
    TouchProbability,
    terminal_yes_probability,
    touch_probability,
)
from polymarket_alpha_lab.papersim.pipeline import (
    STEP_ORDER,
    EntryDecision,
    EntryRequest,
    bridge_fingerprint,
    decide_entry,
    policy_code_sha256,
)
from polymarket_alpha_lab.papersim.soccer_model import SoccerCandidate

FIXTURES = Path(__file__).parent / "fixtures" / "papersim"

# Reconstructed representative ladders for market 5856164 (#48
# Brentford-Forest O2.5), mirroring tests/test_papersim_gates.py.
ASK_LADDER_5856164 = [
    (0.56, 1000.0),
    (0.57, 14000.0),
    (0.58, 12993.0),
    (0.60, 30000.0),
]

NOW = datetime.datetime(2026, 11, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)


def _gate48_case() -> dict:
    data = json.loads(
        (FIXTURES / "regression_gate_arithmetic.json").read_text(encoding="utf-8")
    )
    assert data["schema"] == "papersim.regression.gate_arithmetic.v1"
    return data["case"]


def _r23_case(case_id: str) -> dict:
    data = json.loads(
        (FIXTURES / "regression_r23_soccer.json").read_text(encoding="utf-8")
    )
    return data["cases"][case_id]


def _concordant(fixture: str) -> gates.NewsCheck:
    return gates.check_news(fixture, "recheck T-1d", news_delta="unchanged")


def _accepted_soccer_request() -> EntryRequest:
    """The frozen #48 Brentford-Forest O2.5 record as an accepted request."""

    case = _gate48_case()
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
    return EntryRequest(
        market_id=case["market_id"],
        question=entry["question"],
        fixture="BRE-FOR_O2.5",
        market_kind="total",
        side="Over/Yes(side0)",
        book=ASK_LADDER_5856164,
        fee_category="sports",
        model_quote=candidate,
        gamma_liquidity=case["r24_book_ladder"]["liq"],
        news=_concordant("BRE-FOR_O2.5"),
        o25_hits=6,
        line=2.5,
        bankroll=10_000.0,
        cash=10_000.0,
        reserved=0.0,
        book_time=NOW,
        now=NOW,
        max_book_age_seconds=300.0,
    )


def _eth2000_terminal() -> TerminalProbability:
    return TerminalProbability(
        asset="ETH",
        barrier=2000.0,
        horizon_hours=1595.12,
        convention_a=0.2224,
        convention_b=0.2531,
    )


def _accepted_crypto_request() -> EntryRequest:
    """An accepted crypto_terminal candidate (ETH-2000 below, buying YES)."""

    return EntryRequest(
        market_id="m-eth2000-term",
        question="Ethereum below $2,000 on date",
        fixture="ETH-2000",
        market_kind="crypto_terminal",
        side="yes",
        book=[(0.15, 5000.0)],
        fee_category="crypto",
        probability=_eth2000_terminal(),
        yes_when="below",
        buy_side="yes",
        yes_ask=0.15,
        no_ask=0.80,
        gamma_liquidity=6000.0,
        news=_concordant("ETH-2000"),
        bankroll=10_000.0,
        cash=10_000.0,
        reserved=0.0,
        book_time=NOW,
        now=NOW,
        max_book_age_seconds=300.0,
    )


HOF_TEAM_HOME = "TSG 1899 Hoffenheim"
HOF_LEAGUE = "bundesliga"
LYO_TEAM_AWAY = "Olympique Lyonnais"
LYO_LEAGUE = "ligue_1"
STRONG_BUNDES_BRIDGE = {HOF_LEAGUE: math.log(1.25), LYO_LEAGUE: 0.0}


def _hof_request(
    *,
    qs_variants: tuple[float, float] = (0.59, 0.61),
    model_median: float = 0.60,
    **overrides,
) -> EntryRequest:
    """A cross-league match-winner request around the HOF-LYO fixture.

    Defaults describe a bridged, gate-passing candidate at the frozen
    $150 marginal unit; ``bridge``/``bridge_fingerprint`` steering is
    done by the callers through ``overrides``.
    """

    quote = {
        "model_median": model_median,
        "qs_variants": qs_variants,
    }
    kwargs: dict = dict(
        market_id="m-hof-lyo",
        question="TSG 1899 Hoffenheim vs. Olympique Lyonnais: moneyline",
        fixture="HOF-LYO",
        market_kind="1x2",
        side="yes",
        book=[(0.52, 1000.0)],
        fee_category="sports",
        cross_league=True,
        home_league=HOF_LEAGUE,
        away_league=LYO_LEAGUE,
        model_quote=quote,
        gamma_liquidity=20_000.0,
        news=_concordant("HOF-LYO"),
        lineup_confirmation=1.0,
        bankroll=10_000.0,
        cash=10_000.0,
        reserved=0.0,
        book_time=NOW,
        now=NOW,
        max_book_age_seconds=300.0,
    )
    kwargs.update(overrides)
    return EntryRequest(**kwargs)


# ---------------------------------------------------------------------------
# Original behavior regressions (frozen anchors, pre-pipeline APIs)
# ---------------------------------------------------------------------------


def test_48_gate_arithmetic_original_behavior():
    """The frozen #48 record still evaluates PASS through evaluate_candidate."""

    case = _gate48_case()
    entry = case["entry_r23"]
    report = gates.evaluate_candidate(
        dict(model_median=entry["model_median"], qs_variants=entry["qs_variants"]),
        ASK_LADDER_5856164,
        "ask",
        gamma_liquidity=case["r24_book_ladder"]["liq"],
        news=_concordant("BRE-FOR_O2.5"),
        fee_rate=gates.FEE_RATE_SPORTS,
    )
    assert report.decision.passed is True
    assert report.entry_price == 0.56
    assert report.exec_edge_gross == 0.0742
    assert report.exec_edge == 0.0619
    assert report.worst_variant_edge == 0.0635
    assert report.variant_spread == 0.0211


def test_bou_lee_original_behavior_variant_spread_rejection():
    case = _r23_case("BOU-LEE_O2.5")
    report = gates.evaluate_candidate(
        dict(model_median=case["model_median"], qs_variants=case["qs_variants"]),
        [(case["entry_ask_vwap250"], 1000.0)],
        "ask",
        gamma_liquidity=case["liq_gamma"],
        news=_concordant("BOU-LEE"),
        fee_rate=gates.FEE_RATE_SPORTS,
    )
    assert report.variant_spread == pytest.approx(case["var_spread"], abs=1e-4)
    assert report.decision.passed is False
    assert report.decision.failed == ("variant_spread",)
    assert case["fail_reasons"] == ["var>6c"]


def test_hof_lyo_original_behavior_unbridged_guard():
    """The soccer-model cross-league guard still returns None without a bridge."""

    banned = json.loads(
        (FIXTURES / "regression_banned_path.json").read_text(encoding="utf-8")
    )["case"]
    snapshot = {
        "bundesliga_2026": {
            "dates": [],
            "teams": {
                "3": {
                    "title": banned["home"]["team"],
                    "history": [{"xG": 1.5, "xGA": 1.5}],
                }
            },
        },
        "ligue_1_2026": {
            "dates": [],
            "teams": {
                "4": {
                    "title": banned["away"]["team"],
                    "history": [{"xG": 1.9, "xGA": 1.1}],
                }
            },
        },
    }
    from polymarket_alpha_lab.papersim import soccer_model

    assert (
        soccer_model.match_lambdas(
            snapshot,
            banned["home"]["team"],
            banned["home"]["league"],
            banned["away"]["team"],
            banned["away"]["league"],
        )
        is None
    )


# ---------------------------------------------------------------------------
# The three anchors through decide_entry
# ---------------------------------------------------------------------------


def test_48_accepted_through_entry_point():
    decision = decide_entry(_accepted_soccer_request())
    assert decision.accepted is True
    assert decision.reasons == ()
    assert decision.notional == 250.0
    assert decision.tier is not None and decision.tier.tier == risk_policy.TIER_FULL_EDGE
    assert decision.market_class == risk_policy.STANDARD_CLASS
    assert decision.fee_category == "sports"
    assert decision.fee_rate == 0.05
    assert decision.entry_fee == pytest.approx(250.0 * 0.05 * (1 - 0.56), abs=1e-6)
    # frozen gate numbers reproduced through the entry point
    assert decision.gate_report is not None
    assert decision.gate_report.exec_edge_gross == 0.0742
    assert decision.gate_report.exec_edge == 0.0619
    assert decision.gate_report.worst_variant_edge == 0.0635
    assert decision.gate_report.variant_spread == 0.0211
    assert decision.acceptance_walk is not None
    assert decision.acceptance_walk.vwap == 0.56
    assert decision.acceptance_walk.depth_near2c == 16076.0
    assert decision.actual_walk is not None
    assert decision.actual_walk.vwap == 0.56
    assert decision.actual_walk.shares == pytest.approx(250.0 / 0.56, abs=1e-4)
    assert decision.under_risk_flagged is False
    assert decision.model_version == pipeline.MODEL_VERSION_SOCCER
    assert decision.gate_version == pipeline.GATE_VERSION
    assert decision.code_sha256 == policy_code_sha256()
    assert [s.step for s in decision.steps] == list(STEP_ORDER)
    assert all(s.status == "pass" for s in decision.steps)


def test_bou_lee_rejected_for_true_6_09c_spread():
    case = _r23_case("BOU-LEE_O2.5")
    request = EntryRequest(
        market_id=case["market_id"],
        question=case["question"],
        fixture="BOU-LEE_O2.5",
        market_kind="total",
        side="Over/Yes(side0)",
        book=[(case["entry_ask_vwap250"], 1000.0)],
        fee_category="sports",
        model_quote=dict(
            model_median=case["model_median"],
            qs_variants=tuple(case["qs_variants"]),
            lambda_home=case["lambda_home"],
            lambda_away=case["lambda_away"],
        ),
        gamma_liquidity=case["liq_gamma"],
        news=_concordant("BOU-LEE"),
        o25_hits=6,
        line=2.5,
        bankroll=10_000.0,
        cash=10_000.0,
        reserved=0.0,
        book_time=NOW,
        now=NOW,
        max_book_age_seconds=300.0,
    )
    decision = decide_entry(request)
    assert decision.accepted is False
    assert decision.reasons == ("variant_spread",)
    assert decision.gate_report is not None
    assert decision.gate_report.variant_spread == pytest.approx(0.0609, abs=1e-4)


def test_hof_lyo_without_bridge_rejected():
    decision = decide_entry(_hof_request())
    assert decision.accepted is False
    assert "cross_league_bridge" in decision.reasons
    assert decision.market_class == risk_policy.CROSS_LEAGUE_ML_CLASS


def test_hof_lyo_with_bridge_accepted_at_fixed_150():
    request = _hof_request(
        bridge=STRONG_BUNDES_BRIDGE,
        bridge_fingerprint=bridge_fingerprint(STRONG_BUNDES_BRIDGE),
    )
    decision = decide_entry(request)
    assert decision.accepted is True, decision.reasons
    assert decision.reasons == ()
    # the +5c extra check and the CROSS_LEAGUE_ML_CLASS sizing run together;
    # a passing cross-league MW candidate is ALWAYS $150, even with confirmed
    # lineups (lineup_confirmation=1.0 would otherwise give FULL_EDGE).
    assert decision.notional == 150.0
    assert decision.tier is not None
    assert decision.tier.tier == risk_policy.TIER_MARGINAL
    assert decision.market_class == risk_policy.CROSS_LEAGUE_ML_CLASS
    assert decision.cross_league_mw_check is not None
    assert decision.cross_league_mw_check.passed is True
    assert decision.bridge_sha256 == bridge_fingerprint(STRONG_BUNDES_BRIDGE)
    assert decision.entry_fee == pytest.approx(150.0 * 0.05 * (1 - 0.52), abs=1e-6)


def test_cross_league_alias_1x2_normalized_by_entry_point():
    """The '1x2' MW alias drives both the +5c check and the sizing class."""

    assert "1x2" in pipeline.MATCH_WINNER_KINDS
    decision = decide_entry(
        _hof_request(
            bridge=STRONG_BUNDES_BRIDGE,
            bridge_fingerprint=bridge_fingerprint(STRONG_BUNDES_BRIDGE),
            market_kind="ml",
        )
    )
    assert decision.accepted is True
    assert decision.market_class == risk_policy.CROSS_LEAGUE_ML_CLASS
    assert decision.notional == 150.0


def test_cross_league_worst_edge_4_9c_rejected_and_5c_boundary_passes():
    kwargs = dict(
        bridge=STRONG_BUNDES_BRIDGE,
        bridge_fingerprint=bridge_fingerprint(STRONG_BUNDES_BRIDGE),
    )
    rejected = decide_entry(
        _hof_request(qs_variants=(0.569, 0.61), model_median=0.60, **kwargs)
    )
    assert rejected.accepted is False
    assert rejected.reasons == ("cross_league_worst_edge",)
    assert rejected.gate_report is not None
    assert rejected.gate_report.worst_variant_edge == pytest.approx(0.049, abs=1e-4)
    accepted = decide_entry(
        _hof_request(qs_variants=(0.57, 0.61), model_median=0.60, **kwargs)
    )
    assert accepted.accepted is True, accepted.reasons
    assert accepted.gate_report is not None
    assert accepted.gate_report.worst_variant_edge == pytest.approx(0.05, abs=1e-9)
    assert accepted.notional == 150.0


# ---------------------------------------------------------------------------
# Strict crossbridge evidence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "overrides,expected_reason",
    [
        (dict(bridge=True), "bridge_invalid"),
        (dict(bridge={HOF_LEAGUE: True, LYO_LEAGUE: 0.0}), "bridge_invalid"),
        (dict(bridge={HOF_LEAGUE: float("nan"), LYO_LEAGUE: 0.0}), "bridge_invalid"),
        (dict(bridge={"epl": 0.1, "laliga": 0.2}), "bridge_invalid"),
        (
            dict(bridge=STRONG_BUNDES_BRIDGE, bridge_fingerprint=None),
            "bridge_fingerprint_missing",
        ),
        (
            dict(bridge=STRONG_BUNDES_BRIDGE, bridge_fingerprint="0" * 64),
            "bridge_fingerprint_mismatch",
        ),
        # tampered bridge: same fingerprint, different kappa
        (
            dict(
                bridge={HOF_LEAGUE: 0.0, LYO_LEAGUE: 0.0},
                bridge_fingerprint=bridge_fingerprint(STRONG_BUNDES_BRIDGE),
            ),
            "bridge_fingerprint_mismatch",
        ),
    ],
)
def test_crossbridge_evidence_rejections(overrides, expected_reason):
    decision = decide_entry(_hof_request(**overrides))
    assert decision.accepted is False
    assert expected_reason in decision.reasons


@pytest.mark.parametrize(
    "overrides",
    [
        dict(home_league="bundesliga", away_league="bundesliga"),  # equal, claimed cross
        dict(home_league=None, away_league=None),  # cross-league without league evidence
    ],
)
def test_cross_league_league_metadata_mismatch(overrides):
    decision = decide_entry(
        _hof_request(
            bridge=STRONG_BUNDES_BRIDGE,
            bridge_fingerprint=bridge_fingerprint(STRONG_BUNDES_BRIDGE),
            **overrides,
        )
    )
    assert decision.accepted is False
    assert "cross_league_league_mismatch" in decision.reasons


def test_domestic_candidate_with_different_leagues_rejected():
    request = dataclasses.replace(
        _accepted_soccer_request(),
        cross_league=False,
        home_league="epl",
        away_league="laliga",
    )
    decision = decide_entry(request)
    assert decision.accepted is False
    assert decision.reasons == ("cross_league_league_mismatch",)


def test_bridge_fingerprint_is_stable_and_order_independent():
    a = {"bundesliga": 0.2231, "ligue_1": 0.0}
    b = {"ligue_1": 0.0, "bundesliga": 0.2231}
    assert bridge_fingerprint(a) == bridge_fingerprint(b)
    assert len(bridge_fingerprint(a)) == 64
    assert bridge_fingerprint(a) != bridge_fingerprint({"bundesliga": 0.0, "ligue_1": 0.0})


def test_bridge_with_non_numeric_extra_key_rejected_not_crash():
    """Review P2-1: a bridge carrying a non-numeric extra key (the
    reviewer's ``"note": "wp-p2a"`` reproduction) must be rejected as
    invalid bridge evidence -- the ValueError from the fingerprint's
    float() conversion must NEVER escape decide_entry."""

    bridge = {
        HOF_LEAGUE: math.log(1.25),
        LYO_LEAGUE: 0.0,
        "note": "wp-p2a",
    }
    # A non-None fingerprint is what drives the flow INTO the
    # bridge_fingerprint computation (the reviewer's reproduction).
    decision = decide_entry(_hof_request(bridge=bridge, bridge_fingerprint="0" * 64))
    assert isinstance(decision, EntryDecision)
    assert decision.accepted is False
    assert "bridge_invalid" in decision.reasons
    assert "cross_league_bridge" in decision.reasons  # bridge_ok stays False
    step = next(s for s in decision.steps if s.step == "cross_league_mw")
    assert step.status == "fail"


def test_bridge_with_extra_numeric_key_and_matching_fingerprint_accepted():
    """Extra NUMERIC keys are tolerated when the fingerprint covers the
    same table (pure kappa-table semantics: numbers anywhere, strings
    nowhere)."""

    bridge = {HOF_LEAGUE: math.log(1.25), LYO_LEAGUE: 0.0, "epl": 0.1}
    decision = decide_entry(
        _hof_request(bridge=bridge, bridge_fingerprint=bridge_fingerprint(bridge))
    )
    assert decision.accepted is True, decision.reasons
    assert decision.bridge_sha256 == bridge_fingerprint(bridge)


def test_bridge_with_numeric_string_extra_key_rejected():
    """Numeric-STRING values anywhere in the bridge are invalid kappa
    evidence (uniform pure-kappa-table rule; this deliberately closes
    the P3-2-recorded permissiveness where an extra numeric-string key
    slipped through the fingerprint's float() conversion)."""

    bridge = {HOF_LEAGUE: math.log(1.25), LYO_LEAGUE: 0.0, "epl": "0.1"}
    decision = decide_entry(
        _hof_request(bridge=bridge, bridge_fingerprint="0" * 64)
    )
    assert isinstance(decision, EntryDecision)
    assert decision.accepted is False
    assert "bridge_invalid" in decision.reasons


# ---------------------------------------------------------------------------
# Fee category handling (FX-06 / R06 acceptance)
# ---------------------------------------------------------------------------


def test_explicit_category_resolves_table_rate_and_is_recorded():
    decision = decide_entry(_accepted_soccer_request())
    assert decision.fee_category == "sports"
    assert decision.fee_rate == fees.taker_fee_rate("sports") == 0.05


def test_zero_fee_rate_is_a_valid_value():
    request = dataclasses.replace(_accepted_soccer_request(), fee_category="geopolitics")
    decision = decide_entry(request)
    assert decision.accepted is True, decision.reasons
    assert decision.fee_rate == 0.0
    assert decision.entry_fee == 0.0


def test_market_metadata_rate_matching_table_is_honored():
    request = dataclasses.replace(
        _accepted_soccer_request(), market_rate=0.05
    )
    decision = decide_entry(request)
    assert decision.accepted is True
    assert decision.fee_rate == 0.05


def test_non_crypto_team_does_not_inherit_sports_category():
    """A politics-team candidate must resolve its EXPLICIT category, not the
    historical sports-by-team scan rule."""

    request = dataclasses.replace(
        _accepted_soccer_request(), fee_category="politics", team="politics_us"
    )
    decision = decide_entry(request)
    assert decision.accepted is True, decision.reasons
    assert decision.fee_rate == 0.04  # politics row, NOT the sports 0.05


def test_legacy_scan_fee_category_never_called_on_entry_path(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("legacy_scan_fee_category used on the new-entry path")

    monkeypatch.setattr(fees, "legacy_scan_fee_category", boom)
    decision = decide_entry(_accepted_soccer_request())
    assert decision.accepted is True


# ---------------------------------------------------------------------------
# FX-13: terminal/touch direction handling on the crypto path
# ---------------------------------------------------------------------------


def _touch_eth2000() -> TouchProbability:
    return touch_probability(
        spot=2326.84,
        sigma_daily=0.02430307766195731,
        barrier=2000.0,
        horizon_hours=1595.12,
        asset="ETH",
    )


def _accepted_touch_request() -> EntryRequest:
    touch = _touch_eth2000()
    fair = min(touch.convention_a, touch.convention_b)
    return EntryRequest(
        market_id="m-eth2000-touch",
        question="Ethereum touches $2,000 before date",
        fixture="ETH-2000",
        market_kind="crypto_touch",
        side="yes",
        book=[(round(fair - 0.08, 4), 5000.0)],
        fee_category="crypto",
        probability=touch,
        buy_side="yes",
        yes_ask=round(fair - 0.08, 4),
        no_ask=0.80,
        gamma_liquidity=6000.0,
        news=_concordant("ETH-2000"),
        bankroll=10_000.0,
        cash=10_000.0,
        reserved=0.0,
        book_time=NOW,
        now=NOW,
        max_book_age_seconds=300.0,
    )


def test_accepted_crypto_terminal_candidate_details():
    decision = decide_entry(_accepted_crypto_request())
    assert decision.accepted is True, decision.reasons
    assert decision.notional == 250.0
    assert decision.fee_rate == 0.07
    assert decision.model_version == pipeline.MODEL_VERSION_CRYPTO
    evidence = decision.crypto_evidence
    assert evidence is not None
    assert evidence.record_type == "terminal"
    assert (evidence.original_convention_a, evidence.original_convention_b) == (
        0.2224,
        0.2531,
    )
    assert evidence.yes_when == "below"
    assert evidence.market_yes_convention_a == 0.2224
    assert evidence.market_yes_convention_b == 0.2531
    assert "terminal_yes_probability" in evidence.direction_source
    assert evidence.model_median == pytest.approx(0.2224)
    assert evidence.qs_variants == (0.2224, 0.2531)
    assert decision.gate_report is not None
    assert decision.gate_report.worst_variant_edge == pytest.approx(0.2224 - 0.15)


def test_terminal_above_yes_mirrors_below_no_under_symmetric_quotes():
    term = _eth2000_terminal()
    below = decide_entry(_accepted_crypto_request()).crypto_evidence
    above = decide_entry(
        dataclasses.replace(
            _accepted_crypto_request(),
            question="Ethereum above $2,000 on date",
            yes_when="above",
            yes_ask=0.80,
            no_ask=0.15,
            book=[(0.80, 5000.0)],
        )
    ).crypto_evidence
    assert below is not None and above is not None
    # same barrier, symmetric quotes: above's YES fair/edge == below's NO
    assert above.fair_yes == pytest.approx(below.fair_no, abs=1e-12)
    assert above.edge_yes == pytest.approx(below.edge_no, abs=1e-12)
    assert above.fair_no == pytest.approx(below.fair_yes, abs=1e-12)
    # and the complementary buy direction derives the same conservative quote
    below_buy_no = decide_entry(
        dataclasses.replace(
            _accepted_crypto_request(), buy_side="no", book=[(0.80, 5000.0)]
        )
    ).crypto_evidence
    assert below_buy_no is not None
    assert below_buy_no.model_median == pytest.approx(below.fair_no, abs=1e-12)
    # direction provenance recorded for both sides
    assert above.yes_when == "above" and below.yes_when == "below"
    assert term.convention_a == 0.2224  # fixture sanity


def test_pipeline_calls_the_direction_wrapper_for_terminal_records(monkeypatch):
    calls: list[str] = []

    real = crypto_model.conservative_edges_for_terminal

    def spy(probabilities, *, yes_when, yes_ask, no_ask):
        calls.append(yes_when)
        return real(
            probabilities, yes_when=yes_when, yes_ask=yes_ask, no_ask=no_ask
        )

    monkeypatch.setattr(
        crypto_model, "conservative_edges_for_terminal", spy
    )
    decision = decide_entry(_accepted_crypto_request())
    assert decision.accepted is True
    assert calls == ["below"]

    # the touch path must NOT go through the terminal wrapper
    calls.clear()

    def no_terminal(*args, **kwargs):
        raise AssertionError("touch record routed through the terminal wrapper")

    monkeypatch.setattr(
        crypto_model, "conservative_edges_for_terminal", no_terminal
    )
    touch_decision = decide_entry(_accepted_touch_request())
    assert touch_decision.crypto_evidence is not None
    assert touch_decision.crypto_evidence.record_type == "touch"


def test_terminal_above_market_is_not_priced_as_below_by_omission():
    """The P-8 hazard: naive below-barrier pricing of an above market."""

    above = decide_entry(
        dataclasses.replace(
            _accepted_crypto_request(),
            yes_when="above",
            book=[(0.80, 5000.0)],
            yes_ask=0.80,
            no_ask=0.15,
        )
    ).crypto_evidence
    term = _eth2000_terminal()
    naive = crypto_model.conservative_edges(term, yes_ask=0.80, no_ask=0.15)
    assert above is not None
    assert above.fair_yes != naive.fair_yes
    assert above.fair_yes == pytest.approx(1.0 - max(0.2224, 0.2531), abs=1e-12)


def test_replay_preserves_original_direction_and_recomputes_edges():
    decision = decide_entry(_accepted_crypto_request())
    evidence = decision.crypto_evidence
    assert evidence is not None
    # the ORIGINAL pre-transform record is preserved on the decision
    assert (evidence.original_convention_a, evidence.original_convention_b) == (
        0.2224,
        0.2531,
    )
    original = TerminalProbability(
        asset=evidence.asset,
        barrier=evidence.barrier,
        horizon_hours=evidence.horizon_hours,
        convention_a=evidence.original_convention_a,
        convention_b=evidence.original_convention_b,
    )
    replayed = crypto_model.conservative_edges_for_terminal(
        original,
        yes_when=evidence.yes_when,
        yes_ask=evidence.yes_ask,
        no_ask=evidence.no_ask,
    )
    assert replayed.fair_yes == pytest.approx(evidence.fair_yes, abs=1e-12)
    assert replayed.edge_yes == pytest.approx(evidence.edge_yes, abs=1e-12)
    assert replayed.fair_no == pytest.approx(evidence.fair_no, abs=1e-12)
    # and the gate quote is re-derived identically from the oriented pair
    if evidence.buy_side == "yes":
        median = replayed.fair_yes
        variants = (
            evidence.market_yes_convention_a,
            evidence.market_yes_convention_b,
        )
    else:
        median = replayed.fair_no
        variants = (
            1.0 - evidence.market_yes_convention_a,
            1.0 - evidence.market_yes_convention_b,
        )
    assert median == pytest.approx(evidence.model_median, abs=1e-12)
    assert variants == evidence.qs_variants


@pytest.mark.parametrize(
    "case_key,spot,sigma,barrier,asset",
    [
        ("ETH-2000", 2326.84, 0.02430307766195731, 2000.0, "ETH"),
        ("ETH-2250", 2326.84, 0.02430307766195731, 2250.0, "ETH"),
        ("BTC-65k", 80342.38, 0.01583874457257652, 65000.0, "BTC"),
    ],
)
def test_three_frozen_touch_selfcheck_anchors_unchanged(
    case_key, spot, sigma, barrier, asset
):
    """The three r19 touch anchors pass through the touch path unchanged."""

    fixture = json.loads(
        (FIXTURES / "regression_r19_crypto.json").read_text(encoding="utf-8")
    )
    frozen = fixture["cases"][case_key]
    touch = touch_probability(
        spot=spot, sigma_daily=sigma, barrier=barrier,
        horizon_hours=1595.12, asset=asset,
    )
    fair = min(touch.convention_a, touch.convention_b)
    request = EntryRequest(
        market_id=f"m-{case_key}",
        question=f"{asset} barrier touch",
        fixture=case_key,
        market_kind="crypto_touch",
        side="yes",
        book=[(round(max(fair - 0.08, 0.02), 4), 5000.0)],
        fee_category="crypto",
        probability=touch,
        buy_side="yes",
        yes_ask=round(max(fair - 0.08, 0.02), 4),
        no_ask=0.80,
        gamma_liquidity=6000.0,
        news=_concordant(case_key),
        bankroll=10_000.0,
        cash=10_000.0,
        reserved=0.0,
        book_time=NOW,
        now=NOW,
        max_book_age_seconds=300.0,
    )
    decision = decide_entry(request)
    evidence = decision.crypto_evidence
    assert evidence is not None
    # frozen A/B anchors carried through UNCHANGED (no terminal transform)
    assert evidence.original_convention_a == pytest.approx(frozen["A"], abs=1e-4)
    assert evidence.original_convention_b == pytest.approx(frozen["B"], abs=1e-4)
    assert evidence.market_yes_convention_a is None
    assert evidence.market_yes_convention_b is None
    assert evidence.yes_when is None
    assert "touch" in evidence.direction_source
    assert evidence.model_median == pytest.approx(min(frozen["A"], frozen["B"]), abs=1e-4)
    assert evidence.qs_variants == (
        evidence.original_convention_a,
        evidence.original_convention_b,
    )


# ---------------------------------------------------------------------------
# Book freshness / time evidence
# ---------------------------------------------------------------------------


def test_fresh_book_at_exact_max_age_boundary_passes():
    request = dataclasses.replace(
        _accepted_soccer_request(),
        book_time=NOW - datetime.timedelta(seconds=300),
        now=NOW,
        max_book_age_seconds=300.0,
    )
    assert decide_entry(request).accepted is True


def test_stale_book_rejected_with_original_walk_still_recorded():
    request = dataclasses.replace(
        _accepted_soccer_request(),
        book_time=NOW - datetime.timedelta(seconds=301),
    )
    decision = decide_entry(request)
    assert decision.accepted is False
    assert decision.reasons == ("stale_book",)
    # the remaining computable checks still ran and recorded their outcomes
    assert decision.gate_report is not None
    assert decision.gate_report.decision.passed is True


def test_future_book_time_rejected():
    request = dataclasses.replace(
        _accepted_soccer_request(),
        book_time=NOW + datetime.timedelta(seconds=1),
    )
    decision = decide_entry(request)
    assert decision.accepted is False
    assert decision.reasons == ("book_time_in_future",)


def test_naive_vs_aware_time_inputs_rejected():
    request = dataclasses.replace(
        _accepted_soccer_request(), now=datetime.datetime(2026, 11, 1, 12, 0, 0)
    )
    decision = decide_entry(request)
    assert decision.accepted is False
    assert "time_inputs_incomparable" in decision.reasons


# ---------------------------------------------------------------------------
# News, under-risk, held-fixture, caps, bankroll
# ---------------------------------------------------------------------------


def test_missing_news_is_blocked_and_gate_fails_concordance():
    request = dataclasses.replace(_accepted_soccer_request(), news=None)
    decision = decide_entry(request)
    assert decision.accepted is False
    assert decision.reasons == ("news_concordant", "news_missing")
    gate_step = next(s for s in decision.steps if s.step == "gate_evaluate")
    assert "news_missing" in gate_step.reasons


def test_worse_news_rejected():
    news = gates.check_news("BRE-FOR_O2.5", "48h", news_delta="worse")
    request = dataclasses.replace(_accepted_soccer_request(), news=news)
    decision = decide_entry(request)
    assert decision.accepted is False
    assert decision.reasons == ("news_concordant",)


def test_under_risk_flagged_candidate_needs_the_8c_bar():
    quote = {
        "model_median": 0.60,
        "qs_variants": (0.58, 0.61),
        "lambda_home": 1.2,
        "lambda_away": 1.1,
    }
    request = dataclasses.replace(
        _accepted_soccer_request(),
        model_quote=quote,
        book=[(0.52, 1000.0)],
        o25_hits=2,
    )
    decision = decide_entry(request)
    assert decision.accepted is False
    assert decision.reasons == ("exec_edge",)
    assert decision.under_risk_flagged is True
    assert decision.gate_report is not None
    assert decision.gate_report.under_risk is True


def test_under_risk_materials_missing_is_blocked():
    request = dataclasses.replace(_accepted_soccer_request(), o25_hits=None)
    decision = decide_entry(request)
    assert decision.accepted is False
    assert decision.reasons == ("under_risk_inputs_missing",)
    gate_step = next(s for s in decision.steps if s.step == "gate_evaluate")
    assert gate_step.status == "blocked"


def test_same_direction_held_position_blocks_add():
    request = dataclasses.replace(
        _accepted_soccer_request(), held_sides=("Over 3.5",)
    )
    decision = decide_entry(request)
    assert decision.accepted is False
    assert decision.reasons == ("held_fixture_blocked",)
    held_step = next(s for s in decision.steps if s.step == "held_fixture")
    assert held_step.status == "fail"


def test_opposite_direction_add_on_held_fixture_allowed():
    request = dataclasses.replace(
        _accepted_soccer_request(), held_sides=("Under 2.5",)
    )
    assert decide_entry(request).accepted is True


def test_team_cap_exceeded_rejects():
    request = dataclasses.replace(_accepted_soccer_request(), team_committed=1800.0)
    decision = decide_entry(request)
    assert decision.accepted is False
    assert decision.reasons == ("team_cap_exceeded",)


@pytest.mark.parametrize("cash", [100.0, 254.0])
def test_bankroll_or_cash_insufficient_rejects(cash):
    """bankroll_available must cover the stake AND the entry fee (no double
    charge: principal + one entry-leg fee)."""

    request = dataclasses.replace(_accepted_soccer_request(), cash=cash)
    decision = decide_entry(request)
    assert decision.accepted is False
    assert decision.reasons == ("bankroll_insufficient",)
    assert decision.entry_fee == pytest.approx(5.5, abs=1e-6)


def test_reserved_funds_reduce_available_cash():
    request = dataclasses.replace(
        _accepted_soccer_request(), cash=10_000.0, reserved=9_800.0
    )
    decision = decide_entry(request)
    assert decision.accepted is False
    assert decision.reasons == ("bankroll_insufficient",)


def test_partial_fill_rejects_both_walks():
    # $112 of depth: neither the $250 acceptance walk nor the $250 actual
    # stake walk completes (exec/worst edges still compute at the partial
    # VWAP, so only the two fill checks fail).
    request = dataclasses.replace(_accepted_soccer_request(), book=[(0.56, 200.0)])
    decision = decide_entry(request)
    assert decision.accepted is False
    assert decision.reasons == ("actual_walk_incomplete", "fill_250")
    actual = decision.actual_walk
    assert actual is not None and actual.filled is False


def test_notional_cap_guard_rejects_above_acceptance_notional(monkeypatch):
    """Guard test: even if a future tier produced > $250, the entry point
    refuses to exceed the acceptance walk's notional."""

    def oversized(tier, *, lineup_confirmation=None):
        return 300.0

    monkeypatch.setattr(risk_policy, "tier_notional", oversized)
    decision = decide_entry(_accepted_soccer_request())
    assert decision.accepted is False
    assert "notional_cap_exceeded" in decision.reasons


# ---------------------------------------------------------------------------
# Structure, immutability, aggregation
# ---------------------------------------------------------------------------


def test_reasons_are_stable_sorted_and_unique():
    request = dataclasses.replace(
        _accepted_soccer_request(),
        book_time=NOW - datetime.timedelta(seconds=600),
        team_committed=1800.0,
        held_sides=("Over 3.5",),
    )
    decision = decide_entry(request)
    assert decision.accepted is False
    assert decision.reasons == tuple(sorted(set(decision.reasons)))
    assert set(decision.reasons) == {
        "stale_book",
        "team_cap_exceeded",
        "held_fixture_blocked",
    }


def test_decision_and_request_are_immutable():
    decision = decide_entry(_accepted_soccer_request())
    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.accepted = True  # type: ignore[misc]
    request = _accepted_soccer_request()
    with pytest.raises(dataclasses.FrozenInstanceError):
        request.market_id = "x"  # type: ignore[misc]


def test_blocked_dependency_still_collects_other_reasons():
    """A blocked fee category does not stop suspension/gate-independent checks."""

    request = dataclasses.replace(
        _accepted_soccer_request(),
        fee_category=None,
        team_committed=1800.0,
    )
    decision = decide_entry(request)
    assert decision.accepted is False
    assert set(decision.reasons) == {"fee_category_missing", "team_cap_exceeded"}
    statuses = {s.step: s.status for s in decision.steps}
    assert statuses["fee_category"] == "blocked"
    assert statuses["gate_evaluate"] == "blocked"
    assert statuses["team_cap"] == "fail"
    assert statuses["sizing"] == "pass"
    gate_step = next(s for s in decision.steps if s.step == "gate_evaluate")
    assert gate_step.reasons == ()  # the blocking reason lives on the blocker


def test_step_results_carry_original_objects():
    decision = decide_entry(_accepted_soccer_request())
    by_step = {s.step: s for s in decision.steps}
    assert isinstance(by_step["suspension_policy"].result, gates.SuspensionDecision)
    assert isinstance(by_step["gate_evaluate"].result, gates.GateReport)
    assert isinstance(by_step["cross_league_mw"].result, gates.GateDecision)
    assert isinstance(by_step["held_fixture"].result, risk_policy.CorrelationDecision)
    assert isinstance(by_step["sizing"].result, risk_policy.SizingTier)
    assert isinstance(by_step["actual_walk"].result, gates.BookWalk)


def test_policy_code_sha256_is_deterministic_hex_digest():
    digest = policy_code_sha256()
    assert len(digest) == 64
    int(digest, 16)
    assert digest == policy_code_sha256()
    assert f"fees-{fees.FEE_SCHEDULE_AS_OF}" in pipeline.GATE_VERSION


def test_step_order_matches_spec():
    assert STEP_ORDER == (
        "book_freshness",
        "suspension_policy",
        "fee_category",
        "under_risk_screen",
        "crypto_direction",
        "gate_evaluate",
        "cross_league_mw",
        "held_fixture",
        "sizing",
        "actual_walk",
        "notional_cap",
        "team_cap",
        "bankroll_cash",
    )


def test_accepted_implies_all_steps_pass():
    for request in (_accepted_soccer_request(), _accepted_crypto_request()):
        decision = decide_entry(request)
        assert decision.accepted is True
        assert decision.reasons == ()
        assert all(step.status == "pass" for step in decision.steps)


# ---------------------------------------------------------------------------
# Exhaustive rejection matrix: every reason id has a producing case, and no
# case with any reason is ever accepted.
# ---------------------------------------------------------------------------


def _matrix_cases() -> list[tuple[str, EntryRequest]]:
    soccer = _accepted_soccer_request()
    crypto = _accepted_crypto_request()
    touch = _accepted_touch_request()
    hof = dict(
        bridge=STRONG_BUNDES_BRIDGE,
        bridge_fingerprint=bridge_fingerprint(STRONG_BUNDES_BRIDGE),
    )
    cases: list[tuple[str, EntryRequest]] = [
        ("stale_book", dataclasses.replace(soccer, book_time=NOW - datetime.timedelta(seconds=600))),
        ("book_time_missing", dataclasses.replace(soccer, book_time=None)),
        ("now_missing", dataclasses.replace(soccer, now=None)),
        ("max_book_age_missing", dataclasses.replace(soccer, max_book_age_seconds=None)),
        ("book_time_in_future", dataclasses.replace(soccer, book_time=NOW + datetime.timedelta(seconds=60))),
        ("time_inputs_incomparable", dataclasses.replace(soccer, now=datetime.datetime(2026, 11, 1, 12, 0, 0))),
        ("suspension_ineligible", dataclasses.replace(soccer, market_kind="spread")),
        ("fee_category_missing", dataclasses.replace(soccer, fee_category=None)),
        ("fee_category_unknown", dataclasses.replace(soccer, fee_category="hobbies")),
        ("fee_rate_conflict", dataclasses.replace(soccer, market_rate=0.9)),
        ("under_risk_inputs_missing", dataclasses.replace(soccer, o25_hits=None)),
        ("model_evidence_missing", dataclasses.replace(soccer, model_quote=None)),
        ("model_evidence_ambiguous", dataclasses.replace(soccer, probability=_eth2000_terminal())),
        (
            "model_evidence_mismatch",
            dataclasses.replace(soccer, model_quote=None, probability=_touch_eth2000()),
        ),
        ("news_missing", dataclasses.replace(soccer, news=None)),
        ("news_concordant", dataclasses.replace(soccer, news=gates.check_news("f", "48h", news_delta="worse"))),
        (
            "variant_spread",
            dataclasses.replace(
                soccer,
                model_quote=dict(
                    model_median=0.6096,
                    qs_variants=(0.5714, 0.6323),
                    lambda_home=1.89,
                    lambda_away=1.26,
                ),
                book=[(0.52, 1000.0)],
            ),
        ),
        (
            "worst_edge",
            dataclasses.replace(
                soccer,
                model_quote=dict(
                    model_median=0.6342,
                    qs_variants=(0.59, 0.64),
                    lambda_home=1.894,
                    lambda_away=1.364,
                ),
            ),
        ),
        (
            "exec_edge",
            dataclasses.replace(
                soccer,
                model_quote=dict(
                    model_median=0.50,
                    qs_variants=(0.49, 0.52),
                    lambda_home=1.894,
                    lambda_away=1.364,
                ),
                book=[(0.44, 5000.0)],
            ),
        ),
        ("liq", dataclasses.replace(soccer, gamma_liquidity=100.0)),
        ("fill_250", dataclasses.replace(soccer, book=[(0.56, 200.0)])),
        ("actual_walk_incomplete", dataclasses.replace(soccer, book=[(0.56, 200.0)])),
        ("entry_window", dataclasses.replace(soccer, book=[(0.95, 5000.0)])),
        (
            "step_error",
            dataclasses.replace(
                soccer,
                model_quote=dict(
                    model_median=float("nan"),
                    qs_variants=(0.62, 0.64),
                    lambda_home=1.894,
                    lambda_away=1.364,
                ),
            ),
        ),
        ("cross_league_league_mismatch", dataclasses.replace(soccer, cross_league=False, home_league="epl", away_league="laliga")),
        ("held_fixture_blocked", dataclasses.replace(soccer, held_sides=("Over 3.5",))),
        ("team_cap_exceeded", dataclasses.replace(soccer, team_committed=1800.0)),
        ("bankroll_insufficient", dataclasses.replace(soccer, cash=100.0)),
        ("cross_league_bridge", _hof_request()),
        ("cross_league_worst_edge", _hof_request(qs_variants=(0.569, 0.61), **hof)),
        ("cross_league_mw_blocked", _hof_request(book=[], **hof)),
        ("bridge_invalid", _hof_request(bridge=True)),
        ("bridge_fingerprint_missing", _hof_request(bridge=STRONG_BUNDES_BRIDGE)),
        ("bridge_fingerprint_mismatch", _hof_request(bridge=STRONG_BUNDES_BRIDGE, bridge_fingerprint="0" * 64)),
        ("model_evidence_missing", dataclasses.replace(crypto, probability=None)),
        ("model_evidence_ambiguous", dataclasses.replace(crypto, model_quote=dict(model_median=0.9, qs_variants=(0.8, 0.9)))),
        ("model_evidence_mismatch", dataclasses.replace(crypto, probability=None, model_quote=dict(model_median=0.9, qs_variants=(0.8, 0.9)))),
        ("probability_type_conflict", dataclasses.replace(crypto, market_kind="crypto_touch", yes_when=None)),
        (
            "probability_type_conflict",
            dataclasses.replace(touch, market_kind="crypto_terminal", yes_when="below"),
        ),
        ("yes_when_missing", dataclasses.replace(crypto, yes_when=None)),
        ("yes_when_invalid", dataclasses.replace(crypto, yes_when="up")),
        ("yes_when_conflict", dataclasses.replace(crypto, contract_direction="above")),
        ("touch_terminal_conflict", dataclasses.replace(touch, yes_when="below")),
        (
            "terminal_record_pretransformed",
            dataclasses.replace(
                crypto, probability=terminal_yes_probability(_eth2000_terminal(), yes_when="below")
            ),
        ),
        ("buy_side_missing", dataclasses.replace(crypto, buy_side=None)),
        ("buy_side_invalid", dataclasses.replace(crypto, buy_side="maybe")),
        (
            "buy_side_conflict",
            dataclasses.replace(crypto, yes_token="t-yes", no_token="t-no", buy_token="t-yes", buy_side="no"),
        ),
        ("crypto_asks_missing", dataclasses.replace(crypto, yes_ask=None)),
        ("crypto_asks_invalid", dataclasses.replace(crypto, yes_ask=1.5)),
        ("crypto_ask_conflict", dataclasses.replace(crypto, yes_ask=0.17)),
    ]
    return cases


@pytest.mark.parametrize(
    "reason,entry_request",
    _matrix_cases(),
)
def test_every_rejection_reason_forces_rejection(reason, entry_request):
    decision = decide_entry(entry_request)
    assert decision.accepted is False, (
        f"reason {reason!r} produced an ACCEPTED decision"
    )
    assert reason in decision.reasons, (
        f"expected reason {reason!r} in {decision.reasons}"
    )


def test_rejection_matrix_reason_alphabet_is_complete():
    """Every reason id the module can emit appears in the matrix (except
    ``notional_cap_exceeded``, unreachable inside current tier bounds and
    covered by its dedicated monkeypatch guard test)."""

    emitted = {name for name in dir(pipeline) if name.startswith("REASON_")}
    expected = {getattr(pipeline, name) for name in emitted}
    matrix = {reason for reason, _ in _matrix_cases()}
    assert set(pipeline.GATE_REASON_IDS) <= matrix
    assert expected - {"notional_cap_exceeded"} <= matrix, (
        f"reason ids missing a matrix case: "
        f"{sorted(expected - {'notional_cap_exceeded'} - matrix)}"
    )
