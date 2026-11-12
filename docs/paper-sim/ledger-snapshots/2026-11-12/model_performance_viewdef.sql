 WITH weighted_decisions AS (
         SELECT d.id,
            d.ts,
            d.market_id,
            d.question,
            d.side,
            d.price,
            d.shares,
            d.stake,
            d.fair_low,
            d.fair_high,
            d.spot,
            d.vol,
            d.horizon_days,
            d.sizing,
            d.reason,
            d.team,
            d.model_prediction,
            d.market_type,
            sum(d.shares) OVER (PARTITION BY d.market_id) AS market_shares,
            bool_and(COALESCE(d.shares >= 0::numeric AND d.shares < 'Infinity'::numeric, false)) OVER (PARTITION BY d.market_id) AS valid_shares
           FROM decisions d
        ), allocated AS (
         SELECT d.market_type,
            d.model_prediction,
            r.outcome,
            r.pnl,
                CASE
                    WHEN d.valid_shares AND d.market_shares > 0::numeric THEN r.pnl * d.shares / d.market_shares
                    ELSE NULL::numeric
                END AS allocated_pnl
           FROM weighted_decisions d
             JOIN resolutions r ON r.market_id = d.market_id
        )
 SELECT market_type,
    count(*) AS total_settled,
    sum(
        CASE
            WHEN (outcome = ANY (ARRAY['YES'::text, 'NO'::text, 'YES-basket'::text])) AND pnl > 0::numeric THEN 1
            ELSE 0
        END) AS wins,
    sum(
        CASE
            WHEN (outcome = ANY (ARRAY['YES'::text, 'NO'::text, 'YES-basket'::text])) AND pnl <= 0::numeric THEN 1
            ELSE 0
        END) AS losses,
    sum(
        CASE
            WHEN outcome = 'EXITED'::text THEN 1
            ELSE 0
        END) AS exits,
    round(100.0 * sum(
        CASE
            WHEN (outcome = ANY (ARRAY['YES'::text, 'NO'::text, 'YES-basket'::text])) AND pnl > 0::numeric THEN 1
            ELSE 0
        END)::numeric / NULLIF(sum(
        CASE
            WHEN outcome = ANY (ARRAY['YES'::text, 'NO'::text, 'YES-basket'::text]) THEN 1
            ELSE 0
        END), 0)::numeric, 1) AS win_rate_pct,
        CASE
            WHEN count(allocated_pnl) = count(*) THEN round(sum(allocated_pnl), 2)
            ELSE NULL::numeric
        END AS total_pnl,
    round(avg(model_prediction), 3) AS avg_model_prediction
   FROM allocated
  GROUP BY market_type;
