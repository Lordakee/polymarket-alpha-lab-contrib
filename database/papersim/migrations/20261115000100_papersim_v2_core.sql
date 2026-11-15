-- Papersim v2 core schema (FX-09S, design 2026-11-15 v2 sections 4 and 5):
-- seven ledger tables plus the two scoring-link tables. All insert-only
-- (append-only triggers below), paper evidence storage only; no order,
-- account or execution authorization is granted by this schema.
-- P1-1 (b): market_outcomes has NO superseded_by column; versioning is the
-- observed_at recursion (later observation wins, tie-break outcome_id DESC).
-- P3-8: candidates has NO decision_evidence_id pointer; the decision-time
-- observation of a candidate is the DECISION row with the smallest
-- evidence_id. The only cross-table FK between candidates and evidence is
-- the single direction candidate_price_evidence.candidate_id.
begin;
create table papersim.scan_runs (
  scan_id       bigint generated always as identity primary key,
  scan_key      text not null unique,
  scan_payload_sha256 text not null check (scan_payload_sha256 ~ '^[a-f0-9]{64}$'),
  team          text not null,
  started_at    timestamptz not null check (isfinite(started_at)),
  finished_at   timestamptz not null check (isfinite(finished_at)),
  code_commit   text check (code_commit is null or code_commit ~ '^[0-9a-f]{40}$'),
  schema_version integer not null,
  gate_version  text not null,
  operator      text not null,
  params        jsonb not null,
  is_legacy     boolean not null default false,
  paper_only  boolean not null default true check (paper_only is true),
  report_only boolean not null default true check (report_only is true),
  readonly    boolean not null default true check (readonly is true),
  check (started_at <= finished_at),
  check (is_legacy or code_commit is not null)
);

create table papersim.snapshots (
  content_sha256 text primary key check (content_sha256 ~ '^[a-f0-9]{64}$'),
  content        bytea not null,
  byte_length    bigint not null check (byte_length > 0),
  kind           text not null,
  source         text not null,
  fetched_at     timestamptz not null check (isfinite(fetched_at)),
  schema_version integer not null,
  paper_only  boolean not null default true check (paper_only is true),
  report_only boolean not null default true check (report_only is true),
  readonly    boolean not null default true check (readonly is true),
  check (octet_length(content) = byte_length),
  check (encode(sha256(content), 'hex') = content_sha256)
);

-- Construction-failed candidates may have all market binding columns NULL
-- (construction never reached the binding step); scoring then treats them
-- as INSUFFICIENT. NULL is never silently a market.
create table papersim.candidates (
  candidate_id  bigint generated always as identity primary key,
  scan_id       bigint not null references papersim.scan_runs(scan_id),
  candidate_key text not null,
  legacy_source_id text,
  condition_id  text,
  market_id     text,
  market_slug   text,
  yes_token_id  text,
  no_token_id   text,
  side          text not null check (side in ('YES','NO','YES-basket','NO-basket')),
  market_kind   text not null check (market_kind in ('terminal','touch','other')),
  market_type   text,
  team          text not null,
  binding_version integer not null default 1,
  model_name    text not null,
  model_version text not null,
  median_probability numeric check (median_probability is null
      or (median_probability >= 0 and median_probability <= 1)),
  variant_quotes jsonb not null default '[]'::jsonb,
  input_payload jsonb not null,
  snapshot_refs jsonb not null default '[]'::jsonb,
  order_book jsonb,
  book_fetched_at timestamptz check (book_fetched_at is null or isfinite(book_fetched_at)),
  check ((order_book is null) = (book_fetched_at is null)),
  conclusion     text not null check (conclusion in ('ACCEPTED','REJECTED','CONSTRUCTION_FAILED')),
  gate_report    jsonb not null,
  rejection_reasons jsonb not null default '[]'::jsonb,
  evaluated_at   timestamptz not null check (isfinite(evaluated_at)),
  is_legacy boolean not null default false,
  paper_only  boolean not null default true check (paper_only is true),
  report_only boolean not null default true check (report_only is true),
  readonly    boolean not null default true check (readonly is true),
  check (is_legacy or legacy_source_id is null),
  unique (scan_id, candidate_key)
);
create index candidates_scan_idx on papersim.candidates(scan_id);
create index candidates_market_idx on papersim.candidates(condition_id, market_id, market_slug);

-- Built AFTER candidates: the only FK is the single direction below.
create table papersim.candidate_price_evidence (
  evidence_id     bigint generated always as identity primary key,
  evidence_key    text not null unique,
  candidate_id    bigint not null references papersim.candidates(candidate_id),
  evidence_role   text not null check (evidence_role in ('DECISION','CLOSE')),
  observed_at     timestamptz not null check (isfinite(observed_at)),
  model_probability numeric check (model_probability is null
      or (model_probability >= 0 and model_probability <= 1)),
  market_ref_kind text not null
      check (market_ref_kind in ('condition_id','market_id','token_id','market_slug')),
  market_ref      text not null,
  token_ref       text,
  side            text not null
      check (side in ('YES','NO','YES-basket','NO-basket')),
  bid numeric check (bid is null or (bid > 0 and bid < 1)),
  ask numeric check (ask is null or (ask > 0 and ask < 1)),
  mid numeric check (mid is null or (mid > 0 and mid < 1)),
  last numeric,
  book_sha256     text check (book_sha256 is null or book_sha256 ~ '^[a-f0-9]{64}$'),
  snapshot_sha256 text check (snapshot_sha256 is null or snapshot_sha256 ~ '^[a-f0-9]{64}$'),
  source_kind     text not null,
  source_ref      text,
  paper_only  boolean not null default true check (paper_only is true),
  report_only boolean not null default true check (report_only is true),
  readonly    boolean not null default true check (readonly is true),
  check (bid is null or ask is null or bid <= ask),
  check (mid is null or bid is null or ask is null or mid between bid and ask),
  check (last is null
         or (evidence_role = 'CLOSE'    and last >= 0 and last <= 1)
         or (evidence_role = 'DECISION' and last >  0 and last <  1)),
  check (evidence_role <> 'CLOSE' or (observed_at is not null and last is not null
          or mid is not null or bid is not null or ask is not null))
);
create index candidate_price_evidence_candidate_idx
    on papersim.candidate_price_evidence(candidate_id, evidence_role, observed_at);

create table papersim.market_outcomes (
  outcome_id     bigint generated always as identity primary key,
  evidence_key   text not null unique,
  condition_id   text,
  market_id      text,
  market_slug    text,
  yes_token_id   text,
  no_token_id    text,
  outcome        text not null
    check (outcome in ('YES','NO','YES-basket','VOIDED','UNKNOWN')),
  outcome_detail text,
  confirmed_at   timestamptz check (confirmed_at is null or isfinite(confirmed_at)),
  observed_at    timestamptz not null check (isfinite(observed_at)),
  source_kind    text not null
    check (source_kind in ('gamma_close','clob_terminal_price','data_api_resolution',
                           'operator_attestation','legacy_import')),
  source_ref     text,
  source_snapshot_sha256 text check (source_snapshot_sha256 is null
                                     or source_snapshot_sha256 ~ '^[a-f0-9]{64}$'),
  paper_only  boolean not null default true check (paper_only is true),
  report_only boolean not null default true check (report_only is true),
  readonly    boolean not null default true check (readonly is true),
  check (coalesce(condition_id, market_id, market_slug) is not null),
  check (outcome <> 'UNKNOWN' or confirmed_at is null)
);
create index market_outcomes_condition_idx on papersim.market_outcomes(condition_id);
create index market_outcomes_market_idx    on papersim.market_outcomes(market_id);
create index market_outcomes_slug_idx      on papersim.market_outcomes(market_slug);
create index market_outcomes_observed_idx  on papersim.market_outcomes(observed_at);

create table papersim.entries (
  entry_id     bigint generated always as identity primary key,
  candidate_id bigint not null unique references papersim.candidates(candidate_id),
  legacy_source_id text,
  stake numeric not null check (stake > 0 and stake < 'Infinity'::numeric),
  price numeric not null check (price > 0 and price < 1),
  shares numeric not null check (shares > 0 and shares < 'Infinity'::numeric),
  fee_category text not null,
  fee_rate  numeric not null check (fee_rate >= 0 and fee_rate < 'Infinity'::numeric),
  entry_fee numeric not null check (entry_fee >= 0 and entry_fee < 'Infinity'::numeric),
  fee_source text not null default 'schedule' check (fee_source in ('schedule','estimated')),
  tier text not null,
  entered_at timestamptz not null check (isfinite(entered_at)),
  is_legacy boolean not null default false,
  paper_only  boolean not null default true check (paper_only is true),
  report_only boolean not null default true check (report_only is true),
  readonly    boolean not null default true check (readonly is true),
  check (is_legacy or legacy_source_id is null),
  check (abs(shares * price - stake) < 0.01)
);

-- Mark values use the CLOSED interval [0,1] (design P3-10): a mark is the
-- market price of the held direction and 0/1 extremes are legal near
-- settlement, mirroring settle_exit's exit_price; the quote columns of
-- candidate_price_evidence stay OPEN (0/1 quotes are not fillable).
create table papersim.marks (
  mark_id   bigint generated always as identity primary key,
  entry_id  bigint not null references papersim.entries(entry_id),
  mark_key  text not null unique,
  marked_at timestamptz not null check (isfinite(marked_at)),
  bid numeric check (bid is null or (bid >= 0 and bid <= 1 and bid < 'Infinity'::numeric)),
  ask numeric check (ask is null or (ask >= 0 and ask <= 1 and ask < 'Infinity'::numeric)),
  mid numeric check (mid is null or (mid >= 0 and mid <= 1 and mid < 'Infinity'::numeric)),
  is_close  boolean not null default false,
  source_kind text not null,
  source_ref text,
  paper_only  boolean not null default true check (paper_only is true),
  report_only boolean not null default true check (report_only is true),
  readonly    boolean not null default true check (readonly is true),
  check (bid is null or ask is null or bid <= ask)
);
create unique index marks_one_close_per_entry_idx on papersim.marks(entry_id) where is_close;

create table papersim.settlements (
  settlement_id bigint generated always as identity primary key,
  entry_id      bigint not null unique references papersim.entries(entry_id),
  classification text not null check (classification in ('NATURAL','EXIT','VOIDED_REFUND')),
  outcome_label  text,
  win_loss      text check (win_loss is null or win_loss in ('win','loss')),
  exit_price    numeric check (exit_price is null or (exit_price >= 0 and exit_price <= 1)),
  proceeds numeric not null check (proceeds >= 0 and proceeds < 'Infinity'::numeric),
  pnl_gross numeric not null check (pnl_gross > '-Infinity'::numeric and pnl_gross < 'Infinity'::numeric),
  fee_total numeric not null default 0 check (fee_total >= 0 and fee_total < 'Infinity'::numeric),
  fee_source text not null default 'schedule' check (fee_source in ('schedule','estimated')),
  pnl_net numeric not null check (pnl_net > '-Infinity'::numeric and pnl_net < 'Infinity'::numeric),
  check (pnl_net = pnl_gross - fee_total),
  check ((classification = 'NATURAL') = (win_loss is not null)),
  source_outcome_id bigint references papersim.market_outcomes(outcome_id),
  exit_mark_id bigint references papersim.marks(mark_id),
  evidence text,
  confirmed_by text not null,
  confirmed_at timestamptz not null check (isfinite(confirmed_at)),
  is_legacy boolean not null default false,
  paper_only  boolean not null default true check (paper_only is true),
  report_only boolean not null default true check (report_only is true),
  readonly    boolean not null default true check (readonly is true)
);

create table papersim.bankroll_events (
  event_id  bigint generated always as identity primary key,
  event_key text not null unique,
  occurred_at timestamptz not null check (isfinite(occurred_at)),
  currency  text not null default 'USD',
  amount numeric not null check (amount > '-Infinity'::numeric and amount < 'Infinity'::numeric),
  reason text not null check (reason in ('INITIAL','SCAN_ENTRY','SETTLE_NATURAL','SETTLE_EXIT',
        'VOIDED_REFUND','FEE','ADJUSTMENT','REVERSAL','LEGACY_IMPORT')),
  entry_id bigint references papersim.entries(entry_id),
  scan_id  bigint references papersim.scan_runs(scan_id),
  reverses_event_id bigint unique references papersim.bankroll_events(event_id),
  note text,
  is_legacy boolean not null default false,
  paper_only  boolean not null default true check (paper_only is true),
  report_only boolean not null default true check (report_only is true),
  readonly    boolean not null default true check (readonly is true),
  check (reason <> 'REVERSAL' or reverses_event_id is not null)
);
create index bankroll_events_entry_idx on papersim.bankroll_events(entry_id);

-- Uniform append-only proof surface: every business table rejects
-- UPDATE/DELETE (row triggers) and TRUNCATE (statement triggers).
create trigger immutable_scan_runs before update or delete on papersim.scan_runs
  for each row execute function papersim_private.reject_mutation();
create trigger immutable_snapshots before update or delete on papersim.snapshots
  for each row execute function papersim_private.reject_mutation();
create trigger immutable_candidates before update or delete on papersim.candidates
  for each row execute function papersim_private.reject_mutation();
create trigger immutable_candidate_price_evidence before update or delete on papersim.candidate_price_evidence
  for each row execute function papersim_private.reject_mutation();
create trigger immutable_market_outcomes before update or delete on papersim.market_outcomes
  for each row execute function papersim_private.reject_mutation();
create trigger immutable_entries before update or delete on papersim.entries
  for each row execute function papersim_private.reject_mutation();
create trigger immutable_marks before update or delete on papersim.marks
  for each row execute function papersim_private.reject_mutation();
create trigger immutable_settlements before update or delete on papersim.settlements
  for each row execute function papersim_private.reject_mutation();
create trigger immutable_bankroll_events before update or delete on papersim.bankroll_events
  for each row execute function papersim_private.reject_mutation();
create trigger no_truncate_scan_runs before truncate on papersim.scan_runs
  for each statement execute function papersim_private.reject_mutation();
create trigger no_truncate_snapshots before truncate on papersim.snapshots
  for each statement execute function papersim_private.reject_mutation();
create trigger no_truncate_candidates before truncate on papersim.candidates
  for each statement execute function papersim_private.reject_mutation();
create trigger no_truncate_candidate_price_evidence before truncate on papersim.candidate_price_evidence
  for each statement execute function papersim_private.reject_mutation();
create trigger no_truncate_market_outcomes before truncate on papersim.market_outcomes
  for each statement execute function papersim_private.reject_mutation();
create trigger no_truncate_entries before truncate on papersim.entries
  for each statement execute function papersim_private.reject_mutation();
create trigger no_truncate_marks before truncate on papersim.marks
  for each statement execute function papersim_private.reject_mutation();
create trigger no_truncate_settlements before truncate on papersim.settlements
  for each statement execute function papersim_private.reject_mutation();
create trigger no_truncate_bankroll_events before truncate on papersim.bankroll_events
  for each statement execute function papersim_private.reject_mutation();

-- Explicit grants for the application role only (the V1 post-migration
-- GRANTS cover public/research_capture and never touch this schema, so it
-- can neither grant nor revoke these rights later).
grant select, insert on all tables in schema papersim to pal_app;
grant usage, select on all sequences in schema papersim to pal_app;
commit;
