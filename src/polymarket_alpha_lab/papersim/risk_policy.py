"""Paper sizing and bankroll policy.

Single responsibility: convert gated candidates into paper stake amounts
under the unit-size and cash-availability rules, and answer whether the
bankroll can absorb a new entry. Pure arithmetic on caller-supplied
state; this module never touches real money, real accounts or orders
(paper-only boundary).

Canonical lineage: sizing discipline stabilized in the soccer lineage
(``r5c -> r15 -> r23``; e.g. round23 ``bankroll_context`` with
``3 x $250`` paper entries) and the crypto lineage (``r19``, team-at-cap
monitoring mode). The r24 head adds max-new-candidates-per-round caps.

WP-P1 implementation notes (implementation commit): the P0 stub surfaces
(``PaperStake``, :func:`paper_stake`, :func:`bankroll_available`) keep
their frozen signatures (``paper_stake`` only gains defaulted
keyword-only ``units``/``currency`` arguments, so existing call sites are
unchanged). Added alongside: sizing tiers (FULL_EDGE / MARGINAL /
EARLY_ENTRY), parameterized team caps (the r19 crypto ``$1,900`` cap
pattern), held-fixture correlation rules (no same-direction adds; nested
bets count as one risk unit) and the bankroll identity checker with
exit-aware record accounting (EXITED excluded from W/L, included in PnL).
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

# Sizing-tier names and notional bounds (book of record).
TIER_FULL_EDGE = "FULL_EDGE"
TIER_MARGINAL = "MARGINAL"
TIER_EARLY_ENTRY = "EARLY_ENTRY"

FULL_EDGE_NOTIONAL_USD = 250.0
MARGINAL_NOTIONAL_USD = 150.0
EARLY_ENTRY_MIN_NOTIONAL_USD = 150.0
EARLY_ENTRY_MAX_NOTIONAL_USD = 250.0

STANDARD_CLASS = "standard"
DOMESTIC_ML_CLASS = "domestic_ml"
# Cross-league match_winner sizing class (codex-review finding 4,
# 2026-11-07): the book-of-record wording caps bridged cross-league MW
# at $150 marginal sizing (T4 accumulation: >=20 settled cross-league MW
# bets before standard sizing), so this class can ONLY ever produce the
# MARGINAL tier -- never the full $250 unit.
CROSS_LEAGUE_ML_CLASS = "cross_league_ml"

# Team cap pattern from the r19 crypto head ("team AT CAP $1,870/$1,900"):
# parameterized, defaulting to the crypto book-of-record value.
DEFAULT_TEAM_CAP_USD = 1900.0

# Paper ledger starts from the book-of-record initial bankroll
# (cash = initial - sum(stakes) + sum(realized payoffs)).
INITIAL_BANKROLL_USD = 10000.0

# Position statuses for record accounting.
STATUS_WON = "WON"
STATUS_LOST = "LOST"
STATUS_EXITED = "EXITED"
STATUS_OPEN = "OPEN"

# Direction families for correlation grouping (goal-correlation / event
# side): over/yes style sides are one direction, under/no the other.
DIRECTION_LONG = "long"
DIRECTION_SHORT = "short"
DIRECTION_UNKNOWN = "unknown"


def _require_finite_amount(name: str, value: object) -> float:
    """Validate one monetary input BEFORE any clamping/comparison/rounding.

    Non-finite amounts must fail loudly, not silently: a NaN flowing
    into ``max(0.0, x)`` / ``min(a, b)`` compares False against every
    bound, so e.g. a NaN ``reserved`` was silently dropped (returning
    the unreserved amount as spendable) instead of rejected (codex
    review 2026-11-03, major 2). ``bool`` is rejected explicitly even
    though it subclasses ``int`` — ``True`` must never pass as ``$1``.
    """
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number, got {value!r} (bool)")
    try:
        amount = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite number, got {value!r}") from exc
    if not math.isfinite(amount):
        raise ValueError(f"{name} must be a finite number, got {value!r}")
    return amount


@dataclass(frozen=True)
class PaperStake:
    """One paper stake decision for a gated candidate."""

    fixture: str
    question: str
    notional: float
    entry_price: float
    currency: str


@dataclass(frozen=True)
class SizingTier:
    """Sizing tier for one gated candidate.

    ``min_notional``/``max_notional`` bracket the allowed stake; a tier
    with equal bounds is a fixed unit (FULL_EDGE $250, MARGINAL $150)
    while EARLY_ENTRY scales between its bounds with lineup
    confirmation.
    """

    tier: str
    min_notional: float
    max_notional: float
    reason: str


@dataclass(frozen=True)
class TeamCapStatus:
    """Team-cap arithmetic for one asset/team exposure class."""

    committed: float
    cap: float
    unit_notional: float
    remaining: float
    at_cap: bool

    def allows(self, stake: float) -> bool:
        """Whether one more stake of ``stake`` fits under the cap."""
        return self.committed + float(stake) <= self.cap + 1e-9


@dataclass(frozen=True)
class CorrelationDecision:
    """Held-fixture correlation ruling for one prospective add."""

    allowed: bool
    reason: str


@dataclass(frozen=True)
class SettledPosition:
    """One realized or open paper position for record accounting.

    ``proceeds`` is the realized cash returned: settlement payoff for
    WON, exit sale proceeds for EXITED, 0 for LOST and OPEN.
    """

    position_id: str
    status: str
    stake: float
    proceeds: float = 0.0


@dataclass(frozen=True)
class BankrollCheck:
    """Result of the cash-identity checker."""

    ok: bool
    reported_cash: float
    expected_cash: float
    difference: float
    tolerance: float


@dataclass(frozen=True)
class RecordSummary:
    """W/L/PnL summary where EXITED positions are excluded from the
    win/loss counts but included in realized PnL."""

    wins: int
    losses: int
    exits: int
    open_positions: int
    win_rate: float | None
    pnl: float
    staked_total: float
    payoff_total: float


def paper_stake(
    fixture: str,
    question: str,
    entry_price: float,
    *,
    unit_notional: float = 250.0,
    units: int = 1,
    currency: str = "USD",
) -> PaperStake:
    """Size a paper entry as whole units of ``unit_notional`` (default $250).

    ``units`` must be a whole positive integer, so the notional is always
    a whole-unit multiple (fractional sizing is a policy violation, not a
    rounding event). Price bounds are structural (0 < p <= 1); the entry
    window itself is a gate concern, enforced in
    :mod:`polymarket_alpha_lab.papersim.gates`. All amounts
    (``entry_price``, ``unit_notional``) must be finite numbers; a NaN
    or infinite amount raises ``ValueError`` before any sizing
    arithmetic.
    """
    price = _require_finite_amount("entry_price", entry_price)
    if not 0.0 < price <= 1.0:
        raise ValueError(f"entry_price must be in (0, 1], got {entry_price!r}")
    unit = _require_finite_amount("unit_notional", unit_notional)
    if unit <= 0:
        raise ValueError("unit_notional must be positive")
    if (
        isinstance(units, bool)
        or not math.isfinite(float(units))
        or int(units) != units
        or units < 1
    ):
        raise ValueError(f"units must be a whole positive integer, got {units!r}")
    return PaperStake(
        fixture=fixture,
        question=question,
        notional=round(units * unit, 2),
        entry_price=price,
        currency=currency,
    )


def bankroll_available(
    bankroll: float,
    cash: float,
    reserved: float,
) -> float:
    """Cash available for new paper entries after reserved commitments.

    The r23 shape: ``bankroll`` (cash + open marks) never unlocks more
    than ``cash``, and committed-but-unsettled reservations come off the
    top. Never negative. All three amounts must be finite numbers: a
    NaN/Inf ``bankroll``, ``cash`` or ``reserved`` raises
    ``ValueError`` BEFORE any clamping or comparison (a NaN reserved
    used to be silently dropped by ``max(0.0, nan) == 0.0``,
    overstating spendable cash — codex review 2026-11-03, major 2).
    """
    bankroll_value = _require_finite_amount("bankroll", bankroll)
    cash_value = _require_finite_amount("cash", cash)
    reserved_value = _require_finite_amount("reserved", reserved)
    usable = min(cash_value, bankroll_value)
    return round(max(0.0, usable - max(0.0, reserved_value)), 2)


def sizing_tier(
    *,
    market_class: str = STANDARD_CLASS,
    fragile_pass: bool = False,
    lineup_confirmation: float | None = None,
) -> SizingTier:
    """Select the sizing tier for one gated candidate.

    - MARGINAL ($150 fixed): the cross-league match_winner deprioritized
      class (unconditionally -- it can never size at the full $250 unit)
      and the domestic match_winner deprioritized class combined with a
      fragile gate pass.
    - EARLY_ENTRY ($150-$250): lineups not yet confirmed; the stake
      scales up with ``lineup_confirmation`` (0 = predicted-only, 1 =
      official XIs confirmed) via :func:`tier_notional`.
    - FULL_EDGE ($250): clean pass on a confirmed or non-lineup-sensitive
      state.

    ``lineup_confirmation`` outside [0, 1] is rejected. MARGINAL takes
    precedence: a fragile domestic-ML pass stays at $150 regardless of
    lineup state, and the cross-league class stays at $150 regardless of
    anything (neither lineup confirmation nor a non-fragile pass
    graduates it; T4 accumulation wording: >=20 settled cross-league MW
    bets before standard sizing).
    """
    if lineup_confirmation is not None and not 0.0 <= float(lineup_confirmation) <= 1.0:
        raise ValueError(
            f"lineup_confirmation must be in [0, 1], got {lineup_confirmation!r}"
        )
    klass = str(market_class or STANDARD_CLASS).strip().lower()
    if klass == CROSS_LEAGUE_ML_CLASS:
        # codex-review finding 4 (2026-11-07): the cross-league MW class
        # can ONLY ever produce the $150 deprioritized tier -- never the
        # full $250 -- exactly as the book-of-record wording requires
        # ("$150 marginal sizing"). Unconditional by design: candidacy
        # prerequisites (explicit bridge + worst-variant >= +5c) are
        # enforced upstream by gates.check_cross_league_mw, not here.
        return SizingTier(
            tier=TIER_MARGINAL,
            min_notional=MARGINAL_NOTIONAL_USD,
            max_notional=MARGINAL_NOTIONAL_USD,
            reason=(
                "cross-league match_winner deprioritized class: fixed $150 "
                "marginal unit (bridge + worst-variant >= +5c enforced by "
                "gates.check_cross_league_mw; T4 accumulation: >=20 settled "
                "cross-league MW bets before standard sizing)"
            ),
        )
    if klass == DOMESTIC_ML_CLASS and fragile_pass:
        return SizingTier(
            tier=TIER_MARGINAL,
            min_notional=MARGINAL_NOTIONAL_USD,
            max_notional=MARGINAL_NOTIONAL_USD,
            reason=(
                "domestic match_winner deprioritized class with a fragile gate "
                "pass: fixed reduced unit"
            ),
        )
    if lineup_confirmation is not None and lineup_confirmation < 1.0 - 1e-9:
        return SizingTier(
            tier=TIER_EARLY_ENTRY,
            min_notional=EARLY_ENTRY_MIN_NOTIONAL_USD,
            max_notional=EARLY_ENTRY_MAX_NOTIONAL_USD,
            reason=(
                "lineups not confirmed: stake scales $150-$250 with lineup "
                "confirmation state"
            ),
        )
    return SizingTier(
        tier=TIER_FULL_EDGE,
        min_notional=FULL_EDGE_NOTIONAL_USD,
        max_notional=FULL_EDGE_NOTIONAL_USD,
        reason="clean full-edge pass: standard unit",
    )


def tier_notional(tier: SizingTier, *, lineup_confirmation: float | None = None) -> float:
    """Stake notional for a tier, scaling EARLY_ENTRY by confirmation.

    EARLY_ENTRY maps confirmation 0 -> $150 (predicted-only lineups) up
    to confirmation 1 -> $250 (official XIs); the value is clamped to
    the tier bounds. Fixed tiers return their fixed unit.
    """
    if tier.tier == TIER_EARLY_ENTRY and lineup_confirmation is not None:
        fraction = min(max(float(lineup_confirmation), 0.0), 1.0)
        scaled = EARLY_ENTRY_MIN_NOTIONAL_USD + (
            EARLY_ENTRY_MAX_NOTIONAL_USD - EARLY_ENTRY_MIN_NOTIONAL_USD
        ) * fraction
        return round(
            min(max(scaled, tier.min_notional), tier.max_notional),
            2,
        )
    if tier.tier == TIER_FULL_EDGE:
        return FULL_EDGE_NOTIONAL_USD
    if tier.tier == TIER_MARGINAL:
        return MARGINAL_NOTIONAL_USD
    raise ValueError(f"unknown sizing tier: {tier!r}")


def team_cap_status(
    committed_notional: float,
    *,
    cap: float = DEFAULT_TEAM_CAP_USD,
    unit_notional: float = FULL_EDGE_NOTIONAL_USD,
) -> TeamCapStatus:
    """Team-cap arithmetic (the r19 crypto ``$1,900`` pattern).

    ``at_cap`` means one more standard unit does NOT fit under the cap
    (r19: committed $1,870 + unit $250 > $1,900 -> AT CAP, monitoring
    mode, hold-do-not-add), not merely ``committed >= cap``. All
    amounts must be finite numbers: NaN/Inf ``committed_notional``,
    ``cap`` or ``unit_notional`` raises ``ValueError`` before any cap
    arithmetic.
    """
    committed = _require_finite_amount("committed_notional", committed_notional)
    if committed < 0:
        raise ValueError("committed_notional must be non-negative")
    cap_value = _require_finite_amount("cap", cap)
    if cap_value <= 0:
        raise ValueError("cap must be positive")
    unit_value = _require_finite_amount("unit_notional", unit_notional)
    if unit_value <= 0:
        raise ValueError("unit_notional must be positive")
    remaining = round(max(0.0, cap_value - committed), 2)
    at_cap = committed + unit_value > cap_value + 1e-9
    return TeamCapStatus(
        committed=round(committed, 2),
        cap=cap_value,
        unit_notional=unit_value,
        remaining=remaining,
        at_cap=at_cap,
    )


def team_add_allowed(
    committed_notional: float,
    stake: float,
    *,
    cap: float = DEFAULT_TEAM_CAP_USD,
) -> bool:
    """Whether a specific additional stake fits under the team cap."""
    return float(committed_notional) + float(stake) <= cap + 1e-9


def side_direction(side: str) -> str:
    """Direction family of a side label.

    ``Over/Yes(side0)``-style labels map to ``long`` (the over/event-yes
    family), ``Under/No(side1)``-style to ``short``; anything
    unclassifiable is ``unknown`` and treated conservatively by the
    correlation rules.
    """
    label = str(side or "").strip().lower()
    if label.startswith("over") or label.startswith("yes"):
        return DIRECTION_LONG
    if label.startswith("under") or label.startswith("no"):
        return DIRECTION_SHORT
    return DIRECTION_UNKNOWN


def held_fixture_add_allowed(held_sides: Iterable[str], side: str) -> CorrelationDecision:
    """Correlation rule for adding exposure on an already-held fixture.

    No same-direction adds on held fixtures (r15/r24 goal-correlation
    concentration rule): an add in the same direction family as any held
    side on the fixture is blocked; an opposite-direction add is allowed.
    A held side OR a prospective side that cannot be classified blocks
    conservatively: an unclassifiable prospective side cannot be
    established as opposite to any held side.
    """
    new_direction = side_direction(side)
    for held in held_sides:
        if new_direction == DIRECTION_UNKNOWN:
            return CorrelationDecision(
                allowed=False,
                reason=(
                    "held-fixture correlation rule (no same-direction adds on "
                    f"held fixtures): new side {side!r} cannot be classified "
                    "into a direction family, so it cannot be established as "
                    "opposite to a held side"
                ),
            )
        held_direction = side_direction(held)
        if held_direction == DIRECTION_UNKNOWN or held_direction == new_direction:
            return CorrelationDecision(
                allowed=False,
                reason=(
                    "held-fixture correlation rule (no same-direction adds on "
                    f"held fixtures): held {held!r} vs new {side!r}"
                ),
            )
    return CorrelationDecision(
        allowed=True,
        reason="no held position in the same direction on this fixture",
    )


def _position_fields(position: Any) -> tuple[str, str]:
    """Extract ``(fixture, side)`` from a position-ish input."""
    if isinstance(position, Mapping):
        fixture = position.get("fixture")
        side = position.get("side")
    elif isinstance(position, (tuple, list)) and len(position) >= 2:
        fixture, side = position[0], position[1]
    else:
        fixture = getattr(position, "fixture", None)
        side = getattr(position, "side", None)
    if fixture is None or side is None:
        raise ValueError(f"cannot extract fixture/side from position {position!r}")
    return str(fixture), str(side)


def risk_unit_keys(positions: Iterable[Any]) -> tuple[tuple[str, str], ...]:
    """Deduplicated risk-unit keys for a set of positions.

    A risk unit is one ``(fixture, direction)`` family: nested bets (an
    O2.5 Over plus an O3.5 Over plus a team-total Over on the same
    fixture) count as ONE risk unit, while an opposite-direction
    position on the same fixture is a separate unit.
    """
    keys: list[tuple[str, str]] = []
    for position in positions:
        fixture, side = _position_fields(position)
        key = (fixture, side_direction(side))
        if key not in keys:
            keys.append(key)
    return tuple(keys)


def count_risk_units(positions: Iterable[Any]) -> int:
    """Number of distinct risk units (nested bets collapse to one)."""
    return len(risk_unit_keys(positions))


def _settled_fields(position: Any) -> SettledPosition:
    """Normalize a position-ish input into a :class:`SettledPosition`."""
    if isinstance(position, SettledPosition):
        return position
    if isinstance(position, Mapping):
        return SettledPosition(
            position_id=str(position.get("position_id", "")),
            status=str(position["status"]).upper(),
            stake=float(position["stake"]),
            proceeds=float(position.get("proceeds", 0.0) or 0.0),
        )
    stake = getattr(position, "stake", None)
    status = getattr(position, "status", None)
    if stake is None or status is None:
        raise ValueError(f"cannot extract status/stake from position {position!r}")
    return SettledPosition(
        position_id=str(getattr(position, "position_id", "")),
        status=str(status).upper(),
        stake=float(stake),
        proceeds=float(getattr(position, "proceeds", 0.0) or 0.0),
    )


def position_pnl(position: SettledPosition) -> float:
    """Realized PnL of one position; OPEN positions carry none."""
    if position.status == STATUS_OPEN:
        return 0.0
    return round(position.proceeds - position.stake, 2)


def settle_record(positions: Iterable[Any]) -> RecordSummary:
    """Aggregate W/L/PnL with exit-aware accounting.

    EXITED positions are excluded from the win/loss counts (win_rate is
    over WON+LOST only, None when nothing settled) but their realized
    PnL is included in ``pnl``; OPEN positions contribute stake
    commitment only. Lineage: ``review/settled_ledger.json`` ->
    ``review/model_performance.json`` (40 settled, 5 EXITED -> 22W-13L,
    exit PnL inside the total).
    """
    wins = losses = exits = opens = 0
    pnl = staked = payoff = 0.0
    for raw in positions:
        position = _settled_fields(raw)
        staked += position.stake
        if position.status == STATUS_WON:
            wins += 1
            payoff += position.proceeds
            pnl += position_pnl(position)
        elif position.status == STATUS_LOST:
            losses += 1
            payoff += position.proceeds
            pnl += position_pnl(position)
        elif position.status == STATUS_EXITED:
            exits += 1
            payoff += position.proceeds
            pnl += position_pnl(position)
        elif position.status == STATUS_OPEN:
            opens += 1
        else:
            raise ValueError(f"unknown position status {position.status!r}")
    settled = wins + losses
    return RecordSummary(
        wins=wins,
        losses=losses,
        exits=exits,
        open_positions=opens,
        win_rate=(round(wins / settled, 6) if settled else None),
        pnl=round(pnl, 2),
        staked_total=round(staked, 2),
        payoff_total=round(payoff, 2),
    )


def expected_cash(
    stakes: Iterable[float],
    payoffs: Iterable[float],
    *,
    initial: float = INITIAL_BANKROLL_USD,
) -> float:
    """Bankroll cash identity: ``initial - sum(stakes) + sum(payoffs)``.

    ``stakes`` are ALL entry stakes ever laid (open and closed);
    ``payoffs`` are realized payoffs (WON settlement proceeds plus EXITED
    sale proceeds). Open marks are not cash and do not appear here.
    """
    return round(float(initial) - math.fsum(stakes) + math.fsum(payoffs), 2)


def check_bankroll_identity(
    reported_cash: float,
    stakes: Iterable[float],
    payoffs: Iterable[float],
    *,
    initial: float = INITIAL_BANKROLL_USD,
    tolerance: float = 0.005,
) -> BankrollCheck:
    """Flag any mismatch between reported cash and the cash identity.

    ``ok`` is True when ``|reported - expected| <= tolerance`` (default
    half a cent); a False result is a ledger-integrity flag, not an
    auto-correction.
    """
    expected = expected_cash(stakes, payoffs, initial=initial)
    reported = round(float(reported_cash), 2)
    difference = round(reported - expected, 2)
    return BankrollCheck(
        ok=abs(difference) <= tolerance + 1e-12,
        reported_cash=reported,
        expected_cash=expected,
        difference=difference,
        tolerance=tolerance,
    )
