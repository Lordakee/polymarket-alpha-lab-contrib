"""FX-01 read-only paper-ledger gross/net performance report.

Single responsibility: load settled paper-ledger rows from a checked-in
export (JSON snapshot or ``\\copy`` CSV pair), or from the live
paper_sim cluster with a READ-ONLY ``SELECT``, and print gross and net
(after-fee) returns by queue. This is the minimal predecessor of the
FX-11 evaluation module (it will be absorbed there); the aggregation
itself lives in the library
(:func:`polymarket_alpha_lab.papersim.ledger.queue_performance`) and
this script only does I/O and formatting.

Fee semantics (V-6 evidence run 2026-11-12,
``~/paper-sim/review/audit2026_v6_v7/`` on the ops host): official
formula ``fee = shares x rate x p x (1 - p)`` with ``shares =
stake / price`` (== ``stake * rate * (1 - p)``), rates from the FX-06
category table via the scan-lineage classification (``crypto_%`` teams
7%, every other team 5%; ``market_type`` does not override — the gold
and equity-index rows recorded under ``crypto_touch`` are sports-rate);
``EXITED`` rows additionally charge the sell fee at the exit price
reconstructed from the recorded PnL; ``VOIDED`` rows are stake-refunded
and excluded; unresolved rows are excluded.

Read-only and paper-only: no writes anywhere, no orders, no
credentials. The PG path resolves its DSN exclusively through
``ledger.papersim_dsn()`` (the single audited
``validate_local_postgres_dsn`` door — never a raw ``psql`` bypass) and
opens the session with ``default_transaction_read_only=on``; the SCRAM
password is only read at connect time from the operator-supplied
``PAPERSIM_PG_PASSWORD_FILE`` when that variable is set.

CAVEAT printed with every report: net figures are ESTIMATES
back-computed with the fee schedule as of
``fees.FEE_SCHEDULE_AS_OF``; whether the historical markets were
actually charged, and at which tier, cannot be verified from the repo.

Usage::

    # 1) the checked-in audit snapshot (reproduces the published
    #    gross 23.30% and nets fees; JSON rows carry recorded pnl,
    #    so the default pnl source there is 'recorded'):
    python tools/papersim_ledger_report.py \
        --ledger-json docs/paper-sim/review-2026-10-30/settled_ledger.json

    # 2) a \\copy export pair from the live cluster (V-6 shape);
    #    default pnl source 'recomputed' (per-entry, V-6 primary):
    python tools/papersim_ledger_report.py \
        --decisions-csv decisions.csv --resolutions-csv resolutions.csv

    # 3) read-only SELECT against PAPERSIM_PG_DSN:
    python tools/papersim_ledger_report.py --from-pg
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Callable

# Repo/package bootstrap: prefer the installed package; fall back to the
# worktree's src/ so the script also runs from a plain checkout.
try:
    from polymarket_alpha_lab.papersim import fees, ledger
except ImportError:  # pragma: no cover - exercised only outside the venv
    _SRC = Path(__file__).resolve().parents[1] / "src"
    sys.path.insert(0, str(_SRC))
    from polymarket_alpha_lab.papersim import fees, ledger

# Read-only session flag: every connection this tool opens refuses writes
# at the server, on top of the script itself issuing SELECTs only.
_PG_READONLY_OPTIONS = "-c default_transaction_read_only=on"

# The single read-only join the PG mode runs (decisions LEFT JOIN
# resolutions; unresolved decisions keep outcome/pnl NULL).
_PG_SELECT_SQL = (
    "select d.id, d.market_id, d.team, d.market_type, d.side, "
    "d.stake, d.price, r.outcome, r.pnl "
    "from public.decisions d "
    "left join public.resolutions r on r.market_id = d.market_id "
    "order by d.id"
)


def _optional_float(value: Any) -> float | None:
    """Parse a possibly-null numeric field (CSV strings, PG numerics)."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return float(text)


def load_rows_json(path: Path) -> list[dict[str, Any]]:
    """Load a settled-ledger JSON export (list of decision-shaped rows)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not all(
        isinstance(row, dict) for row in data
    ):
        raise ValueError(
            f"{path}: expected a JSON list of decision-shaped row objects"
        )
    return data


def load_rows_csv(decisions_csv: Path, resolutions_csv: Path) -> list[dict[str, Any]]:
    """Join a ``\\copy`` decisions/resolutions CSV pair into ledger rows.

    The resolution is joined per ``market_id`` exactly like the read-only
    PG query; decisions without a resolution row stay unresolved
    (``outcome=None``) and are excluded by the aggregation.
    """
    resolutions: dict[str, dict[str, Any]] = {}
    with resolutions_csv.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            market_id = (row.get("market_id") or "").strip()
            if market_id:
                resolutions[market_id] = row
    rows: list[dict[str, Any]] = []
    with decisions_csv.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            market_id = (row.get("market_id") or "").strip()
            resolution = resolutions.get(market_id, {})
            rows.append(
                {
                    "id": row.get("id"),
                    "team": row.get("team"),
                    "market_type": row.get("market_type"),
                    "side": row.get("side"),
                    "stake": _optional_float(row.get("stake")),
                    "price": _optional_float(row.get("price")),
                    "outcome": resolution.get("outcome"),
                    "pnl": _optional_float(resolution.get("pnl")),
                }
            )
    return rows


def load_rows_pg(connect: Callable[..., Any]) -> list[dict[str, Any]]:
    """Read the ledger join through a read-only PG connection.

    ``connect`` is injected so tests can pass a fake; production wiring
    builds it from ``ledger.papersim_dsn()`` (the validated DSN) plus
    the operator's out-of-band password file. Raises ``ImportError``
    guidance when psycopg is not installed.
    """
    connection = connect(
        ledger.papersim_dsn(),
        connect_timeout=5,
        options=_PG_READONLY_OPTIONS,
    )
    try:
        with connection:
            cursor = connection.execute(_PG_SELECT_SQL)
            columns = [desc.name for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    finally:
        connection.close()


def _build_connect() -> Callable[..., Any]:
    """Build the production psycopg connect (password file honored)."""
    try:
        import psycopg
    except ImportError as error:  # pragma: no cover - env-dependent
        raise SystemExit(
            "the --from-pg mode requires psycopg (not installed)"
        ) from error
    import os

    kwargs: dict[str, Any] = {}
    password_file = os.environ.get(ledger.PAPERSIM_PG_PASSWORD_FILE_ENV_VAR)
    if password_file:
        kwargs["password"] = Path(password_file).read_text(
            encoding="utf-8"
        ).strip()
    return lambda dsn, **extra: psycopg.connect(dsn, **extra, **kwargs)


def _percent(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100.0:+.2f}%"


def _money(value: float) -> str:
    return f"{value:.2f}"


def render_report(
    performance: ledger.LedgerPerformance,
    *,
    source_label: str,
    mode: str,
    pnl_source: str,
) -> str:
    """Format one LedgerPerformance as the deterministic text report."""
    lines = [
        "papersim ledger report - gross and net performance by queue (FX-01)",
        f"source: {source_label} (mode: {mode}, pnl source: {pnl_source})",
        "fee schedule: TAKER_FEE_RATES as of "
        f"{performance.fee_schedule_as_of} ({fees.FEE_SCHEDULE_SOURCE})",
        "classification: scan mirror (team rule) - team 'crypto_*' -> crypto "
        "(0.07); every other team -> sports (0.05); market_type does not "
        "override",
        "caveat: net figures are ESTIMATES back-computed with the "
        f"{performance.fee_schedule_as_of} fee schedule; actual historical "
        "charging is not verifiable from the repo.",
    ]
    if pnl_source == ledger.PNL_SOURCE_RECORDED:
        lines.append(
            "gross basis: recorded per-row pnl as exported (market-level "
            "joins are not re-allocated here; FX-09 will own allocation)"
        )
    else:
        lines.append(
            "gross basis: per-entry recomputed (V-6 primary); EXITED rows "
            "use the recorded market pnl (exit price reconstructed)"
        )
    lines += [
        "",
        f"entries counted: {performance.entries} "
        f"(VOIDED refunded/excluded: {performance.voided_excluded}; "
        f"unresolved/open excluded: {performance.unresolved_excluded})",
        f"stake: {_money(performance.stake)}",
        f"gross pnl: {_money(performance.gross_pnl)}   "
        f"gross roi: {_percent(performance.gross_roi)}",
        f"entry fees: {_money(performance.entry_fees)}",
        f"exit fees: {_money(performance.exit_fees)}",
        f"net pnl (entry fees): "
        f"{_money(performance.net_pnl_entry_fees_only)}   "
        f"net roi: {_percent(performance.net_roi_entry_fees_only)}",
        f"net pnl (entry+exit fees): {_money(performance.net_pnl)}   "
        f"net roi: {_percent(performance.net_roi)}",
        "",
        "queue (market_type) | categories | n | stake | gross | entry fees"
        " | exit fees | net | net roi",
    ]
    for queue in performance.queues:
        lines.append(
            f"{queue.market_type} | {'+'.join(queue.categories)} | "
            f"{queue.entries} | {_money(queue.stake)} | "
            f"{_money(queue.gross_pnl)} | {_money(queue.entry_fees)} | "
            f"{_money(queue.exit_fees)} | {_money(queue.net_pnl)} | "
            f"{_percent(queue.net_roi)}"
        )
    lines += [
        "",
        "classification (team -> category, rate):",
    ]
    lines += [
        f"{team} -> {category} ({rate:.2f})"
        for team, category, rate in performance.team_classification
    ]
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="papersim_ledger_report",
        description=(
            "Read-only paper-ledger gross/net performance report (FX-01)."
        ),
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--ledger-json",
        type=Path,
        help=(
            "settled-ledger JSON export (list of decision-shaped rows with "
            "recorded pnl, e.g. docs/paper-sim/review-2026-10-30/"
            "settled_ledger.json)"
        ),
    )
    source.add_argument(
        "--decisions-csv",
        type=Path,
        help="decisions \\copy CSV (requires --resolutions-csv)",
    )
    source.add_argument(
        "--from-pg",
        action="store_true",
        help=(
            "read-only SELECT against PAPERSIM_PG_DSN (validated through "
            "ledger.papersim_dsn; no psql bypass)"
        ),
    )
    parser.add_argument(
        "--resolutions-csv",
        type=Path,
        help="resolutions \\copy CSV joined by market_id",
    )
    parser.add_argument(
        "--pnl-source",
        choices=(
            "auto",
            ledger.PNL_SOURCE_RECORDED,
            ledger.PNL_SOURCE_RECOMPUTED,
        ),
        default="auto",
        help=(
            "gross basis: 'recorded' reproduces exported pnl as published; "
            "'recomputed' is the V-6 per-entry primary. Default 'auto': "
            "recorded for --ledger-json, recomputed for CSV/PG."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.decisions_csv is not None and args.resolutions_csv is None:
        raise SystemExit("--decisions-csv requires --resolutions-csv")
    if args.decisions_csv is None and args.resolutions_csv is not None:
        raise SystemExit("--resolutions-csv requires --decisions-csv")
    if args.ledger_json is not None:
        rows = load_rows_json(args.ledger_json)
        mode = "ledger-json"
        source_label = args.ledger_json.as_posix()
        default_source = ledger.PNL_SOURCE_RECORDED
    elif args.decisions_csv is not None:
        rows = load_rows_csv(args.decisions_csv, args.resolutions_csv)
        mode = "decisions+resolutions csv"
        source_label = (
            f"{args.decisions_csv.as_posix()} + "
            f"{args.resolutions_csv.as_posix()}"
        )
        default_source = ledger.PNL_SOURCE_RECOMPUTED
    else:
        rows = load_rows_pg(_build_connect())
        mode = "pg read-only select"
        source_label = "PAPERSIM_PG_DSN (validated)"
        default_source = ledger.PNL_SOURCE_RECOMPUTED
    pnl_source = (
        default_source if args.pnl_source == "auto" else args.pnl_source
    )
    performance = ledger.queue_performance(rows, pnl_source=pnl_source)
    print(render_report(
        performance,
        source_label=source_label,
        mode=mode,
        pnl_source=pnl_source,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
