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
- Convention A: zero-log-drift GBM. Convention B: median-flat
  (``mu_log = -sigma^2 / 2``).
- Touch: drifted first-passage via the reflection-principle form.
- Terminal horizons anchor to the scan timestamp and run to market close
  (``Dec31_2359`` in the r19 record).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class TouchProbability:
    """Touch probability for one barrier under both conventions."""

    asset: str
    barrier: float
    horizon_hours: float
    convention_a: float
    convention_b: float


def realized_vol_daily(closes: Sequence[float], bar_hours: float = 6.0) -> float:
    """Daily realized volatility from complete-bar close prices.

    RMS of log returns over ``closes`` scaled by ``sqrt(24 / bar_hours)``.
    Callers must pass complete bars only (the live partial bar is used for
    spot, never for vol).
    """
    raise NotImplementedError


def touch_probability(
    spot: float,
    sigma_daily: float,
    barrier: float,
    horizon_hours: float,
    *,
    asset: str,
) -> TouchProbability:
    """Drifted first-passage touch probability under conventions A and B."""
    raise NotImplementedError
