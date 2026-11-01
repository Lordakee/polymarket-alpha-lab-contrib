# Paper-Sim Optimization Fixes (2026-10-30, codex gpt-6-astra/max review + audits)

## 1. Ledger accounting (DB paper_sim)
- model_performance view rebuilt: exits separated from W/L (trading PnL vs forecast calibration are different questions)
- MCI EPL title (#10) reclassified match_winner -> season_winner (was polluting 90-min calibration cohort)
- NEW view forecast_calibration: natural resolutions only, judged by forecast quality
- Effect: match_winner true record 40% (2W-3L), not 33.3%; suspension stands on sample-size + cohort-audit grounds

## 2. Crypto model (round19/model19.py — the living copy future rounds copy from)
- FIX (orientation bug): per-side conservative edges — edge_yes = min(pA,pB) - yes_ask; edge_no = (1-max(pA,pB)) - no_ask.
  Was: touch_dn used fair_yes=max(pA,pB) (overstated YES edge ~3.4c on ETH-2000 example); touch_up overstated NO edge.
- FIX (label): convention B relabeled "mean-flat / zero-arithmetic-drift (E[S_T]=S_0)". A is BOTH zero-log-drift AND median-flat
  (mathematically identical, as the external review stated). The A/B pair is genuinely distinct conventions — not a duplicate.
- Verified: reflection identity (touch = 2x terminal at nu=0) exact; patched math matches auditor's independent numbers.

## 3. Historical annotation (do NOT retro-edit)
- round12/model.py p_above: A/B formulas are SWAPPED vs rounds 13+ (r12-A == r13-B and vice versa) — do not difference
  A/B time series across the round12->13 boundary.
- round12/model.py p_touch_up conv B: mirror technique flips drift sign (+sigma^2/2 instead of -sigma^2/2) — round12
  up-market B fairs are wrong by up to ~6pp. Historical evidence only.

## 4. Rejected (by review math)
- Dixon-Coles rho refit from O/U outcomes: IMPOSSIBLE — rho only adjusts 0-0/1-0/0-1/1-1 cells; zero sensitivity to
  O/U 2.5+, team totals, blowout tails. Recalibration direction = goal-rate estimation / shrinkage instead.

## Pending
- xG shrinkage shadow experiment (w=.5/p=16, w=.25/p=8, w=.75/p=8 vs baseline) — hooks into next soccer scan
- Away-underdog cohort + cross-league xG comparability audit (in flight)
- Tool-chain consolidation into shared library (next week)

## 5. Match-winner cohort audit verdict (2026-10-30, independent audit agent)
- OUTCOME evidence: UNDETERMINED — P(0/3 | model floor) = 0.28; model's all-5 floor calibration near-perfect (2.01 expected vs 2 actual); market under-called winners (1.56 vs 2).
- MECHANISM: CONFIRMED STRUCTURAL DEFECT — the 4 European bets came from bespoke scripts (round7/8 soccer7/8.py, round10 model10.py) that relaxed the production guard `if lgh != lga: return None` WITHOUT a league-strength adjustment. Domestic xG multipliers combined cross-league raw. Smoking gun: HOF-LYO favorite FLIP (model Lyon 0.375-0.457 fav vs market correctly Hoffenheim 0.48) = pure Ligue1xBundesliga multiplier artifact. All 3 losses displaced home->away, same direction. Totals/BTTS from same construction WON (RM-Leipzig BTTS, BAY-ARS O2.5) -> defect is specifically the cross-league 1X2 H/A directional channel.
- Two divergent ad-hoc implementations exist (soccer7/8 vs model10 averaging differ); walk-forward validation was domestic-only — the European extension was NEVER backtested.

## 6. Policy changes (effective 2026-10-30)
- match_winner suspension REFINED: cross-league (UCL/UEL/intl) match_winner SUSPENDED until a 2-3 season UCL/UEL walk-forward backtest passes with a league-strength coefficient bridging domestic xG (league-Elo or UEFA-coefficient anchor; cap away-side edge until calibrated). Domestic-league match_winner eligible under standard tightened gates, but remains deprioritized vs O/U (sample 1W-0L).
- Scan dispatch rule: bespoke scripts may NOT relax the lgh!=lga guard; cross-league modeling requires the shared strength-adjusted path (to be built in the consolidation workstream).
