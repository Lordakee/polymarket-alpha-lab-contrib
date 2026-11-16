-- Papersim M2 closed-loop operations schema (S0, M2 plan sections 3.1,
-- 3.2 and 5.3): the three operation tables the plan names (command run
-- events, candidate marks, queue control events), the daily bankroll
-- identity check table, and the nullable unique scan_runs.operation_key
-- scheduling link. Same invariants as the M1 core migration: insert-only
-- (append-only triggers below), three-true paper boundary columns on every
-- new table, explicit pal_app grants. Paper evidence storage only; this
-- schema grants no order, account or execution authorization.
-- Drift must fail loudly: no IF NOT EXISTS, published M1 bytes untouched.
begin;

-- Scheduling and run receipts (plan section 3.1 command_run_events): one
-- row per attempt phase; first errors and every attempt are preserved as
-- appended history and never overwritten by a later attempt.
create table papersim.command_run_events (
  run_event_id   bigint generated always as identity primary key,
  run_event_key  text not null unique,
  operation_key  text not null,
  attempt        integer not null check (attempt >= 1),
  phase          text not null
    check (phase in ('STARTED','PREPARED','SUCCEEDED','FAILED','RECOVERY_READ')),
  command        text not null,
  queue_id       text,
  scheduled_for  timestamptz check (scheduled_for is null or isfinite(scheduled_for)),
  occurred_at    timestamptz not null check (isfinite(occurred_at)),
  code_commit    text check (code_commit is null or code_commit ~ '^[0-9a-f]{40}$'),
  config_digest  text check (config_digest is null or config_digest ~ '^[a-f0-9]{64}$'),
  input_evidence jsonb not null default '[]'::jsonb,
  output_evidence jsonb not null default '[]'::jsonb,
  error_code     text,
  scan_id        bigint references papersim.scan_runs(scan_id),
  paper_only  boolean not null default true check (paper_only is true),
  report_only boolean not null default true check (report_only is true),
  readonly    boolean not null default true check (readonly is true)
);
create index command_run_events_operation_idx
    on papersim.command_run_events(operation_key, occurred_at);

-- Periodic and close marks for EVERY candidate (plan section 3.1
-- candidate_marks): rejected and construction-failed candidates keep their
-- marks because scoring must not depend on entries. Value columns use the
-- CLOSED interval [0,1] like M1 marks: terminal 0/1 prices are legal mark
-- states, while executable quote evidence stays open-interval in
-- candidate_price_evidence (Gamma terminal 0/1 is a reference last here,
-- never a fillable quote). At most one CLOSE row exists per candidate.
create table papersim.candidate_marks (
  candidate_mark_id bigint generated always as identity primary key,
  candidate_mark_key text not null unique,
  candidate_id   bigint not null references papersim.candidates(candidate_id),
  sampling_kind  text not null check (sampling_kind in ('PERIODIC','CLOSE')),
  observed_at    timestamptz not null check (isfinite(observed_at)),
  market_ref_kind text not null
    check (market_ref_kind in ('condition_id','market_id','token_id','market_slug')),
  market_ref     text not null,
  token_ref      text,
  side           text not null
    check (side in ('YES','NO','YES-basket','NO-basket')),
  bid numeric check (bid is null or (bid >= 0 and bid <= 1 and bid < 'Infinity'::numeric)),
  ask numeric check (ask is null or (ask >= 0 and ask <= 1 and ask < 'Infinity'::numeric)),
  mid numeric check (mid is null or (mid >= 0 and mid <= 1 and mid < 'Infinity'::numeric)),
  last numeric check (last is null or (last >= 0 and last <= 1 and last < 'Infinity'::numeric)),
  source_kind    text not null,
  source_ref     text,
  snapshot_sha256 text check (snapshot_sha256 is null or snapshot_sha256 ~ '^[a-f0-9]{64}$'),
  paper_only  boolean not null default true check (paper_only is true),
  report_only boolean not null default true check (report_only is true),
  readonly    boolean not null default true check (readonly is true),
  check (bid is null or ask is null or bid <= ask),
  check (last is not null or mid is not null or bid is not null or ask is not null)
);
create index candidate_marks_candidate_idx
    on papersim.candidate_marks(candidate_id, observed_at);
create unique index candidate_marks_one_close_per_candidate_idx
    on papersim.candidate_marks(candidate_id) where sampling_kind = 'CLOSE';

-- Queue control evidence (plan sections 3.1 and 3.8 queue_control_events):
-- the FX-17/general pause latch. Pause rows are appended evidence; a
-- restart never clears them and only a reviewed RESUME row may follow one.
create table papersim.queue_control_events (
  control_event_id bigint generated always as identity primary key,
  control_key    text not null unique,
  queue_id       text not null,
  control_kind   text not null check (control_kind in ('PAUSE','RESUME')),
  rule           text not null,
  rule_version   text not null,
  metrics        jsonb not null default '{}'::jsonb,
  evidence_watermark jsonb not null default '{}'::jsonb,
  reason         text,
  reviewed_by    text,
  observed_at    timestamptz not null check (isfinite(observed_at)),
  scan_id        bigint references papersim.scan_runs(scan_id),
  paper_only  boolean not null default true check (paper_only is true),
  report_only boolean not null default true check (report_only is true),
  readonly    boolean not null default true check (readonly is true),
  check (control_kind = 'PAUSE' or reviewed_by is not null)
);
create index queue_control_events_queue_idx
    on papersim.queue_control_events(queue_id, observed_at);

-- Daily cash identity check evidence (plan section 5.3): every component
-- (event cash, base funds, open principal, realized net PnL, open entry
-- fees) is recomputed independently inside one read transaction; rows are
-- check receipts, never adjustments, and never repair the identity.
create table papersim.bankroll_checks (
  check_id     bigint generated always as identity primary key,
  check_key    text not null unique,
  as_of        timestamptz not null check (isfinite(as_of)),
  queue_id     text,
  event_watermark bigint not null check (event_watermark >= 0),
  cash_total numeric not null
    check (cash_total > '-Infinity'::numeric and cash_total < 'Infinity'::numeric),
  deployed_total numeric not null
    check (deployed_total >= 0 and deployed_total < 'Infinity'::numeric),
  initial_and_adjustments numeric not null
    check (initial_and_adjustments > '-Infinity'::numeric
           and initial_and_adjustments < 'Infinity'::numeric),
  realized_net numeric not null
    check (realized_net > '-Infinity'::numeric and realized_net < 'Infinity'::numeric),
  open_entry_fees numeric not null
    check (open_entry_fees >= 0 and open_entry_fees < 'Infinity'::numeric),
  identity_difference numeric not null
    check (identity_difference > '-Infinity'::numeric
           and identity_difference < 'Infinity'::numeric),
  tolerance numeric not null
    check (tolerance >= 0 and tolerance < 'Infinity'::numeric),
  passed boolean not null,
  code_commit text not null check (code_commit ~ '^[0-9a-f]{40}$'),
  report_digest text check (report_digest is null or report_digest ~ '^[a-f0-9]{64}$'),
  paper_only  boolean not null default true check (paper_only is true),
  report_only boolean not null default true check (report_only is true),
  readonly    boolean not null default true check (readonly is true)
);
create index bankroll_checks_as_of_idx on papersim.bankroll_checks(as_of);

-- Stable scheduling identity link (plan section 3.1): nullable for all M1
-- rows and callers, unique so one scheduled task cannot enter twice.
alter table papersim.scan_runs add column operation_key text;
create unique index scan_runs_operation_key_idx on papersim.scan_runs(operation_key);

-- The same uniform append-only proof surface as the M1 core tables.
create trigger immutable_command_run_events before update or delete on papersim.command_run_events
  for each row execute function papersim_private.reject_mutation();
create trigger immutable_candidate_marks before update or delete on papersim.candidate_marks
  for each row execute function papersim_private.reject_mutation();
create trigger immutable_queue_control_events before update or delete on papersim.queue_control_events
  for each row execute function papersim_private.reject_mutation();
create trigger immutable_bankroll_checks before update or delete on papersim.bankroll_checks
  for each row execute function papersim_private.reject_mutation();
create trigger no_truncate_command_run_events before truncate on papersim.command_run_events
  for each statement execute function papersim_private.reject_mutation();
create trigger no_truncate_candidate_marks before truncate on papersim.candidate_marks
  for each statement execute function papersim_private.reject_mutation();
create trigger no_truncate_queue_control_events before truncate on papersim.queue_control_events
  for each statement execute function papersim_private.reject_mutation();
create trigger no_truncate_bankroll_checks before truncate on papersim.bankroll_checks
  for each statement execute function papersim_private.reject_mutation();

-- Explicit grants for the application role on the new objects only (same
-- style as the M1 core grant block; the V1 post-migration GRANTS never
-- touch this schema, so they can neither grant nor revoke these rights).
grant select, insert on papersim.command_run_events, papersim.candidate_marks,
    papersim.queue_control_events, papersim.bankroll_checks to pal_app;
grant usage, select on all sequences in schema papersim to pal_app;
commit;
