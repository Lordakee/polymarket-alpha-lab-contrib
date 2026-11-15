"""Opt-in native papersim store proofs on the assembled managed face.

Runs only inside the disposable native cluster environment (the CI
throwaway papersim partition or an explicitly assembled local cluster).
Never touches a business cluster: the environment DSNs point at the
one-shot assembled managed face (roles ``pal_owner``/``pal_app``,
database ``polymarket_alpha_lab``, V1 bootstrap applied). Covers design
section 8.2 items B7-B20 plus the D-CONN allowlist pin and the managed
DSN equivalence proof.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import md5, sha256
import importlib.util
import os
import sys
from pathlib import Path
import uuid

import pytest

from polymarket_alpha_lab.papersim import migrations as pm
from polymarket_alpha_lab.papersim import store

ROOT = Path(__file__).resolve().parents[1]
ENABLED = os.environ.get('POLYMARKET_ALPHA_LAB_RUN_NATIVE_PROJECT_POSTGRES') == '1'
OWNER_DSN = os.environ.get('PAPERSIM_NATIVE_MANAGED_OWNER_DSN', '')
APP_DSN = os.environ.get('PAPERSIM_NATIVE_MANAGED_APP_DSN', '')
NATIVE = pytest.mark.skipif(not ENABLED or not OWNER_DSN or not APP_DSN,
                            reason='explicit native papersim store proof is opt-in')


def adapter():
    """Import the connection adapter lazily.

    The offline suite guards a lazy-import invariant elsewhere in the repo
    (``psycopg`` must never linger in ``sys.modules`` after collection), so
    this file never imports the driver-backed adapter at module level.
    """
    if not ENABLED:
        pytest.skip('the papersim connection adapter runs in the native lane only')
    return pytest.importorskip('polymarket_alpha_lab.papersim.store_psycopg')


def at(minutes: int) -> datetime:
    return datetime(2026, 11, 15, 12, 0, tzinfo=UTC) + timedelta(minutes=minutes)


def connect(dsn, *, autocommit=False):
    psycopg = pytest.importorskip('psycopg')
    connection = psycopg.connect(dsn)
    connection.autocommit = autocommit
    return connection


@pytest.fixture(scope='module')
def managed_face():
    """Apply the papersim catalog once for this module's shared face."""
    owner = connect(OWNER_DSN)
    result = pm.apply_pending_migrations(owner, ROOT)
    assert result['applied'] in (0, 1, 2)
    assert pm.migration_status(owner, ROOT)['pending'] == []
    owner.close()
    return OWNER_DSN, APP_DSN


def outcome(**overrides):
    # The design 4.4 idempotency key is condition_id|market_id|source_kind|
    # source_ref|observed_at (no slug): slug-only markets therefore keep a
    # per-market source reference, like a real close-event id.
    identity = (overrides.get('market_slug') or overrides.get('market_id')
                or overrides.get('condition_id') or 'fixed-market')
    values = dict(condition_id=None, market_id=None, market_slug=None, yes_token_id=None,
                  no_token_id=None, outcome='YES', outcome_detail=None, confirmed_at=at(60),
                  observed_at=at(30), source_kind='gamma_close',
                  source_ref='close-' + identity,
                  source_snapshot_sha256=None)
    values.update(overrides)
    return store.MarketOutcomeObservation(**values)


def evidence(**overrides):
    values = dict(observed_at=at(5), evidence_role='DECISION', model_probability=None,
                  market_ref_kind='market_slug', market_ref='fed-hike-jan', token_ref=None,
                  side='YES', bid=None, ask=None, mid=None, last=None, book_sha256=None,
                  snapshot_sha256=None, source_kind='gamma_close', source_ref='r1')
    values.update(overrides)
    return store.PriceEvidenceObservation(**values)


def entry(**overrides):
    values = dict(stake=Decimal('250'), price=Decimal('0.56'), shares=Decimal('446.4286'),
                  fee_category='crypto', fee_rate=Decimal('0.07'), entry_fee=Decimal('10.08'),
                  fee_source='schedule', tier='standard', entered_at=at(6), legacy_source_id=None,
                  is_legacy=False)
    values.update(overrides)
    return store.EntrySubmission(**values)


def candidate(**overrides):
    values = dict(candidate_key='m1-YES', conclusion='REJECTED', side='YES', market_kind='terminal',
                  team='crypto_eth', model_name='gbm', model_version='r19', input_payload='{}',
                  gate_report='{}', evaluated_at=at(5), condition_id=None, market_id=None,
                  market_slug='fed-hike-jan', yes_token_id=None, no_token_id=None,
                  market_type='terminal', binding_version=1, median_probability=Decimal('0.44'),
                  variant_quotes='[]', snapshot_refs='[]', rejection_reasons='["edge"]',
                  order_book=None, book_fetched_at=None, legacy_source_id=None, is_legacy=False,
                  price_evidence=(), entry=None)
    values.update(overrides)
    return store.CandidateSubmission(**values)


def scan_run(finished=6):
    return store.ScanRunRecord(team='crypto_eth', started_at=at(0), finished_at=at(finished),
                               code_commit='c' * 40, schema_version=1, gate_version='g1',
                               operator='unattended', params='{"run": "%s"}' % uuid.uuid4().hex[:8])


def unique_slug() -> str:
    return 'market-' + uuid.uuid4().hex[:10]


# ---------------------------------------------------------------------------
# D-CONN allowlist pin and managed DSN equivalence (8.2 items 13 and 16)
# ---------------------------------------------------------------------------

def test_frozen_connector_allowlist_contains_exactly_the_papersim_adapter():
    from tests.test_database_persistence_iron_rule import FROZEN_CONNECTOR_ALLOWLIST
    assert 'src/polymarket_alpha_lab/papersim/store_psycopg.py' in FROZEN_CONNECTOR_ALLOWLIST
    assert 'src/polymarket_alpha_lab/papersim/store.py' not in FROZEN_CONNECTOR_ALLOWLIST
    assert 'src/polymarket_alpha_lab/papersim/migrations.py' not in FROZEN_CONNECTOR_ALLOWLIST


@NATIVE
def test_managed_dsn_is_byte_equal_to_the_v1_construction():
    store_psycopg = adapter()
    from polymarket_alpha_lab.project_postgres.server import ProjectPostgres
    info = {'port': 55433}
    assert store_psycopg.managed_dsn(info, owner=False, repo_root=ROOT) == \
        ProjectPostgres(ROOT)._dsn(info, owner=False)
    assert store_psycopg.managed_dsn(info, owner=True, repo_root=ROOT) == \
        ProjectPostgres(ROOT)._dsn(info, owner=True)


@NATIVE
def test_binding_verify_accepts_the_instance_triple_and_rejects_drift(managed_face):
    _, app_dsn = managed_face
    owner = connect(OWNER_DSN)
    with owner.cursor() as cursor:
        cursor.execute('SELECT instance_id, root_sha256, system_identifier '
                       'FROM project_private.instance WHERE singleton IS TRUE')
        triple = cursor.fetchone()
    owner.close()
    application = connect(app_dsn)
    from polymarket_alpha_lab.project_postgres import binding
    from polymarket_alpha_lab.project_postgres.files import ProjectDatabaseError
    with binding.bound(*triple):
        binding.verify_connection(application.cursor())
    with pytest.raises(ProjectDatabaseError, match='project_postgres_connection_identity_mismatch'):
        with binding.bound('0' * 32, triple[1], triple[2]):
            binding.verify_connection(application.cursor())
    application.close()


# ---------------------------------------------------------------------------
# Scan transaction (8.2 items 7, 8, 10, 11)
# ---------------------------------------------------------------------------

@NATIVE
def test_full_scan_write_read_and_idempotent_rerecord(managed_face):
    store_psycopg = adapter()
    _, app_dsn = managed_face
    app = connect(app_dsn)
    slug = unique_slug()
    accepted = candidate(candidate_key='k-accepted', conclusion='ACCEPTED', market_slug=slug,
                         price_evidence=(evidence(market_ref=slug),), entry=entry())
    rejected = candidate(candidate_key='k-rejected', market_slug=unique_slug())
    submission = store.ScanSubmission(scan=scan_run(), candidates=(accepted, rejected))
    first = store_psycopg.record_scan(app, submission)
    assert first['inserted'] is True and len(first['candidate_ids']) == 2
    assert len(first['bankroll_event_keys']) == 1
    with app.cursor() as cursor:
        cursor.execute('SELECT team, operator, code_commit FROM papersim.scan_runs '
                       'WHERE scan_id = %s', (first['scan_id'],))
        assert cursor.fetchone() == ('crypto_eth', 'unattended', 'c' * 40)
        cursor.execute('SELECT candidate_key, conclusion FROM papersim.candidates '
                       'WHERE scan_id = %s ORDER BY candidate_id', (first['scan_id'],))
        assert cursor.fetchall() == [('k-accepted', 'ACCEPTED'), ('k-rejected', 'REJECTED')]
        cursor.execute('SELECT count(*) FROM papersim.candidate_price_evidence c '
                       'JOIN papersim.candidates k ON k.candidate_id = c.candidate_id '
                       'WHERE k.scan_id = %s', (first['scan_id'],))
        assert cursor.fetchone()[0] == 1
        cursor.execute('SELECT stake, price, fee_source FROM papersim.entries e '
                       'JOIN papersim.candidates k ON k.candidate_id = e.candidate_id '
                       'WHERE k.scan_id = %s', (first['scan_id'],))
        assert cursor.fetchall() == [(Decimal('250'), Decimal('0.56'), 'schedule')]
        cursor.execute('SELECT event_key, amount, reason FROM papersim.bankroll_events '
                       'WHERE scan_id = %s', (first['scan_id'],))
        cash = cursor.fetchall()
        assert len(cash) == 1 and cash[0][1] == Decimal('-260.08') and cash[0][2] == 'SCAN_ENTRY'
    again = store_psycopg.record_scan(app, submission)
    assert again['inserted'] is False and again['scan_id'] == first['scan_id']
    assert again['candidate_ids'] == first['candidate_ids']
    drifted = store.ScanSubmission(scan=submission.scan, candidates=(
        accepted, candidate(candidate_key='k-rejected', market_slug=rejected.market_slug,
                            rejection_reasons='["changed"]')))
    with pytest.raises(store.PapersimStoreError, match='papersim_scan_payload_conflict'):
        store_psycopg.record_scan(app, drifted)
    with app.cursor() as cursor:
        cursor.execute('SELECT count(*) FROM papersim.scan_runs WHERE scan_key = %s',
                       (submission.scan.key(),))
        assert cursor.fetchone()[0] == 1
    app.close()


@NATIVE
def test_all_rejected_zero_entry_scan_joins_outcomes_and_prices(managed_face):
    store_psycopg = adapter()
    _, app_dsn = managed_face
    app = connect(app_dsn)
    resolved = unique_slug()
    token_mismatch = unique_slug()
    missing = unique_slug()
    store_psycopg.record_market_outcome(app, outcome(market_slug=resolved, outcome='YES',
                                                     yes_token_id='tok-a', no_token_id='tok-b'))
    store_psycopg.record_market_outcome(app, outcome(market_slug=token_mismatch, outcome='NO',
                                                     yes_token_id='tok-x', no_token_id='tok-y'))
    rows = (candidate(candidate_key='r1', market_slug=resolved, yes_token_id='tok-a',
                      no_token_id='tok-b',
                      price_evidence=(evidence(market_ref=resolved, mid=Decimal('0.62')),)),
            candidate(candidate_key='r2', market_slug=missing,
                      price_evidence=(evidence(market_ref=missing, mid=Decimal('0.31')),)),
            candidate(candidate_key='r3', market_slug=token_mismatch, yes_token_id='tok-q',
                      no_token_id='tok-r',
                      price_evidence=(evidence(market_ref=token_mismatch, mid=Decimal('0.5')),)))
    result = store_psycopg.record_scan(app, store.ScanSubmission(scan=scan_run(), candidates=rows))
    with app.cursor() as cursor:
        cursor.execute('SELECT count(*) FROM papersim.entries e JOIN papersim.candidates k '
                       'ON k.candidate_id = e.candidate_id WHERE k.scan_id = %s',
                       (result['scan_id'],))
        assert cursor.fetchone()[0] == 0  # zero-entry scan still scores below
    effective = {slug: store_psycopg.effective_market_outcome(app, market_slug=slug)
                 for slug in (resolved, missing, token_mismatch)}
    assert (effective[resolved].outcome, effective[resolved].is_effective) == ('YES', True)
    assert (effective[missing].outcome, effective[missing].outcome_id) == ('UNKNOWN', None)
    assert effective[token_mismatch].outcome == 'NO'
    for key in ('r1', 'r2', 'r3'):
        decision = store_psycopg.decision_time_evidence(app, result['candidate_ids'][key])
        assert store.decision_price_status(decision) == 'AVAILABLE'
    # Wrong token family on a matched market is a binding mismatch, not a sample.
    assert store.binding_token_status('tok-q', 'tok-r', 'tok-x', 'tok-y') is False
    assert store.natural_alignment('YES', effective[resolved].outcome) is True
    assert store.natural_alignment('YES', effective[token_mismatch].outcome) is False
    app.close()


@NATIVE
def test_correction_row_wins_tie_break_and_unknown_never_shadows(managed_face):
    store_psycopg = adapter()
    _, app_dsn = managed_face
    app = connect(app_dsn)
    slug = unique_slug()
    store_psycopg.record_market_outcome(app, outcome(market_slug=slug, outcome='YES',
                                                     observed_at=at(30)))
    correction = store_psycopg.record_market_outcome(
        app, outcome(market_slug=slug, outcome='NO', observed_at=at(90), confirmed_at=at(95)))
    effective = store_psycopg.effective_market_outcome(app, market_slug=slug)
    assert (effective.outcome_id, effective.outcome) == (correction['outcome_id'], 'NO')
    tie = unique_slug()
    store_psycopg.record_market_outcome(app, outcome(market_slug=tie, outcome='YES',
                                                     observed_at=at(30)))
    later_id = store_psycopg.record_market_outcome(
        app, outcome(market_slug=tie, outcome='NO', observed_at=at(30),
                     source_ref='close-2-' + tie))['outcome_id']
    tied = store_psycopg.effective_market_outcome(app, market_slug=tie)
    assert (tied.outcome_id, tied.outcome) == (later_id, 'NO')
    shadowed = unique_slug()
    settled = store_psycopg.record_market_outcome(app, outcome(market_slug=shadowed, outcome='YES',
                                                               observed_at=at(30)))
    store_psycopg.record_market_outcome(app, outcome(market_slug=shadowed, outcome='UNKNOWN',
                                                     confirmed_at=None, observed_at=at(200)))
    still = store_psycopg.effective_market_outcome(app, market_slug=shadowed)
    assert (still.outcome_id, still.outcome) == (settled['outcome_id'], 'YES')
    app.close()


@NATIVE
def test_market_outcome_idempotency_and_payload_conflict(managed_face):
    store_psycopg = adapter()
    _, app_dsn = managed_face
    app = connect(app_dsn)
    slug = unique_slug()
    observation = outcome(market_slug=slug, observed_at=at(30))
    first = store_psycopg.record_market_outcome(app, observation)
    repeat = store_psycopg.record_market_outcome(app, observation)
    assert repeat == {'outcome_id': first['outcome_id'], 'inserted': False}
    conflicting = outcome(market_slug=slug, observed_at=at(30), outcome='NO')
    with pytest.raises(store.PapersimStoreError, match='papersim_outcome_evidence_conflict'):
        store_psycopg.record_market_outcome(app, conflicting)
    with app.cursor() as cursor:
        cursor.execute('SELECT outcome FROM papersim.market_outcomes WHERE evidence_key = %s',
                       (observation.evidence_key(),))
        assert cursor.fetchone()[0] == 'YES'
    app.close()


@NATIVE
def test_time_order_violation_rejects_the_whole_scan(managed_face):
    store_psycopg = adapter()
    _, app_dsn = managed_face
    app = connect(app_dsn)
    slug = unique_slug()
    rows = (candidate(candidate_key='bad-order', market_slug=slug, price_evidence=(
        evidence(observed_at=at(3), evidence_role='CLOSE', source_kind='clob_terminal_price',
                 source_ref='t', last=Decimal('1')),
        evidence(observed_at=at(4), evidence_role='DECISION', market_ref=slug),),),)
    submission = store.ScanSubmission(scan=scan_run(), candidates=rows)
    with pytest.raises(store.PapersimStoreError, match='papersim_evidence_time_order_invalid'):
        store_psycopg.record_scan(app, submission)
    with app.cursor() as cursor:
        cursor.execute('SELECT count(*) FROM papersim.scan_runs WHERE scan_key = %s',
                       (submission.scan.key(),))
        assert cursor.fetchone()[0] == 0
        cursor.execute("SELECT count(*) FROM papersim.candidates WHERE candidate_key = 'bad-order'")
        assert cursor.fetchone()[0] == 0
    app.close()


@NATIVE
def test_backend_termination_mid_transaction_leaves_no_half_scan(managed_face):
    psycopg = pytest.importorskip('psycopg')
    _, app_dsn = managed_face
    key = 'terminated-' + uuid.uuid4().hex[:10]
    connection = psycopg.connect(app_dsn)
    try:
        with connection.transaction():
            cursor = connection.cursor()
            cursor.execute(
                'INSERT INTO papersim.scan_runs (scan_key, scan_payload_sha256, team, started_at, '
                'finished_at, code_commit, schema_version, gate_version, operator, params) '
                'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb) RETURNING scan_id',
                (key, 'd' * 64, 'crypto_eth', at(0), at(6), 'c' * 40, 1, 'g1', 'unattended', '{}'))
            cursor.fetchone()
            cursor.execute('SELECT pg_terminate_backend(pg_backend_pid())')
            cursor.fetchone()
    except psycopg.OperationalError:
        pass
    connection.close()
    app = connect(app_dsn)
    with app.cursor() as cursor:
        cursor.execute('SELECT count(*) FROM papersim.scan_runs WHERE scan_key = %s', (key,))
        assert cursor.fetchone()[0] == 0
    app.close()


# ---------------------------------------------------------------------------
# Guard and constraint negatives (8.2 items 12, 15, 19, 20)
# ---------------------------------------------------------------------------

PAPERSIM_TABLES = ('scan_runs', 'snapshots', 'candidates', 'candidate_price_evidence',
                   'market_outcomes', 'entries', 'marks', 'settlements', 'bankroll_events')


def _seed_every_table(owner, app):
    """One row in every guarded table so row triggers have something to hit."""
    store_psycopg = adapter()
    slug = unique_slug()
    result = store_psycopg.record_scan(app, store.ScanSubmission(
        scan=scan_run(),
        candidates=(candidate(candidate_key='seed', conclusion='ACCEPTED', market_slug=slug,
                              price_evidence=(evidence(market_ref=slug),), entry=entry()),)))
    outcome_id = store_psycopg.record_market_outcome(app, outcome(market_slug=slug))['outcome_id']
    candidate_id = result['candidate_ids']['seed']
    with owner.cursor() as cursor:
        cursor.execute('SELECT entry_id FROM papersim.entries WHERE candidate_id = %s',
                       (candidate_id,))
        entry_id = cursor.fetchone()[0]
        content = ('seed-snapshot-' + uuid.uuid4().hex).encode()
        cursor.execute('INSERT INTO papersim.snapshots (content_sha256, content, byte_length, '
                       'kind, source, fetched_at, schema_version) VALUES (%s,%s,%s,%s,%s,%s,%s)',
                       (sha256(content).hexdigest(), content, len(content), 'book',
                        'seed', at(1), 1))
        cursor.execute('INSERT INTO papersim.marks (entry_id, mark_key, marked_at, mid, is_close, '
                       'source_kind) VALUES (%s,%s,%s,%s,%s,%s)',
                       (entry_id, 'seed:' + uuid.uuid4().hex[:8], at(5), Decimal('0.55'), False,
                        'clob_terminal_price'))
        cursor.execute('SELECT mark_id FROM papersim.marks WHERE entry_id = %s', (entry_id,))
        mark_id = cursor.fetchone()[0]
        cursor.execute('INSERT INTO papersim.settlements (entry_id, classification, outcome_label, '
                       'win_loss, proceeds, pnl_gross, fee_total, pnl_net, source_outcome_id, '
                       'exit_mark_id, confirmed_by, confirmed_at) '
                       'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                       (entry_id, 'EXIT', None, None, Decimal('239.29'), Decimal('-10.71'),
                        Decimal('0'), Decimal('-10.71'), outcome_id, mark_id, 'seed', at(70)))
        cursor.execute('INSERT INTO papersim_private.observed_baseline (observed_at, '
                       'relation_kind, relation_name, source_system_identifier, source_cluster, '
                       'registered_by, registered_run) VALUES (%s,%s,%s,%s,%s,%s,%s)',
                       (at(30), 'table', 'decisions', '7695033081798129054',
                        'legacy_paper_sim_loopback', 'seed', 'seed-run'))
    return entry_id, candidate_id


@NATIVE
def test_update_delete_truncate_rejected_on_every_guarded_table(managed_face):
    owner = connect(OWNER_DSN, autocommit=True)
    app = connect(APP_DSN)
    _seed_every_table(owner, app)
    psycopg = pytest.importorskip('psycopg')
    targets = [('papersim.' + name, 'paper_only') for name in PAPERSIM_TABLES]
    targets += [('papersim_private.observed_baseline', 'paper_only'),
                ('papersim_private.migrations', 'sha256')]
    for relation, column in targets:
        # TRUNCATE needs CASCADE on FK-referenced tables so the statement
        # reaches the BEFORE TRUNCATE triggers instead of being refused by
        # the planner's foreign-key shortcut; the trigger then rejects the
        # mutation on every cascaded table and nothing is truncated.
        for statement in (f'UPDATE {relation} SET {column} = {column}',
                          f'DELETE FROM {relation}',
                          f'TRUNCATE {relation} CASCADE'):
            with pytest.raises(psycopg.errors.DatabaseError, match='papersim_mutation_rejected'):
                owner.execute(statement)
    owner.close()
    app.close()


@NATIVE
def test_duplicate_entry_and_settlement_are_rejected(managed_face):
    psycopg = pytest.importorskip('psycopg')
    owner = connect(OWNER_DSN, autocommit=True)
    app = connect(APP_DSN)
    entry_id, candidate_id = _seed_every_table(owner, app)
    with owner.cursor() as cursor:
        cursor.execute('SELECT stake, price, shares, fee_category, fee_rate, entry_fee, '
                       'fee_source, tier, entered_at FROM papersim.entries WHERE entry_id = %s',
                       (entry_id,))
        stake, price, shares, category, rate, fee, source, tier, entered_at = cursor.fetchone()
        with pytest.raises(psycopg.errors.UniqueViolation):
            cursor.execute('INSERT INTO papersim.entries (candidate_id, stake, price, shares, '
                           'fee_category, fee_rate, entry_fee, fee_source, tier, entered_at) '
                           'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                           (candidate_id, stake, price, shares, category, rate, fee, source,
                            tier, entered_at))
        with pytest.raises(psycopg.errors.UniqueViolation):
            cursor.execute('INSERT INTO papersim.settlements (entry_id, classification, proceeds, '
                           'pnl_gross, pnl_net, confirmed_by, confirmed_at) '
                           'VALUES (%s,%s,%s,%s,%s,%s,%s)',
                           (entry_id, 'EXIT', 0, 0, 0, 'dup', at(80)))
    owner.close()
    app.close()


@NATIVE
def test_legacy_gating_and_settlement_classification_negatives(managed_face):
    psycopg = pytest.importorskip('psycopg')
    owner = connect(OWNER_DSN, autocommit=True)
    app = connect(APP_DSN)
    entry_id, candidate_id = _seed_every_table(owner, app)
    with owner.cursor() as cursor:
        with pytest.raises(psycopg.errors.CheckViolation):  # P3-7 on candidates
            cursor.execute('INSERT INTO papersim.candidates (scan_id, candidate_key, side, '
                           'market_kind, team, model_name, model_version, input_payload, '
                           'gate_report, evaluated_at, conclusion, legacy_source_id) '
                           'VALUES ((SELECT scan_id FROM papersim.candidates WHERE candidate_id=%s),'
                           '%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                           (candidate_id, 'legacy-' + uuid.uuid4().hex[:6], 'YES', 'terminal',
                            't', 'm', 'v', '{}', '{}', at(5), 'REJECTED', '17'))
        with pytest.raises(psycopg.errors.CheckViolation):  # P3-7 on entries
            cursor.execute('INSERT INTO papersim.entries (candidate_id, stake, price, shares, '
                           'fee_category, fee_rate, entry_fee, tier, entered_at, legacy_source_id) '
                           'VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                           (candidate_id, 10, 0.5, 20, 'crypto', 0.07, 0, 't', at(6), '18'))
        with pytest.raises(psycopg.errors.CheckViolation):  # NATURAL without win/loss
            cursor.execute('INSERT INTO papersim.settlements (entry_id, classification, win_loss, '
                           'proceeds, pnl_gross, pnl_net, confirmed_by, confirmed_at) '
                           'VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',
                           (entry_id, 'NATURAL', None, 0, 0, 0, 'x', at(80)))
        with pytest.raises(psycopg.errors.CheckViolation):  # EXIT with win/loss
            cursor.execute('INSERT INTO papersim.settlements (entry_id, classification, win_loss, '
                           'proceeds, pnl_gross, pnl_net, confirmed_by, confirmed_at) '
                           'VALUES (%s,%s,%s,%s,%s,%s,%s,%s)',
                           (entry_id, 'EXIT', 'win', 0, 0, 0, 'x', at(81)))
    owner.close()
    app.close()


@NATIVE
def test_numeric_boundary_negatives_accept_and_reject_correctly(managed_face):
    psycopg = pytest.importorskip('psycopg')
    owner = connect(OWNER_DSN, autocommit=True)
    app = connect(APP_DSN)
    entry_id, candidate_id = _seed_every_table(owner, app)
    rejects = (
        # entries: positive stake, open price interval, finite numbers only
        f'INSERT INTO papersim.entries (candidate_id, stake, price, shares, fee_category, '
        f'fee_rate, entry_fee, tier, entered_at) VALUES ({candidate_id}, 0, 0.5, 2, \'c\', 0.07, '
        f'0, \'t\', \'{at(6).isoformat()}\')',
        f'INSERT INTO papersim.entries (candidate_id, stake, price, shares, fee_category, '
        f'fee_rate, entry_fee, tier, entered_at) VALUES ({candidate_id}, 10, 1, 20, \'c\', 0.07, '
        f'0, \'t\', \'{at(6).isoformat()}\')',
        f'INSERT INTO papersim.entries (candidate_id, stake, price, shares, fee_category, '
        f'fee_rate, entry_fee, tier, entered_at) VALUES ({candidate_id}, 10, 0, 20, \'c\', 0.07, '
        f'0, \'t\', \'{at(6).isoformat()}\')',
        f'INSERT INTO papersim.entries (candidate_id, stake, price, shares, fee_category, '
        f'fee_rate, entry_fee, tier, entered_at) VALUES ({candidate_id}, \'NaN\'::numeric, 0.5, '
        f'20, \'c\', 0.07, 0, \'t\', \'{at(6).isoformat()}\')',
        f'INSERT INTO papersim.entries (candidate_id, stake, price, shares, fee_category, '
        f'fee_rate, entry_fee, tier, entered_at) VALUES ({candidate_id}, \'Infinity\'::numeric, '
        f'0.5, 20, \'c\', 0.07, 0, \'t\', \'{at(6).isoformat()}\')',
        # the three-true boundary columns are structural
        f'INSERT INTO papersim.entries (candidate_id, stake, price, shares, fee_category, '
        f'fee_rate, entry_fee, tier, entered_at, paper_only) VALUES ({candidate_id}, 10, 0.5, 20, '
        f'\'c\', 0.07, 0, \'t\', \'{at(6).isoformat()}\', false)',
        # quotes stay open (0,1); a 0/1 bid is not a fillable quote
        f'INSERT INTO papersim.candidate_price_evidence (evidence_key, candidate_id, '
        f'evidence_role, observed_at, market_ref_kind, market_ref, side, bid, source_kind) '
        f'VALUES (\'ev-{uuid.uuid4().hex[:8]}\', {candidate_id}, \'DECISION\', '
        f'\'{at(5).isoformat()}\', \'market_id\', \'m\', \'YES\', 0, \'x\')',
        f'INSERT INTO papersim.candidate_price_evidence (evidence_key, candidate_id, '
        f'evidence_role, observed_at, market_ref_kind, market_ref, side, last, source_kind) '
        f'VALUES (\'ev-{uuid.uuid4().hex[:8]}\', {candidate_id}, \'DECISION\', '
        f'\'{at(5).isoformat()}\', \'market_id\', \'m\', \'YES\', 1, \'x\')',
    )
    for statement in rejects:
        with pytest.raises(psycopg.errors.CheckViolation):
            owner.execute(statement)
    accepts = (
        # marks use the closed interval [0,1]
        f'INSERT INTO papersim.marks (entry_id, mark_key, marked_at, bid, ask, source_kind) '
        f'VALUES ({entry_id}, \'mk-{uuid.uuid4().hex[:6]}\', \'{at(5).isoformat()}\', 0, 1, '
        f'\'clob_terminal_price\')',
        # CLOSE last prices use the closed interval [0,1]
        f'INSERT INTO papersim.candidate_price_evidence (evidence_key, candidate_id, '
        f'evidence_role, observed_at, market_ref_kind, market_ref, side, last, source_kind) '
        f'VALUES (\'ev-{uuid.uuid4().hex[:8]}\', {candidate_id}, \'CLOSE\', '
        f'\'{at(5).isoformat()}\', \'market_id\', \'m\', \'YES\', 1, \'x\')',
        f'INSERT INTO papersim.candidate_price_evidence (evidence_key, candidate_id, '
        f'evidence_role, observed_at, market_ref_kind, market_ref, side, last, source_kind) '
        f'VALUES (\'ev-{uuid.uuid4().hex[:8]}\', {candidate_id}, \'CLOSE\', '
        f'\'{at(5).isoformat()}\', \'market_id\', \'m\', \'YES\', 0, \'x\')',
    )
    for statement in accepts:
        owner.execute(statement)
    owner.close()
    app.close()


@NATIVE
def test_snapshot_references_must_be_registered_before_the_scan(managed_face):
    store_psycopg = adapter()
    _, app_dsn = managed_face
    app = connect(app_dsn)
    content = b'referenced-by-candidate'
    reference = sha256(content).hexdigest()
    dangling = candidate(candidate_key='dangling-ref',
                         snapshot_refs='["' + reference + '"]')
    submission = store.ScanSubmission(scan=scan_run(), candidates=(dangling,))
    with pytest.raises(store.PapersimStoreError, match='papersim_snapshot_ref_missing'):
        store_psycopg.record_scan(app, submission)
    with app.cursor() as cursor:
        cursor.execute('SELECT count(*) FROM papersim.scan_runs WHERE scan_key = %s',
                       (submission.scan.key(),))
        assert cursor.fetchone()[0] == 0
    owner = connect(OWNER_DSN, autocommit=True)
    with owner.cursor() as cursor:
        cursor.execute('INSERT INTO papersim.snapshots (content_sha256, content, byte_length, '
                       'kind, source, fetched_at, schema_version) VALUES (%s,%s,%s,%s,%s,%s,%s)',
                       (reference, content, len(content), 'book', 'seed', at(1), 1))
    owner.close()
    result = store_psycopg.record_scan(app, submission)
    assert result['inserted'] is True
    app.close()


@NATIVE
def test_single_direction_fk_and_min_evidence_id_decision_rule(managed_face):
    store_psycopg = adapter()
    psycopg = pytest.importorskip('psycopg')
    _, app_dsn = managed_face
    app = connect(app_dsn)
    slug = unique_slug()
    rows = (candidate(candidate_key='two-decisions', market_slug=slug, price_evidence=(
        evidence(observed_at=at(4), market_ref=slug, mid=Decimal('0.50')),
        evidence(observed_at=at(5), market_ref=slug, mid=Decimal('0.70')))),)
    result = store_psycopg.record_scan(app, store.ScanSubmission(scan=scan_run(), candidates=rows))
    candidate_id = result['candidate_ids']['two-decisions']
    first = store_psycopg.decision_time_evidence(app, candidate_id)
    assert first['mid'] == Decimal('0.50')  # smallest evidence_id, not the appended row
    owner = connect(OWNER_DSN, autocommit=True)
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        owner.execute('INSERT INTO papersim.candidate_price_evidence (evidence_key, candidate_id, '
                      'evidence_role, observed_at, market_ref_kind, market_ref, side, '
                      'source_kind) VALUES (%s, 999999999, \'DECISION\', %s, \'market_id\', '
                      '\'m\', \'YES\', \'x\')',
                      ('ev-dangling-' + uuid.uuid4().hex[:6], at(5)))
    owner.close()
    app.close()


# ---------------------------------------------------------------------------
# FX-09L: legacy import DB proofs and settlement cash-ledger proofs
# (design 8.3 items 3-10; the offline dry-run contracts live in
# tests/test_papersim_import_legacy.py)
# ---------------------------------------------------------------------------

LEGACY_DSN = os.environ.get('PAPERSIM_PG_DSN', '')
LEGACY_FACE = pytest.mark.skipif(
    not ENABLED or not LEGACY_DSN,
    reason='the legacy-face proofs need the fixture-loaded throwaway '
           'paper_sim cluster (PAPERSIM_PG_DSN)')
SNAPSHOT_DIR = ROOT / 'docs' / 'paper-sim' / 'ledger-snapshots' / '2026-11-12'
IMPORT_TOOL = ROOT / 'tools' / 'papersim_import_legacy.py'


@pytest.fixture(scope='module')
def importer():
    spec = importlib.util.spec_from_file_location(
        'papersim_import_legacy_native', IMPORT_TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclass annotation resolution
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope='module')
def imported_plan(importer):
    return importer.build_import_plan(importer.load_snapshot(SNAPSHOT_DIR))


@NATIVE
def test_legacy_import_executes_idempotently_and_conserves(
        managed_face, importer, imported_plan):
    _, app_dsn = managed_face
    # Target through the adapter's validated explicit-DSN door.
    store_psycopg = adapter()
    target = store_psycopg.connect_explicit(
        app_dsn, label='PAPERSIM_MIGRATIONS_PG_DSN')
    try:
        first = importer.execute_import(target, imported_plan)
    finally:
        target.close()
    assert first['inserted'] == {'scan_runs': 1, 'candidates': 71, 'entries': 71,
                                 'cash_events': 67, 'market_outcomes': 60,
                                 'settlements': 66}
    owner = connect(OWNER_DSN, autocommit=True)
    with owner.cursor() as cursor:
        cursor.execute('SELECT count(*) FROM papersim.candidates '
                       'WHERE is_legacy AND legacy_source_id IS NOT NULL')
        assert cursor.fetchone()[0] == 71
        cursor.execute('SELECT count(*) FROM papersim.entries WHERE is_legacy')
        assert cursor.fetchone()[0] == 71
        cursor.execute('SELECT count(*) FROM papersim.market_outcomes '
                       "WHERE source_kind = 'legacy_import'")
        assert cursor.fetchone()[0] == 60
        cursor.execute('SELECT count(*) FROM papersim.settlements WHERE is_legacy')
        assert cursor.fetchone()[0] == 66
        # 8.3-4: per-cent conservation against the legacy resolutions.
        cursor.execute('SELECT sum(pnl_gross) FROM papersim.settlements '
                       'WHERE is_legacy')  # the 09S seeds are not legacy rows
        assert cursor.fetchone()[0] == Decimal('3768.33')
        cursor.execute('SELECT e.legacy_source_id, s.pnl_gross, s.fee_total, '
                       's.pnl_net FROM papersim.settlements s '
                       'JOIN papersim.entries e ON e.entry_id = s.entry_id '
                       "WHERE e.legacy_source_id IN ('1','14') "
                       'ORDER BY e.legacy_source_id')
        rows = cursor.fetchall()
        assert [(row[1], row[2], row[3]) for row in rows] == [
            (Decimal('743.79'), Decimal('25.46'), Decimal('718.33')),
            (Decimal('561.41'), Decimal('19.08'), Decimal('542.33'))]
        # 8.3-6: label semantics survive the round trip through SQL.
        cursor.execute('SELECT o.outcome, o.outcome_detail FROM papersim.market_outcomes o '
                       'JOIN papersim.settlements s ON s.source_outcome_id = o.outcome_id '
                       "WHERE s.outcome_label IN ('win','loss') LIMIT 1")
        unknown_label = cursor.fetchone()
        assert unknown_label[0] == 'UNKNOWN'
        assert unknown_label[1] in ('recorded_label=win', 'recorded_label=loss')
        cursor.execute('SELECT count(*) FROM papersim.settlements s '
                       'LEFT JOIN papersim.market_outcomes o '
                       'ON o.outcome_id = s.source_outcome_id '
                       'WHERE s.classification = \'EXIT\' AND s.exit_price IS NOT NULL '
                       'AND o.outcome_id IS NULL')
        assert cursor.fetchone()[0] == 5  # exits never mint market rows
        cursor.execute('SELECT count(*) FROM papersim.settlements s '
                       'JOIN papersim.entries e ON e.entry_id = s.entry_id '
                       "WHERE s.classification = 'VOIDED_REFUND' "
                       'AND s.proceeds = e.stake AND s.pnl_gross = 0 '
                       'AND s.fee_total = 0')
        assert cursor.fetchone()[0] == 4
        # The single INITIAL anchor plus per-settle events exist.
        cursor.execute('SELECT count(*) FROM papersim.bankroll_events '
                       "WHERE event_key = 'legacy:bankroll:initial'")
        assert cursor.fetchone()[0] == 1
        cursor.execute("SELECT count(*) FROM papersim.bankroll_events "
                       "WHERE event_key LIKE 'legacy:settle:%'")
        assert cursor.fetchone()[0] == 66
        # Append-only holds for importer-written rows, not just seeds.
        psycopg = pytest.importorskip('psycopg')
        with pytest.raises(psycopg.errors.DatabaseError,
                           match='papersim_mutation_rejected'):
            owner.execute('UPDATE papersim.settlements SET pnl_net = pnl_net')
    owner.close()
    # Idempotent re-run: nothing new, same mapping (design 7.5).
    target = store_psycopg.connect_explicit(
        app_dsn, label='PAPERSIM_MIGRATIONS_PG_DSN')
    try:
        second = importer.execute_import(target, imported_plan)
    finally:
        target.close()
    assert second['inserted'] == {'scan_runs': 0, 'candidates': 0, 'entries': 0,
                                  'cash_events': 0, 'market_outcomes': 0,
                                  'settlements': 0}
    assert second['scan_id'] == first['scan_id']
    assert second['entry_ids'] == first['entry_ids']
    owner = connect(OWNER_DSN, autocommit=True)
    with owner.cursor() as cursor:
        cursor.execute('SELECT count(*) FROM papersim.settlements WHERE is_legacy')
        assert cursor.fetchone()[0] == 66
    owner.close()


@NATIVE
def test_importer_without_authorization_writes_nothing_on_a_writable_face(
        managed_face, importer, imported_plan, capsys):
    _, app_dsn = managed_face
    owner = connect(OWNER_DSN, autocommit=True)
    with owner.cursor() as cursor:
        cursor.execute('SELECT count(*) FROM papersim.scan_runs WHERE scan_key = %s',
                       (imported_plan.scan_key,))
        before = cursor.fetchone()[0]
    owner.close()
    # The gate refuses BEFORE any connection: a dead port proves it.
    code = importer.main(['--dsn', 'postgresql://paper_sim@127.0.0.1:1/paper_sim'])
    assert code == 2
    assert 'production insertion is not authorized' in capsys.readouterr().err
    owner = connect(OWNER_DSN, autocommit=True)
    with owner.cursor() as cursor:
        cursor.execute('SELECT count(*) FROM papersim.scan_runs WHERE scan_key = %s',
                       (imported_plan.scan_key,))
        assert cursor.fetchone()[0] == before
    owner.close()


@NATIVE
def test_settlement_net_identity_check_rejects_drift(managed_face):
    psycopg = pytest.importorskip('psycopg')
    owner = connect(OWNER_DSN, autocommit=True)
    app = connect(APP_DSN)
    store_psycopg = adapter()
    slug = unique_slug()
    result = store_psycopg.record_scan(app, store.ScanSubmission(
        scan=scan_run(),
        candidates=(candidate(candidate_key='net-check', conclusion='ACCEPTED',
                              market_slug=slug,
                              price_evidence=(evidence(market_ref=slug),),
                              entry=entry()),)))
    with owner.cursor() as cursor:
        cursor.execute('SELECT entry_id FROM papersim.entries WHERE candidate_id = %s',
                       (result['candidate_ids']['net-check'],))
        entry_id = cursor.fetchone()[0]
        # 8.3-5 CHECK proof: pnl_net must equal pnl_gross - fee_total.
        with pytest.raises(psycopg.errors.CheckViolation):
            cursor.execute(
                'INSERT INTO papersim.settlements (entry_id, classification, '
                'win_loss, proceeds, pnl_gross, fee_total, pnl_net, '
                'confirmed_by, confirmed_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                (entry_id, 'NATURAL', 'win', 300, 50, 1, 48, 'x', at(80)))
    owner.close()
    app.close()


@NATIVE
def test_reversal_cash_events_reverse_by_reference_only(managed_face):
    psycopg = pytest.importorskip('psycopg')
    owner = connect(OWNER_DSN, autocommit=True)
    marker = uuid.uuid4().hex[:10]
    with owner.cursor() as cursor:
        cursor.execute('INSERT INTO papersim.bankroll_events (event_key, occurred_at, '
                       'currency, amount, reason, note) VALUES (%s,%s,%s,%s,%s,%s) '
                       'RETURNING event_id',
                       ('reversal-src-' + marker, at(10), 'USD', Decimal('12.34'),
                        'ADJUSTMENT', 'fx09l reversal proof'))
        source_id = cursor.fetchone()[0]
        cursor.execute('INSERT INTO papersim.bankroll_events (event_key, occurred_at, '
                       'currency, amount, reason, reverses_event_id) '
                       'VALUES (%s,%s,%s,%s,%s,%s) RETURNING event_id',
                       ('reversal-of-' + marker, at(11), 'USD', Decimal('-12.34'),
                        'REVERSAL', source_id))
        reversal_id = cursor.fetchone()[0]
        assert reversal_id != source_id
        # A REVERSAL without a reference is structurally refused (5.7).
        with pytest.raises(psycopg.errors.CheckViolation):
            cursor.execute('INSERT INTO papersim.bankroll_events (event_key, '
                           'occurred_at, currency, amount, reason) '
                           'VALUES (%s,%s,%s,%s,%s)',
                           ('reversal-dangling-' + marker, at(12), 'USD',
                            Decimal('-1.00'), 'REVERSAL'))
        # One reversal per reversed event (unique reverses_event_id).
        with pytest.raises(psycopg.errors.UniqueViolation):
            cursor.execute('INSERT INTO papersim.bankroll_events (event_key, '
                           'occurred_at, currency, amount, reason, reverses_event_id) '
                           'VALUES (%s,%s,%s,%s,%s,%s)',
                           ('reversal-dup-' + marker, at(13), 'USD', Decimal('-1.00'),
                            'REVERSAL', source_id))
        cursor.execute('SELECT coalesce(sum(amount), 0) FROM papersim.bankroll_events '
                       'WHERE event_id IN (%s, %s)', (source_id, reversal_id))
        assert cursor.fetchone()[0] == Decimal('0.00')  # reversal nets to zero
    owner.close()


@LEGACY_FACE
def test_register_baseline_appends_observed_evidence_and_stays_private(
        managed_face, importer):
    from polymarket_alpha_lab.papersim import ledger, store_psycopg
    _, app_dsn = managed_face
    legacy_dsn = ledger.papersim_dsn()
    owner = connect(OWNER_DSN, autocommit=True)
    with owner.cursor() as cursor:
        cursor.execute('SELECT count(*) FROM papersim_private.observed_baseline')
        before = cursor.fetchone()[0]
    owner.close()

    def connect_legacy():
        return store_psycopg.connect_legacy_readonly(legacy_dsn)

    owner = connect(OWNER_DSN, autocommit=True)
    try:
        result = importer.register_baseline(
            owner, connect_legacy, registered_by='fx09l-native-proof',
            registered_run='fx09l-run-1')
    finally:
        owner.close()
    assert result['registered'] >= 5
    assert {'decisions', 'resolutions', 'bankroll',
            'model_performance', 'forecast_calibration'} <= set(result['relations'])
    owner = connect(OWNER_DSN, autocommit=True)
    with owner.cursor() as cursor:
        cursor.execute('SELECT count(*) FROM papersim_private.observed_baseline')
        after = cursor.fetchone()[0]
        assert after == before + result['registered']
        # Select THIS run's rows: the 09S seed rows carry fixed later
        # timestamps and no row counts, so observed_at ordering must not
        # decide which observation is inspected.
        cursor.execute('SELECT row_count FROM papersim_private.observed_baseline '
                       "WHERE relation_name = 'decisions' AND registered_run = %s",
                       ('fx09l-run-1',))
        assert cursor.fetchone()[0] == 71  # fixture-loaded throwaway face
        cursor.execute('SELECT definition_md5 FROM papersim_private.observed_baseline '
                       "WHERE relation_name = 'model_performance' "
                       "AND registered_run = %s", ('fx09l-run-1',))
        assert cursor.fetchone()[0] is not None
    owner.close()
    # The evidence table stays invisible to the application role.
    app = connect(app_dsn)
    psycopg = pytest.importorskip('psycopg')
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with app.cursor() as cursor:
            cursor.execute('SELECT count(*) FROM papersim_private.observed_baseline')
    app.close()


@LEGACY_FACE
def test_legacy_face_is_unchanged_by_import_and_registration(
        managed_face, importer, imported_plan):
    from polymarket_alpha_lab.papersim import ledger
    store_psycopg = adapter()
    _, app_dsn = managed_face

    def fingerprint(connection):
        with connection.cursor() as cursor:
            cursor.execute('SELECT c.relname, c.relkind FROM pg_class c '
                           'JOIN pg_namespace n ON n.oid = c.relnamespace '
                           "WHERE n.nspname = 'public' AND c.relkind IN ('r','v') "
                           "AND c.relname NOT LIKE 'pg_%' ORDER BY c.relname")
            relations = cursor.fetchall()
            parts = []
            for name, kind in relations:
                if kind == 'v':
                    definition = cursor.execute(
                        'SELECT pg_get_viewdef(%s::regclass, true)', (name,)
                    ).fetchone()[0]
                    parts.append((name, kind, md5(
                        definition.encode('utf-8')).hexdigest()))
                else:
                    count = cursor.execute(
                        'SELECT count(*) FROM public.' + name).fetchone()[0]
                    parts.append((name, kind, int(count)))
        return tuple(parts)

    legacy_dsn = ledger.papersim_dsn()
    read_only = store_psycopg.connect_legacy_readonly(legacy_dsn)
    before = fingerprint(read_only)
    read_only.close()
    # A full import dry run (offline files), an authorized execution against
    # the MANAGED face and a read-only re-observation pass through; the
    # legacy face itself is only ever read (8.3 item 8).
    assert importer.main([]) == 0
    target = store_psycopg.connect_explicit(
        app_dsn, label='PAPERSIM_MIGRATIONS_PG_DSN')
    try:
        importer.execute_import(target, imported_plan)
    finally:
        target.close()
    read_only = store_psycopg.connect_legacy_readonly(legacy_dsn)
    after = fingerprint(read_only)
    read_only.close()
    assert after == before
