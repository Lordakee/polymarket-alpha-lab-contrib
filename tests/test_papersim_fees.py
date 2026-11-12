"""FX-06 tests: category taker-fee schedule, fee arithmetic, the scan
classification mirror and market-metadata precedence.

Pins (fix-list FX-06 acceptance):
- one test per category with the official-docs rate as of
  ``FEE_SCHEDULE_AS_OF`` (docs re-read at implementation time, values
  unchanged);
- unknown categories raise (never default to the sports rate);
- the table is read-only (MappingProxyType, like the FX-14 constants);
- ``fee_per_share`` equals ``gates.fee_cost`` (the two doors to the
  per-share fee model cannot diverge);
- ``gates.FEE_RATE_CRYPTO`` / ``gates.FEE_RATE_SPORTS`` stay frozen and
  equal the table's ``crypto`` / ``sports`` rows;
- the scan classification mirror puts gold/equity rows recorded under
  ``crypto_touch`` at the SPORTS rate (team rule, V-6 evidence run).
"""

from __future__ import annotations

from types import MappingProxyType

import pytest

from polymarket_alpha_lab.papersim import fees, gates


def test_schedule_provenance_pins_as_of_and_source():
    assert fees.FEE_SCHEDULE_AS_OF == "2026-11-12"
    assert fees.FEE_SCHEDULE_SOURCE == "https://docs.polymarket.com/trading/fees"


@pytest.mark.parametrize(
    "category,expected_rate",
    [
        ("crypto", 0.07),
        ("sports", 0.05),
        ("finance", 0.04),
        ("politics", 0.04),
        ("economics", 0.05),
        ("culture", 0.05),
        ("weather", 0.05),
        ("other", 0.05),
        ("mentions", 0.04),
        ("tech", 0.04),
        ("geopolitics", 0.0),
        ("combos", 0.05),
    ],
)
def test_every_category_rate_matches_official_docs(category, expected_rate):
    # FX-06 acceptance: one test per category, values from the official
    # docs as of FEE_SCHEDULE_AS_OF.
    assert fees.TAKER_FEE_RATES[category] == expected_rate
    assert fees.taker_fee_rate(category) == expected_rate


def test_taker_fee_rate_normalizes_case_and_whitespace():
    assert fees.taker_fee_rate(" Crypto ") == 0.07
    assert fees.taker_fee_rate("SPORTS") == 0.05


@pytest.mark.parametrize("bad", ["sport", "cryptoc", "", "  ", "crypto touch", "sports*"])
def test_taker_fee_rate_unknown_category_raises_without_sports_default(bad):
    with pytest.raises(ValueError, match="unknown fee category"):
        fees.taker_fee_rate(bad)


def test_fee_table_is_read_only():
    assert isinstance(fees.TAKER_FEE_RATES, MappingProxyType)
    with pytest.raises(TypeError):
        fees.TAKER_FEE_RATES["crypto"] = 0.10
    with pytest.raises(TypeError):
        del fees.TAKER_FEE_RATES["sports"]
    with pytest.raises(AttributeError):
        fees.TAKER_FEE_RATES.update({"crypto": 0.10})


@pytest.mark.parametrize(
    "price,rate",
    [
        (0.56, 0.05),
        (0.56, 0.07),
        (0.5, 0.05),
        (0.23, 0.05),
        (0.985, 0.05),
        (0.07, 0.05),
        (0.515, 0.07),
        (0.5, 0.0),
        (0.1, 0.04),
        (0.92, 0.04),
    ],
)
def test_fee_per_share_equals_gates_fee_cost(price, rate):
    assert fees.fee_per_share(price, rate) == gates.fee_cost(price, rate)


def test_entry_fee_official_and_simplified_forms_agree():
    # FX-01 hand case: $250 @ 0.56, sports rate -> shares 446.4286,
    # fee 250 * 0.05 * 0.44 = 5.50.
    rate = fees.taker_fee_rate("sports")
    assert rate == 0.05
    official = (250.0 / 0.56) * fees.fee_per_share(0.56, rate)
    simplified = 250.0 * rate * (1.0 - 0.56)
    assert official == pytest.approx(5.50, abs=1e-9)
    assert simplified == pytest.approx(5.50, abs=1e-9)
    assert fees.entry_fee(250.0, 0.56, rate) == pytest.approx(5.50, abs=1e-9)
    assert 250.0 / 0.56 == pytest.approx(446.4286, abs=1e-4)


def test_entry_fee_crypto_rate_and_zero_rate():
    assert fees.entry_fee(250.0, 0.515, fees.taker_fee_rate("crypto")) == pytest.approx(
        750.0 * 0.07 * (1.0 - 0.515) * (250.0 / 750.0), abs=1e-9
    )
    # Geopolitics is fee-free: rate 0 is a valid table value.
    assert fees.entry_fee(250.0, 0.56, fees.taker_fee_rate("geopolitics")) == 0.0


@pytest.mark.parametrize(
    "stake,price,rate",
    [
        (0.0, 0.56, 0.05),
        (-250.0, 0.56, 0.05),
        (float("nan"), 0.56, 0.05),
        (250.0, 0.0, 0.05),
        (250.0, 1.0, 0.05),
        (250.0, float("inf"), 0.05),
        (250.0, 0.56, -0.01),
        (250.0, 0.56, float("nan")),
        (250.0, 0.56, float("inf")),
    ],
)
def test_entry_fee_rejects_bad_inputs(stake, price, rate):
    with pytest.raises(ValueError):
        fees.entry_fee(stake, price, rate)


def test_exit_fee_hand_case_and_bounds():
    # FX-01 exit hand case: 400 @ 0.69 -> shares 579.7101; sell at
    # 0.585 at the sports rate -> 579.7101 * 0.05 * 0.585 * 0.415 = 7.04.
    shares = 400.0 / 0.69
    assert shares == pytest.approx(579.7101, abs=1e-4)
    assert fees.exit_fee(shares, 0.585, 0.05) == pytest.approx(7.04, abs=0.005)
    assert fees.exit_fee(shares, 0.0, 0.05) == 0.0
    assert fees.exit_fee(shares, 1.0, 0.05) == 0.0
    assert fees.exit_fee(shares, 0.585, 0.0) == 0.0


@pytest.mark.parametrize(
    "shares,exit_price,rate",
    [
        (0.0, 0.585, 0.05),
        (-10.0, 0.585, 0.05),
        (float("nan"), 0.585, 0.05),
        (579.71, -0.01, 0.05),
        (579.71, 1.01, 0.05),
        (579.71, float("nan"), 0.05),
        (579.71, 0.585, -0.01),
        (579.71, 0.585, float("inf")),
    ],
)
def test_exit_fee_rejects_bad_inputs(shares, exit_price, rate):
    with pytest.raises(ValueError):
        fees.exit_fee(shares, exit_price, rate)


@pytest.mark.parametrize(
    "team,market_type,expected_category,expected_rate",
    [
        ("crypto_eth", "crypto_touch", "crypto", 0.07),
        ("crypto_btc", "crypto_daily", "crypto", 0.07),
        # Scan-rule edges: gold and equity-index rows recorded under
        # market_type 'crypto_touch' are SPORTS-rate (team rule, V-6).
        ("commodities_gold", "crypto_touch", "sports", 0.05),
        ("equity_indices", "crypto_touch", "sports", 0.05),
        ("sports_soccer", "ou_over", "sports", 0.05),
        ("sports_other", "spread", "sports", 0.05),
        ("politics", "election", "sports", 0.05),
        ("macro_rates", "macro", "sports", 0.05),
        ("econ_commodities", "commodity_touch", "sports", 0.05),
        ("ent_tech", "market_cap", "sports", 0.05),
        (" Crypto_ETH ", "crypto_touch", "crypto", 0.07),
    ],
)
def test_scan_classification_mirrors_the_scan_team_rule(
    team, market_type, expected_category, expected_rate
):
    category = fees.scan_fee_category(team, market_type)
    assert category == expected_category
    assert fees.taker_fee_rate(category) == expected_rate


def test_scan_classification_requires_a_team():
    with pytest.raises(ValueError, match="team"):
        fees.scan_fee_category("", "crypto_touch")
    with pytest.raises(ValueError, match="team"):
        fees.scan_fee_category(None, "crypto_touch")


def test_gates_frozen_fee_constants_equal_table_rows():
    # FX-06: gates.py keeps its two constants; tests pin them equal to
    # the schedule so the frozen book and the table cannot diverge.
    assert gates.FEE_RATE_CRYPTO == fees.TAKER_FEE_RATES["crypto"] == 0.07
    assert gates.FEE_RATE_SPORTS == fees.TAKER_FEE_RATES["sports"] == 0.05


def test_market_metadata_rate_matches_table_and_is_returned():
    assert (
        fees.resolve_taker_fee_rate("sports", market_rate=0.05)
        == fees.TAKER_FEE_RATES["sports"]
    )
    assert fees.resolve_taker_fee_rate("sports") == 0.05
    assert (
        fees.resolve_taker_fee_rate("geopolitics", market_rate=0.0)
        == fees.TAKER_FEE_RATES["geopolitics"]
    )


@pytest.mark.parametrize("category,market_rate", [("sports", 0.07), ("crypto", 0.05), ("finance", 0.05)])
def test_market_metadata_disagreement_refuses_and_alarms(category, market_rate):
    with pytest.raises(ValueError, match="needs updating"):
        fees.resolve_taker_fee_rate(category, market_rate=market_rate)


def test_market_metadata_rate_must_be_finite_non_negative():
    for bad in (-0.01, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            fees.resolve_taker_fee_rate("sports", market_rate=bad)
