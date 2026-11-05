"""Command-line entry points for the paper-sim library.

Single responsibility: expose the library's read-only research flows
(load snapshots, price fixtures, evaluate gates, render reports, dump
regression comparisons against the frozen fixtures) as CLI subcommands.
Every subcommand is paper-only / report-only / readonly: none may place,
sign or submit real orders, authenticate accounts or handle credentials.

Canonical lineage: this CLI replaces the per-round bespoke scripts of the
soccer lineage (``r5c -> r15 -> r23``: discover/model/finalize per round)
and the crypto lineage (``r19``: fetch19/model19/finalize19) with one
consolidated, testable surface. Bespoke scripts may not relax model
guards (``review/FIXES.md`` scan-dispatch rule).

Subcommands (WP-P1 final commit):

- ``selfcheck``: the invariant suite. Imports the package surface, then
  recomputes the frozen regression anchors through the REAL
  implementations — the three r19 crypto touch anchors (ETH-2000 /
  ETH-2250 / BTC-65k), the four r23 soccer anchors (BRE-FOR / HUL-IPS /
  CHE-MUN / BOU-LEE over the ten sweep variants), the banned
  cross-league path (HOF-LYO must yield ``None``) and the frozen #48
  gate-arithmetic record (book walk, edge identities, gate pass).
  Prints one ``[PASS]``/``[FAIL]`` line per check plus a summary; exit
  code 0 only when every check passes. No network, no database
  connection, no writes.
- ``schema``: emit the paper-sim ledger migration text
  (:func:`polymarket_alpha_lab.papersim.ledger.ddl`) verbatim to stdout.
  Descriptive evidence only: applying migrations stays the exclusive
  job of the transactional native-Postgres migration ledger, never this
  command.
- ``validate-dsn``: report-only validation of the ledger DSN
  environment variable through the single audited
  ``validate_local_postgres_dsn`` (via
  :func:`polymarket_alpha_lab.papersim.ledger.papersim_dsn`). This CLI
  never reads the process environment itself: the env-vs-default source
  metadata comes from the sanctioned
  ``polymarket_alpha_lab.supabase_papersim_config`` boundary
  (``from_papersim_db_env``), the only module allowed to read the DSN
  environment. Never opens a connection, never reads
  ``PAPERSIM_PG_PASSWORD_FILE`` and never prints the DSN value (repo
  redaction discipline).
"""

from __future__ import annotations

import argparse
import datetime
import json
from collections.abc import Callable, Sequence
from pathlib import Path

from polymarket_alpha_lab.papersim import (
    crypto_model,
    gates,
    ledger,
    risk_policy,
    soccer_model,
    xg,
)

__all__ = ["main"]

# ---------------------------------------------------------------------------
# Frozen reconstruction constants (shared with the wave test files).
#
# These byte-frozen values duplicate constants documented with full
# provenance in ``tests/test_papersim_soccer_model.py`` (EPL_2025
# aggregates, frozen from /home/ubuntu/paper-sim/round23/raw/
# xg_epl_23.json key "EPL_2025": 380 isResult dates, 38-row team
# histories) and ``tests/test_papersim_gates.py`` (the representative
# #48 ladders reproducing the frozen r24 book-ladder summary; round24/
# raw/books24.json stores the walk summary, not the raw levels). The
# selfcheck intentionally re-embeds them so the CLI regression suite
# runs without importing test modules; if a value ever needs to change,
# it is a fixture/regression change, not a tune-up.
# ---------------------------------------------------------------------------

EPL_2025_HOME_RATE = 1.6946258894736843
EPL_2025_AWAY_RATE = 1.3643311084210525
EPL_2025_TEAM_RATES: dict[str, tuple[float, float]] = {
    "Bournemouth": (1.758804, 1.4939418157894737),
    "Brentford": (1.7435966842105264, 1.5555292368421054),
    "Chelsea": (1.9003278947368418, 1.5294069210526315),
    "Leeds": (1.5729118421052632, 1.4822607894736841),
    "Manchester United": (1.8996939473684211, 1.3231953684210527),
    "Nottingham Forest": (1.287795947368421, 1.7036741052631579),
}

# r23 regression cases: (case id, excerpt home title, excerpt away title,
# O/U line). Hull and Ipswich are deliberately absent from
# EPL_2025_TEAM_RATES (promoted sides), exercising the league-average
# fallback exactly as the r23 model did.
R23_CASES: tuple[tuple[str, str, str, float], ...] = (
    ("BRE-FOR_O2.5", "Brentford", "Nottingham Forest", 2.5),
    ("HUL-IPS_O2.5", "Hull", "Ipswich", 2.5),
    ("CHE-MUN_O3.5", "Chelsea", "Manchester United", 3.5),
    ("BOU-LEE_O2.5", "Bournemouth", "Leeds", 2.5),
)

# Reconstructed representative ladders for market 5856164 (#48
# Brentford-Forest O2.5) reproducing the frozen r24 book-ladder summary:
# ask best/vwap 0.56 filled depth_near2c $16,076; bid best/vwap 0.54
# filled depth_near2c $13,759.
LADDER_5856164_ASK: tuple[tuple[float, float], ...] = (
    (0.56, 1000.0),
    (0.57, 14000.0),
    (0.58, 12993.0),
    (0.60, 30000.0),
)
LADDER_5856164_BID: tuple[tuple[float, float], ...] = (
    (0.54, 800.0),
    (0.53, 15000.0),
    (0.52, 10340.0),
    (0.51, 20000.0),
)

_CHECK_TOLERANCE = 1e-4
_LAMBDA_TOLERANCE = 5e-4


def _fixtures_dir() -> Path:
    """Repository location of the frozen papersim regression fixtures."""
    return Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "papersim"


def _load_fixture(name: str) -> dict:
    path = _fixtures_dir() / name
    if not path.is_file():
        raise FileNotFoundError(f"frozen fixture missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# selfcheck checks: each returns (name, ok, detail)
# ---------------------------------------------------------------------------


def _check_module_imports() -> tuple[str, bool, str]:
    from polymarket_alpha_lab import papersim as package

    modules = (crypto_model, gates, ledger, risk_policy, soccer_model, xg)
    unresolved = [
        name for name in package.__all__ if getattr(package, name, None) is None
    ]
    if unresolved:
        return (
            "module-imports",
            False,
            f"unresolved package exports: {', '.join(sorted(unresolved))}",
        )
    return (
        "module-imports",
        True,
        f"6 modules imported ({', '.join(m.__name__.rpartition('.')[2] for m in modules)}); "
        f"{len(package.__all__)} package exports resolve "
        "(ledger.record_entry/mark_to_market remain frozen stubs by design)",
    )


def _r19_horizon_hours(fixture: dict) -> float:
    """Recompute the r19 ``T`` exactly as model19.py did (see W2 tests)."""
    anchor = datetime.datetime.fromisoformat(fixture["anchor"]["raw_scan_generated_at"])
    dec31 = datetime.datetime(2026, 12, 31, 23, 59, tzinfo=datetime.timezone.utc)
    return (dec31 - anchor).total_seconds() / 86400.0 * 24.0


def _check_crypto_r19(case_key: str) -> tuple[str, bool, str]:
    fixture = _load_fixture("regression_r19_crypto.json")
    case = fixture["cases"][case_key]
    inputs = fixture["inputs"]
    spot = float(inputs["spot"][case["asset"]])
    sigma = float(inputs["realized_vol_daily"][case["asset"]][inputs["sig_table"]])
    horizon = _r19_horizon_hours(fixture)
    probs = crypto_model.touch_probability(
        spot=spot,
        sigma_daily=sigma,
        barrier=float(case["barrier"]),
        horizon_hours=horizon,
        asset=str(case["asset"]),
    )
    delta_a = abs(probs.convention_a - float(case["A"]))
    delta_b = abs(probs.convention_b - float(case["B"]))
    horizon_ok = round(horizon, 2) == float(case["horizon_hours"])
    # All three frozen barriers sit below spot: mean-flat B (negative log
    # drift pushes mass down) must touch more often than median-flat A.
    ordering_ok = probs.convention_b > probs.convention_a
    ok = (
        delta_a <= _CHECK_TOLERANCE
        and delta_b <= _CHECK_TOLERANCE
        and horizon_ok
        and ordering_ok
    )
    return (
        f"crypto-r19:{case_key}",
        ok,
        f"A={probs.convention_a:.4f} (want {case['A']}) B={probs.convention_b:.4f} "
        f"(want {case['B']}) |dA|={delta_a:.2e} |dB|={delta_b:.2e} "
        f"horizon={round(horizon, 2)}h",
    )


def _r23_snapshot(fixture: dict) -> dict[str, object]:
    """Rebuild the regression snapshot from the fixture excerpt (W1 tests)."""
    excerpt = fixture["xg_snapshot_excerpt"]
    prior_teams = {
        team_id: {
            "id": team_id,
            "title": row["title"],
            "history": [
                {
                    "xG": EPL_2025_TEAM_RATES[row["title"]][0],
                    "xGA": EPL_2025_TEAM_RATES[row["title"]][1],
                }
            ],
        }
        for team_id, row in excerpt["teams"].items()
        if row["title"] in EPL_2025_TEAM_RATES
    }
    return {
        "EPL_2025": {
            "dates": [
                {
                    "isResult": True,
                    "xG": {"h": EPL_2025_HOME_RATE, "a": EPL_2025_AWAY_RATE},
                }
            ],
            "teams": prior_teams,
        },
        "EPL_2026": {"dates": [], "teams": excerpt["teams"]},
    }


def _check_soccer_r23(case_id: str) -> tuple[str, bool, str]:
    fixture = _load_fixture("regression_r23_soccer.json")
    case = fixture["cases"][case_id]
    home, away, line = next(
        (h, a, ln) for cid, h, a, ln in R23_CASES if cid == case_id
    )
    snapshot = xg.load_xg_payload(_r23_snapshot(fixture))
    variants = soccer_model.fixture_variants(snapshot, home, "EPL", away, "EPL")
    if variants is None:
        return (f"soccer-r23:{case_id}", False, "fixture_variants returned None")
    quotes = [soccer_model.over_probability(v.outputs, line) for v in variants]
    variant_ok = all(
        abs(got - want) <= _CHECK_TOLERANCE
        for got, want in zip(quotes, case["qs_variants"])
    )
    median_ok = (
        abs(soccer_model.median(quotes) - float(case["model_median"]))
        <= _CHECK_TOLERANCE
    )
    range_ok = (
        abs(min(quotes) - float(case["model_range"][0])) <= _CHECK_TOLERANCE
        and abs(max(quotes) - float(case["model_range"][1])) <= _CHECK_TOLERANCE
    )
    lambdas = soccer_model.match_lambdas(snapshot, home, "EPL", away, "EPL")
    lambda_ok = (
        lambdas is not None
        and abs(lambdas[0] - float(case["lambda_home"])) <= _LAMBDA_TOLERANCE
        and abs(lambdas[1] - float(case["lambda_away"])) <= _LAMBDA_TOLERANCE
    )
    ok = variant_ok and median_ok and range_ok and lambda_ok
    return (
        f"soccer-r23:{case_id}",
        ok,
        f"median={soccer_model.median(quotes):.4f} (want {case['model_median']}) "
        f"range={min(quotes):.4f}..{max(quotes):.4f} "
        f"(want {case['model_range'][0]}..{case['model_range'][1]}) "
        f"variants_1e-4={variant_ok} "
        f"lambdas=({lambdas[0]:.3f}, {lambdas[1]:.3f}) "
        f"(want {case['lambda_home']}, {case['lambda_away']})",
    )


def _check_banned_path() -> tuple[str, bool, str]:
    fixture = _load_fixture("regression_banned_path.json")
    case = fixture["case"]
    home = case["home"]
    away = case["away"]
    snapshot = {
        "bundesliga_2025": {
            "dates": [{"isResult": True, "xG": {"h": 1.7, "a": 1.4}}],
            "teams": {
                "3": {
                    "title": "TSG 1899 Hoffenheim",
                    "history": [{"xG": 1.5, "xGA": 1.5}],
                }
            },
        },
        "bundesliga_2026": {
            "dates": [],
            "teams": {
                "3": {
                    "title": "TSG 1899 Hoffenheim",
                    "history": [{"xG": 1.5, "xGA": 1.5}],
                }
            },
        },
        "ligue_1_2025": {
            "dates": [{"isResult": True, "xG": {"h": 1.6, "a": 1.3}}],
            "teams": {
                "4": {
                    "title": "Olympique Lyonnais",
                    "history": [{"xG": 1.4, "xGA": 1.4}],
                }
            },
        },
        "ligue_1_2026": {
            "dates": [],
            "teams": {
                "4": {
                    "title": "Olympique Lyonnais",
                    "history": [{"xG": 1.4, "xGA": 1.4}],
                }
            },
        },
    }
    lambdas = soccer_model.match_lambdas(
        snapshot, home["team"], home["league"], away["team"], away["league"]
    )
    variants = soccer_model.fixture_variants(
        snapshot, home["team"], home["league"], away["team"], away["league"]
    )
    policy = gates.suspension_policy("match_winner", cross_league=True)
    ok = (
        lambdas is None
        and variants is None
        and case["expected_match_lambdas"] is None
        and policy.policy == gates.POLICY_BANNED
        and policy.eligible is False
    )
    return (
        "banned-path:HOF-LYO",
        ok,
        f"match_lambdas={lambdas} fixture_variants={'None' if variants is None else 'not-None'} "
        f"cross-league match_winner policy={policy.policy}",
    )


def _check_gate_arithmetic_48() -> tuple[str, bool, str]:
    fixture = _load_fixture("regression_gate_arithmetic.json")
    case = fixture["case"]
    entry = case["entry_r23"]
    recheck = case["r24_recheck"]
    ladder = case["r24_book_ladder"]

    ask = gates.walk_book(LADDER_5856164_ASK, "ask")
    bid = gates.walk_book(LADDER_5856164_BID, "bid")
    walk_ok = (
        (ask.best, ask.vwap, ask.filled, ask.depth_near2c)
        == (
            ladder["tok0_ask"]["best"],
            ladder["tok0_ask"]["vwap"],
            ladder["tok0_ask"]["filled"],
            ladder["tok0_ask"]["depth_near2c"],
        )
        and (bid.best, bid.vwap, bid.filled, bid.depth_near2c)
        == (
            ladder["tok0_bid"]["best"],
            ladder["tok0_bid"]["vwap"],
            ladder["tok0_bid"]["filled"],
            ladder["tok0_bid"]["depth_near2c"],
        )
    )
    variants = entry["qs_variants"]
    edge_exec = round(entry["model_median"] - ask.vwap, 4)
    edge_worst = round(min(variants) - ask.vwap, 4)
    spread = round(max(variants) - min(variants), 4)
    identity_ok = (
        edge_exec == recheck["edge_exec_now"]
        and edge_worst == recheck["edge_worst_now"]
        and spread == entry["var_spread"]
        and round(edge_exec * 100, 1) == recheck["expected_edge_exec_cents"]
        and round(edge_worst * 100, 1) == recheck["expected_edge_worst_cents"]
        and round(bid.best - entry["entry_ask_vwap250"], 4)
        == recheck["mark_bid_vs_entry"]
    )
    decision = gates.evaluate_gates(
        variant_spread=spread,
        worst_variant_edge=edge_worst,
        median_exec_edge=edge_exec,
        gamma_liquidity=float(ladder["liq"]),
    )
    gates_ok = decision.passed is True and decision.failed == ()
    # Fee accounting (2026-11-05 fix): the same record through the NET
    # exec bar. Per-share fee at entry 0.56, sports rate:
    # 0.05 * 0.56 * 0.44 = 1.23c, so exec +7.42c gross = +6.19c net,
    # still clearing the frozen +5c bar; both doors (the fee-aware
    # evaluate_gates and evaluate_candidate with its default sports
    # fee_rate) must agree on the net edge and the pass.
    fee = round(gates.fee_cost(ask.vwap, gates.FEE_RATE_SPORTS), 4)
    edge_exec_net = round(edge_exec - fee, 4)
    net_decision = gates.evaluate_gates(
        variant_spread=spread,
        worst_variant_edge=edge_worst,
        median_exec_edge=edge_exec,
        gamma_liquidity=float(ladder["liq"]),
        fee_rate=gates.FEE_RATE_SPORTS,
        entry_price=ask.vwap,
    )
    report = gates.evaluate_candidate(
        dict(model_median=entry["model_median"], qs_variants=variants),
        LADDER_5856164_ASK,
        gamma_liquidity=float(ladder["liq"]),
        news=gates.check_news(
            case["position"], "r24 recheck", news_delta=gates.NEWS_UNCHANGED
        ),
    )
    net_ok = (
        net_decision.passed is True
        and net_decision.failed == ()
        and report.exec_edge_gross == edge_exec
        and report.exec_edge == edge_exec_net
        and report.checks["exec>=+5c"] is True
        and report.decision.passed is True
    )
    ok = walk_ok and identity_ok and gates_ok and net_ok
    return (
        "gate-arithmetic:#48",
        ok,
        f"ask walk best/vwap={ask.best}/{ask.vwap} depth_near2c={ask.depth_near2c:.0f} "
        f"exec=+{edge_exec * 100:.1f}c gross / +{edge_exec_net * 100:.1f}c net "
        f"(fee {fee * 100:.2f}c @ {ask.vwap:.2f}) worst=+{edge_worst * 100:.1f}c "
        f"spread={spread * 100:.2f}c gates={'pass' if gates_ok else 'fail'} "
        f"net_gates={'pass' if net_ok else 'fail'}",
    )


# ---------------------------------------------------------------------------
# subcommands
# ---------------------------------------------------------------------------


def _cmd_selfcheck() -> int:
    # Each entry is (failure label, zero-argument check callable): a check
    # that raises is REPORTED as a failure, never a traceback (a missing
    # or unreadable fixture must fail the suite cleanly).
    check_calls: list[tuple[str, Callable[[], tuple[str, bool, str]]]] = [
        ("module-imports", _check_module_imports),
        ("crypto-r19:ETH-2000", lambda: _check_crypto_r19("ETH-2000")),
        ("crypto-r19:ETH-2250", lambda: _check_crypto_r19("ETH-2250")),
        ("crypto-r19:BTC-65k", lambda: _check_crypto_r19("BTC-65k")),
        ("soccer-r23:BRE-FOR_O2.5", lambda: _check_soccer_r23("BRE-FOR_O2.5")),
        ("soccer-r23:HUL-IPS_O2.5", lambda: _check_soccer_r23("HUL-IPS_O2.5")),
        ("soccer-r23:CHE-MUN_O3.5", lambda: _check_soccer_r23("CHE-MUN_O3.5")),
        ("soccer-r23:BOU-LEE_O2.5", lambda: _check_soccer_r23("BOU-LEE_O2.5")),
        ("banned-path:HOF-LYO", _check_banned_path),
        ("gate-arithmetic:#48", _check_gate_arithmetic_48),
    ]
    check_results: list[tuple[str, bool, str]] = []
    for label, check in check_calls:
        try:
            check_results.append(check())
        except Exception as exc:  # report, do not crash
            check_results.append((label, False, f"error: {exc}"))
    lines = ["papersim selfcheck (read-only: no network, no database, no writes)"]
    passed = 0
    for name, ok, detail in check_results:
        lines.append(f"[{'PASS' if ok else 'FAIL'}] {name} - {detail}")
        passed += 1 if ok else 0
    total = len(check_results)
    overall = "PASS" if passed == total else "FAIL"
    lines.append(f"selfcheck: {overall} ({passed}/{total} checks)")
    print("\n".join(lines))
    return 0 if passed == total else 1


def _cmd_schema() -> int:
    print(ledger.ddl(), end="")
    return 0


def _cmd_validate_dsn() -> int:
    env_var = ledger.PAPERSIM_PG_DSN_ENV_VAR
    # This module never reads the process environment (F9 boundary: DSN
    # environment reads live only inside supabase_papersim_config). The
    # env-vs-default source metadata comes from that sanctioned module:
    # ``dsn is None`` means the variable is unset, empty or whitespace
    # only, so the documented example default is what would be used.
    try:
        source = (
            f"environment {env_var}"
            if ledger.from_papersim_db_env().dsn is not None
            else "documented default (env unset or empty)"
        )
    except ValueError:
        # The env-provided DSN already failed validation inside the
        # sanctioned config boundary; report it via the shared failure
        # path below, where papersim_dsn re-raises the exact reason.
        source = f"environment {env_var}"
    lines = [
        "validate-dsn (report-only: no connection opened, no password read)",
        f"source: {source}",
        "validator: validate_local_postgres_dsn (single audited implementation)",
        "value: <redacted>",
    ]
    try:
        ledger.papersim_dsn()
    except ValueError as exc:
        lines.insert(1, "validate-dsn: FAIL")
        lines.append(f"reason: {exc}")
        print("\n".join(lines))
        return 1
    lines.insert(1, "validate-dsn: PASS")
    lines.append(
        f"password file: {ledger.PAPERSIM_PG_PASSWORD_FILE_ENV_VAR} "
        "is out-of-band and never read by this command"
    )
    print("\n".join(lines))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="papersim",
        description=(
            "Paper-simulation core library CLI (paper-only / report-only / "
            "readonly; no order, account or credential surface)."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "selfcheck",
        help="recompute the frozen regression anchors; exit 0 only if all pass",
    )
    subparsers.add_parser(
        "schema",
        help="emit the paper-sim ledger migration DDL verbatim",
    )
    subparsers.add_parser(
        "validate-dsn",
        help="report-only validation of the ledger DSN environment variable (never connects)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the papersim CLI; returns a process exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "selfcheck":
        return _cmd_selfcheck()
    if args.command == "schema":
        return _cmd_schema()
    if args.command == "validate-dsn":
        return _cmd_validate_dsn()
    parser.error(f"unknown command {args.command!r}")  # pragma: no cover
    raise AssertionError("unreachable")  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
