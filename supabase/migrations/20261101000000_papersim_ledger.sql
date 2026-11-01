-- WP-P1 W4: paper-sim ledger DDL mirrored from the live paper_sim
-- evidence cluster (loopback 127.0.0.1:55432, pulled 2026-11-01).
-- Mirrored verbatim: decisions / resolutions / bankroll tables and the
-- FIXED model_performance / forecast_calibration views (exits separated
-- from W/L; forecast calibration judged on natural resolutions only).
-- Documented repo-convention delta versus the live cluster: the
-- paper_only / report_only / readonly boundary columns on decisions,
-- matching the repo paper_trade migration style. This schema is paper
-- evidence storage only; it grants no order, account or execution
-- authorization.

create table public.decisions (
  id bigserial primary key,
  ts timestamptz default now(),
  market_id text,
  question text,
  side text,
  price numeric,
  shares numeric,
  stake numeric,
  fair_low numeric,
  fair_high numeric,
  spot numeric,
  vol numeric,
  horizon_days numeric,
  sizing text,
  reason text,
  team text default 'crypto_eth'::text,
  model_prediction numeric,
  market_type text,
  paper_only boolean not null default true check (paper_only is true),
  report_only boolean not null default true check (report_only is true),
  readonly boolean not null default true check (readonly is true)
);

create table public.resolutions (
  market_id text primary key,
  ts timestamptz default now(),
  outcome text,
  payoff numeric,
  pnl numeric,
  evidence text
);

create table public.bankroll (
  ts timestamptz default now(),
  cash numeric,
  deployed numeric,
  note text
);

create view public.model_performance as
select d.market_type,
       count(*) as total_settled,
       sum(case when r.outcome = any (array['YES'::text, 'NO'::text, 'YES-basket'::text]) and r.pnl > 0::numeric then 1 else 0 end) as wins,
       sum(case when r.outcome = any (array['YES'::text, 'NO'::text, 'YES-basket'::text]) and r.pnl <= 0::numeric then 1 else 0 end) as losses,
       sum(case when r.outcome = 'EXITED'::text then 1 else 0 end) as exits,
       round(100.0 * sum(case when r.outcome = any (array['YES'::text, 'NO'::text, 'YES-basket'::text]) and r.pnl > 0::numeric then 1 else 0 end)::numeric
             / nullif(sum(case when r.outcome = any (array['YES'::text, 'NO'::text, 'YES-basket'::text]) then 1 else 0 end), 0)::numeric, 1) as win_rate_pct,
       round(sum(r.pnl), 2) as total_pnl,
       round(avg(d.model_prediction), 3) as avg_model_prediction
from public.decisions d
  join public.resolutions r on r.market_id = d.market_id
group by d.market_type;

create view public.forecast_calibration as
select d.market_type,
       count(*) as n,
       sum(case when (d.side = any (array['YES'::text, 'YES-basket'::text])) and r.outcome = d.side
                 or d.side = 'NO'::text and r.outcome = 'NO'::text
                 or d.side = 'NO-basket'::text and r.outcome = 'NO'::text
                then 1 else 0 end) as forecast_hits,
       round(avg(d.model_prediction), 3) as avg_forecast,
       round(avg(case when (d.side = any (array['YES'::text, 'YES-basket'::text])) and r.outcome = d.side
                       or d.side = 'NO'::text and r.outcome = 'NO'::text
                  then d.model_prediction
                  else 1::numeric - d.model_prediction end), 3) as avg_prob_of_realized
from public.decisions d
  join public.resolutions r on r.market_id = d.market_id
where r.outcome = any (array['YES'::text, 'NO'::text, 'YES-basket'::text])
group by d.market_type;
