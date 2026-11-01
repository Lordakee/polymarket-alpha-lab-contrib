"""Paper position ledger records.

Single responsibility: build and mark the paper ledger entries (open,
hold, exit, realized/unrealized) for gated paper positions, and compute
the per-position marks used in reports. This module defines the record
shapes and the arithmetic only. Durable persistence of these records is
project-private native PostgreSQL (Project Iron Rule 1) via the store
adapters elsewhere in this package; this module must not create
file-backed journals (legacy file surfaces are frozen).

Canonical lineage: coordinator-maintained ledger practice from the soccer
lineage (``r5c -> r15 -> r23``; position ids such as ``#48
Brentford-Forest O2.5 Over $250 @ 0.560`` with r24 recheck blocks) and the
crypto lineage (``r19`` positions-MTM table). Paper-only: entries record
simulated fills, never real orders.

WP-P1 ledger DSN, settlement arithmetic and DDL (W4):

- ``papersim_dsn()`` resolves the ledger DSN from ``PAPERSIM_PG_DSN``
  (documented example default:
  ``postgresql://paper_sim@127.0.0.1:55432/paper_sim``, the loopback
  paper_sim evidence cluster) and always passes the value through the
  single audited ``validate_local_postgres_dsn`` with
  ``env_var_name="PAPERSIM_PG_DSN"`` before any caller can open a
  connection. The SCRAM password is never part of the DSN and is never
  read, printed or committed by this module: operators inject it
  out-of-band via ``PAPERSIM_PG_PASSWORD_FILE`` (an environment variable
  holding the path of a one-line password file); only a connection
  adapter explicitly asked to connect may read that path at connect
  time. There is no default password path.
- ``classify_outcome`` buckets a resolution outcome as open / exited /
  settled. A discipline ``EXITED`` realizes trading PnL but is never a
  win or a loss: ``settle_natural`` rejects it and
  ``PaperSettlement.win_loss`` is ``None`` for exits, matching the fixed
  ``model_performance`` view (exits separated from W/L, included in
  total PnL) and the natural-resolution-only ``forecast_calibration``.
- ``settle_natural`` / ``settle_exit`` realize a position with
  ``pnl = proceeds - stake``: a natural win pays ``stake / price`` per
  $1.00 of payoff, a natural loss pays 0, and an exit realizes
  ``(stake / price) * exit_price`` (live book-of-record example: the Fed
  Jan-hike NO exited at 0.585 -> proceeds 339.30 on 580 shares).
- ``bankroll_identity`` checks the reconciled book-of-record identity
  ``bankroll == cash + deployed`` (2026-11-01 row: 12374.33 = 9488.68
  cash + 2885.65 deployed).
- ``ddl()`` returns the exact text of the checked-in migration
  ``20261101000000_papersim_ledger.sql``: the live paper_sim
  ``decisions`` / ``resolutions`` / ``bankroll`` tables and the fixed
  ``model_performance`` / ``forecast_calibration`` views, mirrored
  verbatim plus the documented repo-convention deltas of
  paper-only/report-only/readonly boundary columns on ``decisions``
  and the NO-basket clause added to the ``avg_prob_of_realized`` hit
  predicate so it matches ``forecast_hits`` (codex-review F5; the LIVE
  paper_sim cluster view still needs the same one-line fix applied
  operationally - this module never touches the live cluster).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math

from polymarket_alpha_lab.supabase_papersim_config import (
    DEFAULT_PAPERSIM_PG_DSN,
    PAPERSIM_PG_DSN_ENV_VAR,
    PAPERSIM_PG_PASSWORD_FILE_ENV_VAR,
    from_papersim_db_env,
)


PAPERSIM_LEDGER_MIGRATION_NAME = "20261101000000_papersim_ledger.sql"

OUTCOME_OPEN = "open"
OUTCOME_EXITED = "exited"
OUTCOME_SETTLED = "settled"
EXITED_OUTCOME = "EXITED"
NATURAL_OUTCOMES = ("YES", "NO", "YES-basket")


@dataclass(frozen=True)
class PaperLedgerEntry:
    """One immutable paper ledger event for a single position."""

    position_id: str
    fixture: str
    question: str
    side: str
    notional: float
    price: float
    event: str  # "entry" | "recheck" | "exit"
    evidence: tuple[str, ...]


def record_entry(
    position_id: str,
    fixture: str,
    question: str,
    side: str,
    notional: float,
    price: float,
    *,
    evidence: tuple[str, ...] = (),
) -> PaperLedgerEntry:
    """Build an entry event for a newly gated paper position."""
    raise NotImplementedError


def mark_to_market(entry_price: float, exit_bid: float) -> float:
    """Mark-to-market delta of a paper position versus its entry price."""
    raise NotImplementedError


def papersim_dsn(env: Mapping[str, str] | None = None) -> str:
    """Return the validated paper-sim ledger DSN.

    Resolution order:

    1. ``PAPERSIM_PG_DSN`` from ``env`` (default: the process
       environment, read inside the sanctioned config module
       ``supabase_papersim_config``), when set to a non-empty value.
    2. The documented example default
      ``postgresql://paper_sim@127.0.0.1:55432/paper_sim`` (loopback
       paper_sim cluster; no password embedded in the DSN).

    The resolved value always passes through the single audited
    ``validate_local_postgres_dsn`` with ``env_var_name="PAPERSIM_PG_DSN"``
    (both inside ``SupabasePapersimConfig``), so hosted hosts,
    keyword-DSN socket escapes and sqlite/jsonl file fallbacks are
    rejected here rather than at connect time.

    Password convention (documented only; never default-read, never
    printed, never committed): the SCRAM password for the ``paper_sim``
    role is supplied out-of-band via ``PAPERSIM_PG_PASSWORD_FILE`` — an
    environment variable holding the path of a one-line password file
    owned by the operator. This function never reads, logs or commits
    that file or its contents, and no default path exists. Only a
    connection adapter explicitly directed to connect may read the path
    at connect time and must never include it in logs or errors.
    """
    return from_papersim_db_env(env).resolved_dsn()


def classify_outcome(outcome: str | None) -> str:
    """Classify a resolution outcome as ``open`` / ``exited`` / ``settled``.

    ``None`` (no resolution row yet) means the position is still open.
    ``"EXITED"`` is a discipline exit: realized trading PnL, but never a
    win or a loss for forecast scoring. ``"YES"`` / ``"NO"`` /
    ``"YES-basket"`` are natural market resolutions. Any other token is
    unknown data and raises instead of being silently bucketed
    (``null``, ``0`` and ``unknown`` stay distinguishable).
    """
    if outcome is None:
        return OUTCOME_OPEN
    if outcome == EXITED_OUTCOME:
        return OUTCOME_EXITED
    if outcome in NATURAL_OUTCOMES:
        return OUTCOME_SETTLED
    raise ValueError(f"unknown resolution outcome: {outcome!r}")


@dataclass(frozen=True)
class PaperSettlement:
    """Realized result of one paper position: ``pnl = proceeds - stake``."""

    classification: str  # OUTCOME_SETTLED | OUTCOME_EXITED
    proceeds: float
    pnl: float

    @property
    def win_loss(self) -> str | None:
        """``"win"`` / ``"loss"`` for natural resolutions; ``None`` for exits.

        Encodes the fixed-view rule that an ``EXITED`` position realizes
        PnL (included in ``total_pnl``) but is excluded from the win and
        loss counts (``EXITED`` is not W/L).
        """
        if self.classification != OUTCOME_SETTLED:
            return None
        return "win" if self.pnl > 0.0 else "loss"


def _require_finite(value: float, name: str) -> None:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")


def _require_stake_and_price(stake: float, price: float) -> None:
    _require_finite(stake, "stake")
    _require_finite(price, "price")
    if stake <= 0:
        raise ValueError("stake must be positive")
    if not 0.0 < price < 1.0:
        raise ValueError("price must be in the open interval (0, 1)")


def _natural_hit(side: str, outcome: str) -> bool:
    """Mirror the fixed ``forecast_calibration`` hit expression verbatim.

    ``YES`` and ``YES-basket`` sides hit when the natural outcome equals
    the side; ``NO`` and ``NO-basket`` sides hit when the outcome is
    ``NO`` (basket legs resolve on the natural ``NO``).
    """
    if side in ("YES", "YES-basket"):
        return outcome == side
    if side in ("NO", "NO-basket"):
        return outcome == "NO"
    raise ValueError(f"unknown side: {side!r}")


def settle_natural(
    stake: float,
    price: float,
    side: str,
    outcome: str,
) -> PaperSettlement:
    """Settle a naturally resolved position (win pays shares at $1.00).

    A win pays ``proceeds = stake / price`` (payout per $1.00 of payoff);
    a loss pays ``proceeds = 0``. In both cases ``pnl = proceeds - stake``.
    ``EXITED`` is not a natural resolution and is rejected here — use
    :func:`settle_exit` for discipline exits.
    """
    _require_stake_and_price(stake, price)
    if outcome not in NATURAL_OUTCOMES:
        raise ValueError(
            "settle_natural accepts natural resolutions only "
            f"({'/'.join(NATURAL_OUTCOMES)}); got {outcome!r} — use settle_exit for EXITED"
        )
    proceeds = stake / price if _natural_hit(side, outcome) else 0.0
    return PaperSettlement(
        classification=OUTCOME_SETTLED,
        proceeds=proceeds,
        pnl=proceeds - stake,
    )


def settle_exit(
    stake: float,
    price: float,
    exit_price: float,
) -> PaperSettlement:
    """Settle a discipline exit at ``exit_price`` (``pnl = proceeds - stake``).

    The exit realizes ``proceeds = (stake / price) * exit_price`` on the
    full position; the result is classified ``exited`` so it carries PnL
    but never a win/loss label (book-of-record example: $400 NO @ 0.690
    exited at 0.585 -> proceeds 339.30 on 580 recorded shares, pnl -60.70).
    """
    _require_stake_and_price(stake, price)
    _require_finite(exit_price, "exit_price")
    if not 0.0 <= exit_price <= 1.0:
        raise ValueError("exit_price must be in the closed interval [0, 1]")
    proceeds = (stake / price) * exit_price
    return PaperSettlement(
        classification=OUTCOME_EXITED,
        proceeds=proceeds,
        pnl=proceeds - stake,
    )


def bankroll_identity(
    bankroll: float,
    cash: float,
    deployed: float,
    *,
    tolerance: float = 0.005,
) -> bool:
    """Check the paper bankroll identity ``bankroll == cash + deployed``.

    The live book of record reconciles to exactly this identity (round-12
    recompute row and every subsequent row; e.g. 2026-11-01:
    12374.33 = 9488.68 cash + 2885.65 deployed). ``tolerance`` is a
    half-cent guard for money recorded at cent precision and float
    arithmetic; tighten or loosen it explicitly when needed.
    """
    for value, name in (
        (bankroll, "bankroll"),
        (cash, "cash"),
        (deployed, "deployed"),
    ):
        _require_finite(value, name)
    _require_finite(tolerance, "tolerance")
    if tolerance < 0.0:
        raise ValueError("tolerance must be non-negative")
    return abs(bankroll - (cash + deployed)) <= tolerance


_MIGRATION_DDL = """\
-- WP-P1 W4: paper-sim ledger DDL mirrored from the live paper_sim
-- evidence cluster (loopback 127.0.0.1:55432, pulled 2026-11-01).
-- Mirrored verbatim: decisions / resolutions / bankroll tables and the
-- FIXED model_performance / forecast_calibration views (exits separated
-- from W/L; forecast calibration judged on natural resolutions only).
-- Documented repo-convention deltas versus the live cluster: the
-- paper_only / report_only / readonly boundary columns on decisions,
-- matching the repo paper_trade migration style; and the
-- avg_prob_of_realized hit predicate adds the NO-basket clause
-- (codex-review F5) so it is identical to the forecast_hits predicate:
-- a winning NO-basket row contributes model_prediction, not its
-- complement.
-- OPERATIONAL NOTE: the LIVE paper_sim cluster forecast_calibration
-- view still carries the one-clause-short avg_prob_of_realized
-- predicate and needs this same one-line fix applied operationally by
-- an operator; this migration never touches the live cluster. This
-- schema is paper evidence storage only; it grants no order, account
-- or execution authorization.

create table public.decisions (
  id bigserial primary key,
  ts timestamptz default now(),
  market_id text,
  question text,
  side text,
  price numeric,
  shares numeric,
  stake numeric,
  fair_low numeric,
  fair_high numeric,
  spot numeric,
  vol numeric,
  horizon_days numeric,
  sizing text,
  reason text,
  team text default 'crypto_eth'::text,
  model_prediction numeric,
  market_type text,
  paper_only boolean not null default true check (paper_only is true),
  report_only boolean not null default true check (report_only is true),
  readonly boolean not null default true check (readonly is true)
);

create table public.resolutions (
  market_id text primary key,
  ts timestamptz default now(),
  outcome text,
  payoff numeric,
  pnl numeric,
  evidence text
);

create table public.bankroll (
  ts timestamptz default now(),
  cash numeric,
  deployed numeric,
  note text
);

create view public.model_performance as
select d.market_type,
       count(*) as total_settled,
       sum(case when r.outcome = any (array['YES'::text, 'NO'::text, 'YES-basket'::text]) and r.pnl > 0::numeric then 1 else 0 end) as wins,
       sum(case when r.outcome = any (array['YES'::text, 'NO'::text, 'YES-basket'::text]) and r.pnl <= 0::numeric then 1 else 0 end) as losses,
       sum(case when r.outcome = 'EXITED'::text then 1 else 0 end) as exits,
       round(100.0 * sum(case when r.outcome = any (array['YES'::text, 'NO'::text, 'YES-basket'::text]) and r.pnl > 0::numeric then 1 else 0 end)::numeric
             / nullif(sum(case when r.outcome = any (array['YES'::text, 'NO'::text, 'YES-basket'::text]) then 1 else 0 end), 0)::numeric, 1) as win_rate_pct,
       round(sum(r.pnl), 2) as total_pnl,
       round(avg(d.model_prediction), 3) as avg_model_prediction
from public.decisions d
  join public.resolutions r on r.market_id = d.market_id
group by d.market_type;

create view public.forecast_calibration as
select d.market_type,
       count(*) as n,
       sum(case when (d.side = any (array['YES'::text, 'YES-basket'::text])) and r.outcome = d.side
                 or d.side = 'NO'::text and r.outcome = 'NO'::text
                 or d.side = 'NO-basket'::text and r.outcome = 'NO'::text
                then 1 else 0 end) as forecast_hits,
       round(avg(d.model_prediction), 3) as avg_forecast,
       round(avg(case when (d.side = any (array['YES'::text, 'YES-basket'::text])) and r.outcome = d.side
                       or d.side = 'NO'::text and r.outcome = 'NO'::text
                       or d.side = 'NO-basket'::text and r.outcome = 'NO'::text
                  then d.model_prediction
                  else 1::numeric - d.model_prediction end), 3) as avg_prob_of_realized
from public.decisions d
  join public.resolutions r on r.market_id = d.market_id
where r.outcome = any (array['YES'::text, 'NO'::text, 'YES-basket'::text])
group by d.market_type;
"""


def ddl() -> str:
    """Return the paper-sim ledger migration text (see the module docstring).

    The returned text is byte-identical to the checked-in migration
    ``supabase/migrations/20261101000000_papersim_ledger.sql`` and is the
    single DDL source for the ledger surface: the mirrored live
    ``decisions`` / ``resolutions`` / ``bankroll`` tables plus the fixed
    ``model_performance`` / ``forecast_calibration`` views and the
    repo-convention paper-only/report-only/readonly delta on ``decisions``.
    It is descriptive evidence for tests and tooling; applying it remains
    the exclusive job of the transactional native-Postgres migration
    ledger, never this module.
    """
    return _MIGRATION_DDL
