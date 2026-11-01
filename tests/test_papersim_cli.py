"""WP-P1 W5 tests: papersim CLI (selfcheck / schema / validate-dsn).

The selfcheck invariant suite must run green end-to-end both in-process
(``cli.main``) and as a real subprocess (``python -m
polymarket_alpha_lab.papersim.cli``); the schema subcommand must emit the
ledger migration text byte-identically; validate-dsn must accept local
DSNs, reject hosted/file fallbacks, never print the DSN value and never
read the password file. Everything here is read-only: no network, no
database connection, no writes outside a temp dir.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from polymarket_alpha_lab import papersim
from polymarket_alpha_lab.papersim import cli, ledger

SELFCHECK_CHECK_NAMES = (
    "module-imports",
    "crypto-r19:ETH-2000",
    "crypto-r19:ETH-2250",
    "crypto-r19:BTC-65k",
    "soccer-r23:BRE-FOR_O2.5",
    "soccer-r23:HUL-IPS_O2.5",
    "soccer-r23:CHE-MUN_O3.5",
    "soccer-r23:BOU-LEE_O2.5",
    "banned-path:HOF-LYO",
    "gate-arithmetic:#48",
)

LOCAL_DSNS = (
    "postgresql://paper_sim@127.0.0.1:55432/paper_sim",
    "postgresql://paper_sim@localhost:55432/paper_sim",
    "host=127.0.0.1 port=55432 dbname=paper_sim user=paper_sim",
)
HOSTED_DSN = "postgresql://paper_sim@db.internal.example.com:5432/paper_sim"


# ---------------------------------------------------------------------------
# selfcheck
# ---------------------------------------------------------------------------


def test_selfcheck_passes_in_process(capsys) -> None:
    code = cli.main(["selfcheck"])
    out = capsys.readouterr().out
    assert code == 0
    for name in SELFCHECK_CHECK_NAMES:
        assert f"[PASS] {name} " in out
    assert "[FAIL]" not in out
    assert "selfcheck: PASS (10/10 checks)" in out


def test_selfcheck_passes_as_subprocess() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "polymarket_alpha_lab.papersim.cli", "selfcheck"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "selfcheck: PASS (10/10 checks)" in result.stdout
    assert "[FAIL]" not in result.stdout


def test_selfcheck_reports_failure_when_a_model_drifts(monkeypatch, capsys) -> None:
    # A drifted soccer model must fail exactly the four soccer anchors.
    def drifted(*args, **kwargs):
        return 0.5

    monkeypatch.setattr(
        "polymarket_alpha_lab.papersim.soccer_model.over_probability", drifted
    )
    code = cli.main(["selfcheck"])
    out = capsys.readouterr().out
    assert code == 1
    assert "selfcheck: FAIL (6/10 checks)" in out
    for name in SELFCHECK_CHECK_NAMES:
        expected = "FAIL" if name.startswith("soccer-r23:") else "PASS"
        assert f"[{expected}] {name} " in out


def test_selfcheck_fails_cleanly_when_fixtures_missing(monkeypatch, capsys) -> None:
    bogus = Path("/nonexistent-papersim-fixtures")
    monkeypatch.setattr(cli, "_fixtures_dir", lambda: bogus)
    code = cli.main(["selfcheck"])
    out = capsys.readouterr().out
    assert code == 1
    assert "selfcheck: FAIL (1/10 checks)" in out
    # Only the import check survives; every anchor names the missing file.
    assert out.count("[FAIL]") == 9
    assert "[PASS] module-imports " in out
    assert "frozen fixture missing" in out


# ---------------------------------------------------------------------------
# schema
# ---------------------------------------------------------------------------


def test_schema_emits_ledger_ddl_verbatim(capsys) -> None:
    code = cli.main(["schema"])
    assert code == 0
    assert capsys.readouterr().out == ledger.ddl()


def test_schema_subprocess_matches_migration_file() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "polymarket_alpha_lab.papersim.cli", "schema"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    migration = (
        Path(ledger.__file__).resolve().parents[3]
        / "supabase"
        / "migrations"
        / ledger.PAPERSIM_LEDGER_MIGRATION_NAME
    )
    assert result.stdout == migration.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# validate-dsn
# ---------------------------------------------------------------------------


def test_validate_dsn_default_passes_without_env(monkeypatch, capsys) -> None:
    monkeypatch.delenv(ledger.PAPERSIM_PG_DSN_ENV_VAR, raising=False)
    code = cli.main(["validate-dsn"])
    out = capsys.readouterr().out
    assert code == 0
    assert "validate-dsn: PASS" in out
    assert "documented default" in out
    assert "validate_local_postgres_dsn" in out
    # Redaction discipline: the DSN value is never printed.
    assert ledger.DEFAULT_PAPERSIM_PG_DSN not in out


@pytest.mark.parametrize("dsn", LOCAL_DSNS)
def test_validate_dsn_accepts_local_overrides(monkeypatch, capsys, dsn) -> None:
    monkeypatch.setenv(ledger.PAPERSIM_PG_DSN_ENV_VAR, dsn)
    code = cli.main(["validate-dsn"])
    out = capsys.readouterr().out
    assert code == 0
    assert "validate-dsn: PASS" in out
    assert f"environment {ledger.PAPERSIM_PG_DSN_ENV_VAR}" in out
    assert dsn not in out  # never echoed


def test_validate_dsn_rejects_hosted_dsn(monkeypatch, capsys) -> None:
    monkeypatch.setenv(ledger.PAPERSIM_PG_DSN_ENV_VAR, HOSTED_DSN)
    code = cli.main(["validate-dsn"])
    out = capsys.readouterr().out
    assert code == 1
    assert "validate-dsn: FAIL" in out
    assert ledger.PAPERSIM_PG_DSN_ENV_VAR in out
    # The rejected value is not leaked into the report.
    assert HOSTED_DSN not in out
    assert "db.internal.example.com" not in out


def test_validate_dsn_never_reads_password_file(monkeypatch, capsys, tmp_path) -> None:
    bogus = tmp_path / "no-such-password-file"
    monkeypatch.setenv(ledger.PAPERSIM_PG_PASSWORD_FILE_ENV_VAR, str(bogus))
    monkeypatch.delenv(ledger.PAPERSIM_PG_DSN_ENV_VAR, raising=False)
    code = cli.main(["validate-dsn"])
    out = capsys.readouterr().out
    assert code == 0
    assert not bogus.exists()
    assert ledger.PAPERSIM_PG_PASSWORD_FILE_ENV_VAR in out
    assert "never read" in out


# ---------------------------------------------------------------------------
# argument surface
# ---------------------------------------------------------------------------


def test_unknown_command_exits_two() -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["bogus-command"])
    assert excinfo.value.code == 2


def test_missing_command_exits_two() -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main([])
    assert excinfo.value.code == 2


def test_cli_main_is_the_package_export() -> None:
    assert papersim.cli_main is cli.main
    assert callable(papersim.cli_main)
