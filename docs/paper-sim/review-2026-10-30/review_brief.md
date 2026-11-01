# Paper-Sim Trading System Review (read-only)

You are reviewing a Polymarket PAPER-TRADING research system (paper only, no real money) that has run 23 scan rounds (Oct 10-30, 2026). Your job: find concrete, implementable optimizations. Do NOT modify any files — this is a READ-ONLY review producing a findings report.

## Where things are
- Settled ledger (38 settled bets, full fields incl. model fair ranges): `~/paper-sim/review/settled_ledger.json`
- Model performance by type: `~/paper-sim/review/model_performance.json`
- Soccer model core (original round-5c): `~/paper-sim/round5/tools/model_round5c.py`
- Current soccer tools (round-15 production set): `~/paper-sim/round15/soccer_tools/`
- Latest scan tools: `~/paper-sim/round22/` and `~/paper-sim/round23/` (EPL/SerieA/LaLiga-Bund/Ligue sub-scans, xG refreshes)
- Crypto GBM touch model tools: `~/paper-sim/round19/raw/` + `~/paper-sim/round15/raw/crypto_scan.json` (model conventions embedded)
- xG data: `~/paper-sim/round23/raw/xg_epl_23.json`, `~/paper-sim/round22/raw/xg_understat_22.json` (Understat, 2-season blend)
- Do NOT read anything under `~/pal-artifacts/` (credentials). Do NOT access the database directly.

## System description
- Soccer: 10-variant xG-Poisson (2-season blend w=.5 p=8, Dixon-Coles rho=-0.1 fixed), median= fair, variant range = uncertainty. Entry gates (tightened Oct 24 after losses): executable edge >=+5c vs $250-VWAP ask, worst-variant >=+4c, variant spread <=6c, liquidity >=$5k.
- match_winner type SUSPENDED at 2W-4L (33.3%) — suspected systematic overrating of away underdogs in Europe (UEL 0-3 x2, Villarreal 4-3 L, MCI title exit). Recalibration pending.
- Spread/blowout-tail suspended: model underprices favorite blowout margins (Depor +2.5 flagged 4 rounds, unclosed 14c edge; forward test 1W-1L).
- team_total type: 1W-2L so far.
- ou_over: 11W-6L (64.7%) overall — was 7W-0L before Oct 22, 4W-6L since. Did the edge decay or was early record luck?
- Crypto: GBM touch model, realized vol from 6h candles, two drift conventions (zero-log-drift A, median-flat B), conservative convention = fair. ETH-2250 dip just WON +$1,305 (touched Oct 29). Deep-OTM "dip NO" markets systematically overpriced (documented fear-premium factor).
- Election/geopolitics: fresh-poll-vs-market divergence lens (Brazil Lula +$475 win; Senate-D pending).

## Review tasks (produce a numbered findings report)
1. SOCCER MODEL RECALIBRATION: from the settled ledger, analyze losses vs wins. Test hypotheses: (a) match_winner overrates away underdogs — quantify from data; (b) Dixon-Coles rho=-0.1 mis-fit — what rho would the settled O/U outcomes imply?; (c) 2-season blend (w=.5) vs recent-form — did teams with extreme recent form (PSG 4.47 xgpg, Köln 3.66 xgpg vs 1.6 actual) break the model? Propose concrete parameter changes with expected effect sizes.
2. GATE CALIBRATION: with 38 settled bets, evaluate whether the tightened gates (worst>=+4c, var<=6c) actually improved post-Oct-24 selection (4W-2L ou_over since). Would different thresholds have been better? Sample-size honest.
3. CRYPTO MODEL: review the GBM conventions; the one crypto_daily loss (-$200, resolution-convention error) and one crypto_touch exit — any model-side fix worth making, or is it purely a resolution-rule diligence issue (already fixed procedurally)?
4. TOOL-CHAIN: 23 rounds of accumulated scan tools — propose a consolidation plan (one shared library vs copy-per-round). Estimate maintenance risk of current state.
5. LEDGER: any schema/reporting gaps worth fixing (e.g., missing entry timestamp fields, MTM history not persisted, exit-vs-loss misclassification in model_performance view — note exits count as losses there)?
6. PRIORITIZED TOP-5: rank all proposed optimizations by expected PnL impact / effort.

Output: a markdown report to STDOUT titled `# Optimization Review Findings`, with a final line `VERDICT: <findings count> items, top priority = <name>`. Be specific: file paths, parameter values, data references. Do not pad with generic advice.
