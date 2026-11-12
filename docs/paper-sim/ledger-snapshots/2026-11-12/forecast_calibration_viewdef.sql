 SELECT d.market_type,
    count(*) AS n,
    sum(
        CASE
            WHEN (d.side = ANY (ARRAY['YES'::text, 'YES-basket'::text])) AND r.outcome = d.side OR d.side = 'NO'::text AND r.outcome = 'NO'::text OR d.side = 'NO-basket'::text AND r.outcome = 'NO'::text THEN 1
            ELSE 0
        END) AS forecast_hits,
    round(avg(d.model_prediction), 3) AS avg_forecast,
    round(avg(
        CASE
            WHEN (d.side = ANY (ARRAY['YES'::text, 'YES-basket'::text])) AND r.outcome = d.side OR d.side = 'NO'::text AND r.outcome = 'NO'::text OR d.side = 'NO-basket'::text AND r.outcome = 'NO'::text THEN d.model_prediction
            ELSE 1::numeric - d.model_prediction
        END), 3) AS avg_prob_of_realized
   FROM decisions d
     JOIN resolutions r ON r.market_id = d.market_id
  WHERE r.outcome = ANY (ARRAY['YES'::text, 'NO'::text, 'YES-basket'::text])
  GROUP BY d.market_type;
