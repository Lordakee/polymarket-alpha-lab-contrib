-- Papersim reporting views (M3 node V2, design m3-v1-views-design
-- 2026-11-15; M3 plan section 7.1 contracts). Three read-only
-- aggregation views over the v2 core tables; they add no table, no
-- write path and no promotion logic (criteria A-F judgements and
-- bootstrap intervals stay in the Python evaluation module).
--   papersim.natural_settlement_summary : per effective market outcome,
--     settlement-class hit counts and gross/fee/net sums (view one).
--   papersim.candidate_scoring_view     : one row per candidate (all
--     conclusions), decision/close representative evidence, effective
--     outcome, three-valued natural_hit, coverage status chain and the
--     per-pair Brier / log-loss difference terms (view two).
--   papersim.queue_summary_view         : per queue key (model_name,
--     model_version, market_type, gate_version, is_legacy) the A-F
--     metric inputs: counts, spans, fee visibility, CLV inputs, market
--     scoring aggregates, gross/net PnL, ROI, top-market gross AND net
--     concentration (OD-G E reads the net column) and net drawdown.
-- Semantics pinned by the design and plan section 7.1: settlements
-- aggregate per entry (one settlement per entry at most, so no one-to-
-- many amplification); NATURAL/EXIT/VOIDED_REFUND stay separate; gross
-- and net stand side by side (net = gross - fee_total per the table
-- CHECK identity); every ratio wraps its denominator in nullif so a
-- zero denominator is NULL, never 0; hit counting uses classification
-- 'NATURAL' plus win_loss (the section 78.5 P3 lesson: win/loss labels
-- must count as natural settlements); rejected candidates participate
-- in calibration (a rejection is never a trade: entry columns stay
-- NULL for them); the decision representative is the smallest
-- evidence_id, the close representative the latest observed_at; the
-- effective outcome per market identity prefers non-UNKNOWN rows
-- (observed_at desc, outcome_id desc) and a later UNKNOWN never
-- shadows a known outcome; early exits are never natural losses and
-- UNKNOWN outcomes stay gaps (no zero filling). All amounts are the
-- recorded numeric columns; nothing is recomputed in floating point.
-- Apply ONCE through the papersim catalog applier; drift must fail.
begin;

create view papersim.natural_settlement_summary as
with mo_ident AS (
  select 'condition_id'::text AS ref_kind, condition_id AS ref,
         outcome_id, outcome, confirmed_at, observed_at, source_kind,
         yes_token_id, no_token_id
  from papersim.market_outcomes where condition_id is not null
  union all
  select 'market_id'::text, market_id, outcome_id, outcome, confirmed_at,
         observed_at, source_kind, yes_token_id, no_token_id
  from papersim.market_outcomes where market_id is not null
  union all
  select 'market_slug'::text, market_slug, outcome_id, outcome,
         confirmed_at, observed_at, source_kind, yes_token_id, no_token_id
  from papersim.market_outcomes where market_slug is not null
),
eff_non_unknown AS (
  select distinct on (ref_kind, ref) ref_kind, ref, outcome_id, outcome,
         confirmed_at, observed_at, source_kind, yes_token_id, no_token_id
  from mo_ident where outcome <> 'UNKNOWN'
  order by ref_kind, ref, observed_at desc, outcome_id desc
),
eff_unknown AS (
  select distinct on (ref_kind, ref) ref_kind, ref, outcome_id, outcome,
         confirmed_at, observed_at, source_kind, yes_token_id, no_token_id
  from mo_ident where outcome = 'UNKNOWN'
  order by ref_kind, ref, observed_at desc, outcome_id desc
),
effective_outcomes AS (
  select ref_kind, ref, outcome_id, outcome, confirmed_at, observed_at,
         source_kind, yes_token_id, no_token_id
  from eff_non_unknown
  union all
  select u.ref_kind, u.ref, u.outcome_id, u.outcome, u.confirmed_at,
         u.observed_at, u.source_kind, u.yes_token_id, u.no_token_id
  from eff_unknown u
  left join eff_non_unknown n
    on n.ref_kind = u.ref_kind and n.ref = u.ref
  where n.ref is null
),
settlement_bound AS (
  -- Each settlement reaches exactly one market identity through its
  -- entry's candidate binding (strict layering: condition_id, else
  -- market_id, else market_slug), so sums never double count.
  select s.settlement_id, s.entry_id, s.classification, s.win_loss,
         s.pnl_gross, s.fee_total, s.pnl_net, s.fee_source, s.confirmed_at,
         s.is_legacy,
         c.condition_id, c.market_id, c.market_slug, c.side, c.team,
         coalesce(c.condition_id, c.market_id, c.market_slug) AS market_key
  from papersim.settlements s
  join papersim.entries e on e.entry_id = s.entry_id
  join papersim.candidates c on c.candidate_id = e.candidate_id
)
select
  eo.ref_kind                                     AS market_ref_kind,
  eo.ref                                          AS market_ref,
  eo.outcome_id                                   AS effective_outcome_id,
  eo.outcome                                      AS effective_outcome,
  eo.confirmed_at                                 AS outcome_confirmed_at,
  eo.observed_at                                  AS outcome_observed_at,
  eo.source_kind                                  AS outcome_source_kind,
  count(sb.settlement_id)                         AS settlements_total,
  count(sb.settlement_id) filter (where sb.classification = 'NATURAL')
                                                  AS natural_settled,
  count(sb.settlement_id) filter (where sb.classification = 'NATURAL'
                                        and sb.win_loss = 'win')   AS natural_hits,
  count(sb.settlement_id) filter (where sb.classification = 'NATURAL'
                                        and sb.win_loss = 'loss')  AS natural_losses,
  count(sb.settlement_id) filter (where sb.classification = 'NATURAL'
                                        and sb.win_loss = 'win')::numeric
    / nullif(count(sb.settlement_id) filter (where sb.classification = 'NATURAL'), 0)
                                                  AS natural_hit_rate,
  sum(sb.pnl_gross) filter (where sb.classification = 'NATURAL')
                                                  AS natural_pnl_gross,
  sum(sb.fee_total)  filter (where sb.classification = 'NATURAL')
                                                  AS natural_fee_total,
  sum(sb.pnl_net)    filter (where sb.classification = 'NATURAL')
                                                  AS natural_pnl_net,
  count(sb.settlement_id) filter (where sb.classification = 'EXIT')
                                                  AS exit_settled,
  sum(sb.pnl_gross)  filter (where sb.classification = 'EXIT')   AS exit_pnl_gross,
  sum(sb.pnl_net)    filter (where sb.classification = 'EXIT')   AS exit_pnl_net,
  count(sb.settlement_id) filter (where sb.classification = 'VOIDED_REFUND')
                                                  AS voided_settled,
  sum(sb.pnl_gross)  filter (where sb.classification = 'VOIDED_REFUND')
                                                  AS voided_pnl_gross,
  sum(sb.pnl_net)    filter (where sb.classification = 'VOIDED_REFUND')
                                                  AS voided_pnl_net
from effective_outcomes eo
left join settlement_bound sb
  on (eo.ref_kind = 'condition_id' and sb.condition_id is not null
      and sb.condition_id = eo.ref)
  or (eo.ref_kind = 'market_id' and sb.condition_id is null
      and sb.market_id is not null and sb.market_id = eo.ref)
  or (eo.ref_kind = 'market_slug' and sb.condition_id is null
      and sb.market_id is null and sb.market_slug = eo.ref)
group by eo.ref_kind, eo.ref, eo.outcome_id, eo.outcome,
         eo.confirmed_at, eo.observed_at, eo.source_kind
order by eo.ref_kind, eo.ref;

grant select on papersim.natural_settlement_summary to pal_app;

create view papersim.candidate_scoring_view as
with mo_ident AS (
  select 'condition_id'::text AS ref_kind, condition_id AS ref,
         outcome_id, outcome, confirmed_at, observed_at, source_kind,
         yes_token_id, no_token_id
  from papersim.market_outcomes where condition_id is not null
  union all
  select 'market_id'::text, market_id, outcome_id, outcome, confirmed_at,
         observed_at, source_kind, yes_token_id, no_token_id
  from papersim.market_outcomes where market_id is not null
  union all
  select 'market_slug'::text, market_slug, outcome_id, outcome,
         confirmed_at, observed_at, source_kind, yes_token_id, no_token_id
  from papersim.market_outcomes where market_slug is not null
),
eff_non_unknown AS (
  select distinct on (ref_kind, ref) ref_kind, ref, outcome_id, outcome,
         confirmed_at, observed_at, source_kind, yes_token_id, no_token_id
  from mo_ident where outcome <> 'UNKNOWN'
  order by ref_kind, ref, observed_at desc, outcome_id desc
),
eff_unknown AS (
  select distinct on (ref_kind, ref) ref_kind, ref, outcome_id, outcome,
         confirmed_at, observed_at, source_kind, yes_token_id, no_token_id
  from mo_ident where outcome = 'UNKNOWN'
  order by ref_kind, ref, observed_at desc, outcome_id desc
),
effective_outcomes AS (
  select ref_kind, ref, outcome_id, outcome, confirmed_at, observed_at,
         source_kind, yes_token_id, no_token_id
  from eff_non_unknown
  union all
  select u.ref_kind, u.ref, u.outcome_id, u.outcome, u.confirmed_at,
         u.observed_at, u.source_kind, u.yes_token_id, u.no_token_id
  from eff_unknown u
  left join eff_non_unknown n
    on n.ref_kind = u.ref_kind and n.ref = u.ref
  where n.ref is null
),
decision_evidence AS (
  -- Decision representative: the DECISION row with the smallest
  -- evidence_id (P3-8 derived rule; there is no pointer column).
  select distinct on (candidate_id) candidate_id, evidence_id, observed_at,
         model_probability, side, mid
  from papersim.candidate_price_evidence
  where evidence_role = 'DECISION'
  order by candidate_id, evidence_id
),
close_evidence AS (
  -- Close representative: the latest CLOSE row (observed_at desc,
  -- evidence_id desc tie-break, pinned by the design section 2.3).
  select distinct on (candidate_id) candidate_id, evidence_id, observed_at,
         mid AS close_mid, last AS close_last, side AS close_side
  from papersim.candidate_price_evidence
  where evidence_role = 'CLOSE'
  order by candidate_id, observed_at desc, evidence_id desc
),
pairs AS (
  select c.candidate_id, c.scan_id, c.candidate_key, c.conclusion,
         c.is_legacy, c.team, c.side,
         c.condition_id, c.market_id, c.market_slug,
         coalesce(c.condition_id, c.market_id, c.market_slug) AS market_key,
         c.binding_version, c.yes_token_id, c.no_token_id,
         c.median_probability,
         c.model_name, c.model_version, c.market_type, sr.gate_version,
         de.evidence_id    AS decision_evidence_id,
         de.observed_at    AS decision_observed_at,
         de.model_probability,
         de.side           AS decision_side,
         de.mid            AS decision_mid,
         ce.close_mid, ce.close_side, ce.close_last,
         ce.observed_at    AS close_observed_at,
         coalesce(eo_c.outcome_id, eo_m.outcome_id, eo_s.outcome_id)
                                                  AS effective_outcome_id,
         coalesce(eo_c.outcome,   eo_m.outcome,   eo_s.outcome)
                                                  AS effective_outcome,
         coalesce(eo_c.yes_token_id, eo_m.yes_token_id, eo_s.yes_token_id)
                                                  AS mo_yes_token_id,
         coalesce(eo_c.no_token_id,  eo_m.no_token_id,  eo_s.no_token_id)
                                                  AS mo_no_token_id
  from papersim.candidates c
  join papersim.scan_runs sr on sr.scan_id = c.scan_id
  left join decision_evidence de on de.candidate_id = c.candidate_id
  left join close_evidence ce on ce.candidate_id = c.candidate_id
  left join effective_outcomes eo_c
    on c.condition_id is not null
       and eo_c.ref_kind = 'condition_id' and eo_c.ref = c.condition_id
  left join effective_outcomes eo_m
    on c.condition_id is null and c.market_id is not null
       and eo_m.ref_kind = 'market_id' and eo_m.ref = c.market_id
  left join effective_outcomes eo_s
    on c.condition_id is null and c.market_id is null
       and eo_s.ref_kind = 'market_slug' and eo_s.ref = c.market_slug
),
aligned AS (
  select p.*,
         case when p.decision_side = p.side then p.decision_mid
              when p.decision_side is not null and p.side is not null
                   and p.decision_mid is not null then 1 - p.decision_mid
         end AS market_mid_side_aligned,
         case when p.decision_side = p.side then p.close_mid
              when p.close_side is not null and p.side is not null
                   and p.close_mid is not null then 1 - p.close_mid
         end AS close_mid_side_aligned
  from pairs p
),
hit_flagged AS (
  -- Three-valued: true/false only for a natural outcome; NULL when the
  -- market has no observation or is still UNKNOWN. An early exit is
  -- never a natural loss and UNKNOWN is never zero-filled.
  select a.*,
         case when a.effective_outcome in ('YES','NO','YES-basket')
               then (a.side in ('YES','YES-basket')
                     and a.effective_outcome = a.side)
                 or (a.side in ('NO','NO-basket')
                     and a.effective_outcome = 'NO')
         end AS natural_hit
  from aligned a
),
statused AS (
  select h.*,
         case
           when h.market_key is null            then 'NO_BINDING'
           when h.effective_outcome_id is null  then 'NO_OUTCOME_OBSERVATION'
           when h.effective_outcome = 'UNKNOWN' then 'UNKNOWN_OUTCOME'
           when h.mo_yes_token_id is not null and h.mo_no_token_id is not null
            and ( (h.yes_token_id is not null
                   and h.yes_token_id not in (h.mo_yes_token_id, h.mo_no_token_id))
               or (h.no_token_id is not null
                   and h.no_token_id not in (h.mo_yes_token_id, h.mo_no_token_id)) )
                                                then 'BINDING_MISMATCH'
           when h.model_probability is null     then 'MISSING_MODEL_PROBABILITY'
           when h.market_mid_side_aligned is null then 'MISSING_MARKET_MID'
           else 'OK'
         end AS scoring_status
  from hit_flagged h
)
select
  s.candidate_id, s.scan_id, s.candidate_key, s.conclusion, s.is_legacy,
  s.team, s.side,
  s.condition_id, s.market_id, s.market_slug, s.market_key, s.binding_version,
  s.yes_token_id, s.no_token_id, s.median_probability,
  s.model_name, s.model_version, s.market_type, s.gate_version,
  s.decision_evidence_id, s.decision_observed_at, s.model_probability,
  s.decision_side, s.decision_mid,
  s.close_mid, s.close_side, s.close_last, s.close_observed_at,
  s.effective_outcome_id, s.effective_outcome,
  s.mo_yes_token_id, s.mo_no_token_id,
  s.scoring_status, s.natural_hit,
  s.market_mid_side_aligned, s.close_mid_side_aligned,
  case when s.scoring_status = 'OK'
       then s.model_probability - s.market_mid_side_aligned
  end AS model_minus_market,
  case when s.scoring_status = 'OK' then
    (s.model_probability - (case when s.natural_hit then 1 else 0 end)) ^ 2
    - (s.market_mid_side_aligned
       - (case when s.natural_hit then 1 else 0 end)) ^ 2
  end AS brier_pair_diff,
  case when s.scoring_status = 'OK'
        and (case when s.natural_hit then s.model_probability
                  else 1 - s.model_probability end) > 0
        and (case when s.natural_hit then s.market_mid_side_aligned
                  else 1 - s.market_mid_side_aligned end) > 0
    then -ln(case when s.natural_hit then s.model_probability
                  else 1 - s.model_probability end)
         + ln(case when s.natural_hit then s.market_mid_side_aligned
                   else 1 - s.market_mid_side_aligned end)
  end AS logloss_pair_diff,
  case when s.scoring_status = 'OK'
        and ( (case when s.natural_hit then s.model_probability
                    else 1 - s.model_probability end) = 0
           or (case when s.natural_hit then s.market_mid_side_aligned
                    else 1 - s.market_mid_side_aligned end) = 0 )
    then true else false
  end AS infinite_log_loss_pair,
  e.entry_id, e.stake, e.price, e.fee_source
from statused s
left join papersim.entries e on e.candidate_id = s.candidate_id
order by s.candidate_id;

grant select on papersim.candidate_scoring_view to pal_app;

create view papersim.queue_summary_view as
with scored AS (
  select model_name, model_version, market_type, gate_version, is_legacy,
         candidate_id, conclusion, market_key, scoring_status,
         model_probability, market_mid_side_aligned, natural_hit,
         brier_pair_diff, logloss_pair_diff, infinite_log_loss_pair,
         decision_observed_at, entry_id
  from papersim.candidate_scoring_view
),
queues AS (
  select model_name, model_version, market_type, gate_version, is_legacy
  from scored
  group by 1, 2, 3, 4, 5
),
market_rep AS (
  -- One representative per market: the earliest decision observation
  -- (NULL last, candidate_id asc) mirrors the evaluator's
  -- representative order inside each queue x market group.
  select distinct on (model_name, model_version, market_type, gate_version,
                      is_legacy, market_key)
         model_name, model_version, market_type, gate_version, is_legacy,
         market_key, candidate_id, scoring_status, model_probability,
         market_mid_side_aligned, natural_hit, brier_pair_diff,
         logloss_pair_diff, infinite_log_loss_pair, decision_observed_at
  from scored
  where market_key is not null
  order by model_name, model_version, market_type, gate_version, is_legacy,
           market_key, decision_observed_at asc nulls last, candidate_id asc
),
candidate_block AS (
  select model_name, model_version, market_type, gate_version, is_legacy,
         count(*)::bigint AS candidates_total,
         count(*) filter (where conclusion = 'ACCEPTED')::bigint
                       AS candidates_accepted,
         count(*) filter (where conclusion = 'REJECTED')::bigint
                       AS candidates_rejected,
         count(*) filter (where conclusion = 'CONSTRUCTION_FAILED')::bigint
                       AS candidates_construction_failed,
         count(entry_id)::bigint AS entered,
         count(*) filter (where scoring_status = 'NO_BINDING')::bigint
                       AS markets_missing_binding,
         count(*) filter (where market_key is not null)::bigint
                       AS bound_candidates,
         min(decision_observed_at) AS span_first_decision_at,
         max(decision_observed_at) AS span_last_decision_at,
         extract(epoch from (max(decision_observed_at)
                             - min(decision_observed_at))) / 86400.0
                       AS span_days
  from scored
  group by 1, 2, 3, 4, 5
),
entry_side AS (
  select e.entry_id, e.stake, e.price, e.entry_fee, e.fee_source,
         c.model_name, c.model_version, c.market_type, c.is_legacy,
         coalesce(c.condition_id, c.market_id, c.market_slug) AS market_key,
         sr.gate_version,
         s.settlement_id, s.classification, s.win_loss, s.pnl_gross,
         s.fee_total, s.pnl_net, s.confirmed_at,
         m.mark_id AS close_mark_id, m.mid AS close_mid
  from papersim.entries e
  join papersim.candidates c on c.candidate_id = e.candidate_id
  join papersim.scan_runs sr on sr.scan_id = c.scan_id
  left join papersim.settlements s on s.entry_id = e.entry_id
  left join papersim.marks m on m.entry_id = e.entry_id and m.is_close
),
entry_block AS (
  select model_name, model_version, market_type, gate_version, is_legacy,
         count(*)::bigint AS entries_total,
         count(*) filter (where fee_source = 'schedule')::bigint
                       AS entries_fee_source_schedule,
         count(*) filter (where fee_source = 'estimated')::bigint
                       AS entries_fee_source_estimated,
         count(*) filter (where settlement_id is null)::bigint
                       AS entries_unsettled,
         count(close_mark_id)::bigint AS clv_entries_with_close_mark,
         count(close_mid)::bigint AS clv_entries_with_close_mid,
         sum(stake) AS stake_sum,
         sum(entry_fee) AS entry_fee_sum,
         avg(close_mid - price) AS clv_mean
  from entry_side
  group by 1, 2, 3, 4, 5
),
settlement_block AS (
  select model_name, model_version, market_type, gate_version, is_legacy,
         count(*) filter (where classification = 'NATURAL')::bigint
                       AS settled_natural,
         count(*) filter (where classification = 'NATURAL'
                          and win_loss = 'win')::bigint AS natural_hits,
         count(*) filter (where classification = 'EXIT')::bigint
                       AS settled_exit,
         count(*) filter (where classification = 'VOIDED_REFUND')::bigint
                       AS settled_voided,
         sum(pnl_gross) AS gross_pnl_sum,
         sum(fee_total) AS fee_total_sum,
         sum(pnl_net) AS net_pnl_sum,
         -- EXIT sell-leg estimate via the fee identity (design 5.2 B).
         sum(greatest(fee_total - entry_fee, 0)) AS exit_fee_sum,
         extract(epoch from (max(confirmed_at) - min(confirmed_at))) / 86400.0
                       AS span_fallback_settled_days
  from entry_side
  where settlement_id is not null
  group by 1, 2, 3, 4, 5
),
market_block AS (
  select model_name, model_version, market_type, gate_version, is_legacy,
         count(*)::bigint AS markets_total,
         count(*) filter (where scoring_status = 'OK')::bigint
                       AS markets_scored,
         count(*) filter (where scoring_status in
                          ('NO_OUTCOME_OBSERVATION','UNKNOWN_OUTCOME'))::bigint
                       AS markets_missing_outcome,
         count(*) filter (where scoring_status = 'BINDING_MISMATCH')::bigint
                       AS markets_binding_mismatch,
         count(*) filter (where scoring_status = 'MISSING_MODEL_PROBABILITY')::bigint
                       AS markets_missing_model_probability,
         count(*) filter (where scoring_status = 'MISSING_MARKET_MID')::bigint
                       AS markets_missing_market_mid,
         avg(case when scoring_status = 'OK'
                  then (model_probability
                        - (case when natural_hit then 1 else 0 end)) ^ 2
             end) AS model_brier_mean,
         avg(case when scoring_status = 'OK'
                  then (market_mid_side_aligned
                        - (case when natural_hit then 1 else 0 end)) ^ 2
             end) AS market_brier_mean,
         avg(brier_pair_diff) AS brier_diff_mean,
         avg(logloss_pair_diff) AS logloss_diff_mean,
         count(*) filter (where infinite_log_loss_pair)::bigint
                       AS infinite_log_loss_pairs
  from market_rep
  group by 1, 2, 3, 4, 5
),
per_market_pnl AS (
  -- Same-market entries aggregate BEFORE the top-market pick, so multi-
  -- entry markets count once (the 3866000 conservation shape).
  select model_name, model_version, market_type, gate_version, is_legacy,
         market_key, sum(pnl_gross) AS gross_pnl, sum(pnl_net) AS net_pnl
  from entry_side
  where settlement_id is not null
  group by 1, 2, 3, 4, 5, 6
),
top_gross_market AS (
  select distinct on (model_name, model_version, market_type, gate_version,
                      is_legacy)
         model_name, model_version, market_type, gate_version, is_legacy,
         market_key AS top_market_key, gross_pnl AS top_market_pnl
  from per_market_pnl
  order by model_name, model_version, market_type, gate_version, is_legacy,
           gross_pnl desc, market_key asc
),
top_net_market AS (
  select distinct on (model_name, model_version, market_type, gate_version,
                      is_legacy)
         model_name, model_version, market_type, gate_version, is_legacy,
         market_key AS top_market_net_key, net_pnl AS top_market_net_pnl
  from per_market_pnl
  order by model_name, model_version, market_type, gate_version, is_legacy,
           net_pnl desc, market_key asc
),
dd_cum AS (
  select model_name, model_version, market_type, gate_version, is_legacy,
         settlement_id, confirmed_at,
         sum(pnl_net) over step1 AS cum_net
  from entry_side
  where settlement_id is not null
  window step1 AS (partition by model_name, model_version, market_type,
                                  gate_version, is_legacy
                   order by confirmed_at, settlement_id
                   rows between unbounded preceding and current row)
),
dd_series AS (
  select model_name, model_version, market_type, gate_version, is_legacy,
         cum_net, greatest(max(cum_net) over step2, 0) AS peak_net
  from dd_cum
  window step2 AS (partition by model_name, model_version, market_type,
                                  gate_version, is_legacy
                   order by confirmed_at, settlement_id
                   rows between unbounded preceding and current row)
),
dd_block AS (
  select model_name, model_version, market_type, gate_version, is_legacy,
         max(peak_net - cum_net) AS max_drawdown_net,
         count(*)::bigint AS drawdown_rows
  from dd_series
  group by 1, 2, 3, 4, 5
)
select
  q.model_name, q.model_version, q.market_type, q.gate_version, q.is_legacy,
  cb.candidates_total, cb.candidates_accepted, cb.candidates_rejected,
  cb.candidates_construction_failed, cb.entered,
  sb.settled_natural, sb.natural_hits,
  sb.natural_hits::numeric / nullif(sb.settled_natural, 0) AS natural_hit_rate,
  sb.settled_exit, sb.settled_voided,
  eb.entries_unsettled,
  cb.span_first_decision_at, cb.span_last_decision_at, cb.span_days,
  sb.span_fallback_settled_days,
  eb.entries_fee_source_schedule, eb.entries_fee_source_estimated,
  sb.exit_fee_sum,
  eb.entries_total AS clv_entries_eligible,
  eb.clv_entries_with_close_mark, eb.clv_entries_with_close_mid, eb.clv_mean,
  mb.markets_total, mb.markets_scored, mb.markets_missing_outcome,
  cb.markets_missing_binding, mb.markets_binding_mismatch,
  mb.markets_missing_model_probability, mb.markets_missing_market_mid,
  cb.bound_candidates - mb.markets_total AS deduped_repeats,
  mb.model_brier_mean, mb.market_brier_mean, mb.brier_diff_mean,
  mb.logloss_diff_mean, mb.infinite_log_loss_pairs,
  eb.stake_sum, sb.gross_pnl_sum, eb.entry_fee_sum, sb.fee_total_sum,
  sb.net_pnl_sum,
  sb.gross_pnl_sum / nullif(eb.stake_sum, 0) AS gross_roi,
  sb.net_pnl_sum / nullif(eb.stake_sum, 0) AS net_roi,
  tg.top_market_key, tg.top_market_pnl,
  case when sb.gross_pnl_sum > 0 and tg.top_market_pnl is not null
       then tg.top_market_pnl / sb.gross_pnl_sum
  end AS top_market_share,
  tn.top_market_net_key, tn.top_market_net_pnl,
  case when sb.net_pnl_sum > 0 and tn.top_market_net_pnl is not null
       then tn.top_market_net_pnl / sb.net_pnl_sum
  end AS top_market_net_share,
  dd.max_drawdown_net, dd.drawdown_rows
from queues q
join candidate_block cb
  on (cb.model_name, cb.model_version, cb.market_type, cb.gate_version,
      cb.is_legacy) = (q.model_name, q.model_version, q.market_type,
                       q.gate_version, q.is_legacy)
left join entry_block eb
  on (eb.model_name, eb.model_version, eb.market_type, eb.gate_version,
      eb.is_legacy) = (q.model_name, q.model_version, q.market_type,
                       q.gate_version, q.is_legacy)
left join settlement_block sb
  on (sb.model_name, sb.model_version, sb.market_type, sb.gate_version,
      sb.is_legacy) = (q.model_name, q.model_version, q.market_type,
                       q.gate_version, q.is_legacy)
left join market_block mb
  on (mb.model_name, mb.model_version, mb.market_type, mb.gate_version,
      mb.is_legacy) = (q.model_name, q.model_version, q.market_type,
                       q.gate_version, q.is_legacy)
left join top_gross_market tg
  on (tg.model_name, tg.model_version, tg.market_type, tg.gate_version,
      tg.is_legacy) = (q.model_name, q.model_version, q.market_type,
                       q.gate_version, q.is_legacy)
left join top_net_market tn
  on (tn.model_name, tn.model_version, tn.market_type, tn.gate_version,
      tn.is_legacy) = (q.model_name, q.model_version, q.market_type,
                       q.gate_version, q.is_legacy)
left join dd_block dd
  on (dd.model_name, dd.model_version, dd.market_type, dd.gate_version,
      dd.is_legacy) = (q.model_name, q.model_version, q.market_type,
                       q.gate_version, q.is_legacy)
order by q.model_name, q.model_version, q.market_type, q.gate_version,
         q.is_legacy;

grant select on papersim.queue_summary_view to pal_app;

commit;
