"""Round-21 Serie A Wed sub-scan finalize: merge model + books + lineups -> scan + candidates JSON."""
import json, time

RAW = '/home/ubuntu/paper-sim/round21/raw'
model = json.load(open(RAW + '/seriea_model21.json'))
books = json.load(open(RAW + '/seriea_books21.json'))
NOW = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

LINEUPS = {
 'AC Milan vs. Bologna FC 1909': {
  'home': 'ROTATION CONFIRMED (Amorim, Sat derby vs Inter + rotation hints). Sports Mole predicted XI: Maignan; Tomori, De Winter, Pavlovic, Bartesaghi; Hutchinson, Jashari, Musah, Cisse; Pulisic, Ramos. Milan scored 2+ in every home league game this season. Confirmed XI lands ~16:30Z.',
  'away': 'OUT: Orsolini, Piccoli, Holm (long-term, per r20 note, unchanged). Odgaard leads line; Pobega vs old club. Predicted 3-4-3: Skorupski; Darmian, Casale, Theate; Zortea, Ferguson, Pobega, Miranda; Bernardeschi, Odgaard, Cambiaghi.',
  'source': 'sportsmole.co.uk preview 607749 (2 days pre-match); cultofcalcio.com r20 note retained for Bologna'},
 'Parma Calcio 1913 vs. Udinese Calcio': {
  'home': 'Pavoletti doubtful (knee), Frigan among injury concerns (Sportskeeda). Poor form 1W1D3L last 5, ~0.8 goals/game (r20).',
  'away': 'OUT/doubt: Zanoli (unknown), Bayo (hamstring), Solet (muscular) - Solet was a r20 predicted key, now doubtful; weakens both boxes. Form 0W1D4L last 5. Predicted XI (SportsGambler): Okoye; Abankwah, ... 3-4-2-1.',
  'source': 'Yahoo Sports/SportsGambler/Sportskeeda previews 2026-10-28; r20 bettingstats note retained'},
 'Venezia FC vs. FC Internazionale Milano': {
  'home': 'Busio (captain) expected back. OUT: Sverko, Franjic, Adorante; Correia fitness doubt. Predicted 3-5-2: Stankovic; Schingtienne, Halhal, Moreno; Hainaut, Perez, Basic, Sohm, Haps; Yeboah, Adams.',
  'away': 'LAUTARO MARTINEZ OUT (injured); Thuram may be rested (Chivu: could be rested in midweek before derby + Feyenoord UCL); also out: Luis Henrique, Pavard, Stones, Jones (closest to return, likely misses trip). Coach Chivu. Predicted XI: J. Martinez; Bisseck, Akanji, Augusto; Spence, Sucic, A. Stankovic, Zielinski, Dimarco; Bonny, Esposito. Sports Mole predicts 0-3.',
  'source': 'sportsmole.co.uk Venezia vs Inter preview 607740 (team news extracted 2026-10-28)'},
 'Genoa CFC vs. Juventus FC': {
  'home': 'De Rossi; no fresh injuries per r20 note; expected near the XI that beat Venezia 1-0. GenovaToday probabili formazioni (publ. matchday): Bijlow; Marcandelli, Ostigard, Vasquez; Ellertsson, Messias, Frendrup, Traore, Puczka.',
  'away': 'Juve (Spalletti) missing 4 attackers per standing task/r20 note: Yildiz, Thuram, Gonzalez, Conceicao. Italian sources (genovatoday/thefalse9) suggest Woltemade leads line with a Yildiz mention in some probabili formazioni - conflict flagged; treat the 4-attacker absence list as primary until confirmed XI ~16:30Z. Won 2-0 at Lecce Sunday.',
  'source': 'genovatoday.it probabili formazioni 2026 (5h pre-extraction); r20 footballpredictions note retained; conflict noted'},
 'AC Monza vs. SSC Napoli': {
  'home': 'OUT: Pessina (captain), Ziolkowski; Maye doubtful. Predicted 3-4-2-1: Tornqvist; Kouadio, Goglichidze, Carboni; Birindelli, Akinsanmiro, Ondoa, Mangas; Folorunsho, Robinson; Varela.',
  'away': 'OUT: Buongiorno, Neres, Favasuli, Alisson Santos; NEW: Badiashile (muscular, picked up at weekend - could miss this + Porto/Juve trips); Rrahmani back from illness, replaces Badiashile next to Marin. De Bruyne STARTS (predicted XI, leads Serie A scoring 3 goals). McTominay fit - braces in each of last two matches. Coach Allegri TOUCHLINE BANNED (sent off vs Roma). Predicted: Meret; Di Lorenzo, Marin, Rrahmani, Olivera; Anguissa, De Bruyne, McTominay; Politano, Vergara; Hojlund. Sports Mole predicts 1-2.',
  'source': 'sportsmole.co.uk Monza vs Napoli preview 607725 (extracted 2026-10-28); Yahoo Sports preview'},
 'Frosinone Calcio vs. US Lecce': {'home': 'report-only (Thu Oct-29, outside window)', 'away': 'report-only', 'source': None},
 'ACF Fiorentina vs. Atalanta BC': {'home': 'report-only (Thu Oct-29, outside window)', 'away': 'report-only', 'source': None},
}

MATCH_LABELS = {
 'AC Milan vs. Bologna FC 1909': 'Milan-Bologna',
 'Parma Calcio 1913 vs. Udinese Calcio': 'Parma-Udinese',
 'Venezia FC vs. FC Internazionale Milano': 'Venezia-Inter',
 'Genoa CFC vs. Juventus FC': 'Genoa-Juventus',
 'AC Monza vs. SSC Napoli': 'Monza-Napoli',
 'Frosinone Calcio vs. US Lecce': 'Frosinone-Lecce',
 'ACF Fiorentina vs. Atalanta BC': 'Fiorentina-Atalanta',
}

# context lines from r19/r20 sub-scan brief for the delta table
CONTEXT = {
 ('AC Milan vs. Bologna FC 1909', 'AC Milan vs. Bologna FC 1909: Bologna FC 1909 O/U 0.5'): 'r19 top edge Over +8.7c (var 7.8c)',
 ('AC Milan vs. Bologna FC 1909', 'AC Milan vs. Bologna FC 1909: Both Teams to Score'): 'r19 edge Over +7.1c',
 ('Parma Calcio 1913 vs. Udinese Calcio', 'Parma Calcio 1913 vs. Udinese Calcio: O/U 2.5'): 'r19 edge Over +9.0c (var 17.7c)',
 ('Genoa CFC vs. Juventus FC', 'Genoa CFC vs. Juventus FC: Genoa CFC O/U 1.5'): 'r20 edge Over +4.5c',
 ('AC Monza vs. SSC Napoli', 'AC Monza vs. SSC Napoli: SSC Napoli O/U 1.5'): 'r19/20 edge Under +8.1c (var 32c)',
}

per_game = []
for base, rec in model['matches'].items():
    pg = {'match': base, 'label': MATCH_LABELS[base], 'kickoff_utc': rec['kickoff'],
          'in_window': rec['in_window'],
          'lambda_home': rec['lambda_home'], 'lambda_away': rec['lambda_away'],
          'delta_lambda_home_vs_r20': rec['delta_lambda_home'], 'delta_lambda_away_vs_r20': rec['delta_lambda_away'],
          'model_1x2_med': rec['model_1x2_med'], 'vol24': rec['vol24'],
          'lineups': LINEUPS.get(base),
          'top_model_edges': []}
    mrows = []
    for q, mm in rec['markets'].items():
        try: mid = float(mm.get('mid'))
        except (TypeError, ValueError): continue
        if (mm.get('liq') or 0) < 5000: continue  # gate floor; excludes stale far-tail quotes
        eo = round(mm['p0_med'] - mid, 4)
        mrows.append((max(abs(eo), abs(-eo)), q, mm, eo))
    mrows.sort(key=lambda r: -r[0])
    for _, q, mm, eo in mrows[:5]:
        side = 'Over' if eo > 0 else 'Under'
        pg['top_model_edges'].append({'market': q, 'side': side, 'mid': mm['mid'], 'liq': mm['liq'],
                                      'p0_med': mm['p0_med'], 'var_spread': mm['var_spread'],
                                      'mid_edge': eo,
                                      'delta_p0_vs_r20': mm.get('delta_p0_med'),
                                      'delta_varspread_vs_r20': mm.get('delta_var_spread'),
                                      'context_note': CONTEXT.get((base, q))})
    per_game.append(pg)

# gate application on booked non-spread markets
cands = []
flagged = []
spread_flags = []
for b in books:
    e = b['edges']; vs = b['var_spread']
    if b['kind'] == 'spread':
        spread_flags.append({'match': b['match'], 'market': b['q'],
                             'side': 'Over', 'exec_edge': e.get('over_exec'), 'worst_var_edge': e.get('over_worst'),
                             'var_spread': vs, 'liq': b['liq'],
                             'note': 'spread markets flagged-only per hard rules; not candidate-eligible'})
        continue
    side_best = None
    for side in ('over', 'under'):
        ex = e.get(side + '_exec'); wo = e.get(side + '_worst')
        if ex is None: continue
        if side_best is None or ex > side_best[1]:
            side_best = (side, ex, wo)
    if not side_best: continue
    side, ex, wo = side_best
    gates = {'variant_spread<=6c': vs <= 0.06 + 1e-9, 'worst>=+4c': wo >= 0.04,
             'exec>=+5c': ex >= 0.05, 'liq>=5k': (b['liq'] or 0) >= 5000}
    row = {'match': b['match'], 'market': b['q'], 'side': side.capitalize(),
           'exec_ask': b.get('exec_ask_over') if side == 'over' else b.get('exec_ask_under'),
           'exit_bid': b.get('exit_bid_over') if side == 'over' else b.get('exit_bid_under'),
           'exec_edge': ex, 'worst_var_edge': wo, 'var_spread': vs, 'liq': b['liq'],
           'gates': gates, 'all_pass': all(gates.values()),
           'r20_compare': {'r20_p0': b.get('r20_p0'), 'r20_var_spread': b.get('r20_vs')}}
    if all(gates.values()):
        cands.append(row)
    else:
        fails = [k for k, v in gates.items() if not v]
        row['reason'] = 'FAIL: ' + ', '.join(fails)
        flagged.append(row)

# model-side var-gate fails on r19/r20 context lines (cannot be candidates regardless of exec)
m = model['matches']
for base, q, note in [
  ('AC Monza vs. SSC Napoli', 'AC Monza vs. SSC Napoli: AC Monza O/U 1.5', 'new top mid-edge +11.0c Over'),
  ('Venezia FC vs. FC Internazionale Milano', 'Venezia FC vs. FC Internazionale Milano: Venezia FC O/U 1.5', 'mid-edge +10.5c Over'),
  ('AC Monza vs. SSC Napoli', 'AC Monza vs. SSC Napoli: SSC Napoli O/U 1.5', 'mid-edge +9.1c Under (r19: +8.1c)'),
  ('AC Milan vs. Bologna FC 1909', 'AC Milan vs. Bologna FC 1909: Bologna FC 1909 O/U 1.5', 'mid-edge +8.3c Over'),
  ('Parma Calcio 1913 vs. Udinese Calcio', 'Parma Calcio 1913 vs. Udinese Calcio: O/U 2.5', 'mid-edge +8.0c Over (r19: +9.0c)'),
  ('AC Milan vs. Bologna FC 1909', 'AC Milan vs. Bologna FC 1909: Bologna FC 1909 O/U 0.5', 'mid-edge +5.7c Over (r19: +8.7c) - market corrected'),
  ('AC Milan vs. Bologna FC 1909', 'AC Milan vs. Bologna FC 1909: Both Teams to Score', 'mid-edge +4.6c Over (r19: +7.1c)'),
  ('Genoa CFC vs. Juventus FC', 'Genoa CFC vs. Juventus FC: Genoa CFC O/U 1.5', 'mid-edge +4.5c Over (unchanged)'),
]:
    mm = m[base]['markets'].get(q)
    if not mm: continue
    try: mid = float(mm.get('mid'))
    except (TypeError, ValueError): mid = None
    flagged.append({'match': base, 'market': q, 'side': 'Over' if (mm['p0_med'] - (mid or 0)) > 0 else 'Under',
                    'mid': mid, 'p0_med': mm['p0_med'], 'var_spread': mm['var_spread'],
                    'liq': mm['liq'], 'delta_varspread_vs_r20': mm.get('delta_var_spread'),
                    'reason': 'FAIL: variant_spread<=6c (model-side; var unchanged vs r20, exec not reachable to rescue)',
                    'note': note})

scan = {'scan': 'seriea', 'round': 21, 'paper_only': True, 'sub_scan_generated_utc': NOW,
 'window_utc': {'lo': '2026-10-28T01:15:00Z', 'hi': '2026-10-29T01:15:00Z',
                'games': 'Milan-Bologna 17:30Z, Parma-Udinese 17:30Z, Venezia-Inter 17:30Z, Genoa-Juventus 19:45Z, Monza-Napoli 19:45Z; Thu Frosinone-Lecce / Fiorentina-Atalanta report-only'},
 'method': '10-variant xG-Poisson (r15/r19/r20 methodology: 6 blends + current-only + last-only + 2 cross-shrinks; DC rho -0.1 variant), team totals included; Gamma tag sea sweep; CLOB $250-VWAP exec.',
 'xg_refresh': {
   'file': '/home/ubuntu/paper-sim/round21/raw/xg_understat_21.json',
   'serie_a_new_matches_vs_r20_file': [
     '2026-10-27 17:30 Sassuolo 2-6 Lazio (xG 1.067-4.355)',
     '2026-10-27 19:45 Roma 4-2 Cagliari (xG 3.853-2.479)',
     '2026-10-27 19:45 Torino 1-3 Como (xG 1.451-2.708)'],
   'serie_a_last': '2026-10-27 19:45 (Roma 4-2 Cagliari / Torino 1-3 Como)',
   'top_rating_movers_blend_w05_p08': [
     'Lazio attack 1.371->1.454 (+0.083)', 'Sassuolo defence 1.630->1.706 (+0.076)',
     'Cagliari defence 1.603->1.666 (+0.063)', 'Roma attack 1.803->1.860 (+0.057)',
     'Torino defence 1.466->1.500 (+0.035)', 'Como attack 1.800->1.825 (+0.025)'],
   'key_finding': 'All 6 moved teams (Lazio, Roma, Como, Sassuolo, Cagliari, Torino) are ABSENT from every Wednesday fixture. All 7 modelled lambdas have delta +0.000 vs r20 and every per-market delta_p0/delta_var_spread = 0.000. The spread-compression hypothesis is structurally impossible for this fixture set: Tuesday data cannot compress Wednesday variant spreads. Only live Gamma/CLOB prices moved since the r20 scan.'},
 'hard_rules': 'match_winner SUSPENDED; spreads flagged-only; gates var<=6c AND worst>=+4c AND exec>=+5c (CLOB $250-VWAP) AND liq>=$5k; max 2 candidates.',
 'per_game': per_game,
 'books_checked': [{'match': b['match'], 'market': b['q'], 'kind': b['kind'],
                    'exec_ask_over': b.get('exec_ask_over'), 'exec_ask_under': b.get('exec_ask_under'),
                    'exit_bid_over': b.get('exit_bid_over'), 'exit_bid_under': b.get('exit_bid_under'),
                    'edges': b['edges']} for b in books],
 'candidates': cands, 'flagged': flagged, 'spread_flags': spread_flags,
 'bankroll_usd': 10780.73, 'cash_usd': 7045.33,
 'verdict': ('PASS - no Serie A Wednesday candidate meets gates. The whole premise of this scan '
   '(Tuesday data compressing variant spreads) is structurally void: Tuesday\'s six teams do not '
   'appear in any Wednesday fixture, so every lambda, p0 and var-spread is bit-identical to r19/r20. '
   'Markets themselves partially corrected: Bologna O0.5 Over +8.7c->+5.7c, BTTS +7.1c->+4.6c, '
   'Parma O2.5 +9.0c->+8.0c (all still fail var<=6c). The only var-passing liq>=5k non-spread markets '
   'are all Parma-Udinese; on CLOB $250-VWAP they fail exec/worst (Udinese O1.5 Over exec +3.1c/worst +2.1c; '
   'O/U 0.5 Over +2.5c/+0.2c; Udinese O0.5 Over +0.4c/-0.4c). Spread flag Monza (-1.5) exec +5.9c but worst +2.8c '
   'and spreads are flagged-only. Zero positions recommended.')}

json.dump(scan, open(RAW + '/seriea_scan.json', 'w'), indent=1)
json.dump(scan, open('/home/ubuntu/paper-sim/round21/seriea_candidates.json', 'w'), indent=1)
print('saved seriea_scan.json + seriea_candidates.json')
print('candidates:', len(cands), 'flagged:', len(flagged), 'spread_flags:', len(spread_flags))
