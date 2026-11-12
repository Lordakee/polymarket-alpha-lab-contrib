#!/usr/bin/env python3
"""Round-29: build crypto_recommendations.json from crypto_scan.json. PAPER ONLY."""
import json
from datetime import datetime, timezone

RAW = json.load(open('/home/ubuntu/paper-sim/round29/raw/crypto_scan.json'))
OUT = '/home/ubuntu/paper-sim/round29/crypto_recommendations.json'
NOW = datetime.now(timezone.utc).isoformat()

spot = RAW['spot_binance']; vol = RAW['realized_vol_daily_6h']; lows = RAW['eth_recent_lows']
mtm = {m['name']: m for m in RAW['positions_mtm']}
eth2k = mtm['ETH-dip-2000 YES']; btc65 = mtm['BTC-dip-65k NO']
T = RAW['T_dec31_days']; hz = RAW['touch_horizons']

S = spot['ETH']
dist_usd = round(S - 2000.0, 2)
dist_pct = round(100 * (S - 2000.0) / S, 2)
sig30 = vol['ETH']['30d']
sig_terms = round((S / 2000.0 and __import__('math').log(S / 2000.0)) / (sig30 * __import__('math').sqrt(T)), 3)

qual = RAW['report_only_qualifying']
held_keys = ('dip to $2,000 by December 31, 2026', 'dip to $65,000 by December 31, 2026')
new_ideas = [t for t in qual if not any(k in t['q'] for k in held_keys)]
held_edge_rows = [t for t in qual if any(k in t['q'] for k in held_keys)]

def ev_hold(p, shares): return round(p * shares, 2)

rec = {
 'generated_at': NOW,
 'team': 'crypto', 'round': 29,
 'mode': 'PAPER ONLY - monitoring + report-only (team AT CAP $1,870/$1,900; no new entries)',
 'server_time_at_scan': RAW['generated_at'],

 '1_mtm_table': [
  {'position': 'ETH-dip-2000 YES', 'market': 'Will Ethereum dip to $2,000 by Dec 31, 2026?',
   'shares': 1208, 'avg_px': 0.265, 'cost': 320.0,
   'book_bid_ask': [eth2k['bid'], eth2k['ask']], 'gamma_last_yes': 0.445,
   'realizable_bid_walk': eth2k['realizable_cash_bid_walk'], 'walk_avg_px': eth2k['walk_avg_px'],
   'unrealized_bid': eth2k['unrealized_bid'], 'unrealized_bid_pct': eth2k['unrealized_bid_pct'],
   'mark_to_mid': eth2k['mark_to_mid'],
   'note': 'book top flapped 0.43-0.44 across 3 pulls inside the scan window; walk range $500.7-$512.1'},
  {'position': 'BTC-dip-65k NO', 'market': 'Will Bitcoin dip to $65,000 by Dec 31, 2026?',
   'shares': 384.6, 'avg_px': 0.78, 'cost': 300.0,
   'book_bid_ask_NO': [btc65['bid'], btc65['ask']],
   'realizable_bid_walk': btc65['realizable_cash_bid_walk'], 'walk_avg_px': btc65['walk_avg_px'],
   'unrealized_bid': btc65['unrealized_bid'], 'unrealized_bid_pct': btc65['unrealized_bid_pct'],
   'mark_to_mid': btc65['mark_to_mid']},
  {'position': 'ETH-dip-2250 YES (SETTLED)', 'shares': 2555, 'avg_px': 0.489, 'cost': 1250.0,
   'resolution': 'YES - gamma 3866000 resolved [1,0]', 'payout': 2555.0, 'realized_pnl': 1305.0,
   'note': 'first 1h bar <=2250: 2026-10-29 20:00 UTC; low since touch 2174.08 (10-30 01:00 UTC); zero 1h bars <=2000 in last 10d'}
 ],
 'portfolio_pnl': {
  'realized': 1305.0, 'unrealized_bid': round(eth2k['unrealized_bid'] + btc65['unrealized_bid'], 2),
  'open_realizable_cash': round(eth2k['realizable_cash_bid_walk'] + btc65['realizable_cash_bid_walk'], 2),
  'open_cost': 620.0, 'cap_status': 'AT CAP $1,870/$1,900 - report-only'
 },

 '2_spot_vol_flows': {
  'ETH_spot_binance': S, 'BTC_spot_binance': spot['BTC'],
  'ETH_vol_daily_6hRMS': {'7d': vol['ETH']['7d'], '30d': vol['ETH']['30d'], '60d': vol['ETH']['60d']},
  'BTC_vol_daily_6hRMS': {'7d': vol['BTC']['7d'], '30d': vol['BTC']['30d'], '60d': vol['BTC']['60d']},
  'vol_read': 'ETH 30d 2.43%/d vs 7d 1.86%/d - realized vol compressing after the Oct 29-30 dip; 60d 2.29%.',
  'ETH_distance_to_2000': {'usd': dist_usd, 'pct': dist_pct, 'sigma_30d_over_T': sig_terms,
    'calc': 'ln(2254.87/2000) / (2.429% * sqrt(58.9d)) = 0.644 sigma to Dec 31; 1.12 sigma to Fri Nov 7',
    'low_since_2250_touch': lows['low_10d_1h'][0], 'low_at': lows['low_10d_1h'][1],
    'bars_le_2000_last_10d': lows['bars_below_2000_last_10d_1h']},
  'etf_flows': {
   'Mon_Oct26': {'BTC_USD_M': +110.3, 'ETH_USD_M': -88.6, 'ETH_detail': 'ETHA -104.7, FETH +16.1'},
   'Tue_Oct27': {'BTC_USD_M': +176.0, 'ETH_detail_fund': 'IBIT +151.5', 'ETH_USD_M': -60.2,
                 'ETH_detail': 'ETHA -93.3, FETH +28.6'},
   'rest_of_week': 'Wed Oct 28 BTC +137.3 (3-day streak +423.6M); Thu Oct 29 BTC +17.1 / ETH -105.5; Fri Oct 30 ETH -155.7',
   'week_Oct26_30': 'ETH ~-431M (5th consecutive weekly outflow); BTC modest net positive',
   'October_month': 'BTC ~-515M month-end (IBIT +931M); ETH ~-1.08B worst month of 2026',
   'Mon_Nov2_status': 'NOT PUBLISHED at scan time (Nov 3 02:30 UTC = Mon 21:30 ET); Tue Nov 3 US session not yet open',
   'read': 'Persistent ETH ETF bleed is the structural supply overhang behind the ETH-2000 thesis; BTC flows positive all week support the BTC-65k NO hold.'
  },
  'sources': ['farside.co.uk/btc', 'farside.co.uk/eth (via @FarsideUK)', 'sosovalue.com',
              'binance.com square daily flow posts Oct 26/27/29', 'altcoinbuzz.io Oct 27 inflows',
              'cryptopolitan.com Oct outflows', 'cryptoticker.de Oct month-end']
 },

 '3_report_only_edges': {
  'criteria': '>=8c model edge vs executable ask, liquidity >= $10k; fair = 30d-vol drifted first-passage (convention B); team at cap so REPORT-ONLY',
  'n_qualifying': len(qual),
  'top5_new_ideas': [
   {'q': t['q'], 'side': t['best_edge_side'], 'edge_c': t['best_edge'],
    'fair_yes': t['fair_yes'], 'yes_bid_ask': [t['yes_bid'], t['yes_ask']], 'liq': t['liq']} for t in new_ideas[:5]
  ],
  'held_market_edges': [
   {'q': t['q'], 'side': t['best_edge_side'], 'edge_c': t['best_edge'],
    'fair_yes': t['fair_yes'], 'yes_bid_ask': [t['yes_bid'], t['yes_ask']], 'liq': t['liq']} for t in held_edge_rows
  ],
  'caveat': ('All large edges are one model-vs-market disagreement family: market prices fat BTC crash tails '
             '(dip 55k/60k NO cheap vs lognormal) and strong bullish drift on long-dated hit markets (100k/150k '
             '2027 NO cheap vs zero-drift GBM). Zero-drift GBM ignores drift, so long-dated hit-market NO edges '
             'are the least trustworthy; the 2026 dip-barrier NOs have tight books and consistent r19-sign edges.'),
  'full_table': 'round29/raw/crypto_scan.json -> report_only_qualifying (11 rows) / report_only_table_all'
 },

 '4_hold_exit': {
  'ETH_2000_YES': {
   'action': 'HOLD',
   'basis': {
    'exit_now': eth2k['realizable_cash_bid_walk'],
    'ev_hold_model_30d': ev_hold(hz['Dec31_2359']['ETH_2000']['30d']['B'], 1208),
    'ev_hold_model_30d_A': ev_hold(hz['Dec31_2359']['ETH_2000']['30d']['A'], 1208),
    'ev_hold_market_implied': ev_hold(0.445, 1208),
    'remaining_edge_vs_bid_c': round(hz['Dec31_2359']['ETH_2000']['30d']['B'] - eth2k['bid'], 3),
    'remaining_edge_vs_ask_c': round(hz['Dec31_2359']['ETH_2000']['30d']['B'] - eth2k['ask'], 3)},
   'reasoning': ('Exit banks +$180.7 (+56.5%). Model fair to Dec 31 = 0.520-0.551 (30d A/B; 0.496-0.526 on 60d vol; '
                 '0.400-0.424 on 7d vol) vs bid 0.43-0.44: +8.6c to +11.1c remaining edge, EV $628-666 vs $501 exit. '
                 'Even at the market-implied 0.445, hold EV $537.6 > $501 exit (bid-walk costs ~1.6c/sh in depth). '
                 'Hold weakly dominates exit under BOTH model and market probability. '
                 'Touch checkpoints: Fri Nov 7 2.7% / Nov 14 16.2% / Dec 1 38.0% (30d B).'),
   'exit_triggers': ('(a) ETH spot <= 2075: exit into strength - bid will be >=0.65, remaining edge gone; '
                     '(b) YES bid >= 0.60 with spot still >5% above barrier: trim, edge realized; '
                     '(c) ETH >= 2450 sustained (reclaim of pre-dip range): fair decays toward 0.40, edge < 3c, exit; '
                     '(d) another -5%+ ETH ETF outflow week: reassess upward risk, do NOT panic-exit into a thin bid.')
  },
  'BTC_65k_NO': {
   'action': 'HOLD',
   'basis': {
    'exit_now': btc65['realizable_cash_bid_walk'],
    'ev_hold_model_30d': ev_hold(1 - hz['Dec31_2359']['BTC_65k_yes']['30d']['B'], 384.6),
    'ev_hold_model_30d_A': ev_hold(1 - hz['Dec31_2359']['BTC_65k_yes']['30d']['A'], 384.6),
    'ev_hold_market_implied': ev_hold(1 - 0.285, 384.6),
    'remaining_edge_vs_bid_c': round((1 - hz['Dec31_2359']['BTC_65k_yes']['30d']['B']) - btc65['bid'], 3)},
   'reasoning': ('Exit realizes -$26.9 (-9.0%) - the ONLY certain-loss action available. Barrier needs BTC -15.5% '
                 '(spot 76,936 vs 65,000; 10d low 76,326). Model P(touch)=0.180-0.196 (30d A/B) -> NO fair 0.804-0.820 '
                 'vs bid 0.71: +9.4c remaining edge, EV hold $309-315 vs $273 exit (+$36-42). At market-implied YES 0.285, '
                 'EV hold $275 ~= exit $273 - market-implied case is a wash, so entire case rests on the model, which has '
                 'persistently priced this YES 8-10c below market since r19 (fat-tail premium). Position small ($300); '
                 'BTC ETF flows positive all of Oct 26-28 (+$423.6M streak) - no crash-flow signal to validate the fat tail.'),
   'exit_triggers': ('(a) BTC < 72,000: NO bid likely <= 0.62, edge-vs-realized-loss tradeoff deteriorates - reassess/exit; '
                     '(b) BTC ETF flip to heavy sustained outflows (>-$500M over 3 sessions): exit; '
                     '(c) NO bid >= 0.85 with >30d left: take profit into strength; '
                     '(d) hold through Dec 31 otherwise - full payout $384.6 (+$84.6, +28.2% on cost).')
  },
  'overall': ('No exits warranted at current books: both positions carry +9-11c model edge vs bid vs ~1-2c exit friction. '
              'Team at cap: all section-3 edges report-only. Next review: after Mon Nov 2 / Tue Nov 3 ETF prints and at '
              'Fri Nov 7 checkpoint (ETH 1-week touch prob only 2.7%).')
 }
}

json.dump(rec, open(OUT, 'w'), indent=1)
print('WROTE', OUT)
print('ETH dist to 2000: $', dist_usd, '=', dist_pct, '% |', sig_terms, 'sigma (30d, T=', T, 'd)')
print('new ideas:', len(new_ideas), '| held edges:', len(held_edge_rows))
