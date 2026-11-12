"""Round-23 final assembly: seriea_scan.json + seriea_candidates.json (paper-only)."""
import json, time

MODEL = json.load(open('/home/ubuntu/paper-sim/round23/raw/seriea_model23.json'))
GATES = json.load(open('/home/ubuntu/paper-sim/round23/raw/gate_rows23.json'))
ESPN = json.load(open('/home/ubuntu/paper-sim/round23/raw/espn_ita1_r11.json'))

LINEUP = {
 'DERBY Milan-Inter': {
  'inter': 'OUT: Lautaro Martinez (hamstring/soleus, ~1 month, will miss derby per Yardbarker/OneFootball Oct reports). Bonny/Pio Esposito in line to partner Thuram. UCL away Feyenoord Tue Nov 3 (3 days later) - derby is priority, low XI-rotation risk but model overstates Inter attack (rotation-blind 3.01 xG/gm best in league).',
  'milan': 'Injury crisis under Amorim: Loftus-Cheek (thigh tear, out), Tomori (doubt/knock), Rabiot+Gila+Moreira (missed pre-derby Bologna game), Theo Hernandez (thigh bruise, was out vs Roma); up to 7 absences reported. No European midweek game - full week to prep derby. Predicted XI ~16:30Z Sat (r21 pattern).',
  'fragility': 'HIGH: both attacks depleted vs rotation-blind model; model Over 2.5/3.5 lean (edge +6.7c/+6.9c mid) assumes full-strength scoring. Lautaro out cuts Inter lam 1.89 estimate; Milan absences cut 1.54. Direction of correction vs the Over lean: DOWN. Gates already failed on var (26-33c) and worst (-0.9c/-1.2c).'},
 'Udinese-Roma': {
  'udinese': 'OUT/doubt: Solet (muscle, ~64% to miss), Gueye (ankle), Bayo (muscle) per BeSoccer. Udinese worst-tier defense (2.41 xGA/gm) - Solet miss worsens it, supports Roma goals/Over.',
  'roma': 'No fresh confirmed list surfaced; check Corriere dello Sport/Sky closer to matchday. Model has Roma strong away (lam 2.06).',
  'fragility': 'MEDIUM-HIGH: Over lean driven by Udinese defensive weakness; that weakness is structural (not lineup luck), but var spread 41-53c across variants kills gates regardless. Roma lineup unverified.'},
 'Bologna-Monza': {
  'bologna': 'OUT long-term per r21 note + Oct round-up: Orsolini, Piccoli, Holm; plus Pobega (thigh) and Sulemana (MCL). Attacking depth thin despite 55% playerelo.',
  'monza': 'No fresh injury list surfaced; Monza 1.61 xg/gm mid-tier attack, 1.81 xGA mid-tier defense.',
  'fragility': 'MEDIUM: Bologna attacking absences argue AGAINST the model Over 2.5/3.5 lean (edges +3.8c/+3.4c mid); already failing var (24-26c) and worst gates.'},
}

ROTATION_FLAGS = {
 'DERBY Milan-Inter': 'Inter UCL @Feyenoord Tue Nov 3 - derby itself is priority, XI rotation unlikely; watch late-game management only.',
 'Juventus-Napoli': 'Juventus European match midweek Nov 3-5 (vs Dortmund reported, home) 2-3 days after Sun 19:45Z game - moderate squad rotation guess for Juventus; Napoli European schedule unverified.',
 'Atalanta-Parma': 'Atalanta Monday 19:45Z game + likely UCL/UEL midweek = shortest turnaround in round; highest single-team rotation guess (Monday entrant).',
 'Sassuolo-Fiorentina': 'Fiorentina likely UEL/UECL midweek (was in UECL r22 window as opponent) - mild rotation guess away side Monday.',
}

scan = {
 'generated_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
 'scan': 'seriea-r23-early (Thu sub-scan, round-11 full weekend)', 'round': 23, 'seriea_round': 11,
 'paper_only': True, 'match_winner': 'SUSPENDED (even for the derby)', 'spreads': 'flagged-only',
 'window_utc': {'lo': '2026-10-31T00:00:00Z', 'hi': '2026-11-03T00:00:00Z',
   'note': 'task brief said Nov 1-2; actual round-11 spans Sat Oct 31 - Mon Nov 2 (ESPN + Gamma gameStartTime agree)'},
 'xg_refresh': {
   'file': 'round22/raw/xg_understat_22.json',
   'serie_a_2026_matches': 88, 'last_played': '2026-10-28 19:45 UTC Monza-Napoli (full Tue/Wed midweek round in)',
   'other_leagues': 'NOT present in file (Serie_A_2025/2026 keys only) - fine for this Serie A-only sub-scan; other-league sub-scans own their refresh',
   'rating_movers_vs_r15_baseline': 'Lazio/Atalanta att up, Frosinone/Sassuolo/Cagliari def worse (as per r22 xg_refresh note, carried forward)'},
 'fixtures': [
   {'match': e['match'], 'kickoff_utc': e['kickoff_utc'], 'venue': e['venue']} for e in ESPN],
 'model': {'method': MODEL['method'], 'variants': ['blend w=.5 p=8 rho0','blend w=.5 p=8 DC','blend w=1.0 p=8','blend w=.25 p=8','blend w=.5 p=16','blend w=.5 p=4','current-only','last-only','cross-shrink .8','cross-shrink 1.1'],
   'matches': [{'match': m['match'], 'label': m['label'], 'kickoff_utc': m['kickoff_utc'],
     'lambda_home': m['lambda_home'], 'lambda_away': m['lambda_away'], 'lambda_total': m['lambda_total'],
     'form_home': m['form_home'], 'form_away': m['form_away'], 'p1x2_med': m['p1x2_med'], 'fair': m['fair'],
     'n_markets_attached': len(m['markets'])} for m in MODEL['matches']]},
 'lineup_news': LINEUP, 'rotation_flags': ROTATION_FLAGS,
 'gates': GATES['gates'],
 'gate_notes': 'Early entry strict gates: var<=6c, worst>=+4c, exec>=+5c, liq>=$5k, exec filled $250. ZERO markets in entire round have var<=6c at liq>=5k - gate failure is structural (8-9 games 2026 data + blend-family disagreement), not shortlist artifact. Tight-var sweep over all eligible O/U+BTTS+team-total sides confirmed 0.',
 'booked_rows_with_gates': GATES['rows'],
 'decision': 'PASS',
 'decision_rationale': 'No candidate passes all gates. Best mid edges: derby O/U 3.5 Over +6.9c / O/U 2.5 Over +6.7c exec but var 26-33c and worst-variant -1c; Udinese-Roma O3.5 Over +5.4c exec, var 53c, worst -8c. All fail var and worst gates decisively.',
 'near_miss_summary': [{'match': r['match'], 'q': r['q'], 'side': r['side'], 'kind': r['kind'],
   'exec_ask_vwap250': r['exec_ask_vwap250'], 'edge_exec': r['edge_exec'], 'edge_worst': r['edge_worst'],
   'var_spread': r['var_spread'], 'liq': r['liq'], 'checks': r['checks']} for r in GATES['near']],
 'write_scope': 'only /home/ubuntu/paper-sim/round23/raw/* and /home/ubuntu/paper-sim/round23/seriea_candidates.json (per task brief)',
}

cands_out = {
 'generated_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
 'round': 23, 'seriea_round': 11, 'decision': 'PASS',
 'candidates': [], 'max_candidates': 3,
 'gates': GATES['gates'],
 'flagged_only': [
  {'match': r['match'], 'question': r['q'], 'market_id': None, 'kind': 'spread (flagged-only, NOT a candidate)',
   'gamma_mid': r['gamma_mid'], 'model_med': r['p_med'], 'model_range': [r['p_min'], r['p_max']],
   'var_spread': r['var_spread'], 'exec_ask_vwap250': r['exec_ask_vwap250'],
   'edge_exec': r['edge_exec'], 'edge_worst': r['edge_worst'], 'liq': r['liq'],
   'note': 'Spread No side mid edge +6.9c but worst-variant -4.9c and var 14.6c - fails worst/var gates badly; spreads flag-only this round.' if 'Bologna' in r['q'] else
           'Spread No side mid edge +5.6c but worst-variant -33c and var 45.5c - worst gate failure in scan; spreads flag-only this round.'}
  for r in GATES['flagged']],
 'near_misses': [{'match': r['match'], 'question': r['q'], 'side': r['side'], 'kind': r['kind'],
   'entry_ask_vwap250': r['exec_ask_vwap250'], 'edge_exec': r['edge_exec'], 'edge_worst': r['edge_worst'],
   'var_spread': r['var_spread'], 'liq': r['liq'], 'checks': r['checks'],
   'fragility_note': (LINEUP.get(r['match'],{}).get('fragility') if r['match'] in LINEUP else
     ('derby: Lautaro OUT Inter; Milan 7-absence crisis - model Over lean fragile' if 'DERBY' in r['match'] else 'no lineup intel gathered (gates failed pre-news-check)'))}
  for r in GATES['near']],
 'rotation_flags': ROTATION_FLAGS,
 'notes': 'Early-entry Thu scan; kickoffs verified vs ESPN+Gamma (derby Sat Oct 31 19:45Z, brief/round-19 intel saying Sat Nov 1 was one day late). xG base fresh through Oct 28 midweek round. Zero var<=6c markets league-wide this round.',
}

json.dump(scan, open('/home/ubuntu/paper-sim/round23/raw/seriea_scan.json','w'), indent=1)
json.dump(cands_out, open('/home/ubuntu/paper-sim/round23/seriea_candidates.json','w'), indent=1)
print('wrote seriea_scan.json (%d fixtures, %d model matches, %d booked rows) and seriea_candidates.json (cands=%d flagged=%d near=%d)' % (
 len(scan['fixtures']), len(scan['model']['matches']), len(scan['booked_rows_with_gates']),
 len(cands_out['candidates']), len(cands_out['flagged_only']), len(cands_out['near_misses'])))
