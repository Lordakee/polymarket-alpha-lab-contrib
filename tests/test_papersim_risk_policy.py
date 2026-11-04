"""WP-P1 risk-policy tests: sizing tiers, team caps, held-fixture
correlation (nested bets = one risk unit), bankroll identity with
exit-aware accounting. All ledgers here are synthetic.
"""

from __future__ import annotations

import dataclasses
import inspect

import pytest

from polymarket_alpha_lab.papersim.risk_policy import (
    DOMESTIC_ML_CLASS,
    DIRECTION_LONG,
    DIRECTION_SHORT,
    DIRECTION_UNKNOWN,
    EARLY_ENTRY_MAX_NOTIONAL_USD,
    EARLY_ENTRY_MIN_NOTIONAL_USD,
    FULL_EDGE_NOTIONAL_USD,
    INITIAL_BANKROLL_USD,
    MARGINAL_NOTIONAL_USD,
    STATUS_EXITED,
    STATUS_LOST,
    STATUS_OPEN,
    STATUS_WON,
    TIER_EARLY_ENTRY,
    TIER_FULL_EDGE,
    TIER_MARGINAL,
    BankrollCheck,
    CorrelationDecision,
    PaperStake,
    RecordSummary,
    SettledPosition,
    bankroll_available,
    check_bankroll_identity,
    count_risk_units,
    expected_cash,
    held_fixture_add_allowed,
    paper_stake,
    position_pnl,
    risk_unit_keys,
    settle_record,
    side_direction,
    sizing_tier,
    team_add_allowed,
    team_cap_status,
    tier_notional,
)


# ---------------------------------------------------------------------------
# Frozen interfaces
# ---------------------------------------------------------------------------


def test_frozen_stub_surfaces_preserved():
    assert [f.name for f in dataclasses.fields(PaperStake)] == [
        "fixture",
        "question",
        "notional",
        "entry_price",
        "currency",
    ]
    stake = paper_stake(fixture="f", question="q", entry_price=0.56)
    assert stake.notional == 250.0
    assert stake == PaperStake("f", "q", 250.0, 0.56, "USD")
    params = inspect.signature(paper_stake).parameters
    assert params["unit_notional"].default == 250.0
    assert list(inspect.signature(bankroll_available).parameters) == [
        "bankroll",
        "cash",
        "reserved",
    ]


def test_paper_stake_whole_units_only():
    assert paper_stake("f", "q", 0.56, units=2).notional == 500.0
    assert paper_stake("f", "q", 0.425, unit_notional=150.0).notional == 150.0
    assert paper_stake("f", "q", 0.56, currency="USDC").currency == "USDC"
    for bad_units in (0, -1, 1.5, 2.5):
        with pytest.raises(ValueError):
            paper_stake("f", "q", 0.56, units=bad_units)
    for bad_price in (0.0, -0.1, 1.01):
        with pytest.raises(ValueError):
            paper_stake("f", "q", bad_price)
    with pytest.raises(ValueError):
        paper_stake("f", "q", 0.56, unit_notional=0.0)


def test_bankroll_available_round23_context():
    # r23 bankroll_context: bankroll 10780.73, cash 7045.33, 3 x $250
    # reserved -> 6295.33 free.
    assert bankroll_available(10780.73, 7045.33, 750.0) == pytest.approx(6295.33)
    assert bankroll_available(10780.73, 7045.33, 0.0) == pytest.approx(7045.33)
    # over-reserved never goes negative.
    assert bankroll_available(10780.73, 500.0, 750.0) == 0.0
    # an inconsistent cash > bankroll is capped by the bankroll.
    assert bankroll_available(1000.0, 5000.0, 0.0) == pytest.approx(1000.0)
    # negative reservations are ignored, not added.
    assert bankroll_available(1000.0, 5000.0, -100.0) == pytest.approx(1000.0)


# ---------------------------------------------------------------------------
# Sizing tiers
# ---------------------------------------------------------------------------


def test_sizing_tier_full_edge_default():
    tier = sizing_tier()
    assert tier.tier == TIER_FULL_EDGE
    assert tier_notional(tier) == FULL_EDGE_NOTIONAL_USD == 250.0
    confirmed = sizing_tier(market_class="standard", lineup_confirmation=1.0)
    assert confirmed.tier == TIER_FULL_EDGE
    assert tier_notional(confirmed, lineup_confirmation=1.0) == 250.0


def test_sizing_tier_marginal_domestic_ml_fragile():
    tier = sizing_tier(market_class=DOMESTIC_ML_CLASS, fragile_pass=True)
    assert tier.tier == TIER_MARGINAL
    assert tier_notional(tier) == MARGINAL_NOTIONAL_USD == 150.0
    # MARGINAL dominates even with a fully confirmed lineup.
    fixed = sizing_tier(
        market_class=DOMESTIC_ML_CLASS, fragile_pass=True, lineup_confirmation=1.0
    )
    assert fixed.tier == TIER_MARGINAL and tier_notional(fixed) == 150.0
    # the fragile tier needs BOTH halves of the condition.
    assert sizing_tier(market_class=DOMESTIC_ML_CLASS, fragile_pass=False).tier == TIER_FULL_EDGE
    assert sizing_tier(market_class="standard", fragile_pass=True).tier == TIER_FULL_EDGE


def test_sizing_tier_early_entry_scales_with_lineup_confirmation():
    predicted = sizing_tier(lineup_confirmation=0.0)
    assert predicted.tier == TIER_EARLY_ENTRY
    assert EARLY_ENTRY_MIN_NOTIONAL_USD == 150.0
    assert EARLY_ENTRY_MAX_NOTIONAL_USD == 250.0
    assert tier_notional(predicted, lineup_confirmation=0.0) == 150.0
    half = sizing_tier(lineup_confirmation=0.5)
    assert tier_notional(half, lineup_confirmation=0.5) == 200.0
    quarter = sizing_tier(lineup_confirmation=0.25)
    assert tier_notional(quarter, lineup_confirmation=0.25) == 175.0
    confirmed = sizing_tier(lineup_confirmation=1.0)
    assert confirmed.tier == TIER_FULL_EDGE  # full confirmation graduates
    # out-of-range confirmation is a data error
    with pytest.raises(ValueError):
        sizing_tier(lineup_confirmation=1.5)
    with pytest.raises(ValueError):
        sizing_tier(lineup_confirmation=-0.1)
    # clamping inside tier_notional keeps the stake inside the band
    assert tier_notional(predicted, lineup_confirmation=7.0) == 250.0
    assert tier_notional(predicted, lineup_confirmation=-3.0) == 150.0


def test_tier_notional_unknown_tier_rejected():
    bogus = dataclasses.replace(sizing_tier(), tier="NOPE")
    with pytest.raises(ValueError):
        tier_notional(bogus)


# ---------------------------------------------------------------------------
# Team caps (r19 crypto $1,900 pattern)
# ---------------------------------------------------------------------------


def test_team_cap_r19_at_cap_monitoring():
    # r19: "team AT CAP $1,870/$1,900" -> hold, do not add.
    status = team_cap_status(1870.0)
    assert status.committed == 1870.0
    assert status.cap == 1900.0
    assert status.remaining == pytest.approx(30.0)
    assert status.at_cap is True  # one more $250 unit does not fit
    assert status.allows(250.0) is False
    assert team_add_allowed(1870.0, 250.0) is False
    assert status.allows(30.0) is True


def test_team_cap_boundaries_and_parameterization():
    exact = team_cap_status(1650.0)  # 1650 + 250 == 1900 exactly
    assert exact.at_cap is False
    assert exact.allows(250.0) is True
    assert team_add_allowed(1650.0, 250.0) is True
    assert team_add_allowed(1650.0, 251.0) is False
    small = team_cap_status(501.0, cap=600.0, unit_notional=100.0)
    assert small.at_cap is True  # 501 + 100 > 600
    assert small.remaining == pytest.approx(99.0)
    exact_small = team_cap_status(500.0, cap=600.0, unit_notional=100.0)
    assert exact_small.at_cap is False  # 500 + 100 == 600 fits exactly
    ok = team_cap_status(400.0, cap=600.0, unit_notional=100.0)
    assert ok.at_cap is False and ok.allows(200.0) is True
    with pytest.raises(ValueError):
        team_cap_status(-1.0)
    with pytest.raises(ValueError):
        team_cap_status(0.0, cap=0.0)
    with pytest.raises(ValueError):
        team_cap_status(0.0, unit_notional=-5.0)


# ---------------------------------------------------------------------------
# Held-fixture correlation; nested bets count as one risk unit
# ---------------------------------------------------------------------------


def test_side_direction_families():
    assert side_direction("Over/Yes(side0)") == DIRECTION_LONG
    assert side_direction("YES (Sassuolo win)") == DIRECTION_LONG
    assert side_direction("yes") == DIRECTION_LONG
    assert side_direction("Under/No(side1)") == DIRECTION_SHORT
    assert side_direction("NO") == DIRECTION_SHORT
    assert side_direction("draw") == DIRECTION_UNKNOWN
    assert side_direction("") == DIRECTION_UNKNOWN


def test_held_fixture_no_same_direction_adds():
    blocked = held_fixture_add_allowed(["Over/Yes(side0)"], "Over/Yes(side0)")
    assert isinstance(blocked, CorrelationDecision)
    assert blocked.allowed is False
    assert "correlation" in blocked.reason
    opposite = held_fixture_add_allowed(["Over/Yes(side0)"], "Under/No(side1)")
    assert opposite.allowed is True
    empty = held_fixture_add_allowed([], "Over/Yes(side0)")
    assert empty.allowed is True
    # unclassifiable held sides block conservatively.
    unknown = held_fixture_add_allowed(["draw"], "Over/Yes(side0)")
    assert unknown.allowed is False


def test_held_fixture_unclassifiable_prospective_side_blocks():
    # codex review finding 7: a prospective side that cannot be classified
    # (e.g. "draw") cannot be established as opposite to a held side, so it
    # must get the same conservative block as an unclassifiable held side.
    blocked = held_fixture_add_allowed(["Over/Yes(side0)"], "draw")
    assert isinstance(blocked, CorrelationDecision)
    assert blocked.allowed is False
    assert "correlation" in blocked.reason
    # the conservative block holds against any classifiable held direction.
    assert held_fixture_add_allowed(["Under/No(side1)"], "draw").allowed is False
    # unknown held direction still blocks (classification or no classification).
    assert held_fixture_add_allowed(["draw"], "Over/Yes(side0)").allowed is False
    # both sides unclassifiable also blocks.
    assert held_fixture_add_allowed(["draw"], "tie").allowed is False
    # a known-opposite add is still allowed.
    assert held_fixture_add_allowed(["Over/Yes(side0)"], "Under/No(side1)").allowed is True
    # with nothing held there is no held-fixture correlation rule to violate.
    assert held_fixture_add_allowed([], "draw").allowed is True


def test_nested_bets_count_as_one_risk_unit():
    fixture = "AFC Bournemouth vs. Leeds United FC"
    nested = [
        (fixture, "Over/Yes(side0)"),  # O2.5 Over
        (fixture, "Over/Yes(side0)"),  # O3.5 Over (nested)
        {"fixture": fixture, "side": "YES"},  # team-total Over (nested)
    ]
    assert count_risk_units(nested) == 1
    assert risk_unit_keys(nested) == ((fixture, DIRECTION_LONG),)
    with_hedge = nested + [(fixture, "Under/No(side1)")]
    assert count_risk_units(with_hedge) == 2
    other_fixture = [("Coventry City FC vs. Sunderland AFC", "Over/Yes(side0)")]
    assert count_risk_units(nested + other_fixture) == 2
    with pytest.raises(ValueError):
        risk_unit_keys([{"fixture": "f"}])
    # object-style positions also extract fixture/side attributes.
    from types import SimpleNamespace

    obj = SimpleNamespace(fixture=fixture, side="Over/Yes(side0)")
    assert count_risk_units([obj]) == 1


# ---------------------------------------------------------------------------
# Bankroll identity and exit-aware record accounting
# ---------------------------------------------------------------------------


def _synthetic_ledger() -> list[SettledPosition]:
    return [
        SettledPosition("#A", STATUS_WON, 250.0, 471.70),
        SettledPosition("#B", STATUS_LOST, 250.0, 0.0),
        SettledPosition("#C", STATUS_EXITED, 250.0, 190.00),
        SettledPosition("#D", STATUS_OPEN, 250.0, 0.0),
    ]


def test_expected_cash_identity():
    # cash = 10000 - sum(stakes) + sum(realized payoffs)
    assert INITIAL_BANKROLL_USD == 10000.0
    stakes = [250.0, 250.0, 250.0, 250.0]
    payoffs = [471.70, 0.0, 190.00]  # WON payoff + EXITED sale; open pays nothing
    assert expected_cash(stakes, payoffs) == pytest.approx(9661.70)
    assert expected_cash([], []) == 10000.0
    assert expected_cash([250.0], [500.0], initial=100.0) == pytest.approx(350.0)


def test_check_bankroll_identity_flags_mismatch():
    stakes = [250.0, 250.0, 250.0, 250.0]
    payoffs = [471.70, 0.0, 190.00]
    ok = check_bankroll_identity(9661.70, stakes, payoffs)
    assert isinstance(ok, BankrollCheck)
    assert ok.ok is True
    assert ok.expected_cash == pytest.approx(9661.70)
    assert ok.difference == pytest.approx(0.0)
    drift = check_bankroll_identity(9661.00, stakes, payoffs)
    assert drift.ok is False
    assert drift.difference == pytest.approx(-0.70)
    # sub-half-cent rounding differences stay ok at the default tolerance.
    tiny = check_bankroll_identity(9661.696, stakes, payoffs)
    assert tiny.ok is True
    assert tiny.tolerance == 0.005


def test_settle_record_exit_accounting():
    summary = settle_record(_synthetic_ledger())
    assert isinstance(summary, RecordSummary)
    # EXITED excluded from W/L ...
    assert summary.wins == 1 and summary.losses == 1 and summary.exits == 1
    assert summary.open_positions == 1
    assert summary.win_rate == pytest.approx(0.5)
    # ... but included in PnL: (471.7-250) + (-250) + (190-250) + 0.
    assert summary.pnl == pytest.approx(-88.30)
    assert summary.staked_total == pytest.approx(1000.0)
    assert summary.payoff_total == pytest.approx(661.70)


def test_settle_record_no_settled_wl_gives_null_win_rate():
    summary = settle_record(
        [SettledPosition("#X", STATUS_OPEN, 250.0), SettledPosition("#Y", STATUS_EXITED, 250.0, 190.0)]
    )
    assert summary.win_rate is None
    assert summary.wins == 0 and summary.losses == 0
    assert summary.exits == 1
    assert summary.pnl == pytest.approx(-60.0)


def test_settle_record_mapping_inputs_and_bad_status():
    rows = [
        {"position_id": "#A", "status": "won", "stake": 250.0, "proceeds": 500.0},
        {"position_id": "#B", "status": "LOST", "stake": 250.0},
    ]
    assert settle_record(rows).wins == 1
    with pytest.raises(ValueError):
        settle_record([{"position_id": "#Z", "status": "VOID", "stake": 10.0}])


def test_position_pnl_open_is_unrealized():
    assert position_pnl(SettledPosition("#D", STATUS_OPEN, 250.0, 999.0)) == 0.0
    assert position_pnl(SettledPosition("#C", STATUS_EXITED, 250.0, 190.0)) == pytest.approx(-60.0)
    assert position_pnl(SettledPosition("#A", STATUS_WON, 250.0, 471.7)) == pytest.approx(221.7)
    assert position_pnl(SettledPosition("#B", STATUS_LOST, 250.0, 0.0)) == pytest.approx(-250.0)


def test_bankroll_identity_composes_with_settle_record():
    positions = _synthetic_ledger()
    summary = settle_record(positions)
    # open stakes stay deducted; only realized payoffs return as cash.
    stakes = [p.stake for p in positions]
    cash = expected_cash(stakes, _realized_payoffs(summary, positions))
    check = check_bankroll_identity(cash, stakes, _realized_payoffs(summary, positions))
    assert check.ok is True
    reserved = 750.0
    assert bankroll_available(cash + 3735.40, cash, reserved) == pytest.approx(8911.70)


def _realized_payoffs(summary: RecordSummary, positions) -> list[float]:
    assert summary.payoff_total == pytest.approx(sum(p.proceeds for p in positions if p.status != STATUS_OPEN))
    return [p.proceeds for p in positions if p.status != STATUS_OPEN]


# ---------------------------------------------------------------------------
# Non-finite amount rejection (codex review 2026-11-03, major 2)
#
# NaN compares False against every bound, so an unvalidated amount
# silently disappeared into the clamp: bankroll_available(10000, 1000,
# nan) returned 1000 (the NaN reserved dropped via max(0.0, nan) ==
# 0.0), overstating spendable cash. All monetary inputs now raise
# ValueError BEFORE any clamping/comparison/rounding; booleans (an int
# subclass: float(True) == $1) are rejected too.
# ---------------------------------------------------------------------------

def test_bankroll_available_rejects_non_finite_amounts():
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            bankroll_available(bad, 1000.0, 0.0)
        with pytest.raises(ValueError):
            bankroll_available(10000.0, bad, 0.0)
        with pytest.raises(ValueError):
            bankroll_available(10000.0, 1000.0, bad)
    # The frozen defect: a NaN reserved must NOT silently return the
    # unreserved amount.
    with pytest.raises(ValueError):
        bankroll_available(10000.0, 1000.0, float("nan"))
    # bool is an int subclass but not a monetary amount.
    for boolean in (True, False):
        with pytest.raises(ValueError):
            bankroll_available(boolean, 1000.0, 0.0)
        with pytest.raises(ValueError):
            bankroll_available(10000.0, boolean, 0.0)
        with pytest.raises(ValueError):
            bankroll_available(10000.0, 1000.0, boolean)


def test_paper_stake_rejects_non_finite_amounts():
    for bad_price in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            paper_stake("f", "q", bad_price)
    for bad_unit in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            paper_stake("f", "q", 0.56, unit_notional=bad_unit)
    # Non-finite unit counts raise ValueError (inf used to escape as
    # OverflowError from int()).
    with pytest.raises(ValueError):
        paper_stake("f", "q", 0.56, units=float("nan"))
    with pytest.raises(ValueError):
        paper_stake("f", "q", 0.56, units=float("inf"))
    # bool is an int subclass but neither a price nor a unit count.
    with pytest.raises(ValueError):
        paper_stake("f", "q", True)
    with pytest.raises(ValueError):
        paper_stake("f", "q", 0.56, unit_notional=True)
    with pytest.raises(ValueError):
        paper_stake("f", "q", 0.56, units=True)


def test_team_cap_status_rejects_non_finite_amounts():
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            team_cap_status(bad)
        with pytest.raises(ValueError):
            team_cap_status(100.0, cap=bad)
        with pytest.raises(ValueError):
            team_cap_status(100.0, unit_notional=bad)
    with pytest.raises(ValueError):
        team_cap_status(True)
    with pytest.raises(ValueError):
        team_cap_status(100.0, cap=True)
