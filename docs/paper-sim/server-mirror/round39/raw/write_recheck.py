import json, time
NOW = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

held = json.load(open('/home/ubuntu/paper-sim/round39/raw/held_fresh.json'))
near = json.load(open('/home/ubuntu/paper-sim/round39/raw/near_miss_fresh.json'))
fri  = json.load(open('/home/ubuntu/paper-sim/round39/raw/espn_friday_20261106.json'))

ENTRIES = [
 ('62',  '6111575', 'Alaves TT O0.5 OVER',      250.0, 0.6277, 'La Liga Sevilla v Alaves Fri 2026-11-06 20:00Z'),
 ('63',  '6237007', 'Villa-win NO',             150.0, 0.70,   'EPL ManUtd v Villa Sun 2026-11-08 16:30Z'),
 ('64',  '6176123', 'Mainz-Bayern BTTS YES',    250.0, 0.6578, 'Bundesliga Sat 2026-11-07 14:30Z'),
 ('65',  '6180838', 'Osasuna TT O0.5 OVER',     250.0, 0.6611, 'La Liga Sat 2026-11-07 17:30Z'),
 ('66',  '6180689', 'Valencia-RM U3.5 UNDER',   250.0, 0.56,   'La Liga Sat 2026-11-07 20:00Z'),
 ('67',  '6236736', 'Monaco-win NO',            150.0, 0.44,   'Ligue 1 Le Mans v Monaco Sun 2026-11-08 16:15Z'),
 ('68',  '6239548', 'Brest-Lyon O2.5 OVER',     250.0, 0.51,   'Ligue 1 Sun 2026-11-08 16:15Z'),
]
ENTRY_BID_DEPTH_2C = {'6176123':2486.0,'6180838':1092.0,'6180689':5524.0,'6236736':3225.0,'6237007':34132.0,'6239548':1263.0}
SIDE_IDX = {'6111575':0,'6237007':1,'6176123':0,'6180838':0,'6180689':1,'6236736':1,'6239548':0}
KEYMAP = {'6111575':'62_alaves_tt_o05','6237007':'63_villa_win_no','6176123':'64_mainz_bayern_btts_yes',
          '6180838':'65_osasuna_tt_o05','6180689':'66_valencia_rm_u35','6236736':'67_monaco_win_no',
          '6239548':'68_brest_lyon_o25'}

held_marks = []
tot_unreal = 0.0
realized = 0.0
for tag, mid, label, stake, entry, note in ENTRIES:
    h = held[KEYMAP[mid]]
    outs = h['outcomes']
    if isinstance(outs, str):
        outs = json.loads(outs)
    rawp = h['outcomePrices']
    prices = [float(x) for x in (json.loads(rawp) if isinstance(rawp, str) else rawp)]
    idx = SIDE_IDX[mid]
    mark = prices[idx]
    shares = stake/entry
    if h['closed']:
        mtm = (mark-entry)*shares
        realized += mtm
        status = 'RESOLVED_LOST' if mark==0 else 'RESOLVED_WON'
        bid, depth2c_now = None, None
    else:
        mtm = (mark-entry)*shares
        tot_unreal += mtm
        bookside = h['books'][idx]
        bb = bookside['best_bid']
        depth2c_now = round(sum(t['s'] for t in bookside['top_bids'] if t['p'] >= bb-0.02),1)
        bid = bb
        status = 'OPEN'
    rec = {
      'tag': '#'+tag, 'market_id': int(mid), 'position': label, 'stake_usd': stake,
      'entry': entry, 'mark': mark, 'shares': round(shares,2),
      'mtm_usd': round(mtm,2), 'delta_c': round((mark-entry)*100,2),
      'exit_bid': bid, 'bid_depth_2c_now': depth2c_now,
      'bid_depth_2c_entry_r38': ENTRY_BID_DEPTH_2C.get(mid),
      'bid_depth_ratio_vs_entry': (round(depth2c_now/ENTRY_BID_DEPTH_2C[mid],2) if (depth2c_now is not None and mid in ENTRY_BID_DEPTH_2C) else None),
      'adverse_ge_5c': (mark-entry) <= -0.05,
      'status': status, 'fixture': note, 'fetched_utc': h['fetched_utc'],
      'outcome_side': outs[idx],
    }
    held_marks.append(rec)

flip = {
 'Arsenal TT U1.5': {'flip_possible': 'CONDITIONAL-ONLY',
   'why': 'Numeric gates ALL PASS at fresh prices (net +12.61c). Blocker is news-concordance only. Fresh scoreline sweep: Sportsmole 2-0 and SportsGambler 3-1 still contradict Arsenal<=1 (Squawka 1-0 concords but is minority). Stays dead unless preview consensus shifts to <=1-goal Arsenal scorelines.'},
 'Arsenal TT U2.5': {'flip_possible': 'NO', 'why': 'var 6.07c > 6.00c bar. Variant spread is a frozen model property; xG base unchanged (no matches since Nov 1/2; pointer untouched since Nov-5 23:49Z). Odds cannot fix it.'},
 'ManUtd ML home': {'flip_possible': 'NO', 'why': 'var 6.30c > 6c. Model property, unchanged.'},
 'Sunderland O2.5': {'flip_possible': 'NO', 'why': 'var 12.84c > 6c (model property); fresh net edge also shrank to +6.48c as ask rose 0.53->0.54.'},
 'Ipswich O2.5': {'flip_possible': 'NO', 'why': 'var 8.66c > 6c. Model property, unchanged.'},
 'Palace-Liverpool away_no': {'flip_possible': 'NO', 'why': 'var 14.89c > 6c. The +20c edge persists at unchanged 0.39 ask but the 10 variants disagree on the away_no probability by ~15c; only a model change (not an odds change) could revive it.'},
 'Preston ML home': {'flip_possible': 'NO', 'why': 'Numeric passes at fresh prices (net +9.33c, var 5.81c) but killed by (a) news-concordance: fresh Sportsmole 1-3 Southampton, Saints 56-63pct favorites, Preston lost 4 of 5; (b) frozen gate-E Championship 1X2 model limitation. Gate-E cannot be waived by odds.'},
 'Blackburn-WHam TT U1.5 away': {'flip_possible': 'NO', 'why': 'Triple fail: var 42.18c, worst -10.66c, liq 1.7k<5k USD. Fresh Sportsmole 1-3 West Ham also contradicts West Ham U1.5. Dead on model + liquidity + news simultaneously.'},
}
near_out = []
for n in near:
    g = n['fresh_gates']; f = n['fresh']
    near_out.append({
      'market': n['name'], 'market_id': n['market_id'], 'side': n['side'],
      'fresh_best_ask': f['best_ask'], 'fresh_vwap250': (round(g['walk_vwap250'],4) if g['walk_vwap250'] else None),
      'r38_ask': n['r38']['ask'],
      'fresh_edge_net': round(g['exec_edge_net'],4), 'r38_edge_net': n['r38']['exec_edge'],
      'fresh_worst': round(g['worst_variant_edge'],4), 'var_spread': round(g['variant_spread'],4),
      'gate_verdict': 'PASS' if all(v for k,v in g['checks'].items() if k!='news_concordant') else 'FAIL',
      'failed_gates': [k for k,v in g['checks'].items() if not v],
      'fresh_checks': g['checks'],
      'flip_possible': flip[n['name']]['flip_possible'],
      'flip_reason': flip[n['name']]['why'],
      'model_frozen': True,
    })

friday_games = []
NAME = {'eng.1':'EPL','eng.2':'Championship','ger.1':'Bundesliga','fra.1':'Ligue 1','esp.1':'La Liga','ita.1':'Serie A'}
for code, evs in fri.items():
    for e in evs:
        d = e['date']
        hh = int(d[11:13])
        if 13 <= hh <= 23 and d[:10]=='2026-11-06':
            sc = e.get('score') or {}
            hs = sc.get('home',{}).get('score') if isinstance(sc.get('home'),dict) else sc.get('home')
            as_ = sc.get('away',{}).get('score') if isinstance(sc.get('away'),dict) else sc.get('away')
            friday_games.append({
              'league': NAME[code], 'kickoff_utc': d, 'fixture': e['name'],
              'status': e.get('status'), 'final_score': '%s-%s'%(hs,as_),
              'in_task_window_1330_2400Z': True,
              'covered_by_r38_discovery': False,
              'note': 'r38 discovery range was Sat-Sun only; this Friday fixture was outside it. Already finished (FT) at re-check execution Sat 06:5xZ - NOT enterable, no model run for entry purposes.',
              'relates_to_held': ('#62 Alaves TT O0.5 OVER lost: Alaves scored 0' if 'Alav' in e['name'] else None),
            })

saturday_news = [
 {'fixture':'Mainz 05 vs Bayern Munich (Bundesliga, Sat 14:30Z)', 'position':'#64 BTTS YES 250 USD @0.6578',
  'findings':'Mainz: Mwene (5th yellow) and Posch (card suspension) both OUT - backline weakened; Silas out long-term (leg fracture) - attack weakened; Widmer/Gruber expected to deputize. Bayern: Kane back from issue (sub appearance midweek, scored), predicted to START; contracted to 2029; Kompany recovering. Last H2H 4-3 Bayern. Bayern unbeaten in Bundesliga.',
  'concordance_verdict':'MIXED-NEUTRAL, HOLD. Bayern-scoring side reinforced (Kane start + Mainz CB absences); Mainz-scoring side dented by Silas loss but home fixture keeps it balanced. Mark 0.645 (-1.3c) consistent; no exit trigger.',
  'sources':['rotowire.com Mwene suspended','bavarianfootballworks.com full coverage','onefootball.com preview']},
 {'fixture':'Osasuna vs Athletic Club (La Liga, Sat 17:30Z)', 'position':'#65 Osasuna TT O0.5 OVER 250 USD @0.6611',
  'findings':'Budimir FIT and predicted to start; scored in each of last two home games at El Sadar and in 64pct of Osasuna games this season. Osasuna missing Oroz (hamstring), Herrando, Del Castillo; Athletic missing several. Sportsmole predicted XI includes Budimir 4-3-3.',
  'concordance_verdict':'CONCORDANT, HOLD. Primary scorer fit + home form directly supports Over 0.5 team total.',
  'sources':['sportsmole.co.uk preview 608501','sports.yahoo.com preview','fotmob.com match page']},
 {'fixture':'Valencia vs Real Madrid (La Liga, Sat 20:00Z)', 'position':'#66 U3.5 UNDER 250 USD @0.56',
  'findings':'RM squad list heavy on back-line rotation options (Konate, Dumfries, Carreras, Cucurella available); staff unhappy with Sat scheduling compressing UCL rest so rotation expected, front line still featured in predicted XI. Sportsmole prediction 1-2 RM; likeliest scorelines 0-2 (12.2pct), 0-1 (12.1pct), 1-2, 1-1 draw (10.6pct) - all <=3 goals.',
  'concordance_verdict':'CONCORDANT, HOLD. Predicted scoreline distribution entirely under 3.5; rotation risk skews to fewer goals, not more.',
  'sources':['sportsmole.co.uk preview 608525 + match page 239889','Yahoo squad announcement']},
 {'fixture':'Arsenal vs Hull City (EPL, Sat 15:00Z)', 'position':'near-miss Arsenal TT U1.5 (numeric PASS at fresh prices)',
  'findings':'Sportsmole 2-0 Arsenal; SportsGambler 3-1 Arsenal; Squawka 1-0 Arsenal. Arsenal top of EPL; Hull winless in 5, expected 5-4-1 low block. Common angle BTTS-No.',
  'concordance_verdict':'NOT CONCORDANT (2 of 3 published scorelines have Arsenal scoring 2+). Near-miss stays dead despite fresh net edge +12.61c.',
  'sources':['sportsmole.co.uk preview 608461','sportsgambler.com tips']},
 {'fixture':'Preston vs Southampton (Championship, Sat 15:00Z)', 'position':'near-miss Preston ML home',
  'findings':'Sportsmole 1-3 Southampton; Southampton 56-63pct favorites; Preston lost 4 of last 5; Saints scored 25 more goals this season.',
  'concordance_verdict':'NOT CONCORDANT + gate-E (frozen Championship 1X2 limitation). Dead.',
  'sources':['sportsmole.co.uk preview 608543']},
 {'fixture':'Blackburn vs West Ham (Championship, Sat 15:00Z)', 'position':'near-miss West Ham TT U1.5',
  'findings':'Sportsmole 1-3 West Ham; Parker expected to make four changes after chaotic Cardiff result; West Ham favored 42-61pct.',
  'concordance_verdict':'NOT CONCORDANT (WHam predicted 3 goals) + var 42c + liq fail. Dead multiple ways.',
  'sources':['sportsmole.co.uk preview 608439']},
]

out = {
 'round':'39C', 'kind':'drift/lineup re-check of round-38 slate (paper only, no new bets, no DB writes)',
 'executed_utc': NOW,
 'dispatch_note':'Dispatch was written for Fri 2026-11-06 ~13:30Z but executed Sat 2026-11-07 06:50-07:10Z. All six Friday fixtures had already finished; Friday candidate entry is moot.',
 'model_base':'FROZEN - understat_latest_pointer unchanged (pointed_at 2026-11-05T23:49:59Z; FotMob merge through Nov 1/2; no league matches Nov 3-6 international break). Variant spreads and medians from round-38 remain valid.',
 'library':'polymarket_alpha_lab.papersim.gates.evaluate_candidate / walk_book / fee_cost (imported, never re-derived); library selfcheck PASS 10/10 re-run this session.',
 'held_marks': held_marks,
 'held_summary':{
   'realized_usd': round(realized,2),
   'unrealized_usd': round(tot_unreal,2),
   'total_mtm_usd': round(realized+tot_unreal,2),
   'adverse_ge_5c_positions': [r['tag'] for r in held_marks if r['adverse_ge_5c']],
   'exit_bid_collapses': [r['tag'] for r in held_marks if r.get('bid_depth_ratio_vs_entry') is not None and r['bid_depth_ratio_vs_entry']<0.5],
   'resolved':['#62 Alaves TT O0.5 OVER LOST (Sevilla 0-0 Alaves; Alaves scored 0; Gamma resolved Over=0) - paper loss -250.00 USD'],
 },
 'near_miss_recheck': near_out,
 'friday_games': friday_games,
 'friday_summary':'Six Friday fixtures existed (all kicked 19:30-20:00Z Nov 6, inside the task window 13:30-24:00Z): EPL Everton-Coventry, Champ Derby-Bolton, Bundesliga HSV-Gladbach, Ligue 1 Toulouse-Strasbourg, La Liga Sevilla-Alaves (held #62), Serie A Venezia-Udinese. Five were outside r38 discovery (Sat-Sun only) - a genuine slate gap - but all finished FT before this re-check executed, so no entry was possible and no model run for entry purposes was performed.',
 'saturday_news': saturday_news,
 'raw_files':['round39/raw/held_fresh.json','round39/raw/near_miss_fresh.json','round39/raw/espn_friday_20261106.json'],
 'paper_only': True,
}
json.dump(out, open('/home/ubuntu/paper-sim/round39/big5_recheck.json','w'), indent=1)
print('WROTE /home/ubuntu/paper-sim/round39/big5_recheck.json')
for r in held_marks:
    print('%-4s %-24s entry %.4f mark %.3f  mtm %+.2f  %s' % (r['tag'], r['position'], r['entry'], r['mark'], r['mtm_usd'], r['status']))
print('realized', round(realized,2), 'unrealized', round(tot_unreal,2))
