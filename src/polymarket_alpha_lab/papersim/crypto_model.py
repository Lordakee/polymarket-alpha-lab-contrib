"""Crypto barrier touch model (A/B GBM conventions).

Single responsibility: compute first-passage touch probabilities for
crypto price barriers (``ETH-2000`` / ``ETH-2250`` / ``BTC-65k`` style)
from a spot print and a realized-vol signature, under the two book-of-record
conventions, plus the realized-vol estimator that feeds them. Deterministic,
no network access, report-only output.

Canonical lineage: ``r19`` (current head ``round19/model19.py``, raw inputs
``round19/raw/crypto_scan.json``). Conventions frozen at the head:

- Vol source: complete 6h klines, RMS of log returns scaled by ``sqrt(4)``;
  the signature table is the 30-day window.
- Convention A: zero-log-drift GBM, which is simultaneously median-flat
  (the median of ``S_T`` equals ``S_0``). Convention B: mean-flat /
  zero-arithmetic-drift (``mu_log = -sigma^2 / 2``, so ``E[S_T] = S_0``).
- Touch: drifted first-passage via the reflection-principle form.
  At-expiry (terminal) probability for ``above/below on date`` markets is
  a separate function; the two are tied by the reflection identity only at
  zero log drift (``p_touch == 2 * p_terminal`` there, and only there).
- Per-side conservative edges (2026-10-30 audit fix, present only in the
  r19 head): conservative YES fair value is ``min(pA, pB)`` and
  conservative NO fair value is ``1 - max(pA, pB)``. Both sides are
  conservative at once; their sum falls short of 1 by exactly the A/B
  spread. The pre-fix orientation used ``max`` for the YES side on
  touch-down markets, overstating YES fair value by the full A/B spread
  (about 3.4c on the ETH-2000 30d regression anchor).
- Terminal horizons anchor to the scan timestamp and run to market close
  (``Dec31_2359`` in the r19 record).

Historical warning (r12 lineage, pre-r13): round-12 outputs had the A/B
convention labels swapped and carried a mirror sign bug in ``touch_up``.
Never difference or compare probabilities across the r12 -> r13 boundary;
r12-era numbers cannot be re-derived from these conventions and must not
be mixed with this module's outputs.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Mapping

# Frozen r19 window table: number of 6h bars per realized-vol window.
# 7d = 28 bars, 30d = 120 (the signature table), 60d = 240, 87d = 348.
VOL_WINDOW_BARS: Mapping[str, int] = {
    "7d": 28,
    "30d": 120,
    "60d": 240,
    "87d": 348,
}

# The r19 scan table prices every candidate off the 30-day window.
SIGNATURE_WINDOW = "30d"


def _norm_cdf(z: float) -> float:
    """Standard normal CDF, the r19 ``N`` helper (erfc form, no scipy)."""
    return 0.5 * math.erfc(-z / math.sqrt(2.0))


def _p_touch_up(
    distance_log: float,
    mu_log: float,
    sigma_daily: float,
    horizon_days: float,
) -> float:
    """First-passage touch probability of a log-distance ``a`` above.

    Ported verbatim from r19 ``p_touch_up`` (drifted reflection-principle
    form): ``P(sup_{t<=T} (mu*t + sigma*W_t) >= a)``.
    """
    sigma_t = sigma_daily * math.sqrt(horizon_days)
    if sigma_t <= 0.0:
        return 1.0 if distance_log <= 0 else 0.0
    drift = mu_log * horizon_days
    return _norm_cdf((drift - distance_log) / sigma_t) + math.exp(
        2.0 * mu_log * distance_log / (sigma_daily * sigma_daily)
    ) * _norm_cdf(-(drift + distance_log) / sigma_t)


def _p_terminal_below(
    distance_log: float,
    mu_log: float,
    sigma_t: float,
    horizon_days: float,
) -> float:
    """Terminal ``P(S_T <= barrier)`` for log-distance ``x = log(S/K)``.

    ``P(log(S_T/S_0) <= -x) = N(-(x + mu_log * T) / sigma_T)``; the zero
    log drift case collapses to ``N(-x / sigma_T)``, which is exactly the
    first-passage form's first term (the reflection identity pairing).
    """
    return _norm_cdf(-(mu_log * horizon_days + distance_log) / sigma_t)


@dataclass(frozen=True)
class TouchProbability:
    """Touch probability for one barrier under both conventions."""

    asset: str
    barrier: float
    horizon_hours: float
    convention_a: float
    convention_b: float


@dataclass(frozen=True)
class TerminalProbability:
    """At-expiry ``P(S_T <= barrier)`` under both conventions.

    For ``above/below on date`` markets; the YES side of an ``above``
    market is ``1 - convention_x`` of the same record.
    """

    asset: str
    barrier: float
    horizon_hours: float
    convention_a: float
    convention_b: float


@dataclass(frozen=True)
class ConservativeEdges:
    """Per-side conservative fair values and edges for one candidate.

    ``fair_yes = min(pA, pB)`` and ``fair_no = 1 - max(pA, pB)`` (the
    2026-10-30 audit fix): each side's fair value is the conservative end
    of the convention band, so no ask comparison can overstate either
    side. ``edge_yes``/``edge_no`` subtract the respective asks.
    """

    fair_yes: float
    fair_no: float
    edge_yes: float
    edge_no: float


def realized_vol_daily(closes: Sequence[float], bar_hours: float = 6.0) -> float:
    """Daily realized volatility from complete-bar close prices.

    RMS of log returns over ``closes`` scaled by ``sqrt(24 / bar_hours)``.
    Callers must pass complete bars only (the live partial bar is used for
    spot, never for vol).

    The estimator is the uncentered RMS, exactly as r19 ``vol_from``
    computes it (divide by the return count, never subtract the sample
    mean), so a one-sided run of same-sign returns is vol, not zero.
    """
    if bar_hours <= 0.0:
        raise ValueError(f"bar_hours must be positive, got {bar_hours!r}")
    if len(closes) < 2:
        raise ValueError("need at least two closes to form a log return")
    if any(c <= 0.0 for c in closes):
        raise ValueError("closes must be positive prices")
    returns = [
        math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))
    ]
    rms = math.sqrt(sum(r * r for r in returns) / len(returns))
    return rms * math.sqrt(24.0 / bar_hours)


def realized_vol_windows(
    closes: Sequence[float], *, bar_hours: float = 6.0
) -> dict[str, float]:
    """Multi-window realized-vol table (r19: 7/30/60/87d over 6h bars).

    Each window uses the ``VOL_WINDOW_BARS`` most recent closes, exactly
    as r19 ``vol_from`` sliced ``closes[-n:]``: when fewer closes are
    available the estimator silently runs on all of them (r19-faithful),
    so callers wanting the book-of-record table must supply full history.
    """
    return {
        label: realized_vol_daily(closes[-bars:], bar_hours=bar_hours)
        for label, bars in VOL_WINDOW_BARS.items()
    }


def touch_probability(
    spot: float,
    sigma_daily: float,
    barrier: float,
    horizon_hours: float,
    *,
    asset: str,
) -> TouchProbability:
    """Drifted first-passage touch probability under conventions A and B.

    A barrier below spot is a down-touch (r19 ``probs_dn``); a barrier
    above spot is an up-touch (r19 ``probs_up``); a barrier at spot is
    already touched with certainty (both r19 shortcuts return 1.0 there).
    This module cannot tell which side a *market* means once spot has
    crossed its barrier -- callers must not re-model a market whose
    barrier is already breached on the market's own side.

    Convention A prices with zero log drift (median-flat); convention B
    with ``mu_log = -sigma^2 / 2`` (mean-flat, ``E[S_T] = S_0``) in both
    barrier directions, matching r19 exactly.
    """
    if spot <= 0.0 or barrier <= 0.0:
        raise ValueError("spot and barrier must be positive prices")
    if sigma_daily < 0.0:
        raise ValueError(f"sigma_daily must be non-negative, got {sigma_daily!r}")
    if horizon_hours < 0.0:
        raise ValueError(
            f"horizon_hours must be non-negative, got {horizon_hours!r}"
        )
    horizon_days = horizon_hours / 24.0
    mu_b = -sigma_daily * sigma_daily / 2.0
    if barrier == spot:
        conv_a = conv_b = 1.0
    elif barrier < spot:
        x = math.log(spot / barrier)
        # p_touch_dn(x, mu) == p_touch_up(x, -mu): mirror the drift sign.
        conv_a = _p_touch_up(x, 0.0, sigma_daily, horizon_days)
        conv_b = _p_touch_up(x, -mu_b, sigma_daily, horizon_days)
    else:
        a = math.log(barrier / spot)
        conv_a = _p_touch_up(a, 0.0, sigma_daily, horizon_days)
        conv_b = _p_touch_up(a, mu_b, sigma_daily, horizon_days)
    return TouchProbability(
        asset=asset,
        barrier=barrier,
        horizon_hours=horizon_hours,
        convention_a=conv_a,
        convention_b=conv_b,
    )


def terminal_probability(
    spot: float,
    sigma_daily: float,
    barrier: float,
    horizon_hours: float,
    *,
    asset: str,
) -> TerminalProbability:
    """At-expiry ``P(S_T <= barrier)`` under conventions A and B.

    For ``above/below on date`` markets, which resolve on the terminal
    print rather than any barrier touch along the path. The touch and
    terminal models are distinct: at zero log drift only, the reflection
    identity gives ``p_touch == 2 * p_terminal``. The ``above`` side of
    the same market is the complement ``1 - convention_x``.
    """
    if spot <= 0.0 or barrier <= 0.0:
        raise ValueError("spot and barrier must be positive prices")
    if sigma_daily < 0.0:
        raise ValueError(f"sigma_daily must be non-negative, got {sigma_daily!r}")
    if horizon_hours < 0.0:
        raise ValueError(
            f"horizon_hours must be non-negative, got {horizon_hours!r}"
        )
    horizon_days = horizon_hours / 24.0
    sigma_t = sigma_daily * math.sqrt(horizon_days)
    x = math.log(spot / barrier)
    mu_b = -sigma_daily * sigma_daily / 2.0
    if sigma_t <= 0.0:
        # Degenerate flat path: S_T == spot with certainty.
        conv_a = conv_b = 1.0 if spot <= barrier else 0.0
    else:
        conv_a = _p_terminal_below(x, 0.0, sigma_t, horizon_days)
        conv_b = _p_terminal_below(x, mu_b, sigma_t, horizon_days)
    return TerminalProbability(
        asset=asset,
        barrier=barrier,
        horizon_hours=horizon_hours,
        convention_a=conv_a,
        convention_b=conv_b,
    )


def conservative_edges(
    probabilities: TouchProbability | TerminalProbability,
    *,
    yes_ask: float,
    no_ask: float,
) -> ConservativeEdges:
    """Per-side conservative fair values and edges (2026-10-30 fix).

    ``edge_yes = min(pA, pB) - yes_ask`` and
    ``edge_no = (1 - max(pA, pB)) - no_ask``: the YES side is priced off
    the conservative (low) end of the convention band and the NO side off
    the conservative (low) end of the complementary band, so neither side
    can be overstated regardless of drift convention. Works for touch
    markets (``TouchProbability``) and at-expiry markets
    (``TerminalProbability``) alike: the probability pair models whichever
    side the market's YES means.
    """
    conv_a = probabilities.convention_a
    conv_b = probabilities.convention_b
    fair_yes = min(conv_a, conv_b)
    fair_no = 1.0 - max(conv_a, conv_b)
    return ConservativeEdges(
        fair_yes=fair_yes,
        fair_no=fair_no,
        edge_yes=fair_yes - yes_ask,
        edge_no=fair_no - no_ask,
    )
