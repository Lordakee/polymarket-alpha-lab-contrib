"""WP-P1 W2 tests: r19 crypto model port (touch, terminal, conservative edges).

Unit invariants plus the frozen r19 regression anchors from
``tests/fixtures/papersim/regression_r19_crypto.json``:

- (b) reflection identity: at zero log drift ``p_touch == 2 * p_terminal``
  (both barrier directions, to 1e-12), and it must discriminate: the
  drifted convention B violates it.
- (c) per-side conservative orientation in both directions: conservative
  YES is ``min(pA, pB)``, conservative NO is ``1 - max(pA, pB)``, and the
  pre-fix orientation (``max`` for YES on touch-down markets) overstates
  YES fair value by the full A/B spread (~3.4c on the ETH-2000 anchor).
- (d) YES/NO complementarity: each convention's YES/NO pair is exactly
  complementary, while the conservative pair deliberately is not (its
  deficit is exactly the A/B spread).
- regression: the frozen closes below are the complete 6h bar closes as
  of the r19 scan timestamp (2026-10-26T12:51:40Z, the value model19.py
  used as ``NOW``), read from ``round19/raw/{eth,btc}_candles.json``;
  the estimator must reproduce the frozen window tables bit-exactly, and
  the A/B touch anchors must reproduce within 1e-4.
- FX-13 (audit P-8, 2026-11-12): at-expiry market direction is explicit
  via ``terminal_yes_probability`` / ``conservative_edges_for_terminal``
  with ``yes_when="below"|"above"``; ``below`` is the identity transform
  (existing behavior unchanged), ``above`` is the exact complement, and
  the two directions mirror under symmetric quotes.
- FX-14 (audit P-11, 2026-11-12): the frozen r19 window table
  ``VOL_WINDOW_BARS`` is a read-only mapping view.
"""

from __future__ import annotations

import datetime
import json
import math
from pathlib import Path

import pytest

from polymarket_alpha_lab.papersim import crypto_model
from polymarket_alpha_lab.papersim.crypto_model import (
    TerminalYesProbability,
    TouchProbability,
    conservative_edges,
    conservative_edges_for_terminal,
    realized_vol_daily,
    realized_vol_windows,
    terminal_probability,
    terminal_yes_probability,
    touch_probability,
)

FIXTURES = Path(__file__).parent / "fixtures" / "papersim"

ETH_SPOT = 2326.84
ETH_SIG30 = 0.02430307766195731
BTC_SPOT = 80342.38
BTC_SIG30 = 0.01583874457257652
FIXTURE_HORIZON_HOURS = 1595.12

# Complete 6h bar closes as of the r19 scan timestamp (2026-10-26T12:51:40Z),
# frozen from round19/raw/{eth,btc}_candles.json; 360 bars covers the 87d
# window (348 bars) with slicing margin.
ETH_CLOSES_360: list[float] = [
    1901.89, 1922.23, 1912.54, 1915.26, 1916.16, 1910.72,
    1906.34, 1923.22, 1920.88, 1918.31, 1906.13, 1884.26,
    1875.01, 1862.6, 1867.59, 1866.9, 1862.07, 1844.94,
    1876.33, 1852.58, 1868.65, 1885.36, 1859.88, 1839.89,
    1868.84, 1860.5, 1864.42, 1872.89, 1869.53, 1869.75,
    1873.46, 1868.92, 1916.75, 1908.9, 1914.34, 1907.77,
    1914.08, 1904.1, 1901.58, 1916.33, 1912.45, 1914.18,
    1917.56, 1920.99, 1923.85, 1916.74, 1914.46, 1919.23,
    1923.11, 1910.65, 1923.17, 1920.42, 1873.7, 1873.16,
    1874.03, 1892.97, 1864.69, 1882.59, 1891.71, 1915.57,
    1888.14, 1879.81, 1895.81, 1880.39, 1876.98, 1886.15,
    1884.07, 1878.2, 1878.57, 1882.2, 1880.66, 1879.49,
    1884.49, 1882.64, 1879.81, 1880.94, 1885.17, 1876.0,
    1899.65, 1904.46, 1908.91, 1913.6, 1895.63, 1903.11,
    1911.38, 1917.85, 1910.27, 1923.06, 2091.02, 2252.8,
    2248.36, 2296.58, 2344.26, 2326.82, 2368.42, 2370.47,
    2423.61, 2516.3, 2439.95, 2423.93, 2426.32, 2422.6,
    2372.99, 2433.68, 2440.12, 2463.41, 2448.92, 2494.18,
    2468.97, 2482.31, 2508.73, 2477.91, 2471.03, 2442.64,
    2464.92, 2463.09, 2460.84, 2506.78, 2496.63, 2501.73,
    2518.07, 2510.94, 2493.32, 2505.1, 2443.79, 2442.8,
    2438.62, 2435.87, 2450.74, 2457.67, 2456.36, 2460.41,
    2505.73, 2416.88, 2435.99, 2446.35, 2475.42, 2467.65,
    2484.54, 2459.18, 2418.18, 2418.57, 2422.53, 2381.88,
    2393.77, 2391.92, 2404.81, 2407.2, 2500.49, 2507.51,
    2509.25, 2523.02, 2445.36, 2455.85, 2450.93, 2453.67,
    2481.01, 2480.34, 2513.5, 2501.93, 2491.25, 2514.48,
    2504.8, 2489.15, 2495.42, 2490.16, 2473.38, 2474.76,
    2488.07, 2485.06, 2496.56, 2501.0, 2493.62, 2468.13,
    2482.13, 2462.21, 2466.08, 2438.27, 2468.84, 2458.27,
    2566.72, 2516.43, 2511.7, 2536.17, 2525.91, 2525.93,
    2522.52, 2481.05, 2504.89, 2477.1, 2516.28, 2509.21,
    2533.37, 2515.75, 2496.53, 2476.41, 2441.21, 2398.26,
    2407.37, 2422.61, 2390.77, 2418.26, 2437.2, 2442.61,
    2462.85, 2447.28, 2480.62, 2508.12, 2607.44, 2612.14,
    2628.93, 2639.67, 2645.41, 2632.69, 2578.31, 2579.08,
    2626.41, 2645.21, 2665.41, 2725.38, 2743.26, 2776.19,
    2733.54, 2742.6, 2753.9, 2753.63, 2757.8, 2727.96,
    2668.03, 2684.71, 2682.52, 2647.68, 2669.72, 2688.05,
    2679.94, 2717.53, 2685.91, 2691.61, 2686.47, 2689.49,
    2690.57, 2696.33, 2705.03, 2709.8, 2691.36, 2688.65,
    2651.63, 2669.0, 2695.71, 2688.71, 2676.54, 2732.47,
    2673.76, 2677.98, 2675.09, 2697.8, 2682.72, 2686.01,
    2717.96, 2706.56, 2701.05, 2706.42, 2720.65, 2746.63,
    2684.49, 2668.59, 2677.74, 2684.55, 2689.01, 2687.23,
    2694.74, 2699.99, 2702.14, 2726.94, 2706.48, 2718.39,
    2705.63, 2709.98, 2699.56, 2714.09, 2699.28, 2697.49,
    2620.9, 2578.94, 2551.63, 2574.14, 2561.65, 2537.43,
    2418.25, 2474.8, 2491.18, 2506.61, 2488.42, 2487.7,
    2498.17, 2497.42, 2508.32, 2506.52, 2504.63, 2506.58,
    2538.41, 2536.94, 2565.3, 2546.21, 2512.14, 2447.17,
    2531.69, 2500.86, 2501.12, 2497.95, 2503.72, 2504.75,
    2431.81, 2421.6, 2349.6, 2363.31, 2446.55, 2442.08,
    2447.25, 2477.77, 2411.92, 2423.54, 2428.81, 2434.2,
    2411.63, 2402.82, 2411.44, 2418.23, 2369.94, 2410.31,
    2431.41, 2420.04, 2398.4, 2408.01, 2396.84, 2384.68,
    2450.58, 2449.2, 2439.12, 2469.37, 2515.0, 2473.76,
    2438.55, 2400.34, 2380.01, 2389.14, 2404.17, 2403.04,
    2409.59, 2387.6, 2378.0, 2365.74, 2323.25, 2358.82,
    2353.45, 2339.85, 2358.73, 2329.87, 2327.46, 2334.05,
]

BTC_CLOSES_360: list[float] = [
    63685.88, 63915.0, 64067.32, 64507.54, 64269.83, 63984.28,
    64033.89, 64788.0, 64872.0, 64780.02, 64363.06, 63805.51,
    63245.44, 62887.88, 63020.0, 63076.0, 62708.07, 62823.64,
    63453.27, 63031.99, 63300.28, 63570.0, 62827.17, 62560.01,
    63906.0, 63520.0, 63818.48, 63926.0, 63972.09, 64106.56,
    64330.87, 64075.28, 64770.0, 64665.23, 64908.09, 64622.09,
    64621.69, 64323.61, 64336.43, 65029.98, 64764.33, 64923.19,
    64995.39, 64967.35, 65119.75, 64962.6, 64801.58, 64950.0,
    65198.68, 64901.59, 65134.0, 65125.98, 63953.04, 63970.01,
    64000.0, 64389.57, 63607.88, 63600.0, 63849.94, 64240.04,
    63471.0, 63479.99, 63878.0, 63484.3, 63144.38, 63490.86,
    63379.83, 62868.83, 63013.69, 63043.56, 63089.0, 63022.01,
    63070.5, 63086.01, 63069.43, 63013.66, 63159.3, 62900.0,
    63520.18, 63631.1, 64325.99, 64532.1, 64242.76, 64351.19,
    64670.02, 64725.42, 64236.01, 64515.63, 68197.29, 69334.79,
    69406.54, 71927.07, 72737.5, 73025.15, 75472.73, 76722.32,
    77392.68, 78338.03, 77380.75, 77130.02, 77278.01, 77074.93,
    76053.37, 77311.02, 77176.41, 77734.0, 77149.4, 78443.65,
    78761.14, 78992.75, 80731.9, 79117.99, 79240.01, 78539.14,
    79085.98, 78487.26, 78442.83, 79023.75, 78912.55, 79477.67,
    80442.46, 80249.58, 79686.0, 79604.13, 77904.0, 77845.87,
    77632.53, 77584.67, 78100.0, 78230.0, 78127.71, 78166.0,
    79021.02, 77682.0, 78016.0, 78315.43, 78897.36, 78581.29,
    79179.99, 78098.97, 77265.79, 77439.0, 77651.07, 76828.76,
    77381.66, 77340.01, 77809.91, 77948.39, 81042.0, 81270.37,
    80996.15, 81224.86, 79472.22, 79660.77, 79577.53, 79609.28,
    80058.6, 79831.75, 79989.13, 79919.17, 79745.34, 80341.83,
    79759.47, 79420.16, 79185.73, 79112.01, 78578.0, 78430.01,
    78504.38, 78455.8, 78923.43, 79324.75, 78776.01, 78306.43,
    78536.71, 77840.8, 77328.72, 76568.72, 77252.86, 77036.12,
    77534.0, 77225.7, 77218.0, 77356.04, 77210.58, 77278.73,
    77322.01, 76792.32, 77328.94, 76842.01, 77611.79, 77776.0,
    78937.98, 78189.21, 77630.0, 76940.01, 76962.0, 75644.48,
    75962.01, 76250.0, 75768.01, 76206.01, 76333.88, 76482.0,
    76667.86, 76417.01, 77493.8, 78062.0, 81019.0, 80883.87,
    81040.01, 81302.63, 81464.01, 81249.99, 80494.31, 80493.2,
    81147.94, 81178.0, 81550.0, 84887.19, 85897.21, 86620.0,
    85397.37, 85986.62, 86570.24, 86208.56, 86496.01, 85649.95,
    84326.56, 84397.6, 83978.02, 83494.58, 84110.0, 84410.24,
    84194.01, 84582.64, 83785.11, 84099.99, 83919.69, 84176.0,
    84132.4, 84433.1, 84478.06, 84898.0, 84574.0, 84472.0,
    83184.01, 83082.54, 83880.33, 83500.01, 83431.02, 84358.01,
    83078.01, 83663.66, 83384.0, 83915.16, 84031.46, 83623.6,
    84291.48, 83905.76, 84908.01, 84880.05, 86002.01, 86424.85,
    84774.75, 84518.01, 84652.09, 84672.01, 85012.0, 84753.56,
    84912.01, 85309.46, 85319.53, 86530.0, 85767.57, 86216.0,
    85429.24, 85766.87, 85518.35, 86242.01, 85719.42, 85549.93,
    84332.85, 83740.15, 83158.99, 83321.81, 82684.01, 82506.01,
    80748.46, 81754.45, 82352.39, 83246.82, 82717.85, 82635.55,
    82844.01, 82879.71, 83118.0, 82988.36, 83054.66, 83164.0,
    83824.0, 83773.12, 84022.0, 83396.6, 82504.0, 81850.0,
    83681.87, 83360.01, 83095.88, 83169.0, 83466.04, 83465.94,
    81587.1, 81682.01, 80591.73, 80980.01, 82439.7, 82245.93,
    82162.86, 82640.73, 81217.13, 81615.64, 81574.99, 81576.33,
    81383.24, 81491.04, 81734.46, 82069.72, 81193.87, 82116.0,
    82756.38, 82356.86, 81936.0, 81938.4, 81724.0, 81504.32,
    82820.33, 83028.15, 82672.0, 83500.01, 84680.57, 84093.42,
    82816.5, 81750.01, 81211.93, 81416.09, 81850.0, 81726.1,
    81649.25, 81189.43, 80776.01, 80599.41, 80276.1, 80888.16,
    80607.65, 80580.97, 80796.0, 80154.09, 80263.32, 80416.01,
]


EXPECTED_ETH_WINDOWS = {
    "7d": 0.021511978251535887,
    "30d": 0.02430307766195731,
    "60d": 0.02385570964639212,
    "87d": 0.025755531794919153,
}
EXPECTED_BTC_WINDOWS = {
    "7d": 0.014135309851963835,
    "30d": 0.01583874457257652,
    "60d": 0.0171713845652564,
    "87d": 0.01827288888899947,
}


def _load_fixture() -> dict:
    return json.loads(
        (FIXTURES / "regression_r19_crypto.json").read_text(encoding="utf-8")
    )


def _r19_horizon_hours(fixture: dict, *, field: str) -> float:
    """Recompute the r19 ``T`` exactly as model19.py did.

    ``T = (Dec31_2359 - NOW).total_seconds() / 86400.0`` where ``NOW`` is
    the scan generation timestamp (``raw_scan_generated_at``: the value
    whose horizon reproduces the frozen 1595.12h). Returned in hours.
    """
    anchor = datetime.datetime.fromisoformat(fixture["anchor"][field])
    dec31 = datetime.datetime(
        2026, 12, 31, 23, 59, tzinfo=datetime.timezone.utc
    )
    return (dec31 - anchor).total_seconds() / 86400.0 * 24.0


def _eth2000_probs(horizon_hours: float = FIXTURE_HORIZON_HOURS) -> TouchProbability:
    return touch_probability(
        spot=ETH_SPOT,
        sigma_daily=ETH_SIG30,
        barrier=2000.0,
        horizon_hours=horizon_hours,
        asset="ETH",
    )


# ---------------------------------------------------------------------------
# Realized vol: estimator semantics + frozen r19 window tables
# ---------------------------------------------------------------------------


def test_realized_vol_daily_is_uncentered_rms_with_bar_scaling():
    closes = [100.0, 101.0, 102.01]  # two identical returns of ln(1.01)
    r = math.log(1.01)
    # RMS, not centered stdev: same-sign returns are vol, not zero drift
    # (a centered sample stdev of [r, r] would be exactly zero).
    assert realized_vol_daily(closes) == pytest.approx(2.0 * r, rel=1e-12)
    assert realized_vol_daily(closes) > 1e-3
    # sqrt(24 / bar_hours) daily scaling.
    assert realized_vol_daily(closes, bar_hours=1.0) == pytest.approx(
        math.sqrt(24.0) * r, rel=1e-12
    )
    assert realized_vol_daily(closes, bar_hours=12.0) == pytest.approx(
        math.sqrt(2.0) * r, rel=1e-12
    )


def test_realized_vol_daily_rejects_degenerate_inputs():
    with pytest.raises(ValueError):
        realized_vol_daily([100.0])
    with pytest.raises(ValueError):
        realized_vol_daily([100.0, 0.0])
    with pytest.raises(ValueError):
        realized_vol_daily([100.0, 101.0], bar_hours=0.0)


def test_realized_vol_windows_reproduce_frozen_r19_tables():
    eth = realized_vol_windows(ETH_CLOSES_360)
    btc = realized_vol_windows(BTC_CLOSES_360)
    assert eth == pytest.approx(EXPECTED_ETH_WINDOWS, rel=1e-12)
    assert btc == pytest.approx(EXPECTED_BTC_WINDOWS, rel=1e-12)
    fixture = _load_fixture()
    # The 30d signature column is the frozen fixture input, bit-exact.
    assert eth["30d"] == fixture["inputs"]["realized_vol_daily"]["ETH"]["30d"]
    assert btc["30d"] == fixture["inputs"]["realized_vol_daily"]["BTC"]["30d"]
    # Window slicing is r19-faithful: the 30d column cannot see bars older
    # than the window, and a short history degrades to all-available closes.
    trimmed = ETH_CLOSES_360[-120:]
    assert realized_vol_windows(trimmed)["30d"] == eth["30d"]
    assert realized_vol_windows(trimmed)["87d"] == realized_vol_daily(trimmed)


def test_vol_window_bars_is_read_only_view():
    # FX-14 (audit P-11): the frozen r19 window table is a read-only
    # mapping view; every mutation path raises TypeError.
    frozen = {"7d": 28, "30d": 120, "60d": 240, "87d": 348}
    assert crypto_model.VOL_WINDOW_BARS == frozen
    assert list(crypto_model.VOL_WINDOW_BARS) == ["7d", "30d", "60d", "87d"]
    with pytest.raises(TypeError):
        crypto_model.VOL_WINDOW_BARS["7d"] = 29
    with pytest.raises(TypeError):
        crypto_model.VOL_WINDOW_BARS["90d"] = 360
    with pytest.raises(TypeError):
        del crypto_model.VOL_WINDOW_BARS["7d"]
    # Mutating methods are absent from the read-only view (mappingproxy
    # implements only the Mapping protocol), so they cannot even be
    # looked up -- as strong as raising on assignment.
    with pytest.raises(AttributeError):
        crypto_model.VOL_WINDOW_BARS.pop("7d")
    with pytest.raises(AttributeError):
        crypto_model.VOL_WINDOW_BARS.popitem()
    with pytest.raises(AttributeError):
        crypto_model.VOL_WINDOW_BARS.update({"7d": 29})
    with pytest.raises(AttributeError):
        crypto_model.VOL_WINDOW_BARS.setdefault("90d", 360)
    with pytest.raises(AttributeError):
        crypto_model.VOL_WINDOW_BARS.clear()
    # Nothing was mutated through the attempts, and the estimator still
    # reads the unchanged frozen table.
    assert crypto_model.VOL_WINDOW_BARS == frozen
    assert realized_vol_windows(ETH_CLOSES_360) == pytest.approx(
        EXPECTED_ETH_WINDOWS, rel=1e-12
    )


# ---------------------------------------------------------------------------
# Regression: frozen r19 A/B touch anchors
# ---------------------------------------------------------------------------


def test_r19_horizon_reproduces_frozen_hours():
    fixture = _load_fixture()
    anchor = datetime.datetime.fromisoformat(
        fixture["anchor"]["raw_scan_generated_at"]
    )
    assert anchor == datetime.datetime(
        2026, 10, 26, 12, 51, 40, tzinfo=datetime.timezone.utc
    )
    horizon_hours = _r19_horizon_hours(fixture, field="raw_scan_generated_at")
    for case in fixture["cases"].values():
        assert round(horizon_hours, 2) == case["horizon_hours"] == 1595.12
        assert round(horizon_hours / 24.0, 2) == case["horizon_days"] == 66.46
    # The fixture also carries a separate horizon_anchor field (12:58:37Z,
    # ~7 min after the scan timestamp). It yields 1595.01h, not the frozen
    # 1595.12h; the A/B anchors are insensitive to that gap (see below).
    alt_hours = _r19_horizon_hours(fixture, field="horizon_anchor")
    assert round(alt_hours, 2) == 1595.01
    case = fixture["cases"]["ETH-2000"]
    for hours in (horizon_hours, alt_hours):
        probs = _eth2000_probs(hours)
        assert abs(probs.convention_a - case["A"]) <= 1e-4
        assert abs(probs.convention_b - case["B"]) <= 1e-4


@pytest.mark.parametrize("case_key", ["ETH-2000", "ETH-2250", "BTC-65k"])
def test_touch_probability_r19_regression_anchors(case_key):
    fixture = _load_fixture()
    case = fixture["cases"][case_key]
    inputs = fixture["inputs"]
    spot = inputs["spot"][case["asset"]]
    sigma = inputs["realized_vol_daily"][case["asset"]][inputs["sig_table"]]
    horizon_hours = _r19_horizon_hours(fixture, field="raw_scan_generated_at")
    probs = touch_probability(
        spot=spot,
        sigma_daily=sigma,
        barrier=case["barrier"],
        horizon_hours=horizon_hours,
        asset=case["asset"],
    )
    assert probs.asset == case["asset"]
    assert probs.barrier == case["barrier"]
    assert probs.horizon_hours == horizon_hours
    assert abs(probs.convention_a - case["A"]) <= 1e-4
    assert abs(probs.convention_b - case["B"]) <= 1e-4
    # Down-barrier anchors: mean-flat B (log drift -sigma^2/2 pushes mass
    # down) touches more often than median-flat A.
    assert probs.convention_b > probs.convention_a


# ---------------------------------------------------------------------------
# Invariant (b): reflection identity at zero log drift
# ---------------------------------------------------------------------------


def test_reflection_identity_zero_log_drift():
    # Down barrier: p_touch == 2 * p_terminal(below), exactly.
    touch_dn = _eth2000_probs()
    term_dn = terminal_probability(
        spot=ETH_SPOT,
        sigma_daily=ETH_SIG30,
        barrier=2000.0,
        horizon_hours=FIXTURE_HORIZON_HOURS,
        asset="ETH",
    )
    assert touch_dn.convention_a == pytest.approx(
        2.0 * term_dn.convention_a, abs=1e-12
    )
    # Up barrier: p_touch == 2 * (1 - p_terminal(below)), exactly.
    touch_up = touch_probability(
        spot=ETH_SPOT,
        sigma_daily=ETH_SIG30,
        barrier=2450.0,
        horizon_hours=FIXTURE_HORIZON_HOURS,
        asset="ETH",
    )
    term_up = terminal_probability(
        spot=ETH_SPOT,
        sigma_daily=ETH_SIG30,
        barrier=2450.0,
        horizon_hours=FIXTURE_HORIZON_HOURS,
        asset="ETH",
    )
    assert touch_up.convention_a == pytest.approx(
        2.0 * (1.0 - term_up.convention_a), abs=1e-12
    )
    # The identity must discriminate drift: convention B (mu_log =
    # -sigma^2/2) violates it by a material margin on this anchor.
    assert abs(touch_dn.convention_b - 2.0 * term_dn.convention_b) > 1e-3


# ---------------------------------------------------------------------------
# Invariant (c): per-side conservative orientation, both directions
# ---------------------------------------------------------------------------


def test_conservative_orientation_touch_dn():
    probs = _eth2000_probs()
    low, high = min(probs.convention_a, probs.convention_b), max(
        probs.convention_a, probs.convention_b
    )
    spread = high - low
    # Conservative YES is min(pA, pB); conservative NO is 1 - max(pA, pB).
    edges = conservative_edges(probs, yes_ask=0.45, no_ask=0.56)
    assert edges.fair_yes == pytest.approx(low, abs=1e-15)
    assert edges.fair_no == pytest.approx(1.0 - high, abs=1e-15)
    assert edges.fair_no < 1.0 - low  # NO side is conservative too, not 1-min
    assert edges.edge_yes == pytest.approx(low - 0.45, abs=1e-15)
    assert edges.edge_no == pytest.approx((1.0 - high) - 0.56, abs=1e-15)
    # The OLD buggy orientation (max for YES on touch-down markets)
    # overstates YES fair value by the full A/B spread: ~3.4c on this
    # frozen anchor (A=0.4449, B=0.4788).
    assert spread == pytest.approx(0.0339, abs=5e-4)
    assert round(spread * 100.0, 1) == 3.4
    # Decision flip: an ask just under the overstated fair value would
    # signal a +0.4c YES edge under the old orientation while the fixed
    # orientation correctly shows a negative edge.
    yes_ask = high - 0.004
    fixed = conservative_edges(probs, yes_ask=yes_ask, no_ask=0.56)
    assert fixed.edge_yes == pytest.approx(low - yes_ask, abs=1e-15)
    assert fixed.edge_yes < 0.0 < high - yes_ask
    assert (high - yes_ask) - fixed.edge_yes == pytest.approx(spread, abs=1e-12)


def test_conservative_orientation_touch_up():
    # Up-touch market: YES is the touch-up event; conservative NO is
    # 1 - max(pA, pB) with the same orientation rules as touch_dn.
    probs = touch_probability(
        spot=ETH_SPOT,
        sigma_daily=ETH_SIG30,
        barrier=2450.0,
        horizon_hours=720.0,
        asset="ETH",
    )
    # Mean-flat B has negative log drift, so up-touch B < A here.
    assert probs.convention_a > probs.convention_b
    low, high = probs.convention_b, probs.convention_a
    edges = conservative_edges(probs, yes_ask=0.30, no_ask=0.72)
    assert edges.fair_yes == pytest.approx(low, abs=1e-15)
    assert edges.fair_no == pytest.approx(1.0 - high, abs=1e-15)
    assert edges.edge_yes == pytest.approx(low - 0.30, abs=1e-15)
    assert edges.edge_no == pytest.approx((1.0 - high) - 0.72, abs=1e-15)
    # NO-side conservatism is exact: the deficit vs the complementary
    # fair value equals the A/B spread (ordering flips, spread does not).
    spread = high - low
    assert (1.0 - edges.fair_yes) - edges.fair_no == pytest.approx(
        spread, abs=1e-12
    )
    assert spread > 0.0


def test_conservative_orientation_terminal_market():
    # At-expiry market (above/below on date): same per-side orientation.
    term = terminal_probability(
        spot=ETH_SPOT,
        sigma_daily=ETH_SIG30,
        barrier=2000.0,
        horizon_hours=FIXTURE_HORIZON_HOURS,
        asset="ETH",
    )
    assert term.convention_b > term.convention_a
    edges = conservative_edges(term, yes_ask=0.45, no_ask=0.56)
    assert edges.fair_yes == pytest.approx(
        min(term.convention_a, term.convention_b), abs=1e-15
    )
    assert edges.fair_no == pytest.approx(
        1.0 - max(term.convention_a, term.convention_b), abs=1e-15
    )


# ---------------------------------------------------------------------------
# Invariant (d): YES/NO complementarity
# ---------------------------------------------------------------------------


def test_yes_no_complementarity():
    touch = _eth2000_probs()
    # Each convention's YES/NO pair is exactly complementary.
    assert touch.convention_a + (1.0 - touch.convention_a) == 1.0
    assert touch.convention_b + (1.0 - touch.convention_b) == 1.0
    term = terminal_probability(
        spot=ETH_SPOT,
        sigma_daily=ETH_SIG30,
        barrier=2000.0,
        horizon_hours=FIXTURE_HORIZON_HOURS,
        asset="ETH",
    )
    below_a = term.convention_a
    above_a = 1.0 - below_a  # 'above on date' YES under convention A
    assert below_a + above_a == pytest.approx(1.0, abs=1e-15)
    # The conservative pair is deliberately NOT complementary: its sum
    # falls short of 1 by exactly the A/B spread (both sides conservative).
    edges = conservative_edges(touch, yes_ask=0.45, no_ask=0.56)
    spread = max(touch.convention_a, touch.convention_b) - min(
        touch.convention_a, touch.convention_b
    )
    assert edges.fair_yes + edges.fair_no == pytest.approx(1.0 - spread, abs=1e-12)
    # Degenerate agreement: a barrier already at spot is certain under
    # both conventions, so the pair collapses to exactly complementary.
    at_spot = touch_probability(
        spot=ETH_SPOT,
        sigma_daily=ETH_SIG30,
        barrier=ETH_SPOT,
        horizon_hours=FIXTURE_HORIZON_HOURS,
        asset="ETH",
    )
    assert (at_spot.convention_a, at_spot.convention_b) == (1.0, 1.0)
    degenerate = conservative_edges(at_spot, yes_ask=0.99, no_ask=0.99)
    assert degenerate.fair_yes + degenerate.fair_no == pytest.approx(
        1.0, abs=1e-15
    )


# ---------------------------------------------------------------------------
# Terminal model and degenerate paths
# ---------------------------------------------------------------------------


def test_terminal_probability_matches_direct_formula():
    horizon_days = FIXTURE_HORIZON_HOURS / 24.0
    sigma_t = ETH_SIG30 * math.sqrt(horizon_days)
    x = math.log(ETH_SPOT / 2000.0)
    mu_b = -ETH_SIG30 * ETH_SIG30 / 2.0

    def norm_cdf(z: float) -> float:
        return 0.5 * math.erfc(-z / math.sqrt(2.0))

    term = terminal_probability(
        spot=ETH_SPOT,
        sigma_daily=ETH_SIG30,
        barrier=2000.0,
        horizon_hours=FIXTURE_HORIZON_HOURS,
        asset="ETH",
    )
    assert term.convention_a == pytest.approx(norm_cdf(-x / sigma_t), abs=1e-12)
    assert term.convention_b == pytest.approx(
        norm_cdf(-(mu_b * horizon_days + x) / sigma_t), abs=1e-12
    )
    # Mean-flat log drift pushes terminal mass down: B > A below spot.
    assert term.convention_b > term.convention_a


def test_touch_probability_degenerate_paths():
    # Barrier at spot: already touched with certainty (both r19 shortcuts).
    at_spot = touch_probability(
        spot=ETH_SPOT, sigma_daily=0.02, barrier=ETH_SPOT, horizon_hours=240.0,
        asset="ETH",
    )
    assert (at_spot.convention_a, at_spot.convention_b) == (1.0, 1.0)
    # Zero horizon or zero vol: an untouched barrier cannot be reached.
    zero_horizon = touch_probability(
        spot=ETH_SPOT, sigma_daily=0.02, barrier=2000.0, horizon_hours=0.0,
        asset="ETH",
    )
    assert (zero_horizon.convention_a, zero_horizon.convention_b) == (0.0, 0.0)
    zero_vol = touch_probability(
        spot=ETH_SPOT, sigma_daily=0.0, barrier=2000.0, horizon_hours=240.0,
        asset="ETH",
    )
    assert (zero_vol.convention_a, zero_vol.convention_b) == (0.0, 0.0)
    # Terminal on a flat path resolves deterministically at the spot print.
    flat_below = terminal_probability(
        spot=ETH_SPOT, sigma_daily=0.0, barrier=2000.0, horizon_hours=240.0,
        asset="ETH",
    )
    assert (flat_below.convention_a, flat_below.convention_b) == (0.0, 0.0)
    flat_above = terminal_probability(
        spot=ETH_SPOT, sigma_daily=0.0, barrier=2500.0, horizon_hours=240.0,
        asset="ETH",
    )
    assert (flat_above.convention_a, flat_above.convention_b) == (1.0, 1.0)


# ---------------------------------------------------------------------------
# FX-13 (audit P-8): explicit terminal-market direction
# ---------------------------------------------------------------------------


def _eth2000_terminal():
    return terminal_probability(
        spot=ETH_SPOT,
        sigma_daily=ETH_SIG30,
        barrier=2000.0,
        horizon_hours=FIXTURE_HORIZON_HOURS,
        asset="ETH",
    )


def test_terminal_yes_probability_below_is_identity():
    # "below" returns both convention values unchanged: the stored record
    # is already P(S_T <= barrier), i.e. the YES side of a below market.
    term = _eth2000_terminal()
    yes = terminal_yes_probability(term, yes_when="below")
    assert isinstance(yes, TerminalYesProbability)
    assert yes.yes_when == "below"
    assert yes.asset == term.asset == "ETH"
    assert yes.barrier == term.barrier == 2000.0
    assert yes.horizon_hours == term.horizon_hours
    assert yes.convention_a == term.convention_a
    assert yes.convention_b == term.convention_b


def test_terminal_yes_probability_above_is_exact_complement():
    # "above" returns each convention's exact complement 1 - p.
    term = _eth2000_terminal()
    yes = terminal_yes_probability(term, yes_when="above")
    assert yes.yes_when == "above"
    assert yes.convention_a == 1.0 - term.convention_a
    assert yes.convention_b == 1.0 - term.convention_b
    assert yes.convention_a + term.convention_a == pytest.approx(1.0, abs=1e-15)
    assert yes.convention_b + term.convention_b == pytest.approx(1.0, abs=1e-15)


def test_terminal_yes_probability_rejects_unknown_direction():
    term = _eth2000_terminal()
    for bad in ("up", "Above", "ABOVE", "", "below ", "down", "touch", None, 1):
        with pytest.raises(ValueError, match="yes_when"):
            terminal_yes_probability(term, yes_when=bad)


def test_terminal_yes_probability_rejects_touch_records():
    # Touch markets have no direction to state: their YES side is the
    # touch event itself and their record goes straight to
    # conservative_edges.
    touch = _eth2000_probs()
    with pytest.raises(TypeError, match="TerminalProbability"):
        terminal_yes_probability(touch, yes_when="below")


def test_conservative_edges_for_terminal_below_matches_existing_path():
    # The below orientation through the new function is bit-identical to
    # the existing conservative_edges on the raw record: FX-13 changes no
    # below-barrier behavior.
    term = _eth2000_terminal()
    direct = conservative_edges(term, yes_ask=0.45, no_ask=0.56)
    via_new = conservative_edges_for_terminal(
        term, yes_when="below", yes_ask=0.45, no_ask=0.56
    )
    assert via_new == direct


def test_conservative_edges_for_terminal_above_mirrors_below():
    # FX-13 acceptance: for the same barrier under symmetric quotes
    # (above's yes_ask == below's no_ask and vice versa), above's YES
    # fair value/edge equals below's NO fair value/edge, and vice versa.
    term = _eth2000_terminal()
    below = conservative_edges_for_terminal(
        term, yes_when="below", yes_ask=0.45, no_ask=0.56
    )
    above = conservative_edges_for_terminal(
        term, yes_when="above", yes_ask=0.56, no_ask=0.45
    )
    assert above.fair_yes == pytest.approx(below.fair_no, abs=1e-15)
    assert above.fair_no == pytest.approx(below.fair_yes, abs=1e-15)
    assert above.edge_yes == pytest.approx(below.edge_no, abs=1e-15)
    assert above.edge_no == pytest.approx(below.edge_yes, abs=1e-15)
    # Explicit orientation for the above market: conservative YES is
    # min(1 - pA, 1 - pB) == 1 - max(pA, pB) and conservative NO is
    # max(pA, pB)-complement's mirror, i.e. min(pA, pB).
    low = min(term.convention_a, term.convention_b)
    high = max(term.convention_a, term.convention_b)
    assert above.fair_yes == pytest.approx(1.0 - high, abs=1e-15)
    assert above.fair_no == pytest.approx(low, abs=1e-15)


def test_above_market_naive_pricing_error_is_material():
    # The hazard P-8 documented: pricing an above market with the raw
    # below-barrier record (no direction transform) misstates YES fair
    # value by 1 - (low + high) -- more than 50c on this frozen anchor
    # (pA ~= 0.2224, pB ~= 0.2531), far beyond any gate threshold.
    term = _eth2000_terminal()
    low = min(term.convention_a, term.convention_b)
    high = max(term.convention_a, term.convention_b)
    naive = conservative_edges(term, yes_ask=0.45, no_ask=0.56)
    above = conservative_edges_for_terminal(
        term, yes_when="above", yes_ask=0.45, no_ask=0.56
    )
    assert above.fair_yes - naive.fair_yes == pytest.approx(
        1.0 - (low + high), abs=1e-12
    )
    assert above.fair_yes - naive.fair_yes > 0.5


def test_conservative_edges_for_terminal_validates_direction_and_type():
    term = _eth2000_terminal()
    with pytest.raises(ValueError, match="yes_when"):
        conservative_edges_for_terminal(
            term, yes_when="sideways", yes_ask=0.5, no_ask=0.5
        )
    with pytest.raises(TypeError, match="TerminalProbability"):
        conservative_edges_for_terminal(
            _eth2000_probs(), yes_when="below", yes_ask=0.5, no_ask=0.5
        )


def test_terminal_direction_on_degenerate_flat_path():
    # Zero-vol terminal records are exactly 0/1; complements stay exact.
    flat = terminal_probability(
        spot=ETH_SPOT, sigma_daily=0.0, barrier=2000.0, horizon_hours=240.0,
        asset="ETH",
    )
    assert (flat.convention_a, flat.convention_b) == (0.0, 0.0)
    below = terminal_yes_probability(flat, yes_when="below")
    above = terminal_yes_probability(flat, yes_when="above")
    assert (below.convention_a, below.convention_b) == (0.0, 0.0)
    assert (above.convention_a, above.convention_b) == (1.0, 1.0)
    edges = conservative_edges_for_terminal(
        flat, yes_when="above", yes_ask=0.99, no_ask=0.01
    )
    assert edges.fair_yes == 1.0
    assert edges.fair_no == 0.0
    assert edges.edge_yes == pytest.approx(0.01, abs=1e-15)


def test_input_validation():
    with pytest.raises(ValueError):
        touch_probability(
            spot=-1.0, sigma_daily=0.02, barrier=2000.0, horizon_hours=240.0,
            asset="ETH",
        )
    with pytest.raises(ValueError):
        touch_probability(
            spot=ETH_SPOT, sigma_daily=-0.02, barrier=2000.0, horizon_hours=240.0,
            asset="ETH",
        )
    with pytest.raises(ValueError):
        touch_probability(
            spot=ETH_SPOT, sigma_daily=0.02, barrier=2000.0, horizon_hours=-1.0,
            asset="ETH",
        )
    with pytest.raises(ValueError):
        terminal_probability(
            spot=ETH_SPOT, sigma_daily=0.02, barrier=0.0, horizon_hours=240.0,
            asset="ETH",
        )


def test_module_documents_conventions_and_r12_warning():
    # The conventions text must state the correct drift identities (A is
    # zero-log-drift / median-flat; B is mean-flat, mu_log = -sigma^2/2)
    # and carry the r12 historical warning.
    source = Path(crypto_model.__file__).read_text(encoding="utf-8")
    assert "median-flat" in source
    assert "mean-flat" in source
    assert "mu_log = -sigma^2 / 2" in source
    assert "r12" in source
    assert "mirror sign bug" in source
    assert "min(pA, pB)" in source
    assert "1 - max(pA, pB)" in source
    # FX-13: conservative_edges must point at-expiry callers at the
    # direction-explicit wrapper (audit P-8).
    assert "conservative_edges_for_terminal" in crypto_model.conservative_edges.__doc__
