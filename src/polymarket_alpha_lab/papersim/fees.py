"""Category taker-fee schedule for Polymarket paper simulation.

Single responsibility: hold the category -> taker fee rate table
(audit 2026-11-12 finding P-7, fix item FX-06) and the pure fee
arithmetic on top of it. No I/O, no thresholds, no gate logic; this
module never decides candidacy and never opens a connection.

Canonical lineage: the fee MODEL was frozen in the 2026-11-05
fee-accounting fix (``gates.py``: Polymarket charges
``shares * rate * p * (1 - p)`` per trade, so the per-share cost at
entry price ``p`` is ``rate * p * (1 - p)``) with exactly two live
books: crypto 7% and sports 5%. This module widens that to the full
official category schedule and becomes the ONE canonical rate lookup
the whole library shares; ``gates.FEE_RATE_CRYPTO`` /
``gates.FEE_RATE_SPORTS`` stay as frozen constants and are pinned
equal to this table's ``crypto`` / ``sports`` rows by tests.

Schedule provenance: the official Polymarket fee documentation
(:data:`FEE_SCHEDULE_SOURCE`), re-read 2026-11-12 while implementing
FX-06; the values matched the fix list, so :data:`FEE_SCHEDULE_AS_OF`
stays 2026-11-12. Re-read the docs before any future edit: a value
change is a policy change requiring owner review, and a live market
whose metadata disagrees with the table is refused loudly
(:func:`resolve_taker_fee_rate`) instead of being silently charged a
stale rate.

Scan-lineage classification (:func:`scan_fee_category`): the
book-of-record scans charged exactly two rates -- 0.07 for
``crypto_%`` teams (crypto_btc / crypto_eth) and 0.05 for every other
team. That team rule is mirrored verbatim here so historical ledger
rows classify the way the scans actually charged them; in particular
the gold (``commodities_gold``) and equity-index (``equity_indices``)
rows recorded under ``market_type='crypto_touch'`` take the SPORTS
rate, because their teams are not crypto (V-6 evidence run 2026-11-12:
the market_type-prefix alternative is a reported sensitivity, +2.95
USD of fees on the audit-period 40-row subset).

Paper boundary: these are simulated fee charges on simulated fills
(``paper_only=True`` / ``report_only=True`` / ``readonly=True``); this
module grants no execution authorization.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from types import MappingProxyType

# Schedule provenance pins (FX-06 acceptance: values re-read from the
# official docs at implementation time; update BOTH when the docs move).
FEE_SCHEDULE_AS_OF = "2026-11-12"
FEE_SCHEDULE_SOURCE = "https://docs.polymarket.com/trading/fees"

# Read-only category -> taker fee rate mapping (official docs as of
# FEE_SCHEDULE_AS_OF). Read-only: wrapping in MappingProxyType makes
# item assignment/deletion raise TypeError, matching the frozen-threshold
# convention (FX-14). Makers trade fee-free per the same docs; only the
# taker side is modeled here because paper entries walk the ASK ladder.
TAKER_FEE_RATES: Mapping[str, float] = MappingProxyType(
    {
        "crypto": 0.07,
        "sports": 0.05,
        "finance": 0.04,
        "politics": 0.04,
        "economics": 0.05,
        "culture": 0.05,
        "weather": 0.05,
        "other": 0.05,
        "mentions": 0.04,
        "tech": 0.04,
        "geopolitics": 0.0,
        "combos": 0.05,
    }
)

# Absolute tolerance for matching a market-metadata fee parameter
# against the table (exact decimal rates; guards float round-trips only).
_FEE_RATE_MATCH_TOLERANCE = 1e-9


def _normalize_category(category: str) -> str:
    return str(category or "").strip().lower()


def _require_rate(rate: float) -> None:
    if type(rate) not in (int, float) or not math.isfinite(rate):
        raise ValueError(f"fee rate must be a finite number, got {rate!r}")
    if rate < 0:
        raise ValueError(f"fee rate must be non-negative, got {rate!r}")


def taker_fee_rate(category: str) -> float:
    """Canonical taker fee rate lookup for one fee-schedule category.

    The ONE rate lookup the library shares (FX-06): every caller --
    gates, ledger settlement, reports -- resolves rates through here,
    never through a locally hardcoded number. ``category`` is matched
    case-insensitively after a strip; an unrecognized category raises
    :class:`ValueError` listing the valid names and is NEVER defaulted
    to the sports rate (a silent default would undercharge crypto).
    """
    normalized = _normalize_category(category)
    try:
        return TAKER_FEE_RATES[normalized]
    except KeyError:
        raise ValueError(
            f"unknown fee category {category!r}; valid categories: "
            f"{', '.join(sorted(TAKER_FEE_RATES))}"
        ) from None


def resolve_taker_fee_rate(
    category: str,
    *,
    market_rate: float | None = None,
) -> float:
    """Resolve the effective taker rate, honoring market metadata.

    FX-06 precedence rule for market metadata: when the official
    interfaces supply a market's own fee-rate parameter, that parameter
    is authoritative -- pass it as ``market_rate`` and, when it matches
    the table, it is returned (and thereby recorded by the caller).
    When it DISAGREES with :data:`TAKER_FEE_RATES` for the category,
    this raises :class:`ValueError`: the disagreement means the fee
    schedule table is stale, so the candidate is refused and the alarm
    is raised here rather than letting a stale table silently
    misprice the book. ``market_rate=None`` (metadata absent) resolves
    through the table alone.
    """
    table_rate = taker_fee_rate(category)
    if market_rate is None:
        return table_rate
    _require_rate(market_rate)
    if not math.isclose(
        market_rate, table_rate, rel_tol=0.0, abs_tol=_FEE_RATE_MATCH_TOLERANCE
    ):
        raise ValueError(
            f"market metadata fee rate {market_rate!r} disagrees with the "
            f"fee schedule ({category!r} -> {table_rate!r}, as of "
            f"{FEE_SCHEDULE_AS_OF}); the TAKER_FEE_RATES table needs "
            "updating -- refusing this candidate"
        )
    return market_rate


def fee_per_share(price: float, rate: float) -> float:
    """Fee per share at trade price ``p``: ``rate * p * (1 - p)``.

    Equivalent to :func:`polymarket_alpha_lab.papersim.gates.fee_cost`
    (pinned equal by tests); this is the canonical entry point for new
    code. Pure arithmetic, symmetric around ``p = 0.5`` where it is
    maximal; callers validate inputs and round where determinism
    matters.
    """
    return rate * price * (1.0 - price)


def entry_fee(stake: float, price: float, rate: float) -> float:
    """Taker fee charged on entering ``stake`` dollars at ``price``.

    Official formula: ``fee = C * rate * p * (1 - p)`` with ``C`` the
    share count, so with ``C = stake / price`` this is
    ``stake * rate * (1 - price)`` -- the exact simplified form the
    FX-01 net-PnL semantics use. ``rate`` comes from
    :func:`taker_fee_rate` (0 is valid: geopolitics is fee-free).
    """
    _require_rate(rate)
    if type(stake) not in (int, float) or not math.isfinite(stake) or stake <= 0:
        raise ValueError(f"stake must be a finite positive number, got {stake!r}")
    if type(price) not in (int, float) or not math.isfinite(price):
        raise ValueError(f"price must be a finite number, got {price!r}")
    if not 0.0 < price < 1.0:
        raise ValueError("price must be in the open interval (0, 1)")
    shares = stake / price
    return shares * fee_per_share(price, rate)


def exit_fee(shares: float, exit_price: float, rate: float) -> float:
    """Taker fee charged on SELLING ``shares`` at ``exit_price``.

    Mirror of :func:`entry_fee` on the exit leg:
    ``shares * rate * exit_price * (1 - exit_price)`` (V-6 evidence
    run: exits add sell fees at the reconstructed exit price).
    ``exit_price`` bounds match ``ledger.settle_exit`` (closed
    ``[0, 1]``; the fee is 0 at either boundary).
    """
    _require_rate(rate)
    if type(shares) not in (int, float) or not math.isfinite(shares) or shares <= 0:
        raise ValueError(f"shares must be a finite positive number, got {shares!r}")
    if type(exit_price) not in (int, float) or not math.isfinite(exit_price):
        raise ValueError(f"exit_price must be a finite number, got {exit_price!r}")
    if not 0.0 <= exit_price <= 1.0:
        raise ValueError("exit_price must be in the closed interval [0, 1]")
    return shares * fee_per_share(exit_price, rate)


def scan_fee_category(team: str, market_type: str | None = None) -> str:
    """Classify one ledger/scanner row into a fee-schedule category.

    Mirrors the classification the scans used (book-of-record team
    rule, re-verified by the V-6 evidence run 2026-11-12): a team named
    ``crypto_*`` (crypto_btc / crypto_eth) is the crypto book; every
    other team -- soccer, politics, macro, gold, equity indices, tech --
    was charged the sports 5% rate by the scans, so it classifies as
    ``sports``. ``market_type`` is accepted for call-site clarity and
    future refinement but does NOT override the team rule: the
    audit-period gold (``commodities_gold``) and equity-index
    (``equity_indices``) rows recorded under ``market_type=
    'crypto_touch'`` are sports-rate under the scan rule (the
    market_type-prefix alternative overcharges them by 0.02 and is
    reported only as a V-6 sensitivity).
    """
    team_name = str(team or "").strip().lower()
    if not team_name:
        raise ValueError("team must be a non-empty string to classify fees")
    if team_name.startswith("crypto_"):
        return "crypto"
    return "sports"
