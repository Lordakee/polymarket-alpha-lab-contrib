-- WP-P4 / P4-0a: allocate each market resolution to decisions by shares.
-- Research/paper evidence only. This file is NOT applied by the shadow study.
-- Keep the original migration and ledger.ddl() as immutable schema history.
-- Counts, win/loss classification and average prediction remain decision-level;
-- only PnL attribution changes. Partition by market BEFORE grouping by type.
-- Do not round individual allocations: market 3866000's 1305.20 must survive
-- the two-entry split in full. Round only the final market-type aggregate.
-- Missing/negative/nonfinite shares or an all-zero denominator cannot support
-- proportional attribution. Return NULL for the affected type's total_pnl
-- rather than silently omitting an unknown amount or inventing equal weights.
create or replace view public.model_performance as
with weighted_decisions as (
    select d.*,
           sum(d.shares) over (partition by d.market_id) as market_shares,
           bool_and(coalesce(d.shares >= 0 and d.shares < 'Infinity'::numeric, false))
               over (partition by d.market_id) as valid_shares
    from public.decisions d
), allocated as (
    select d.market_type, d.model_prediction, r.outcome, r.pnl,
           case when d.valid_shares and d.market_shares > 0
                then r.pnl * d.shares / d.market_shares
                else null::numeric end as allocated_pnl
    from weighted_decisions d
    join public.resolutions r on r.market_id = d.market_id
)
select market_type,
       count(*) as total_settled,
       sum(case when outcome = any (array['YES'::text, 'NO'::text, 'YES-basket'::text]) and pnl > 0::numeric then 1 else 0 end) as wins,
       sum(case when outcome = any (array['YES'::text, 'NO'::text, 'YES-basket'::text]) and pnl <= 0::numeric then 1 else 0 end) as losses,
       sum(case when outcome = 'EXITED'::text then 1 else 0 end) as exits,
       round(100.0 * sum(case when outcome = any (array['YES'::text, 'NO'::text, 'YES-basket'::text]) and pnl > 0::numeric then 1 else 0 end)::numeric
             / nullif(sum(case when outcome = any (array['YES'::text, 'NO'::text, 'YES-basket'::text]) then 1 else 0 end), 0)::numeric, 1) as win_rate_pct,
       case when count(allocated_pnl) = count(*)
            then round(sum(allocated_pnl), 2)
            else null::numeric end as total_pnl,
       round(avg(model_prediction), 3) as avg_model_prediction
from allocated
group by market_type;
