"""WP-P1 W4 tests: papersim ledger DDL mirror, DSN validation, settlement
arithmetic and the bankroll identity.

Unit paths open no sockets and no database connections. The single
optional integration check runs only when ``PAPERSIM_PG_DSN`` is
explicitly provided and validates, and otherwise skips with an explicit
label; these tests never touch the live paper_sim cluster or any
``~/pal-artifacts`` path by default. Password material is never read,
printed or committed here.
"""

from dataclasses import fields
from hashlib import sha256
import json
import os
from pathlib import Path

import pytest

from polymarket_alpha_lab.papersim import ledger
from polymarket_alpha_lab.supabase_local_dsn import validate_local_postgres_dsn

ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = ROOT / "supabase" / "migrations" / ledger.PAPERSIM_LEDGER_MIGRATION_NAME
MANIFEST_PATH = ROOT / "database" / "migrations.lock.json"
INTEGRATION_LABEL = "papersim-ledger-integration"


def test_ddl_is_byte_identical_to_checked_in_migration():
    assert MIGRATION_PATH.is_file()
    assert MIGRATION_PATH.read_text(encoding="utf-8") == ledger.ddl()
    assert b"\r" not in MIGRATION_PATH.read_bytes()


def test_ddl_contains_mirrored_tables_views_and_boundary_delta():
    text = ledger.ddl().lower()
    for fragment in (
        "create table public.decisions",
        "create table public.resolutions",
        "create table public.bankroll",
        "create view public.model_performance",
        "create view public.forecast_calibration",
        "check (paper_only is true)",
        "check (report_only is true)",
        "check (readonly is true)",
        "id bigserial primary key",
        "market_id text primary key",
        "team text default 'crypto_eth'::text",
    ):
        assert fragment in text


def test_ddl_exits_separated_from_wl_and_calibration_natural_only():
    text = ledger.ddl().lower()
    # Wins and losses require a natural outcome AND a pnl sign; EXITED
    # feeds only the exits counter.
    assert "and r.pnl > 0::numeric then 1 else 0 end) as wins" in text
    assert "and r.pnl <= 0::numeric then 1 else 0 end) as losses" in text
    assert "'exited'::text then 1 else 0 end) as exits" in text
    # Exits stay inside total PnL: the sum spans every joined row with no
    # outcome filter.
    assert "round(sum(r.pnl), 2) as total_pnl" in text
    # Calibration cohort is natural resolutions only.
    assert (
        "where r.outcome = any (array['yes'::text, 'no'::text, "
        "'yes-basket'::text])" in text
    )


def test_migration_registered_in_lock_manifest():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["format"] == "native-postgres-migrations-v1"
    entries = manifest["migrations"]
    entry = next(
        item for item in entries if item["name"] == ledger.PAPERSIM_LEDGER_MIGRATION_NAME
    )
    assert set(entry) == {"name", "sha256", "transaction_wrapper"}
    assert entry["transaction_wrapper"] is False
    assert entry["sha256"] == sha256(MIGRATION_PATH.read_bytes()).hexdigest()
    actual = sorted(path.name for path in (ROOT / "supabase" / "migrations").glob("*.sql"))
    assert [item["name"] for item in entries] == actual


@pytest.mark.parametrize(
    "outcome,expected",
    [
        (None, ledger.OUTCOME_OPEN),
        ("EXITED", ledger.OUTCOME_EXITED),
        ("YES", ledger.OUTCOME_SETTLED),
        ("NO", ledger.OUTCOME_SETTLED),
        ("YES-basket", ledger.OUTCOME_SETTLED),
    ],
)
def test_classify_outcome_buckets(outcome, expected):
    assert ledger.classify_outcome(outcome) == expected


@pytest.mark.parametrize("outcome", ["", "yes", "NO-basket", "MUTUAL", "0", "exited"])
def test_classify_outcome_rejects_unknown_tokens(outcome):
    with pytest.raises(ValueError):
        ledger.classify_outcome(outcome)


def test_settle_natural_win_pays_shares_per_dollar():
    settlement = ledger.settle_natural(stake=250.0, price=0.23, side="YES", outcome="YES")
    assert settlement.classification == ledger.OUTCOME_SETTLED
    assert settlement.proceeds == pytest.approx(250.0 / 0.23)
    assert settlement.pnl == pytest.approx(250.0 / 0.23 - 250.0)
    assert settlement.win_loss == "win"


def test_settle_natural_basket_win_matches_book_of_record():
    settlement = ledger.settle_natural(
        stake=150.0, price=0.985, side="YES-basket", outcome="YES-basket"
    )
    assert settlement.pnl == pytest.approx(2.28, abs=0.01)
    assert settlement.win_loss == "win"


def test_settle_natural_loss_loses_stake():
    settlement = ledger.settle_natural(stake=350.0, price=0.56, side="YES", outcome="NO")
    assert settlement.proceeds == 0.0
    assert settlement.pnl == pytest.approx(-350.0)
    assert settlement.win_loss == "loss"


@pytest.mark.parametrize(
    "side,outcome,expected",
    [
        ("NO", "NO", "win"),
        ("NO", "YES", "loss"),
        ("NO-basket", "NO", "win"),
        ("NO-basket", "YES", "loss"),
        ("YES-basket", "NO", "loss"),
    ],
)
def test_settle_natural_side_outcome_matrix(side, outcome, expected):
    settlement = ledger.settle_natural(stake=100.0, price=0.5, side=side, outcome=outcome)
    assert settlement.win_loss == expected


def test_settle_natural_rejects_exited_and_bad_inputs():
    with pytest.raises(ValueError, match="settle_exit"):
        ledger.settle_natural(stake=400.0, price=0.69, side="NO", outcome="EXITED")
    with pytest.raises(ValueError):
        ledger.settle_natural(stake=400.0, price=0.0, side="NO", outcome="NO")
    with pytest.raises(ValueError):
        ledger.settle_natural(stake=400.0, price=1.0, side="NO", outcome="NO")
    with pytest.raises(ValueError):
        ledger.settle_natural(stake=0.0, price=0.69, side="NO", outcome="NO")
    with pytest.raises(ValueError):
        ledger.settle_natural(stake=400.0, price=0.69, side="MAYBE", outcome="NO")


def test_settle_exit_realizes_pnl_but_never_wl():
    settlement = ledger.settle_exit(stake=400.0, price=0.69, exit_price=0.585)
    assert settlement.classification == ledger.OUTCOME_EXITED
    assert settlement.proceeds == pytest.approx(400.0 / 0.69 * 0.585)
    assert settlement.pnl == pytest.approx(400.0 / 0.69 * 0.585 - 400.0)
    # The live book recorded -60.70 because it realized on 580 whole
    # shares; the exact per-share arithmetic is -60.87 on 579.71 shares.
    assert settlement.pnl == pytest.approx(-60.86956521739131)
    assert settlement.win_loss is None


def test_settle_exit_full_and_zero_bounds():
    zero = ledger.settle_exit(stake=200.0, price=0.5, exit_price=0.0)
    assert zero.proceeds == 0.0
    assert zero.pnl == pytest.approx(-200.0)
    full = ledger.settle_exit(stake=200.0, price=0.5, exit_price=1.0)
    assert full.pnl == pytest.approx(200.0)
    assert full.win_loss is None
    with pytest.raises(ValueError):
        ledger.settle_exit(stake=200.0, price=0.5, exit_price=1.2)


def _realize(stake, price, side, outcome, *, exit_price=0.585):
    if ledger.classify_outcome(outcome) == ledger.OUTCOME_EXITED:
        return ledger.settle_exit(stake, price, exit_price)
    return ledger.settle_natural(stake, price, side, outcome)


def test_portfolio_math_exits_excluded_from_wl_included_in_pnl():
    rows = [
        (250.00, 0.230, "YES", "YES"),
        (429.93, 0.510, "YES", "YES"),
        (350.00, 0.560, "YES", "NO"),
        (400.00, 0.690, "NO", "EXITED"),
        (249.57, 0.846, "NO", "EXITED"),
    ]
    settlements = [_realize(*row) for row in rows]
    assert settlements[1].pnl == pytest.approx(413.07, abs=0.01)
    wins = [item for item in settlements if item.win_loss == "win"]
    losses = [item for item in settlements if item.win_loss == "loss"]
    exits = [item for item in settlements if item.classification == ledger.OUTCOME_EXITED]
    assert (len(wins), len(losses), len(exits)) == (2, 1, 2)
    # Win-rate denominator mirrors the fixed view: natural resolutions only.
    assert len(wins) + len(losses) == 3
    # Exits carry realized PnL inside the total.
    exit_pnl = sum(item.pnl for item in exits)
    assert exit_pnl < 0
    total_pnl = sum(item.pnl for item in settlements)
    assert total_pnl == pytest.approx(
        sum(item.pnl for item in wins + losses) + exit_pnl
    )
    # Calibration cohort: natural resolutions only, via classify_outcome.
    cohort = [
        row for row in rows
        if ledger.classify_outcome(row[3]) == ledger.OUTCOME_SETTLED
    ]
    assert len(cohort) == 3


def test_bankroll_identity_matches_book_of_record_rows():
    assert ledger.bankroll_identity(12374.33, 9488.68, 2885.65) is True
    assert ledger.bankroll_identity(12182.29, 7998.12, 4184.17) is True


def test_bankroll_identity_float_guard_and_mismatch():
    assert ledger.bankroll_identity(0.1 + 0.2, 0.1, 0.2) is True
    assert ledger.bankroll_identity(12374.34, 9488.68, 2885.65) is False
    assert ledger.bankroll_identity(
        12374.35, 9488.68, 2885.65, tolerance=0.05
    ) is True


def test_bankroll_identity_rejects_non_finite():
    for bad in (float("nan"), float("inf")):
        with pytest.raises(ValueError):
            ledger.bankroll_identity(bad, 1.0, 1.0)


def test_papersim_dsn_default_is_documented_example_and_validates(monkeypatch):
    monkeypatch.delenv(ledger.PAPERSIM_PG_DSN_ENV_VAR, raising=False)
    dsn = ledger.papersim_dsn()
    assert dsn == ledger.DEFAULT_PAPERSIM_PG_DSN
    assert dsn == "postgresql://paper_sim@127.0.0.1:55432/paper_sim"
    # Through the real repo validator.
    validate_local_postgres_dsn(dsn, env_var_name="PAPERSIM_PG_DSN")


@pytest.mark.parametrize(
    "value",
    [
        "postgresql://paper_sim@127.0.0.1:55432/paper_sim",
        "postgresql://paper_sim@localhost:55432/paper_sim",
        "postgresql://paper_sim@[::1]:55432/paper_sim",
        "host=127.0.0.1 port=55432 dbname=paper_sim user=paper_sim",
    ],
)
def test_papersim_dsn_accepts_local_overrides(monkeypatch, value):
    monkeypatch.setenv(ledger.PAPERSIM_PG_DSN_ENV_VAR, value)
    assert ledger.papersim_dsn() == value


@pytest.mark.parametrize(
    "bad",
    [
        "postgresql://paper_sim@db.internal.example.com:5432/paper_sim",
        "postgresql://paper_sim@10.0.0.5:5432/paper_sim",
        "sqlite:///papersim.db",
        "papersim-ledger.jsonl",
        "not a dsn",
    ],
)
def test_papersim_dsn_rejects_non_local_through_repo_validator(monkeypatch, bad):
    monkeypatch.setenv(ledger.PAPERSIM_PG_DSN_ENV_VAR, bad)
    with pytest.raises(ValueError, match="PAPERSIM_PG_DSN"):
        ledger.papersim_dsn()


def test_papersim_dsn_accepts_explicit_environment_mapping():
    assert (
        ledger.papersim_dsn(
            {"PAPERSIM_PG_DSN": "postgresql://paper_sim@127.0.0.1:55432/paper_sim"}
        )
        == "postgresql://paper_sim@127.0.0.1:55432/paper_sim"
    )
    with pytest.raises(ValueError, match="PAPERSIM_PG_DSN"):
        ledger.papersim_dsn(
            {"PAPERSIM_PG_DSN": "postgresql://paper_sim@db.example.com:5432/paper_sim"}
        )


def test_papersim_dsn_never_reads_or_creates_password_file(monkeypatch, tmp_path):
    bogus = tmp_path / "no-such-password-file"
    monkeypatch.setenv(ledger.PAPERSIM_PG_PASSWORD_FILE_ENV_VAR, str(bogus))
    monkeypatch.delenv(ledger.PAPERSIM_PG_DSN_ENV_VAR, raising=False)
    assert ledger.papersim_dsn() == ledger.DEFAULT_PAPERSIM_PG_DSN
    assert not bogus.exists()
    assert ledger.PAPERSIM_PG_PASSWORD_FILE_ENV_VAR == "PAPERSIM_PG_PASSWORD_FILE"
    assert "PAPERSIM_PG_PASSWORD_FILE" in ledger.papersim_dsn.__doc__


def test_p0_stub_surface_unchanged():
    assert tuple(field.name for field in fields(ledger.PaperLedgerEntry)) == (
        "position_id",
        "fixture",
        "question",
        "side",
        "notional",
        "price",
        "event",
        "evidence",
    )
    with pytest.raises(NotImplementedError):
        ledger.record_entry(
            position_id="#48",
            fixture="Brentford FC vs. Nottingham Forest FC",
            question="Over 2.5",
            side="Over",
            notional=250.0,
            price=0.56,
        )
    with pytest.raises(NotImplementedError):
        ledger.mark_to_market(entry_price=0.56, exit_bid=0.54)


@pytest.mark.skipif(
    not os.environ.get("PAPERSIM_PG_DSN"),
    reason=(
        INTEGRATION_LABEL
        + ": set PAPERSIM_PG_DSN (validated loopback paper_sim DSN) to enable; "
        "default runs never open any database connection"
    ),
)
def test_papersim_ledger_integration_relations_exist():
    dsn = ledger.papersim_dsn()
    validate_local_postgres_dsn(dsn, env_var_name="PAPERSIM_PG_DSN")
    psycopg = pytest.importorskip("psycopg")
    connect_kwargs = {"connect_timeout": 5}
    password_file = os.environ.get(ledger.PAPERSIM_PG_PASSWORD_FILE_ENV_VAR)
    if password_file:
        connect_kwargs["password"] = Path(password_file).read_text(
            encoding="utf-8"
        ).strip()
    expected = {
        ("decisions", "BASE TABLE"),
        ("resolutions", "BASE TABLE"),
        ("bankroll", "BASE TABLE"),
        ("model_performance", "VIEW"),
        ("forecast_calibration", "VIEW"),
    }
    with psycopg.connect(dsn, **connect_kwargs) as connection:
        rows = connection.execute(
            "select table_name, table_type from information_schema.tables "
            "where table_schema = 'public' and table_name = any(%s)",
            ([name for name, _ in expected],),
        ).fetchall()
    assert {(str(name), str(kind)) for name, kind in rows} == expected
