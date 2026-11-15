-- Papersim managed bootstrap (FX-09S, design 2026-11-15 v2 section 2.4):
-- creates the dedicated papersim schemas, the papersim-private migration
-- ledger and the observed-baseline evidence table. Paper evidence storage
-- only; this schema grants no order, account or execution authorization.
-- Apply ONCE through the papersim catalog applier; no application
-- auto-migration, no IF NOT EXISTS (drift must fail loudly).
begin;
create schema papersim;
create schema papersim_private;
revoke all on schema papersim, papersim_private from public;

create table papersim_private.migrations (
  name text primary key,
  sha256 text not null check (sha256 ~ '^[a-f0-9]{64}$'),
  applied_at timestamptz not null default clock_timestamp()
);

-- Observed evidence of the LEGACY live paper_sim cluster, registered by a
-- dedicated baseline run (design section 2.5). These rows are observation
-- receipts, never applied-migration receipts; unknown provenance stays NULL
-- (legacy_created_at and legacy_operator are unknown as a pair).
create table papersim_private.observed_baseline (
  observed_at timestamptz not null check (isfinite(observed_at)),
  relation_kind text not null,
  relation_name text not null,
  definition_md5 text,
  row_count bigint,
  source_system_identifier text not null,
  source_cluster text not null,
  legacy_created_at timestamptz check (legacy_created_at is null or isfinite(legacy_created_at)),
  legacy_operator text,
  registered_by text not null,
  registered_run text not null,
  paper_only boolean not null default true check (paper_only is true),
  report_only boolean not null default true check (report_only is true),
  readonly boolean not null default true check (readonly is true),
  check ((legacy_created_at is null) = (legacy_operator is null))
);

create function papersim_private.reject_mutation() returns trigger
language plpgsql set search_path = pg_catalog as $$
begin
  raise exception 'papersim_mutation_rejected';
end $$;

-- Row triggers prevent update/delete, including owner mistakes. Statement
-- triggers also prevent TRUNCATE. A superuser/owner can still disable them.
create trigger immutable_papersim_migrations before update or delete on papersim_private.migrations
  for each row execute function papersim_private.reject_mutation();
create trigger no_truncate_papersim_migrations before truncate on papersim_private.migrations
  for each statement execute function papersim_private.reject_mutation();
create trigger immutable_papersim_observed_baseline before update or delete on papersim_private.observed_baseline
  for each row execute function papersim_private.reject_mutation();
create trigger no_truncate_papersim_observed_baseline before truncate on papersim_private.observed_baseline
  for each statement execute function papersim_private.reject_mutation();

-- The application role sees the business schema only: papersim_private
-- (ledger and observed baseline) stays invisible to pal_app.
grant usage on schema papersim to pal_app;
comment on schema papersim is 'Project-private native PostgreSQL paper-simulation evidence; paper-only, not execution authorization.';
comment on schema papersim_private is 'Papersim migration ledger and observed-baseline evidence; owner-managed, not application-visible.';
commit;
