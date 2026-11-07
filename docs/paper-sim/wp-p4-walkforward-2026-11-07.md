# WP-P4 T3 shadow walk-forward

Retrospective event-time replay; no production acceptance, sizing, or threshold change.

Official complete prefixes only. A three-hour result-completion assumption is used; original xG publication/revision timestamps are unavailable.

The unchanged ten-variant median is retained raw. Categorical scores normalize its three medians solely to form a proper probability vector; raw-score sensitivity is in JSON. Totals average three lines (1.5, 2.5, 3.5) per fixture.

| League | Model | Fixtures | 1X2 Brier | 1X2 log loss | Totals log loss |
|---|---|---:|---:|---:|---:|
| ALL | production10 | 360 | 0.603307 | 1.009471 | 0.594403 |
| ALL | recalibrated | 639 | 0.604254 | 1.011596 | 0.595021 |
| ALL | league_average_lambda | 639 | 0.644665 | 1.066884 | 0.604317 |
| EPL | production10 | 70 | 0.642145 | 1.064653 | 0.637012 |
| EPL | recalibrated | 70 | 0.639292 | 1.058552 | 0.616226 |
| EPL | league_average_lambda | 70 | 0.675239 | 1.111097 | 0.644456 |
| La_liga | production10 | 30 | 0.567310 | 0.956052 | 0.550050 |
| La_liga | recalibrated | 30 | 0.582827 | 0.979537 | 0.579185 |
| La_liga | league_average_lambda | 30 | 0.621977 | 1.033501 | 0.609202 |
| Serie_A | production10 | 80 | 0.556542 | 0.947039 | 0.550718 |
| Serie_A | recalibrated | 80 | 0.564781 | 0.959662 | 0.595242 |
| Serie_A | league_average_lambda | 80 | 0.627918 | 1.040130 | 0.570736 |
| Bundesliga | production10 | 54 | 0.607450 | 1.013890 | 0.601798 |
| Bundesliga | recalibrated | 54 | 0.613742 | 1.022219 | 0.598094 |
| Bundesliga | league_average_lambda | 54 | 0.640861 | 1.061342 | 0.617982 |
| Ligue_1 | production10 | 0 | n/a | n/a | n/a |
| Ligue_1 | recalibrated | 0 | n/a | n/a | n/a |
| Ligue_1 | league_average_lambda | 0 | n/a | n/a | n/a |
| Championship | production10 | 72 | 0.609890 | 1.017493 | 0.608668 |
| Championship | recalibrated | 144 | 0.629774 | 1.045976 | 0.623492 |
| Championship | league_average_lambda | 144 | 0.650158 | 1.074258 | 0.644597 |
| Eredivisie | production10 | 54 | 0.629322 | 1.044990 | 0.602114 |
| Eredivisie | recalibrated | 261 | 0.593375 | 0.997439 | 0.574743 |
| Eredivisie | league_average_lambda | 261 | 0.641962 | 1.064141 | 0.578232 |

Rows from unsupported production seasons remain in the shadow/baseline summaries. Every reported paired delta uses exactly the same fixtures.

| League | Comparator | 1X2 log-loss delta (shadow minus comparator) | 95% block interval | Paired fixtures / blocks |
|---|---|---:|---|---:|
| ALL | production10 | 0.001811 | [-0.007597, 0.010589] | 360 / 36 |
| ALL | league_average_lambda | -0.055288 | [-0.075029, -0.036306] | 639 / 65 |
| EPL | production10 | -0.006100 | [-0.022608, 0.009659] | 70 / 7 |
| EPL | league_average_lambda | -0.052545 | [-0.098641, -0.004519] | 70 / 7 |
| La_liga | production10 | 0.023486 | [0.013503, 0.041788] | 30 / 3 |
| La_liga | league_average_lambda | -0.053964 | [-0.086316, -0.018428] | 30 / 3 |
| Serie_A | production10 | 0.012623 | [-0.003222, 0.026916] | 80 / 8 |
| Serie_A | league_average_lambda | -0.080469 | [-0.126430, -0.039608] | 80 / 8 |
| Bundesliga | production10 | 0.008328 | [-0.016580, 0.033107] | 54 / 6 |
| Bundesliga | league_average_lambda | -0.039123 | [-0.070021, -0.012453] | 54 / 6 |
| Ligue_1 | production10 | n/a | n/a | 0 / 0 |
| Ligue_1 | league_average_lambda | n/a | n/a | 0 / 0 |
| Championship | production10 | 0.002823 | [-0.009864, 0.015635] | 72 / 6 |
| Championship | league_average_lambda | -0.028281 | [-0.052125, -0.003571] | 144 / 12 |
| Eredivisie | production10 | -0.023862 | [-0.053978, 0.008095] | 54 / 6 |
| Eredivisie | league_average_lambda | -0.066702 | [-0.105707, -0.025197] | 261 / 29 |

Intervals are descriptive and do not eliminate serial dependence, small-season or multiple-comparison uncertainty. Per-fixture losses, block IDs, tuning cohorts, exclusions, skipped rounds and SHA256/byte source manifests are in the companion JSON.

## Data limitations

- Latest big-five snapshot mixes Understat through 2026-10-31 with FotMob recovery rows on 2026-11-01/02; sources are not independent replications.
- EPL_2025: official round map absent; eligible only as verified complete prior-season warmup, not round-level evaluation.
- La_liga_2025: official round map absent; eligible only as verified complete prior-season warmup, not round-level evaluation.
- La_liga:2026:30775: kickoff conflict reconciled by oriented pair/exact score; original=2026-08-19T19:00:00Z safe-completion-clock=2026-08-19T19:05:00Z; prediction cutoff uses earlier source clock.
- Serie_A_2025: official round map absent; eligible only as verified complete prior-season warmup, not round-level evaluation.
- Serie_A:2026:31636: kickoff conflict reconciled by oriented pair/exact score; original=2026-10-25T17:00:00Z safe-completion-clock=2026-10-25T17:05:00Z; prediction cutoff uses earlier source clock.
- Bundesliga_2025: official round map absent; eligible only as verified complete prior-season warmup, not round-level evaluation.
- Ligue_1_2025: official round map absent; eligible only as verified complete prior-season warmup, not round-level evaluation.
- Ligue_1:2026:31949: kickoff conflict reconciled by oriented pair/exact score; original=2026-08-28T18:45:00Z safe-completion-clock=2026-08-28T19:00:00Z; prediction cutoff uses earlier source clock.
- Ligue_1:2026:32010: kickoff conflict reconciled by oriented pair/exact score; original=2026-10-24T15:15:00Z safe-completion-clock=2026-10-25T16:15:00Z; prediction cutoff uses earlier source clock.
- Ligue_1:2026:32011: kickoff conflict reconciled by oriented pair/exact score; original=2026-10-25T19:45:00Z safe-completion-clock=2026-10-26T19:30:00Z; prediction cutoff uses earlier source clock.
- Ligue_1:2026:32017: kickoff conflict reconciled by oriented pair/exact score; original=2026-10-30T16:15:00Z safe-completion-clock=2026-10-30T18:00:00Z; prediction cutoff uses earlier source clock.
- Event-time replay only: archived final xG and final fixture dates lack original publication timestamps/revision histories; available_at remains null.

Quarantined source rows:

- {"away_team": "Rennes", "home_team": "Paris Saint Germain", "league": "Ligue_1", "reason": "official_identity_or_time_conflict", "season": "2026", "source_kickoff": "2026-08-23T18:45:00Z", "source_match_id": "31948"}
- {"league": "Championship", "official_fixture_id": "4825094", "reason": "cancelled_abandoned_awarded_or_unfinished", "season": "2025", "source_match_id": "4825094"}
- {"league": "Championship", "official_fixture_id": "4825251", "reason": "cancelled_abandoned_awarded_or_unfinished", "season": "2025", "source_match_id": "4825251"}
- {"league": "Championship", "official_fixture_id": "4825249", "reason": "cancelled_abandoned_awarded_or_unfinished", "season": "2025", "source_match_id": "4825249"}

No Gate-E pass is asserted by this outcome-scoring harness. The market archive study is separate; prospective shadow evidence remains outstanding.
