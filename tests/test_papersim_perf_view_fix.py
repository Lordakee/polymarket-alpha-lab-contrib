"""P4-0a regression; opt-in PostgreSQL checks execute SELECT/VALUES only.

Set WP_P4_READONLY_PG=1 plus PAPERSIM_PG_DSN and, if required,
PAPERSIM_PG_PASSWORD_FILE. No DDL, table reads, table writes or temp tables:
the real migration SELECT runs over inline fixture CTEs in a read-only session.
"""
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path

import pytest

from polymarket_alpha_lab.papersim.ledger import papersim_dsn
from polymarket_alpha_lab.local_postgres_dsn import validate_local_postgres_dsn


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase/migrations/20261107000000_papersim_perf_view_fix.sql"


def fixture_query(decisions, resolutions):
    """Exercise the view's verbatim query, substituting only its two relations."""
    sql = MIGRATION.read_text().split("create or replace view public.model_performance as\n", 1)[1]
    sql = sql.replace("public.decisions", "fixture_decisions")
    sql = sql.replace("public.resolutions", "fixture_resolutions")
    return (
        "with fixture_decisions(market_id,market_type,shares,model_prediction) as (values "
        + decisions + "), fixture_resolutions(market_id,outcome,pnl) as (values "
        + resolutions + "), " + sql.removeprefix("with ")
    )


def test_migration_is_additive_and_hash_locked():
    entries = json.loads((ROOT / "database/migrations.lock.json").read_text())["migrations"]
    entry = next(row for row in entries if row["name"] == MIGRATION.name)
    assert entry["sha256"] == hashlib.sha256(MIGRATION.read_bytes()).hexdigest()
    sql = MIGRATION.read_text().lower()
    assert sql.count("create or replace view") == 1
    assert "partition by d.market_id" in sql
    assert "round(sum(allocated_pnl), 2)" in sql
    assert "round(r.pnl" not in sql


@pytest.fixture(scope="module")
def readonly_pg():
    if os.environ.get("WP_P4_READONLY_PG") != "1":
        pytest.skip("WP_P4_READONLY_PG=1 enables SELECT-only PostgreSQL fixture checks")
    psycopg = pytest.importorskip("psycopg")
    dsn = papersim_dsn()
    validate_local_postgres_dsn(dsn, env_var_name="PAPERSIM_PG_DSN")
    options = dict(connect_timeout=5, options="-c default_transaction_read_only=on -c statement_timeout=5000")
    password_path = os.environ.get("PAPERSIM_PG_PASSWORD_FILE")
    if password_path:
        options["password"] = Path(password_path).read_text().strip()
    try:
        conn = psycopg.connect(dsn, **options)
    except psycopg.Error:
        raise RuntimeError("Read-only PostgreSQL fixture connection failed (details redacted)") from None
    options.clear()
    try:
        assert conn.execute("show transaction_read_only").fetchone() == ("on",)
        yield conn
    finally:
        conn.rollback()
        conn.close()


def test_3866000_unique_market_pnl_and_decision_counts(readonly_pg):
    # Synthetic shares mimic two entries; these are not claimed historical lots.
    # The three resolution amounts reproduce the known 2795.00 -> 1489.80 bug.
    rows = readonly_pg.execute(fixture_query(
        "('3866000','crypto_touch',1400::numeric,.680::numeric),"
        "('3866000','crypto_touch',1155::numeric,.606::numeric),"
        "('single-win','crypto_touch',400::numeric,.655::numeric),"
        "('exit','crypto_touch',300::numeric,.944::numeric)",
        "('3866000','YES',1305.20::numeric),"
        "('single-win','NO',192.27::numeric),"
        "('exit','EXITED',-7.67::numeric)",
    )).fetchall()
    assert rows == [("crypto_touch", 4, 3, 0, 1, Decimal("100.0"), Decimal("1489.80"), Decimal("0.721"))]
    assert Decimal("1305.20") * 2 + Decimal("192.27") - Decimal("7.67") == Decimal("2795.00")


def test_allocation_spans_market_types_and_preserves_loss_and_exit(readonly_pg):
    rows = readonly_pg.execute(fixture_query(
        "('shared','a',1::numeric,.5::numeric),('shared','b',3::numeric,.6::numeric),"
        "('loss','a',2::numeric,.7::numeric),('exit','b',2::numeric,.8::numeric)",
        "('shared','YES',100::numeric),('loss','NO',-10::numeric),('exit','EXITED',-5::numeric)",
    )).fetchall()
    by_type = {r[0]: r for r in rows}
    assert by_type["a"][1:5] == (2, 1, 1, 0)
    assert by_type["b"][1:5] == (2, 1, 0, 1)
    assert by_type["a"][6] == Decimal("15.00")
    assert by_type["b"][6] == Decimal("70.00")


def test_no_rounding_loss_at_individual_allocations(readonly_pg):
    rows = readonly_pg.execute(fixture_query(
        "('m','a',1::numeric,.5::numeric),('m','a',1::numeric,.5::numeric),('m','a',1::numeric,.5::numeric)",
        "('m','YES',.01::numeric)",
    )).fetchall()
    assert rows[0][6] == Decimal("0.01")


@pytest.mark.parametrize("shares", ["null", "-1", "'NaN'", "'Infinity'"])
def test_unknown_allocation_is_not_silently_omitted(readonly_pg, shares):
    rows = readonly_pg.execute(fixture_query(
        f"('m','a',{shares}::numeric,.5::numeric),('m','a',1::numeric,.5::numeric)",
        "('m','YES',100::numeric)",
    )).fetchall()
    assert rows[0][6] is None


def test_zero_denominator_remains_unknown(readonly_pg):
    rows = readonly_pg.execute(fixture_query(
        "('m','a',0::numeric,.5::numeric)", "('m','YES',100::numeric)",
    )).fetchall()
    assert rows[0][6] is None
