"""Entry gates for paper candidates.

Single responsibility: decide whether a modeled candidate may become a
paper entry, from the frozen gate thresholds plus the arithmetic inputs
(variant spread, worst-variant edge, median exec edge at the $250 CLOB
VWAP ask, Gamma liquidity) and the fixture news check. Pure computation;
no I/O.

Canonical lineage: the thresholds were frozen in the soccer lineage
(``r5c -> r15 -> r23``; wording fixed in round23/epl_candidates.json
``rules.gates`` and re-verified in round24) and apply unchanged to crypto
candidates from the ``r19`` lineage. Threshold values are book-of-record
constants: changing one is a policy change requiring owner review, not a
tune-up.

WP-P1 implementation notes (implementation commit): the P0 stub surfaces
(``GATES``, ``NewsCheck``, ``GateDecision``, :func:`evaluate_gates`,
:func:`check_news`) keep their frozen signatures exactly. The richer
candidate pipeline from the lineage -- $250 book-ladder VWAP walk
(``round24/raw/books24.py``), 50-50 cancellation haircut applied BEFORE
the exec bar (``round15/soccer_tools/finalize15.py``), the under_risk 8c
screen, the news-concordance overlay, the suspension-policy registry and
the worst-variant-first ranking -- is added alongside the frozen surface
as :func:`walk_book`, :func:`evaluate_candidate` and friends. No stub
contract changed.

WP-P1 codex-review fixes (F2/F3/F6, 2026-11-01): the composite
:func:`evaluate_candidate` acceptance decision now independently
establishes a completed $250 ASK walk over the passed book -- the
entry evaluation is ask-only (non-ask ``side`` raises); configurable
``notional`` no longer feeds any
acceptance check and are recorded only as a supplementary
``valuation_walk``. :func:`evaluate_gates` rejects non-finite (NaN/inf)
numeric inputs instead of letting them slip past the comparisons, and
:func:`rank_candidates` orders only the survivors (passed decisions).

Fee accounting (2026-11-05 review finding): the exec-edge bar is a NET
bar. Polymarket charges ``notional * rate * p * (1 - p)`` per trade
(rate 0.07 crypto / 0.05 sports), so :func:`evaluate_candidate`
subtracts :func:`fee_cost` at the walked entry price from the
executable edge BEFORE the +5c (or +8c under_risk) comparison. The
frozen threshold VALUES are unchanged -- only the edge definition
moved from gross to net. Gross edges stay visible as
``GateReport.exec_edge_gross``, and :func:`evaluate_gates` accepts an
optional ``fee_rate`` + ``entry_price`` pair to net its supplied edge
the same way (without the pair it keeps comparing as supplied).
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

# Frozen entry-gate thresholds (book of record).
# var<=6c; worst-variant exec >= +4c; median exec >= +5c (CLOB $250-VWAP
# ask); liq >= $5k. Additional eligibility (entry .10-.92, book fills
# $250, eligible market kinds) is enforced by callers.
GATES: Mapping[str, float] = {
    "variant_spread_max": 0.06,
    "worst_edge_min": 0.04,
    "exec_edge_min": 0.05,
    "liq_min": 5000.0,
}

# Comparison tolerance carried from the round-24 finalize pass
# (round24/raw/finalize24.py): boundary values pass, next tick fails.
GATE_EPSILON = 1e-9

# Entry price window (book of record wording: "entry .10-.92").
ENTRY_WINDOW: tuple[float, float] = (0.10, 0.92)

# Standard paper notional every exec price is walked for ($250-VWAP).
DEFAULT_NOTIONAL_USD = 250.0

# Polymarket trading-fee model (fee-accounting fix, 2026-11-05 review):
# fee = notional * rate * p * (1 - p), i.e. a per-share cost of
# ``rate * p * (1 - p)`` at entry price ``p`` (:func:`fee_cost`). The
# crypto book pays 7% and the sports book 5%. The frozen exec bar
# (>= +5c) is applied to the NET edge -- gross executable edge minus
# this per-share fee -- so a 5c bar means 5c AFTER fees. The four
# frozen thresholds themselves are unchanged.
FEE_RATE_CRYPTO = 0.07
FEE_RATE_SPORTS = 0.05

# depth_2c: notional within 2 cents of the best level ("depth_near2c").
DEPTH_NEAR_BAND = 0.02

# r15 under_risk screen: Over totals / BTTS-Yes with under-trending form
# need edge >= +8c (and all-variant agreement, subsumed by worst >= +4c).
UNDER_RISK_EXEC_EDGE_MIN = 0.08

SIDE_ASK = "ask"
SIDE_BID = "bid"

# News-delta classification relative to the model's direction (the r24
# news overlay: CHE-MUN "WORSE, not better" blocked; Bournemouth "no new
# injuries" passed).
NEWS_BETTER = "better"
NEWS_WORSE = "worse"
NEWS_UNCHANGED = "unchanged"
NEWS_UNKNOWN = "unknown"
NEWS_DELTAS: tuple[str, ...] = (NEWS_BETTER, NEWS_WORSE, NEWS_UNCHANGED, NEWS_UNKNOWN)

# 50-50 cancellation haircut band (r15): a coin-flip model median halves
# the exec edge BEFORE it is compared with the exec bar.
HAIRCUT_BAND = (0.45, 0.55)
HAIRCUT_FACTOR = 0.5

# Suspension-policy registry (review/FIXES.md 2026-10-30 + r23/r24 rules).
POLICY_BANNED = "BANNED"
POLICY_ELIGIBLE_DEPRIORITIZED = "ELIGIBLE_DEPRIORITIZED"
POLICY_FLAGGED_ONLY = "FLAGGED_ONLY"
POLICY_ELIGIBLE = "ELIGIBLE"

REASON_CROSS_LEAGUE_MATCH_WINNER = (
    "cross-league match_winner ELIGIBLE_DEPRIORITIZED with bridge: WP-P2a bridge validated "
    "(WP-P2b backtest T1-T5 PASS; bridge retro-test fixed all 3 losing fixture directions). "
    "Requires bridge parameter + worst-variant >= +5c (extra margin) + $150 marginal sizing. "
    "T4 accumulation: >=20 settled cross-league MW bets before standard sizing."
)
REASON_DOMESTIC_MATCH_WINNER = (
    "domestic match_winner eligible under the tightened gates but DEPRIORITIZED "
    "vs O/U totals (true record 2W-3L on sample-size and cohort-audit grounds, "
    "review/FIXES.md 2026-10-30)"
)
REASON_SPREADS_FLAGGED_ONLY = (
    "spreads flagged-only (blowout-tail rule): counted and reported per window, "
    "never entered"
)
REASON_ELIGIBLE_KIND = (
    "eligible market kind under the tightened gates (O/U totals, BTTS and team "
    "totals, both directions)"
)

# Registry: (normalized market kind, cross_league) -> (policy, eligible, reason).
SUSPENSION_REGISTRY: Mapping[tuple[str, bool], tuple[str, bool, str]] = {
    ("match_winner", True): (POLICY_ELIGIBLE_DEPRIORITIZED, True, REASON_CROSS_LEAGUE_MATCH_WINNER),
    ("match_winner", False): (POLICY_ELIGIBLE_DEPRIORITIZED, True, REASON_DOMESTIC_MATCH_WINNER),
    ("spread", False): (POLICY_FLAGGED_ONLY, False, REASON_SPREADS_FLAGGED_ONLY),
    ("spread", True): (POLICY_FLAGGED_ONLY, False, REASON_SPREADS_FLAGGED_ONLY),
}

# Kind aliases seen across the lineage records.
_MATCH_WINNER_KINDS = frozenset({"match_winner", "1x2", "ml"})
_SPREAD_KINDS = frozenset({"spread", "spreads", "handicap"})


@dataclass(frozen=True)
class NewsCheck:
    """Lineup/injury concordance check for one fixture.

    ``delta`` is the time-to-kickoff bucket the check ran at (for example
    ``"48h"`` or ``"recheck T-1d"``); ``concordant`` is True when fresh
    news does not contradict the model's fragility assumptions;
    ``blockers`` lists exit conditions met (any entry block);
    ``sources`` lists press-conference / news citations.
    """

    fixture: str
    delta: str
    concordant: bool
    blockers: tuple[str, ...]
    sources: tuple[str, ...]


@dataclass(frozen=True)
class GateDecision:
    """Gate outcome for one candidate."""

    passed: bool
    failed: tuple[str, ...]


@dataclass(frozen=True)
class BookWalk:
    """Result of walking one side of a CLOB book to a dollar notional.

    ``vwap`` is the executable average price for ``notional`` dollars
    (rounded to 4 decimals, lineage convention); ``filled`` is True when
    the book absorbed the full notional; ``depth_near2c`` is the resting
    notional within 2 cents of ``best`` (the ``depth_2c`` metric);
    ``filled_notional``/``shares`` expose partial fills.
    """

    side: str
    notional: float
    best: float | None
    vwap: float | None
    filled: bool
    filled_notional: float
    shares: float
    depth_near2c: float


@dataclass(frozen=True)
class SuspensionDecision:
    """Suspension-policy lookup result for one market kind."""

    market_kind: str
    cross_league: bool
    policy: str
    eligible: bool
    reason: str


@dataclass(frozen=True)
class GateReport:
    """Full candidate gate outcome with per-check booleans.

    ``checks`` mirrors the round-25 candidate record ``gates`` block
    (``variant_spread<=6c`` ... ``news_concordant``) plus the explicit
    ``entry_window`` key; ``decision`` carries the frozen
    :class:`GateDecision` shape with stable failed-check ids.

    ``walk`` is the acceptance walk: the hardcoded $250 ASK walk over the
    passed book (``side='ask'``, ``notional=250``), the only walk any
    acceptance check (``fill_250``, ``entry_window``, the exec/worst
    edges, ``entry_price``) is computed from. ``valuation_walk`` records
    the caller-configured ``side``/``notional`` walk as supplementary
    valuation information only -- it feeds no acceptance check -- and is
    ``None`` when the caller requested exactly the acceptance parameters.

    Edge fields under the fee model (2026-11-05 fee-accounting fix):
    ``exec_edge_gross`` is the raw executable edge
    ``model_median - vwap250``; ``exec_edge`` is the NET edge -- gross
    minus :func:`fee_cost` at the walked entry price and the caller's
    ``fee_rate`` -- and is the edge the frozen exec bar compares (after
    the 50-50 haircut, recorded as ``exec_edge_haircut`` over the NET
    edge). ``worst_variant_edge`` stays GROSS: it is a model-agreement
    margin, not an executable-edge bar.
    """

    decision: GateDecision
    checks: Mapping[str, bool]
    walk: BookWalk
    entry_price: float | None
    gamma_liquidity: float
    exec_edge_gross: float | None
    exec_edge: float | None
    haircut: float
    exec_edge_haircut: float | None
    worst_variant_edge: float | None
    variant_spread: float
    under_risk: bool
    valuation_walk: BookWalk | None = None


# Canonical check order for ``GateDecision.failed`` assembly.
_CANDIDATE_CHECK_ORDER: tuple[tuple[str, str], ...] = (
    ("variant_spread<=6c", "variant_spread"),
    ("worst>=+4c", "worst_edge"),
    ("exec>=+5c", "exec_edge"),
    ("liq>=5k", "liq"),
    ("entry_window", "entry_window"),
    ("fill_250", "fill_250"),
    ("news_concordant", "news_concordant"),
)


def _level_pair(level: Any) -> tuple[float, float]:
    """Normalize one book level to a ``(price, size)`` float pair."""
    if isinstance(level, Mapping):
        price = level["price"]
        size = level["size"]
    else:
        price, size = level[0], level[1]
    return float(price), float(size)


def walk_book(
    levels: Iterable[Any],
    side: str = SIDE_ASK,
    *,
    notional: float = DEFAULT_NOTIONAL_USD,
) -> BookWalk:
    """Walk one side of a book to ``notional`` dollars (canonical $250 VWAP).

    Lineage: ``round24/raw/books24.py`` ``walk``/``walk_bids``. Asks are
    walked cheapest-first, bids dearest-first; each level contributes
    ``min(size, remaining_dollars / price)`` shares. ``filled`` uses the
    lineage tolerance (``cash >= notional - 1e-6``) so partial fills are
    flagged, and ``depth_near2c`` sums the resting notional within 2c of
    the best level.
    """
    if side not in (SIDE_ASK, SIDE_BID):
        raise ValueError(f"side must be {SIDE_ASK!r} or {SIDE_BID!r}, got {side!r}")
    if notional <= 0:
        raise ValueError("notional must be positive")
    clean = [(p, s) for p, s in (_level_pair(lv) for lv in levels) if p > 0 and s > 0]
    clean.sort(key=lambda lv: lv[0], reverse=(side == SIDE_BID))
    if not clean:
        return BookWalk(side, float(notional), None, None, False, 0.0, 0.0, 0.0)
    best = clean[0][0]
    cash = 0.0
    shares = 0.0
    for price, size in clean:
        take = min(size, (notional - cash) / price)
        if take <= 0:
            break
        cash += take * price
        shares += take
        if cash >= notional - 1e-9:
            break
    vwap = (cash / shares) if shares > 0 else best
    if side == SIDE_ASK:
        near = sum(p * s for p, s in clean if p <= best + DEPTH_NEAR_BAND)
    else:
        near = sum(p * s for p, s in clean if p >= best - DEPTH_NEAR_BAND)
    return BookWalk(
        side=side,
        notional=float(notional),
        best=round(best, 4),
        vwap=round(vwap, 4),
        filled=cash >= notional - 1e-6,
        filled_notional=round(cash, 2),
        shares=round(shares, 4),
        depth_near2c=round(near, 0),
    )


def cancellation_haircut(model_median: float) -> float:
    """50-50 cancellation haircut factor for a side's model median.

    Returns 0.5 when the median sits in the inclusive ``[0.45, 0.55]``
    coin-flip band, else 1.0 (r15 ``haircut``). The factor multiplies the
    exec edge BEFORE the exec bar comparison (:func:`haircut_edge`).
    """
    return HAIRCUT_FACTOR if HAIRCUT_BAND[0] <= model_median <= HAIRCUT_BAND[1] else 1.0


def haircut_edge(exec_edge: float, model_median: float) -> float:
    """Apply the 50-50 haircut to an exec edge (lineage rounding: 4 dp)."""
    return round(exec_edge * cancellation_haircut(model_median), 4)


def fee_cost(entry_price: float, fee_rate: float) -> float:
    """Per-share Polymarket trading fee at ``entry_price``.

    Polymarket charges ``notional * rate * p * (1 - p)`` on a trade, so
    the fee per share bought at price ``p`` is ``rate * p * (1 - p)``
    (:data:`FEE_RATE_CRYPTO` = 0.07, :data:`FEE_RATE_SPORTS` = 0.05).
    The fee is symmetric around ``p = 0.5`` where it is maximal (1.25c
    per share at the sports rate). Pure arithmetic; callers round to the
    lineage 4-dp convention where determinism matters.
    """
    return fee_rate * entry_price * (1.0 - entry_price)


def under_risk_check(
    *,
    kind: str,
    side: str,
    o25_hits: int,
    lambda_total: float,
    lambda_home: float,
    lambda_away: float,
    line: float = 2.5,
) -> tuple[bool, str]:
    """Extra-strict low-scoring-risk screen (r15 ``under_risk_check``).

    Only Over totals (``kind='total'``, side starting with ``over``) and
    BTTS-Yes (``kind='btts'``, side ``yes``) are screened. ``o25_hits``
    is the combined last-5 O2.5 hit count of both teams (0-10). A flagged
    candidate needs edge >= +8c (:data:`UNDER_RISK_EXEC_EDGE_MIN`).
    """
    kind_n = str(kind).lower()
    side_n = str(side).lower()
    is_over = kind_n == "total" and side_n.startswith("over")
    is_yes = kind_n == "btts" and side_n == "yes"
    if not (is_over or is_yes):
        return (False, "")
    reasons: list[str] = []
    if is_over:
        need = {1.5: 2.3, 2.5: 2.75, 3.5: 3.4, 4.5: 4.3}.get(line, line + 0.4)
        if lambda_total < need:
            reasons.append(
                f"lambda_total {lambda_total:.2f} < {need:.2f} for O{line:.1f}"
            )
        if o25_hits <= 3:
            reasons.append(f"combined last-5 O2.5 hits {o25_hits}/10")
    if is_yes:
        if min(lambda_home, lambda_away) < 0.75:
            reasons.append(f"min lambda {min(lambda_home, lambda_away):.2f} < 0.75")
        if o25_hits <= 3:
            reasons.append(f"combined last-5 O2.5 hits {o25_hits}/10")
    return (bool(reasons), "; ".join(reasons))


def news_concordance(news_delta: str | None) -> bool:
    """True when a news delta does not contradict the model direction.

    ``better`` and ``unchanged`` are concordant; ``worse`` contradicts
    (the r24 CHE-MUN block) and ``unknown`` cannot support candidacy
    (lineups must be re-verified before a paper entry), so both return
    False.
    """
    delta = str(news_delta or NEWS_UNKNOWN).strip().lower()
    return delta in (NEWS_BETTER, NEWS_UNCHANGED)


def check_news(
    fixture: str,
    delta: str,
    *,
    news_delta: str | None = None,
    blockers: Sequence[str] = (),
    sources: Sequence[str] = (),
) -> NewsCheck:
    """Assemble the news-concordance record for ``fixture`` at ``delta``.

    ``news_delta`` classifies the fresh news versus the model's direction
    (:data:`NEWS_BETTER` / :data:`NEWS_WORSE` / :data:`NEWS_UNCHANGED` /
    :data:`NEWS_UNKNOWN`; missing evidence is ``unknown``). ``blockers``
    are caller-met exit/entry-block conditions; any blocker, a ``worse``
    delta or an ``unknown`` delta makes the record non-concordant.
    """
    classification = str(news_delta or NEWS_UNKNOWN).strip().lower()
    if classification not in NEWS_DELTAS:
        classification = NEWS_UNKNOWN
    block: list[str] = [str(b) for b in blockers]
    if classification == NEWS_WORSE and "news_worse_than_model" not in block:
        block.append("news_worse_than_model")
    if classification == NEWS_UNKNOWN and "news_unknown" not in block:
        block.append("news_unknown")
    concordant = news_concordance(classification) and not block
    return NewsCheck(
        fixture=fixture,
        delta=delta,
        concordant=concordant,
        blockers=tuple(block),
        sources=tuple(sources),
    )


def suspension_policy(market_kind: str, *, cross_league: bool = False) -> SuspensionDecision:
    """Look up the suspension policy for one market kind.

    Cross-league match_winner is ELIGIBLE_DEPRIORITIZED (bridge validated), domestic
    match_winner is ELIGIBLE_DEPRIORITIZED, spreads are FLAGGED_ONLY;
    every other kind (O/U totals, BTTS, team totals) is ELIGIBLE under
    the tightened gates.
    """
    kind = str(market_kind or "").strip().lower()
    registry_kind = kind
    if kind in _MATCH_WINNER_KINDS:
        registry_kind = "match_winner"
    elif kind in _SPREAD_KINDS:
        registry_kind = "spread"
    entry = SUSPENSION_REGISTRY.get((registry_kind, bool(cross_league)))
    if entry is None:
        policy, eligible, reason = POLICY_ELIGIBLE, True, REASON_ELIGIBLE_KIND
    else:
        policy, eligible, reason = entry
    return SuspensionDecision(
        market_kind=kind,
        cross_league=bool(cross_league),
        policy=policy,
        eligible=eligible,
        reason=reason,
    )


def _quote_field(quote: Any, name: str) -> Any:
    """Read a required field off a quote object or mapping."""
    if isinstance(quote, Mapping):
        if name in quote:
            return quote[name]
    else:
        value = getattr(quote, name, None)
        if value is not None:
            return value
    raise ValueError(f"model_quote is missing required field {name!r}")


def _quote_optional(quote: Any, names: tuple[str, ...], default: Any = None) -> Any:
    """Read the first present non-None field off a quote, else ``default``."""
    for name in names:
        if isinstance(quote, Mapping):
            if quote.get(name) is not None:
                return quote[name]
        else:
            value = getattr(quote, name, None)
            if value is not None:
                return value
    return default


def evaluate_candidate(
    model_quote: Any,
    book: Iterable[Any],
    side: str = SIDE_ASK,
    *,
    gamma_liquidity: float | None = None,
    news: NewsCheck | None = None,
    under_risk: bool = False,
    notional: float = DEFAULT_NOTIONAL_USD,
    fee_rate: float = FEE_RATE_SPORTS,
) -> GateReport:
    """Evaluate the full tightened gate set for one candidate.

    The composite entry point over the frozen :func:`evaluate_gates`
    (whose numeric signature cannot take a book): computes the exec and
    worst-variant edges versus the walked price, charges the Polymarket
    trading fee (``fee_rate`` defaults to the sports 5% book; crypto
    candidates pass :data:`FEE_RATE_CRYPTO`) against the executable
    edge, applies the 50-50 cancellation haircut to the NET edge BEFORE
    the exec bar, raises the exec bar to +8c when ``under_risk`` is set,
    and requires the entry window, a completed $250 walk (real-depth
    intent), the Gamma liquidity floor and a concordant
    :class:`NewsCheck`.

    Acceptance walk (codex-review F2 fix + round-3 contract): this entry
    API is ASK-ONLY -- every non-``"ask"`` ``side`` raises
    :class:`ValueError` immediately (a bid ladder must never be walked as
    a pseudo-ask acceptance walk; use :func:`walk_book` directly for
    bid-side valuation). Every acceptance check -- ``fill_250``,
    ``entry_window``, the exec/worst-variant edges and ``entry_price`` --
    is computed from a walk this function performs itself:
    ``walk_book(book, side='ask', notional=250)`` over the passed book. A
    custom ``notional`` (ask side) never feeds an acceptance check; it
    only produces a supplementary ``GateReport.valuation_walk`` for
    valuation information, and invalid values still raise
    :class:`ValueError` from :func:`walk_book`.

    ``model_quote`` is any object or mapping exposing ``model_median``
    and ``qs_variants`` for the side being bought (e.g.
    :class:`~polymarket_alpha_lab.papersim.soccer_model.SoccerCandidate`);
    liquidity falls back to quote fields ``gamma_liquidity``/``liq_gamma``/``liq``
    and missing liquidity counts as 0 (the liq gate fails, lineage
    ``liq = b['liq'] or 0``). Missing news evidence fails the
    ``news_concordant`` check: candidacy requires concordance.

    Fee accounting (2026-11-05 fix): ``fee_rate`` is charged per share
    as :func:`fee_cost` at the walked entry price and subtracted from
    the executable edge BEFORE the exec bar comparison -- the frozen
    +5c bar (and the +8c under_risk bar) are NET-edge bars. The gross
    edge is preserved as ``GateReport.exec_edge_gross``; the net edge is
    ``GateReport.exec_edge`` and the haircut acts on it. ``fee_rate``
    must be a finite non-negative number.
    """
    median = float(_quote_field(model_quote, "model_median"))
    variants = tuple(float(v) for v in _quote_field(model_quote, "qs_variants"))
    if not variants:
        raise ValueError("model_quote carries no qs_variants")
    if gamma_liquidity is not None:
        liq = float(gamma_liquidity)
    else:
        liq = float(
            _quote_optional(model_quote, ("gamma_liquidity", "liq_gamma", "liq"), 0.0)
        )
    # N1 fix: every numeric input must be finite BEFORE any min/max/comparison --
    # non-leading NaN inside qs_variants is silently skipped by min()/max(), and
    # infinite medians/liquidity pass threshold comparisons outright.
    import math as _math
    _nonfinite = [name for name, val in (("model_median", median), ("gamma_liquidity", liq)) if not _math.isfinite(val)]
    _nonfinite += [f"qs_variants[{i}]" for i, v in enumerate(variants) if not _math.isfinite(v)]
    if _nonfinite:
        raise ValueError(f"non-finite model evidence rejected: {', '.join(_nonfinite)}")
    if not _math.isfinite(fee_rate) or fee_rate < 0:
        raise ValueError(
            f"fee_rate must be a finite non-negative number, got {fee_rate!r}"
        )
    # F2 residual fix (review round 2): the single-ladder entry API is ASK-ONLY.
    # A caller passing a bid ladder with side="bid" would otherwise get an
    # ascending pseudo-ask walk over bids (false entry eligibility); callers
    # wanting bid valuation must call walk_book directly.
    if side != "ask":
        raise ValueError(
            "evaluate_candidate acceptance is ask-only; use walk_book directly for bid-side valuation"
        )
    # Materialize once: the acceptance walk and the optional supplementary
    # walk must see the same levels even when ``book`` is a generator.
    levels = list(book)
    # Acceptance walk: hardcoded $250 ASK walk, immune to caller side/notional.
    walk = walk_book(levels, side=SIDE_ASK, notional=DEFAULT_NOTIONAL_USD)
    valuation_walk = None
    if (side, notional) != (SIDE_ASK, DEFAULT_NOTIONAL_USD):
        valuation_walk = walk_book(levels, side=side, notional=notional)
    variant_spread = round(max(variants) - min(variants), 4)
    worst_model = min(variants)
    if walk.vwap is None:
        exec_edge_gross = None
        exec_edge = None
        worst_edge = None
        exec_edge_haircut = None
        haircut = 1.0
    else:
        exec_edge_gross = round(median - walk.vwap, 4)
        # Fee accounting (2026-11-05 fix): the exec bar is a NET-edge bar.
        # The per-share fee is charged at the walked entry price and
        # subtracted from the executable edge BEFORE the bar comparison;
        # the 50-50 haircut then acts on the NET edge (4-dp rounding at
        # each step, lineage convention).
        fee = round(fee_cost(walk.vwap, fee_rate), 4)
        exec_edge = round(exec_edge_gross - fee, 4)
        worst_edge = round(worst_model - walk.vwap, 4)
        haircut = cancellation_haircut(median)
        exec_edge_haircut = round(exec_edge * haircut, 4)
    exec_bar = UNDER_RISK_EXEC_EDGE_MIN if under_risk else GATES["exec_edge_min"]
    exec_key = "exec>=+8c" if under_risk else "exec>=+5c"
    checks: dict[str, bool] = {
        "variant_spread<=6c": variant_spread <= GATES["variant_spread_max"] + GATE_EPSILON,
        "worst>=+4c": worst_edge is not None
        and worst_edge >= GATES["worst_edge_min"] - GATE_EPSILON,
        exec_key: exec_edge_haircut is not None and exec_edge_haircut >= exec_bar - GATE_EPSILON,
        "liq>=5k": liq >= GATES["liq_min"],
        "fill_250": walk.filled,
        "entry_window": walk.vwap is not None
        and ENTRY_WINDOW[0] <= walk.vwap <= ENTRY_WINDOW[1],
        "news_concordant": news is not None and news.concordant,
    }
    order: tuple[tuple[str, str], ...] = _CANDIDATE_CHECK_ORDER
    if under_risk:
        order = tuple(
            (exec_key, gate_id) if key == "exec>=+5c" else (key, gate_id)
            for key, gate_id in _CANDIDATE_CHECK_ORDER
        )
    failed = tuple(gate_id for key, gate_id in order if not checks[key])
    return GateReport(
        decision=GateDecision(passed=not failed, failed=failed),
        checks=checks,
        walk=walk,
        entry_price=walk.vwap,
        gamma_liquidity=liq,
        exec_edge_gross=exec_edge_gross,
        exec_edge=exec_edge,
        haircut=haircut,
        exec_edge_haircut=exec_edge_haircut,
        worst_variant_edge=worst_edge,
        variant_spread=variant_spread,
        under_risk=bool(under_risk),
        valuation_walk=valuation_walk,
    )


def rank_candidates(reports: Iterable[GateReport]) -> list[GateReport]:
    """Rank gated candidates: worst-variant margin first, then exec edge.

    Orders the survivors (usage.md): only reports whose ``decision``
    passed are ranked (codex-review F6 fix) -- a rejected candidate
    (news-discordant, liquidity-failed, thin book, out-of-window entry)
    is excluded no matter how high its edges are. Lineage ordering
    (r15 finalize): ``sort(key=(-edge_worst_variant,
    -edge_exec_haircut))`` -- agreement margin dominates, the
    haircut-adjusted exec edge breaks ties. Reports without computable
    edges (empty book) are not rankable and are dropped.
    """
    rankable = [
        r
        for r in reports
        if r.decision.passed
        and r.worst_variant_edge is not None
        and r.exec_edge_haircut is not None
    ]
    return sorted(rankable, key=lambda r: (-r.worst_variant_edge, -r.exec_edge_haircut))


def evaluate_gates(
    *,
    variant_spread: float,
    worst_variant_edge: float,
    median_exec_edge: float,
    gamma_liquidity: float,
    fee_rate: float | None = None,
    entry_price: float | None = None,
) -> GateDecision:
    """Evaluate the four frozen numeric gates for one candidate.

    ``median_exec_edge`` is compared with ``exec_edge_min`` as supplied:
    callers must apply the 50-50 cancellation haircut (:func:`haircut_edge`)
    BEFORE calling, per the r15 application order (edge halved first,
    then barred). Boundary values pass (round-24 epsilon tolerances).

    Fee accounting (2026-11-05 fix): passing ``fee_rate`` together with
    ``entry_price`` (both keyword-only, both or neither) makes the exec
    gate a NET-edge gate -- ``median_exec_edge`` is then interpreted as
    the GROSS edge and :func:`fee_cost` at ``entry_price`` is subtracted
    from it before the bar comparison, exactly as :func:`evaluate_candidate`
    does internally. Without the pair, the edge is compared as supplied
    (the frozen as-supplied contract; callers who already netted the fee
    or replay frozen gross records keep byte-identical behavior).

    Non-finite inputs (NaN, +/-inf) are rejected with :class:`ValueError`
    (codex-review F3 fix): NaN compares False against every threshold and
    would otherwise pass all four gates.
    """
    inputs = {
        "variant_spread": variant_spread,
        "worst_variant_edge": worst_variant_edge,
        "median_exec_edge": median_exec_edge,
        "gamma_liquidity": gamma_liquidity,
    }
    non_finite = [name for name, value in inputs.items() if not math.isfinite(value)]
    if non_finite:
        raise ValueError(
            "evaluate_gates inputs must be finite numbers; non-finite: "
            + ", ".join(non_finite)
        )
    if (fee_rate is None) != (entry_price is None):
        raise ValueError(
            "fee accounting requires both fee_rate and entry_price "
            "(pass neither to compare the exec edge as supplied)"
        )
    if fee_rate is not None and entry_price is not None:
        if not math.isfinite(fee_rate) or fee_rate < 0:
            raise ValueError(
                f"fee_rate must be a finite non-negative number, got {fee_rate!r}"
            )
        if not math.isfinite(entry_price):
            raise ValueError(
                f"entry_price must be a finite number, got {entry_price!r}"
            )
        median_exec_edge = round(
            median_exec_edge - round(fee_cost(entry_price, fee_rate), 4), 4
        )
    failed: list[str] = []
    if variant_spread > GATES["variant_spread_max"] + GATE_EPSILON:
        failed.append("variant_spread")
    if worst_variant_edge < GATES["worst_edge_min"] - GATE_EPSILON:
        failed.append("worst_edge")
    if median_exec_edge < GATES["exec_edge_min"] - GATE_EPSILON:
        failed.append("exec_edge")
    if gamma_liquidity < GATES["liq_min"]:
        failed.append("liq")
    return GateDecision(passed=not failed, failed=tuple(failed))
