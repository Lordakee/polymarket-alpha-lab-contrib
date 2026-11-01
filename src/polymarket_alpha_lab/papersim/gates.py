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
"""

from __future__ import annotations

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
    "cross-league match_winner BANNED: confirmed structural defect - bespoke "
    "scripts combined domestic xG multipliers across leagues without a "
    "league-strength bridge and produced the HOF-LYO favorite flip "
    "(review/FIXES.md 2026-10-30); stays banned until a league-strength-bridged "
    "UCL/UEL walk-forward backtest passes"
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
    ("match_winner", True): (POLICY_BANNED, False, REASON_CROSS_LEAGUE_MATCH_WINNER),
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
    """

    decision: GateDecision
    checks: Mapping[str, bool]
    walk: BookWalk
    entry_price: float | None
    gamma_liquidity: float
    exec_edge: float | None
    haircut: float
    exec_edge_haircut: float | None
    worst_variant_edge: float | None
    variant_spread: float
    under_risk: bool


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

    Cross-league match_winner is BANNED (structural defect), domestic
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
) -> GateReport:
    """Evaluate the full tightened gate set for one candidate.

    The composite entry point over the frozen :func:`evaluate_gates`
    (whose numeric signature cannot take a book): walks ``book`` to the
    $250 VWAP on ``side`` (default entry ask), computes the exec and
    worst-variant edges versus the walked price, applies the 50-50
    cancellation haircut BEFORE the exec bar, raises the exec bar to +8c
    when ``under_risk`` is set, and requires the entry window, a
    completed $250 walk (real-depth intent), the Gamma liquidity floor
    and a concordant :class:`NewsCheck`. ``model_quote`` is any object or
    mapping exposing ``model_median`` and ``qs_variants`` for the side
    being bought (e.g. :class:`~polymarket_alpha_lab.papersim.soccer_model.SoccerCandidate`);
    liquidity falls back to quote fields ``gamma_liquidity``/``liq_gamma``/``liq``
    and missing liquidity counts as 0 (the liq gate fails, lineage
    ``liq = b['liq'] or 0``). Missing news evidence fails the
    ``news_concordant`` check: candidacy requires concordance.
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
    walk = walk_book(book, side=side, notional=notional)
    variant_spread = round(max(variants) - min(variants), 4)
    worst_model = min(variants)
    if walk.vwap is None:
        exec_edge = None
        worst_edge = None
        exec_edge_haircut = None
        haircut = 1.0
    else:
        exec_edge = round(median - walk.vwap, 4)
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
        exec_edge=exec_edge,
        haircut=haircut,
        exec_edge_haircut=exec_edge_haircut,
        worst_variant_edge=worst_edge,
        variant_spread=variant_spread,
        under_risk=bool(under_risk),
    )


def rank_candidates(reports: Iterable[GateReport]) -> list[GateReport]:
    """Rank gated candidates: worst-variant margin first, then exec edge.

    Lineage ordering (r15 finalize): ``sort(key=(-edge_worst_variant,
    -edge_exec_haircut))`` -- agreement margin dominates, the
    haircut-adjusted exec edge breaks ties. Reports without computable
    edges (empty book) are not rankable and are dropped.
    """
    rankable = [
        r
        for r in reports
        if r.worst_variant_edge is not None and r.exec_edge_haircut is not None
    ]
    return sorted(rankable, key=lambda r: (-r.worst_variant_edge, -r.exec_edge_haircut))


def evaluate_gates(
    *,
    variant_spread: float,
    worst_variant_edge: float,
    median_exec_edge: float,
    gamma_liquidity: float,
) -> GateDecision:
    """Evaluate the four frozen numeric gates for one candidate.

    ``median_exec_edge`` is compared with ``exec_edge_min`` as supplied:
    callers must apply the 50-50 cancellation haircut (:func:`haircut_edge`)
    BEFORE calling, per the r15 application order (edge halved first,
    then barred). Boundary values pass (round-24 epsilon tolerances).
    """
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
