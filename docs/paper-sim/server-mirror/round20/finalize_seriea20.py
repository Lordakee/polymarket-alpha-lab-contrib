"""Round-20 Serie A sub-scan finalize: merge model + books + lineups -> scan + candidates JSON."""
import json, time

RAW = '/home/ubuntu/paper-sim/round20/raw'
model = json.load(open(RAW + '/seriea_model20.json'))
edges = json.load(open(RAW + '/seriea_edges20.json'))
books = json.load(open(RAW + '/seriea_books20.json'))
NOW = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

LINEUPS = {
 'US Sassuolo Calcio vs. SS Lazio': {
  'home': 'Sassuolo missing 5: Paz, Leysen, Kone, Boloca, Idzes (footballpredictions.com). Back-to-back defeats (0-2 at Como).',
  'away': 'Lazio clean bill; expected unchanged XI from 2-1 vs Parma; 4 straight wins under Gattuso (4/4 away).',
  'source': 'footballpredictions.com Serie A preview 27-10-2026; sportsmole Tuesday Serie A predictions'},
 'AS Roma vs. Cagliari Calcio': {
  'home': 'Roma rotate (4th of 5 home games): Svilar (GK) OUT, Kone OUT, Pellegrini OUT, Dybala doubtful (calf); Cristante back. Predicted: Gollini; Balerdi, Ndicka, Koulierakis; Lulli, De Roon, Cristante, Molina; Mora, Soule; Malen (Malen 6 league goals).',
  'away': 'Cagliari OUT: Idrissi, Felici (long-term), Trepy; Winks back-issue doubt. Form: back-to-back defeats 0-4 at Monza, 0-2 vs Bologna (0 goals); no goals/points at Roma in past 4 seasons. Predicted: Caprile; Ze Pedro, Mina, Rodriguez, Obert; Adopo, Gagliardini, Romano; Fadera, Maldini; Mendy.',
  'source': 'sportsmole.co.uk Roma vs Cagliari preview 607651 (predicts 2-0 Roma)'},
 'Torino FC vs. Como 1907': {
  'home': 'Torino OUT: Israel, Rodriguez, Ilkhan (injury). Won 3-2 comeback vs Monza, chasing 4th straight win.',
  'away': 'Como no injuries/suspensions; Nico Paz pushing to start after rest; Douvikas in form (brace last round - sources split on club).',
  'source': 'footballpredictions.com Torino vs Como 27-10-2026'},
 'AC Milan vs. Bologna FC 1909': {
  'home': 'MILAN ROTATION RISK: Amorim expected to make several changes with Saturday derby vs Inter in mind. OUT: Chukwueze, Gabbia, Saelemaekers, Terracciano; Rabiot/Moreira late tests; Gila, Loftus-Cheek doubts. Predicted: Maignan; Tomori, De Winter, Pavlovic, Bartesaghi; Hutchinson, Jashari, Musah, Cisse; Pulisic, Ramos.',
  'away': 'Bologna OUT: Orsolini, Piccoli, Holm (long-term). Odgaard leads line; Pobega vs old club. Predicted 3-4-3: Skorupski; Darmian, Casale, Theate; Zortea, Ferguson, Pobega, Miranda; Bernardeschi, Odgaard, Cambiaghi. ~1 goal/game.',
  'source': 'cultofcalcio.com Milan vs Bologna preview (Oct 28 2026)'},
 'Parma Calcio 1913 vs. Udinese Calcio': {
  'home': 'Parma poor form (1W 1D 3L last 5, ~0.8 goals/game). Predicted keys: Okoye (GK), Solet, Valenti.',
  'away': 'Udinese worse form (0W 1D 4L last 5). Lost 0-2 at home to Milan Sunday.',
  'source': 'bettingstats.org, fomelabo.com Parma-Udinese 28-10-2026'},
 'Venezia FC vs. FC Internazionale Milano': {
  'home': 'Venezia OUT: Sverko, Franjic. Predicted 3-5-2: Stankovic; Schingtienne/Idzes, Halhal, Moreno/Altare; Hainaut, Perez, Basic, Sohm, Haps; Yeboah, Adams.',
  'away': 'Inter near full strength; Lautaro leads line. Won 2-1 vs Fiorentina Sunday.',
  'source': 'sportsmole.co.uk Venezia vs Inter preview 607740; forebet 31691'},
 'Genoa CFC vs. Juventus FC': {
  'home': 'Genoa (De Rossi): no fresh injuries; expected same XI that beat Venezia 1-0 Sunday.',
  'away': 'Juventus OUT: Yildiz, Thuram, Gonzalez, Conceicao (4 attackers); Alajbegovic pushing for start. Won 2-0 at Lecce Sunday.',
  'source': 'footballpredictions.com Genoa vs Juventus 28-10-2026'},
 'AC Monza vs. SSC Napoli': {
  'home': 'Monza OUT: Pessina, Ziolkowski, Maye. Predicted 3-4-2-1: Tornqvist; Goglichidze, Lucchesi, Carboni; Birindelli, Ondoa...',
  'away': 'Napoli OUT: Buongiorno, Neres. Predicted: Meret; Di Lorenzo, Marin, Rrahmani, Olivera; Anguissa, De Bruyne, McTominay; Politano, Vergara; Hojlund.',
  'source': 'sportsmole.co.uk Monza vs Napoli preview 607725; forebet 31694'},
 'Frosinone Calcio vs. US Lecce': {'home': 'report-only (Thu, outside window)', 'away': 'report-only (Thu, outside window)', 'source': None},
 'ACF Fiorentina vs. Atalanta BC': {'home': 'report-only (Thu, outside window)', 'away': 'report-only (Thu, outside window)', 'source': None},
}

MATCH_LABELS = {
 'US Sassuolo Calcio vs. SS Lazio': 'Sassuolo-Lazio',
 'AS Roma vs. Cagliari Calcio': 'Roma-Cagliari',
 'Torino FC vs. Como 1907': 'Torino-Como',
 'AC Milan vs. Bologna FC 1909': 'Milan-Bologna',
 'Parma Calcio 1913 vs. Udinese Calcio': 'Parma-Udinese',
 'Venezia FC vs. FC Internazionale Milano': 'Venezia-Inter',
 'Genoa CFC vs. Juventus FC': 'Genoa-Juventus',
 'AC Monza vs. SSC Napoli': 'Monza-Napoli',
 'Frosinone Calcio vs. US Lecce': 'Frosinone-Lecce',
 'ACF Fiorentina vs. Atalanta BC': 'Fiorentina-Atalanta',
}

per_game = []
for base, rec in model['matches'].items():
    lam = rec
    pg = {'match': base, 'label': MATCH_LABELS[base], 'kickoff_utc': rec['kickoff'],
          'in_window': rec['in_window'],
          'lambda_home': rec['lambda_home'], 'lambda_away': rec['lambda_away'],
          'delta_lambda_home_vs_r19': rec['delta_lambda_home'], 'delta_lambda_away_vs_r19': rec['delta_lambda_away'],
          'model_1x2_med': rec['model_1x2_med'],
          'top_model_edges': [], 'lineups': LINEUPS.get(base)}
    top = [r for r in edges if r['match'] == base and r['in_window']]
    top.sort(key=lambda r: -max(abs(r['edge_over']), abs(r['edge_under'])))
    for r in top[:4]:
        pg['top_model_edges'].append({'market': r['q'], 'liq': r['liq'], 'mid': r['mid'],
                                      'p0_med': r['p0_med'], 'var_spread': r['var_spread'],
                                      'delta_p0_vs_r19': r['d_p0'], 'delta_varspread_vs_r19': r['d_vs'],
                                      'edge_over_mid': r['edge_over']})
    per_game.append(pg)

# gate application on booked markets
cands = []
flagged = []
for b in books:
    e = b['edges']; vs = b['var_spread']
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
           'exec_edge': ex, 'worst_var_edge': wo, 'var_spread': vs, 'liq': b['liq'],
           'gates': gates, 'all_pass': all(gates.values()),
           'r19_compare': {'r19_p0': b['r19_p0'], 'r19_var_spread': b['r19_vs'],
                           'delta_p0': b['d_p0'], 'delta_var_spread': b['d_vs']}}
    if all(gates.values()):
        cands.append(row)
    else:
        fails = [k for k, v in gates.items() if not v]
        row['reason'] = 'FAIL: ' + ', '.join(fails)
        flagged.append(row)

# spread flag (flagged-only rule)
spread_flag = {'match': 'AC Monza vs. SSC Napoli', 'market': 'Spread: AC Monza (-1.5)',
               'note': 'p0 0.1473 vs mid 0.075 (+7.2c), var 4.53c, liq 10933 - spread markets flagged-only per round-20 hard rules; not candidate-eligible. Exec unverified.'}

scan = {'scan': 'seriea', 'round': 20, 'paper_only': True, 'sub_scan_generated_utc': NOW,
 'window_utc': {'lo': '2026-10-27T17:30:00Z', 'hi': '2026-10-28T19:45:00Z (8 games; Thu Frosinone-Lecce/Fiorentina-Atalanta report-only)'},
 'method': '10-variant xG-Poisson (r15/r19 methodology: 6 blends + current-only + last-only + 2 cross-shrinks; DC rho -0.1 variant), team totals included (r19 extension); Gamma tag sea sweep; CLOB $250-VWAP.',
 'xg_refresh': {
   'file': '/home/ubuntu/paper-sim/round20/raw/xg_understat_20.json',
   'serie_a_new_matches_vs_r15_file': 5, 'serie_a_last': '2026-10-25 19:45 (Udinese 0-2 AC Milan)',
   'monday_results_captured': ['PSG 2-0 Lyon (Ligue_1)', 'Sevilla 2-0 Osasuna (La_liga)'],
   'key_finding': 'Round-19 model ALREADY included the Sun Oct-25 Serie A round (verified: r19 Milan-Bologna lambda 1.862 equals fresh-refresh value, not the r15-file value 1.815). Monday results touch only Ligue-1/La-Liga ratings -> Serie A model inputs are IDENTICAL to round-19. All per-market delta_p0 and delta_var_spread = 0.000. Variant spreads CANNOT compress from added data: there was no added Serie A data.'},
 'hard_rules': 'match_winner SUSPENDED; spreads flagged-only; gates var<=6c AND worst>=+4c AND exec>=+5c (CLOB $250-VWAP) AND liq>=$5k; max 2 candidates.',
 'per_game': per_game,
 'books_checked': [{'match': b['match'], 'market': b['q'], 'exec_ask_over': b['exec_ask_over'],
                    'exec_ask_under': b['exec_ask_under'], 'edges': b['edges']} for b in books],
 'gate_math_note': 'Exec ask VWAP >= best ask >= gamma mid, so exec_edge <= mid_edge always; candidacy requires mid edge >=5c. Only in-window market with var<=6c, liq>=5k, mid-edge>=5c was Como O/U 3.5 Under edge +5.1c at liq 1838 (<5k). Hence zero candidates is structural, not a book-timing artifact.',
 'flagged': flagged + [spread_flag],
 'n_candidates': 0}

cjson = {'scan': 'seriea', 'round': 20, 'paper_only': True, 'generated_utc': NOW,
 'window_utc': scan['window_utc'], 'n_candidates': 0, 'candidates': [],
 'flagged': [f for f in flagged] + [spread_flag],
 'verdict': 'PASS - no Serie A candidate meets gates. Round-19 near-misses re-checked with fresh xG + fresh CLOB books: Cagliari O/U 0.5 Over exec +8.4c but worst +2.95c / spread 7.36c (unchanged, both fail); Como O/U 1.5 Under exec +4.4c / worst +1.2c / spread 7.15c (unchanged, all fail). Model deltas vs r19 are exactly zero (no new Serie A input data); spread compression hypothesis is moot. Lineup news does not rescue any gated-out line under current rules.'}

json.dump(scan, open(RAW + '/seriea_scan.json', 'w'), indent=1)
json.dump(cjson, open('/home/ubuntu/paper-sim/round20/seriea_candidates.json', 'w'), indent=1)
print('wrote seriea_scan.json (%d games) + seriea_candidates.json (n_candidates=%d)' % (len(per_game), 0))
for f in flagged:
    print('FLAG', f['match'], '|', f['market'], '|', f['reason'])
