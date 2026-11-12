import json, datetime

RAW='/home/ubuntu/paper-sim/round19/raw'
d=json.load(open(f'{RAW}/crypto_scan.json'))
NOW=datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)

mtm=d['positions_mtm']
th=d['touch_horizons']
ea=d['exit_analysis_eth2250']
fair2250=d['held_fair_dec31']['ETH2250']
fair2000=d['held_fair_dec31']['ETH2000']
fairbtc=d['held_fair_dec31']['BTC65K_yes']

sig30=d['realized_vol_daily']['ETH']['30d']
fA=ea['fair_grid']['30d']['pA_zero_drift']; fB=ea['fair_grid']['30d']['pB_median_flat']
bid=ea['yes_bid']
full=ea['exit_walks']['sell_all_2555']; half=ea['exit_walks']['sell_half_1278']; qtr=ea['exit_walks']['sell_quarter_639']

p_tue=th['ETH_2250']['Tue_close_Oct27_2359']['probs']
p_fomc=th['ETH_2250']['FOMC_decision_Wed_1800']['probs']
p_fri=th['ETH_2250']['Fri_close_Oct30_2359']['probs']
p_nov1=th['ETH_2250']['Nov1_0000']['probs']
p_dec31=th['ETH_2250']['Dec31_2359']['probs']

rec={
 'generated_at':NOW.isoformat(),
 'team':'crypto','round':19,'mode':'PAPER ONLY — monitoring (team AT CAP $1,870/$1,900)',
 'spot':{'ETH':d['spot']['ETH'],'BTC':d['spot']['BTC']},
 'vol_daily':{'ETH':{k:round(v,5) for k,v in d['realized_vol_daily']['ETH'].items()},
              'BTC':{k:round(v,5) for k,v in d['realized_vol_daily']['BTC'].items()}},

 '1_mtm_table':[{
    'name':m['name'],'shares':m['shares'],'avg':m['avg'],'cost':m['cost'],
    'bid':m['book']['best_bid'],'ask':m['book']['best_ask'],'mid':round(m['book']['mid'],3),
    'last_trade':m['last_trade'],
    'realizable_cash_bid_walk':m['realizable_cash'],'walk_avg_px':m['mtm_px'],
    'unrealized_bid':m['unrealized_bid'],'unrealized_bid_pct':m['unrealized_bid_pct'],
    'mark_to_mid':m['mark_to_mid']} for m in mtm],
 'total_realizable_cash':round(sum(m['realizable_cash'] for m in mtm),2),
 'total_cost':sum(m['cost'] for m in mtm),

 '2_weekend_low_verification':{**d['weekend_1m_check'],
   'interpretation':('Weekend low 2282.46 (Sat 15:19 UTC) = 1.44% above the 2250 barrier -> does NOT trigger the '
     'within-1% immediate deep-watch flag (threshold <=2272.5), and zero minutes printed <=2280. '
     'However this is the closest approach since market creation (prior closest 2318, 3.02%), and 79 minutes '
     'printed <=2300. Monday pre-dawn low 2293.09 (03:54 UTC). Keep enhanced-watch cadence but barrier not breached.'),
   'min_low_since_creation_2250':d['barrier_checks']['eth2250']['min_low_since']},

 '3_touch_probabilities':{
   'ETH_2250_from_spot_2327':{
     'Tue_close_Oct27':{'30d_A':p_tue['30d']['A'],'30d_B':p_tue['30d']['B'],'7d_A':p_tue['7d']['A']},
     'FOMC_decision_Wed1800':{'30d_A':p_fomc['30d']['A'],'30d_B':p_fomc['30d']['B'],'7d_A':p_fomc['7d']['A']},
     'Fri_close_Oct30':{'30d_A':p_fri['30d']['A'],'30d_B':p_fri['30d']['B'],'7d_A':p_fri['7d']['A']},
     'Nov1':{'30d_A':p_nov1['30d']['A'],'30d_B':p_nov1['30d']['B']},
     'Dec31_full':{'30d_A':p_dec31['30d']['A'],'30d_B':p_dec31['30d']['B'],'7d_A':p_dec31['7d']['A'],'87d_A':p_dec31['87d']['A']}},
   'vs_round18_model':'round-15 model (Oct 24): P(touch by FOMC)~0.31/0.32, by Nov 1~0.43/0.45. Now 0.353/0.359 by FOMC and 0.555/0.564 by Nov 1 — up ~4pp and ~12pp on spot 2327 (closer) + Fri-only window elapsed.',
   'ETH_2000_near_term':{'Tue':th['ETH_2000']['Tue_close_Oct27_2359']['probs']['30d']['A'],
                         'Fri':th['ETH_2000']['Fri_close_Oct30_2359']['probs']['30d']['A'],
                         'Dec31':{'A':fair2000['30d']['A'],'B':fair2000['30d']['B']}},
   'BTC_65000_touch':{'near_term':'~0 through Nov 1 (barrier ~19% below spot, 1.58% daily vol)',
                      'Dec31':{'A':fairbtc['30d']['A'],'B':fairbtc['30d']['B']}}},

 '4_eth2250_management':{
   'recommendation':'HOLD full 2,555 sh through FOMC. Do NOT scale out now.',
   'numbers':{
     'yes_bid':bid,'yes_ask':ea.get('fair_grid') and 0.82,'fair_30d_A':fA,'fair_30d_B':fB,
     'edge_vs_top_bid_per_share':{'A':round(fA-bid,4),'B':round(fB-bid,4)},
     'position_edge_vs_top_bid':{'A_$':round((fA-bid)*2555,2),'B_$':round((fB-bid)*2555,2)},
     'position_edge_vs_full_walk':{'A_$':round((fA-full['avg_px'])*2555,2),'B_$':round((fB-full['avg_px'])*2555,2)},
     'hold_EV_full_position':{'A_$':round(2555*fA,2),'B_$':round(2555*fB,2)},
     'sell_all_now':full,'sell_half':half,'sell_quarter':qtr,
     'breakeven_daily_vol_for_bid':ea['breakeven_daily_vol_for_bid'],
     'current_30d_vol':ea['current_vol_30d'],
     'vol_ratio_realized_over_implied':round(ea['current_vol_30d']/ea['breakeven_daily_vol_for_bid'],2),
     'breakeven_upward_drift_for_bid':{'log_daily':ea['breakeven_upward_log_drift_at_30d_vol'],
                                       'annualized_pct':ea['breakeven_drift_annualized_pct']}},
   'case':[
     'Model fair 0.865-0.880 vs 0.79 bid = +7.5 to +9.0c/sh (+$193 to +$230 vs top bid; +$275 to +$310 vs full-walk realizable).',
     'Bid 0.79 implies only 1.55% daily vol; realized 30d is 2.43% (1.57x). Even 7d vol (2.15%) is far above implied.',
     'For 0.79 to be FAIR the market needs +0.137%/day (~65%/yr annualized) upward log-drift — an implausibly strong rally assumption.',
     'Path math: P(touch by Nov 1)=0.55; even if NOT touched by Nov 1, conditional P(touch by Dec 31) stays ~0.70 — YES fair decays slowly while the barrier stays 3-6% away.',
     'Near-binary framing cuts both ways, but the binary is priced 7-9c TOO CHEAP vs model, not too rich.',
     'Optional de-risk only if the team wants FOMC variance reduction: sell <=639 sh (top-of-book 1,140 sh >=0.75) at ~0.787 = +$253 realized on that lot; keep >=1,916 sh. EV-favoured action is no sale.'],
   'trigger_update':{
     'prior':'exit review if ETH>$2,650; hold to resolution if ETH<$2,310 (spot 2,327 — 17 usd above the hold line, no trigger fired)',
     'new':'Tighten the upper review line: ETH>$2,400 (log-dist 6.4%, fair falls to ~0.74-0.77 < 0.79 bid -> edge gone) -> scale out 25-50%; ETH<$2,310 hold to resolution; ALSO trim if YES bid >=0.90 while barrier untouched (short-term touch overpriced). If ETH closes Mon/Tue below 2,290 (weekend-low retest), expect YES to run toward 0.85+ — hold.',
     'liquidity_note':'Top of book thin: only 1,140 sh bid >=0.75 (414@0.79, 520@0.78, 100@0.77, 106@0.75); walls 10,000@0.74 and 5,000@0.71. Full 2,555-sh exit averages 0.7578. Any exit >1,000 sh gives up >=2c/sh vs top.'}},

 '5_etf_flows_and_fomc':{
   'monday_oct26_first_prints':'NOT YET PUBLISHED at scan time (12:50 UTC / 08:50 ET — US ETF session opens 13:30 UTC; daily flow prints follow in the US afternoon via Farside/SoSoValue). Action: recheck ~20:00-22:00 UTC.',
   'latest_available':{
     'BTC_spot_ETFs':'Week ending Oct 22: +$442.7M net inflows (rebound from -$228.6M prior week), BUT included the biggest single-day outflow since June (~-$635.5M) as BTC tested $80k; ~$105B total net assets.',
     'ETH_spot_ETFs':'Oct MTD ~-$1.0B net (worst month of 2026, ~62% of 2026 YTD inflows erased); Oct 19 -$103M; Oct 21-22 broke a 5-day outflow streak at +$14.9M; 7-day net was -$448.7M as of Oct 16.'},
   'fomc_oct27_28':{
     'decision':'Wed Oct 28 18:00 UTC (14:00 ET), Powell 18:30 UTC',
     'priced':'Polymarket No-change ~95% / +25bp hike ~5%; OIS ~9.6% hike. (Task brief 5.5c — same story: small hawkish tail.)',
     'context':'Hike odds spiked to 40-50% after Sept core CPI printed 2.6% vs 2.5% exp, then cooled. Sept dot plot: median member sees one more 2026 hike; no SEP at this meeting.',
     'impact_read_for_book':{
       'base_case_hold_neutral_statement':'mild relief-risk-rally in ETH -> modest YES decay; model says hold anyway (edge cushion 7-9c).',
       'hawkish_surprise_5_10pct':'ETH down sharply -> HELPS ETH-2250 YES and ETH-2000 YES; book is a natural hawkish-tail hedge. BTC-65k NO unaffected (barrier 19% away).',
       'dovish_pivot':'main adverse path: ETH rallies >2,400 -> use the new 2,400 scale-out line.'}}},

 '6_report_only_top5':[
   {'mkt':x['q'],'sym':x['sym'],'kind':x['kind'],'K':x['K'],'T':x['T'],
    'fair_yes':x['fair_yes'],'yes_bid':x['yes_bid'],'yes_ask':x['yes_ask'],
    'edge_yes':x['edge_yes'],'edge_no':x['edge_no'],'liq':x['liq'],
    'side':'YES' if x['edge_yes']>x['edge_no'] else 'NO',
    'note':''} for x in d['report_only_table'][:5]],
 'report_only_note':('Team AT CAP — all report-only, no orders. Top-5 is the same structural family as prior rounds: '
   'deep-OTM touch YES is systematically overpriced vs first-passage fair (BTC-65k/60k/55k dips, BTC-100k reach). '
   'Entries #1 and #2 are our HELD positions (BTC-65k NO fair 0.888 vs 0.74 bid; ETH-2000 YES fair 0.479 vs 0.35 ask) — '
   'both remain underpriced in the favorable direction; hold, do not add (cap).'),
 'risks':[
   'FOMC dovish surprise -> ETH rally >2,400 kills the ETH-2250 edge (trigger line added).',
   'Weekend-style thin liquidity: full ETH-2250 exit walks 3.2c below top of book.',
   'Flow shock: ETH ETF Oct MTD -$1B; another large outflow day is the most likely catalyst for a 2250 touch.',
   'Model risk: first-passage GBM with flat vol; a post-FOMC vol crush (7d vol 2.15% falling) lowers touch probs toward the bid-implied 1.55%.'],
}
rec['6_report_only_top5'][0]['note']='HELD (384.6 NO @0.78): fair NO 0.888 vs bid 0.74 — hold'
rec['6_report_only_top5'][1]['note']='HELD (1,208 YES @0.265): fair 0.479 vs ask 0.35 — hold'
rec['6_report_only_top5'][2]['note']='not held; best un-held edge'
rec['6_report_only_top5'][3]['note']='not held'
rec['6_report_only_top5'][4]['note']='not held'

json.dump(rec, open('/home/ubuntu/paper-sim/round19/crypto_recommendations.json','w'), indent=1)
print('wrote crypto_recommendations.json')
print('MTM total realizable',rec['total_realizable_cash'],'cost',rec['total_cost'])
