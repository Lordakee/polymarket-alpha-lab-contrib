"""The single papersim connection and transaction adapter.

This is the ONLY new module in this change set that imports a database
driver; it is the single new entry in the frozen connector allowlist
guarded by ``tests/test_database_persistence_iron_rule.py`` (reviewed
D-CONN diff: exactly one exact path, no globs).

Contract (design 2026-11-15 v2, sections 3.3/3.4 and 5.8):

- Every raw DSN passes the single audited ``validate_local_postgres_dsn``
  (canonical import ``local_postgres_dsn``) BEFORE any connection, wrapper
  or callback is constructed; SQL is fully parameterized.
- ``managed_dsn(info, owner=...)`` reproduces the V1 ``ProjectPostgres``
  DSN construction parameter-for-parameter (byte-equal; pinned by an
  equivalence test against ``ProjectPostgres._dsn`` so a V1 change turns
  the papersim tests red). Passwords travel only through libpq passfiles
  and are never read, logged or committed by this module.
- ``connect_managed`` additionally asserts the instance identity triple
  plus database/role on every managed application connection via
  ``project_postgres.binding`` (same guard as V1 research sessions).
- ``connect_legacy_readonly`` serves the frozen legacy paper_sim cluster
  through the audited read-only face only (default_transaction_read_only),
  with the operator password file convention; it never writes.
- Scan writes are ONE transaction: scan_runs + all candidates (+ price
  evidence) + entries + the matching cash events commit together, the
  same scan key with the same payload returns the original result, a
  changed payload is a conflict, and any exception leaves no half scan.
  Database failures never degrade to a file journal.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path

import psycopg

from polymarket_alpha_lab.local_postgres_dsn import validate_local_postgres_dsn
from polymarket_alpha_lab.papersim.store import (
    EffectiveMarketOutcome,
    MarketOutcomeObservation,
    PapersimStoreError,
    ScanSubmission,
    _as_decimal,
)
from polymarket_alpha_lab.project_postgres import binding, sql
from polymarket_alpha_lab.project_postgres.files import no_links, read_private

MANAGED_DSN_LABEL = 'PAPERSIM_MANAGED_PG_DSN'
OWNER_DSN_LABEL = 'PAPERSIM_OWNER_PG_DSN'
LEGACY_DSN_LABEL = 'PAPERSIM_PG_DSN'
EXPLICIT_DSN_LABEL = 'PAPERSIM_MIGRATIONS_PG_DSN'


def _quote(value: str) -> str:
    # Identical to the V1 server-side quoting so managed_dsn stays byte-equal
    # to ProjectPostgres._dsn (equivalence test pins this).
    return "'" + value.replace('\\', '\\\\').replace("'", "\\'") + "'"


def _validated(dsn: str, label: str) -> str:
    validate_local_postgres_dsn(dsn, env_var_name=label)
    return dsn


def read_instance(repo_root: Path) -> dict:
    """Read the project-private instance descriptor (no credentials inside)."""
    path = Path(repo_root).resolve() / '.local' / 'postgres' / 'instance.json'
    return json.loads(read_private(path))


def managed_dsn(info: dict, *, owner: bool = False, repo_root: Path = Path('.')) -> str:
    """Keyword DSN byte-equal to ``ProjectPostgres(repo_root)._dsn(info, owner=...)``."""
    home = Path(repo_root).resolve() / '.local' / 'postgres'
    values = {'host': '127.0.0.1', 'port': str(info['port']),
              'dbname': sql.DATABASE, 'user': sql.ADMIN if owner else sql.APPLICATION,
              'passfile': str(home / ('owner.pgpass' if owner else 'app.pgpass')),
              'connect_timeout': '5', 'sslmode': 'disable', 'gssencmode': 'disable',
              'application_name': 'polymarket-alpha-lab', 'options': '-c timezone=UTC'}
    dsn = ' '.join(f'{key}={_quote(value)}' for key, value in values.items())
    return _validated(dsn, OWNER_DSN_LABEL if owner else MANAGED_DSN_LABEL)


def connect_managed(repo_root: Path, *, info: dict | None = None):
    """Application connection (pal_app) with per-connection identity assertion."""
    repo_root = Path(repo_root)
    if info is None:
        info = read_instance(repo_root)
    dsn = managed_dsn(info, owner=False, repo_root=repo_root)
    with binding.bound(info['instance_id'], info['root_sha256'], info['system_identifier']):
        connection = psycopg.connect(dsn)
        binding.verify_connection(connection.cursor())
    return connection


def connect_owner(repo_root: Path, *, info: dict | None = None):
    """Owner connection (pal_owner) for migration application only."""
    repo_root = Path(repo_root)
    if info is None:
        info = read_instance(repo_root)
    return psycopg.connect(managed_dsn(info, owner=True, repo_root=repo_root))


def connect_explicit(dsn: str, *, label: str = EXPLICIT_DSN_LABEL):
    """Validated explicit DSN connection (isolated/throwaway clusters only)."""
    return psycopg.connect(_validated(dsn, label))


def connect_legacy_readonly(dsn: str, *, password_file: str | None = None):
    """Read-only connection to the frozen legacy paper_sim cluster.

    The DSN keeps flowing through the audited papersim configuration face;
    the session is forced read-only at connect time. The optional password
    file is the operator's one-line ``PAPERSIM_PG_PASSWORD_FILE``; its
    content is read here at connect time only and never logged or stored.
    """
    kwargs = {'connect_timeout': 5, 'options': '-c default_transaction_read_only=on'}
    if password_file is not None:
        path = Path(password_file)
        no_links(path)
        kwargs['password'] = path.read_text(encoding='utf-8').splitlines()[0]
    return psycopg.connect(_validated(dsn, LEGACY_DSN_LABEL), **kwargs)


_OUTCOME_COLUMNS = ('evidence_key, condition_id, market_id, market_slug, yes_token_id, no_token_id, '
                    'outcome, outcome_detail, confirmed_at, observed_at, source_kind, source_ref, '
                    'source_snapshot_sha256')


def _outcome_row(cursor) -> dict:
    columns = [description.name for description in cursor.description]
    return dict(zip(columns, cursor.fetchone(), strict=True))


def _normalize(value):
    if value is None or isinstance(value, (bool, str, datetime)):
        return value
    return Decimal(str(value))


def record_market_outcome(conn, observation: MarketOutcomeObservation) -> dict:
    """Insert one outcome observation; idempotent per evidence_key (section 4.1-4).

    A unique-key collision re-reads the stored row: an identical payload
    returns the original outcome_id; any difference raises
    ``papersim_outcome_evidence_conflict`` without overwriting the stored row.
    """
    observation.validate()
    params = (observation.evidence_key(), observation.condition_id, observation.market_id,
              observation.market_slug, observation.yes_token_id, observation.no_token_id,
              observation.outcome, observation.outcome_detail, observation.confirmed_at,
              observation.observed_at, observation.source_kind, observation.source_ref,
              observation.source_snapshot_sha256)
    try:
        with conn.transaction():
            cursor = conn.cursor()
            cursor.execute('INSERT INTO papersim.market_outcomes (' + _OUTCOME_COLUMNS + ') '
                           'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING outcome_id', params)
            return {'outcome_id': int(cursor.fetchone()[0]), 'inserted': True}
    except psycopg.errors.UniqueViolation:
        pass  # rolled back above; the idempotent read-back follows
    with conn.transaction():
        cursor = conn.cursor()
        cursor.execute('SELECT outcome_id, ' + _OUTCOME_COLUMNS + ' FROM papersim.market_outcomes '
                       'WHERE evidence_key = %s', (observation.evidence_key(),))
        stored = _outcome_row(cursor)
    expected = observation.comparison()
    for column, value in expected.items():
        if _normalize(stored[column]) != _normalize(value):
            raise PapersimStoreError('papersim_outcome_evidence_conflict')
    return {'outcome_id': int(stored['outcome_id']), 'inserted': False}


_IDENTITY_COLUMNS = ('condition_id', 'market_id', 'market_slug')


def effective_market_outcome(conn, *, condition_id=None, market_id=None, market_slug=None):
    """Effective outcome per section 4.1-3, corrected DISTINCT ON form.

    ``SELECT DISTINCT ON (<identity>) ... ORDER BY <identity>,
    observed_at DESC, outcome_id DESC``: the leftmost ORDER BY expressions
    must match the DISTINCT ON expressions, so the identity column leads
    the ordering and the recursion stays expressible (design N3 fix).
    """
    supplied = [(name, value) for name, value in zip(_IDENTITY_COLUMNS,
                                                      (condition_id, market_id, market_slug),
                                                      strict=True) if value is not None]
    if len(supplied) != 1:
        raise PapersimStoreError('papersim_market_identity_missing')
    column, identity = supplied[0]
    template = ('SELECT DISTINCT ON ({column}) outcome_id, outcome, confirmed_at, source_kind, '
                'observed_at FROM papersim.market_outcomes WHERE {column} = %s '
                'AND outcome {predicate} ORDER BY {column}, observed_at DESC, outcome_id DESC')
    with conn.transaction():
        cursor = conn.cursor()
        cursor.execute(template.format(column=column, predicate='<> \'UNKNOWN\''), (identity,))
        row = cursor.fetchone()
        if row is None:
            cursor.execute(template.format(column=column, predicate='= \'UNKNOWN\''), (identity,))
            row = cursor.fetchone()
    if row is None:
        return EffectiveMarketOutcome(None, 'UNKNOWN')
    return EffectiveMarketOutcome(int(row[0]), row[1], row[4], row[3])


_DECISION_COLUMNS = ('evidence_id, evidence_key, candidate_id, evidence_role, observed_at, '
                     'model_probability, market_ref_kind, market_ref, token_ref, side, bid, ask, '
                     'mid, last, book_sha256, snapshot_sha256, source_kind, source_ref')


def decision_time_evidence(conn, candidate_id: int) -> dict | None:
    """The candidate's decision-time observation: smallest DECISION evidence_id (P3-8)."""
    with conn.transaction():
        cursor = conn.cursor()
        cursor.execute('SELECT ' + _DECISION_COLUMNS + ' FROM papersim.candidate_price_evidence '
                       'WHERE candidate_id = %s AND evidence_role = \'DECISION\' '
                       'ORDER BY evidence_id LIMIT 1', (candidate_id,))
        row = cursor.fetchone()
    if row is None:
        return None
    columns = [description.name for description in cursor.description]
    return dict(zip(columns, row, strict=True))


_CANDIDATE_INSERT = ('INSERT INTO papersim.candidates (scan_id, candidate_key, legacy_source_id, '
                     'condition_id, market_id, market_slug, yes_token_id, no_token_id, side, '
                     'market_kind, market_type, team, binding_version, model_name, model_version, '
                     'median_probability, variant_quotes, input_payload, snapshot_refs, order_book, '
                     'book_fetched_at, conclusion, gate_report, rejection_reasons, evaluated_at, '
                     'is_legacy) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,'
                     '%s,%s,%s::jsonb,%s,%s,%s,%s::jsonb,%s,%s) RETURNING candidate_id')

_EVIDENCE_INSERT = ('INSERT INTO papersim.candidate_price_evidence (evidence_key, candidate_id, '
                    'evidence_role, observed_at, model_probability, market_ref_kind, market_ref, '
                    'token_ref, side, bid, ask, mid, last, book_sha256, snapshot_sha256, '
                    'source_kind, source_ref) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)')

_ENTRY_INSERT = ('INSERT INTO papersim.entries (candidate_id, legacy_source_id, stake, price, shares, '
                 'fee_category, fee_rate, entry_fee, fee_source, tier, entered_at, is_legacy) '
                 'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING entry_id')

_CASH_INSERT = ('INSERT INTO papersim.bankroll_events (event_key, occurred_at, currency, amount, '
                'reason, entry_id, scan_id, note, is_legacy) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)')


def record_scan(conn, submission: ScanSubmission) -> dict:
    """Write one complete scan in a single transaction (section 5.8).

    Same scan key + same payload digest returns the original ids
    (``inserted=False``); a changed payload raises
    ``papersim_scan_payload_conflict``; any failure rolls the whole scan
    back so no half scan ever survives.
    """
    submission.validate()
    scan = submission.scan
    key = scan.key()
    payload = submission.payload_sha256()
    with conn.transaction():
        cursor = conn.cursor()
        cursor.execute('SELECT scan_id, scan_payload_sha256 FROM papersim.scan_runs '
                       'WHERE scan_key = %s', (key,))
        existing = cursor.fetchone()
        if existing is not None:
            if existing[1] != payload:
                raise PapersimStoreError('papersim_scan_payload_conflict')
            scan_id = int(existing[0])
            return {'scan_id': scan_id, 'scan_key': key, 'inserted': False,
                    'candidate_ids': _read_back_candidates(cursor, scan_id),
                    'bankroll_event_keys': _read_back_event_keys(cursor, scan_id)}
        cursor.execute('INSERT INTO papersim.scan_runs (scan_key, scan_payload_sha256, team, '
                       'started_at, finished_at, code_commit, schema_version, gate_version, '
                       'operator, params, is_legacy) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s) '
                       'RETURNING scan_id',
                       (key, payload, scan.team, scan.started_at, scan.finished_at, scan.code_commit,
                        scan.schema_version, scan.gate_version, scan.operator, scan.params, scan.is_legacy))
        scan_id = int(cursor.fetchone()[0])
        candidate_ids: dict[str, int] = {}
        bankroll_keys: list[str] = []
        for candidate in submission.candidates:
            references = json.loads(candidate.snapshot_refs)
            if references:
                # Design 5.3/D-4: snapshot references are validated jsonb
                # refs; the store layer proves each referenced snapshot is
                # already registered inside the same transaction.
                cursor.execute('SELECT content_sha256 FROM papersim.snapshots '
                               'WHERE content_sha256 = ANY(%s)', (references,))
                present = {row[0] for row in cursor.fetchall()}
                if any(reference not in present for reference in references):
                    raise PapersimStoreError('papersim_snapshot_ref_missing')
            cursor.execute(_CANDIDATE_INSERT, _candidate_params(scan_id, candidate))
            candidate_id = int(cursor.fetchone()[0])
            candidate_ids[candidate.candidate_key] = candidate_id
            for evidence in candidate.price_evidence:
                cursor.execute(_EVIDENCE_INSERT, _evidence_params(candidate_id, evidence))
            if candidate.entry is not None:
                entry = candidate.entry
                cursor.execute(_ENTRY_INSERT, (candidate_id, entry.legacy_source_id, entry.stake,
                                               entry.price, entry.shares, entry.fee_category,
                                               entry.fee_rate, entry.entry_fee, entry.fee_source,
                                               entry.tier, entry.entered_at, entry.is_legacy))
                entry_id = int(cursor.fetchone()[0])
                event_key = f'entry:{entry_id}:cash'
                cursor.execute(_CASH_INSERT, (event_key, entry.entered_at, 'USD',
                                              -(_as_decimal(entry.stake) + _as_decimal(entry.entry_fee)),
                                              'SCAN_ENTRY', entry_id, scan_id, None, entry.is_legacy))
                bankroll_keys.append(event_key)
    return {'scan_id': scan_id, 'scan_key': key, 'inserted': True,
            'candidate_ids': candidate_ids, 'bankroll_event_keys': tuple(bankroll_keys)}


def _read_back_candidates(cursor, scan_id: int) -> dict:
    cursor.execute('SELECT candidate_id, candidate_key FROM papersim.candidates '
                   'WHERE scan_id = %s ORDER BY candidate_id', (scan_id,))
    return {key: int(identifier) for identifier, key in cursor.fetchall()}


def _read_back_event_keys(cursor, scan_id: int) -> tuple:
    cursor.execute('SELECT event_key FROM papersim.bankroll_events WHERE scan_id = %s '
                   'ORDER BY event_id', (scan_id,))
    return tuple(key for (key,) in cursor.fetchall())


def _candidate_params(scan_id: int, candidate) -> tuple:
    return (scan_id, candidate.candidate_key, candidate.legacy_source_id, candidate.condition_id,
            candidate.market_id, candidate.market_slug, candidate.yes_token_id, candidate.no_token_id,
            candidate.side, candidate.market_kind, candidate.market_type, candidate.team,
            candidate.binding_version, candidate.model_name, candidate.model_version,
            candidate.median_probability, candidate.variant_quotes, candidate.input_payload,
            candidate.snapshot_refs, candidate.order_book, candidate.book_fetched_at,
            candidate.conclusion, candidate.gate_report, candidate.rejection_reasons,
            candidate.evaluated_at, candidate.is_legacy)


def _evidence_params(candidate_id: int, evidence) -> tuple:
    return (evidence.evidence_key_with(candidate_id), candidate_id, evidence.evidence_role,
            evidence.observed_at, evidence.model_probability, evidence.market_ref_kind,
            evidence.market_ref, evidence.token_ref, evidence.side, evidence.bid, evidence.ask,
            evidence.mid, evidence.last, evidence.book_sha256, evidence.snapshot_sha256,
            evidence.source_kind, evidence.source_ref)