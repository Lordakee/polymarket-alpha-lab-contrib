"""Round-18 finalize: apply tightened gates, write laliga_scan.json + laliga_candidates.json."""
import json, time

RAW = '/home/ubuntu/paper-sim/round18/raw'
OUTDIR = '/home/ubuntu/paper-sim/round18'
model = json.load(open(RAW + '/model18_out.json'))
books = json.load(open(RAW + '/shortlist_books18.json'))
evs = json.load(open(RAW + '/events_window.json'))

GATES = {
    'var_spread_max': 0.06,
    'worst_variant_edge_min': 0.04,
    'exec_edge_min': 0.05,
    'liq_min': 5000,
    'entry_range': [0.10, 0.92],
    'book_fill_dollars': 250,
    'haircut_zone': [0.45, 0.55],
}

cands = []
rejected = []
for b in books:
    q0 = b['q0_med']
    for side_i in (0, 1):
        ask = b.get('exec_ask0') if side_i == 0 else b.get('exec_ask1')
        if ask is None:
            continue
        filled = (b['books'].get('tok%d' % side_i, {}).get('ask', {}) or {}).get('filled')
        depth = (b['books'].get('tok%d' % side_i, {}).get('ask', {}) or {}).get('depth_near2c')
        exit_bid = b.get('exit_bid0') if side_i == 0 else b.get('exit_bid1')
        edge_exec = b.get('edge0_exec') if side_i == 0 else b.get('edge1_exec')
        worst = b.get('worst_var_edge0') if side_i == 0 else b.get('worst_var_edge1')
        p_model = q0 if side_i == 0 else round(1 - q0, 4)
        p_min = b['q0_min'] if side_i == 0 else round(1 - b['q0_max'], 4)
        p_max = b['q0_max'] if side_i == 0 else round(1 - b['q0_min'], 4)
        hair_mult = 0.5 if (GATES['haircut_zone'][0] <= p_model <= GATES['haircut_zone'][1]) else 1.0
        g = {
            'liq>=$5k': (b['liq'] or 0) >= GATES['liq_min'],
            'var_spread<=6c': b['var_spread'] <= GATES['var_spread_max'] + 1e-9,
            'worst_variant>=+4c': worst is not None and worst >= GATES['worst_variant_edge_min'] - 1e-9,
            'exec_edge>=+5c': edge_exec is not None and edge_exec >= GATES['exec_edge_min'] - 1e-9,
            'entry_0.10-0.92': GATES['entry_range'][0] <= ask <= GATES['entry_range'][1],
            'book_fills_$250': bool(filled),
        }
        row = {'question': b['q'], 'side': (b['outcomes'] or ['Over', 'Under'])[side_i],
               'ask_vwap250': ask, 'exit_bid_ref': exit_bid, 'depth_near2c': depth,
               'model_median': p_model, 'variant_range': [p_min, p_max],
               'var_spread_c': round(b['var_spread'] * 100, 2),
               'edge_exec_c': round(edge_exec * 100, 2) if edge_exec is not None else None,
               'edge_worst_variant_c': round(worst * 100, 2) if worst is not None else None,
               'haircut_applied': hair_mult, 'gates': g,
               'liq_gamma': b['liq'], 'mid_gamma': b['mid'], 'market_id': b['id']}
        if all(g.values()):
            cands.append(row)
        else:
            row['failed_gates'] = [k for k, v in g.items() if not v]
            rejected.append(row)

cands.sort(key=lambda r: -(r['edge_exec_c']))
cands = cands[:2]
for i, c in enumerate(cands):
    c['rank'] = i + 1
    c['sizing'] = '$250 paper'
    c['edge_exec_haircut_c'] = round(c['edge_exec_c'] * c['haircut_applied'], 2)

mr = model['model_rec']
scan = {
    'generated_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    'window': '2026-10-26T02:30:00Z .. 2026-10-27T02:30:00Z',
    'paper_only': True,
    'discovery': 'gamma tag_slug=la-liga + la-liga-2 (both orders volume24hr/liquidity), strict market gameStartTime window filter; 10 + 5 unique in-window events',
    'fixtures': {
        'la_liga': [{'match': 'Sevilla FC vs. CA Osasuna', 'kickoff': '2026-10-26T20:00:00Z',
                     'note': 'Jornada 10 Monday closer at Sanchez-Pizjuan'}],
        'la_liga_2_report_only': [
            {'match': 'FC Andorra vs. Burgos CF', 'kickoff': '2026-10-26T19:30:00Z',
             'markets_seen': 92, 'max_market_liq': 19196.25,
             'vol24_total': 5897.8,
             'note': 'match_winner seeded ~15-19k liq (SUSPENDED anyway); O/U 2.5 liq ~10k, BTTS ~6.2k, rest thin'}],
    },
    'la_liga_2_note': '1 fixture in window (FC Andorra vs. Burgos CF, Mon 19:30Z). No Understat La Liga 2 coverage -> no xG model output, REPORT-ONLY per prior-round practice. Totals/BTTS liq mostly <5k (O/U 3.5 10.7k, O/U 1.5 10.6k, O/U 2.5 10.0k, BTTS 6.2k); match_winner suspended. Nothing evaluated, no candidates possible.',
    'model': {
        'method': '10-variant xG-Poisson (round15/17 methodology): blend weights .25/.5/1.0, priors 4/8/16, Dixon-Coles rho=-0.1 variant, current-only, last-season-only, cross-shrink .8/1.1',
        'variants': model['variants'],
        'matches': [mr],
    },
    'shortlist_with_books': books,
    'flagged_spreads': model['flagged_spreads'],
    'kind_counts': model['kind_counts'],
    'lineup_intel': 'Osasuna: no new injury concerns (Football Whispers preview). Sevilla out/injured: Lucas Stassin, Marcao (CB), Miguel Sierra; Jon Guridi (groin) reported available by Fox Sports. Sevilla 3-game winless run entering Monday. No postponement risk identified.',
    'sportsbook_refs': 'Football Whispers tips Over 2.5 (report-only reference, not used in gating).',
    'xg_refresh': 'round18/raw/xg_understat_18.json refreshed 2026-10-26T02:4xZ; Sun Oct-25 results verified recorded: Athletic 4-0 Getafe (xG 0.70-0.35), Celta 0-0 Betis (xG 0.80-1.07), Sociedad 2-1 Levante (xG 2.92-0.75), Barca 1-2 RM (xG 1.64-1.95); La_liga 2026 now 98 recorded matches, last 2026-10-25 20:00.',
    'ucl_context_report_only': 'UCL matchday Oct 27-28: zero UCL match events listed on Polymarket gamma (champions-league/ucl tags) with gameStartTime Oct 27-29 as of scan time; ESPN uefa.champions scoreboard for 20261027/20261028 also returns no fixtures. Outside window regardless; report-only.',
    'gated_out_prelim': model['gated_out_prelim'],
    'candidates_final': cands,
    'rejected_after_books': rejected,
}
json.dump(scan, open(RAW + '/laliga_scan.json', 'w'), indent=1)

cand_out = {
    'generated_utc': scan['generated_utc'],
    'league': 'la-liga (+ la-liga-2 report-only)',
    'window': scan['window'],
    'paper_only': True,
    'decision': 'CANDIDATES (%d)' % len(cands) if cands else 'PASS',
    'max_candidates': 2,
    'rules': {
        'match_winner': 'SUSPENDED per round-18 rules',
        'spread_blowout_tail': 'flagged-only, not recommended',
        'eligible': 'full-match O/U, BTTS, team totals (both directions); halves report-only this round',
        'gates': 'TIGHTENED round-18: var spread<=6c AND worst-variant exec edge>=+4c AND exec edge>=+5c (CLOB $250 VWAP), liq>=$5k, entry 0.10-0.92, book fills $250, 50-50 haircut if model median in [0.45,0.55] or postponement risk (neither triggered)',
        'held_positions': 'none in La Liga this round (Levante O0.5 settled WON Oct-25)',
    },
    'candidates': [
        {
            'rank': c['rank'], 'match': 'Sevilla FC vs. CA Osasuna', 'league': 'La_liga',
            'kickoff': '2026-10-26T20:00:00Z', 'question': c['question'],
            'side': c['side'], 'type_note': 'team total O/U (away)',
            'paper_only': True, 'sizing': '$250',
            'market_id': c['market_id'],
            'entry_ask_vwap250': c['ask_vwap250'],
            'exit_bid_ref': c['exit_bid_ref'],
            'book_filled_250': c['gates']['book_fills_$250'],
            'book_depth_near2c': c['depth_near2c'],
            'model_median': c['model_median'],
            'model_variant_range': c['variant_range'],
            'edge_exec_c': c['edge_exec_c'],
            'edge_worst_variant_c': c['edge_worst_variant_c'],
            'var_spread_c': c['var_spread_c'],
            'haircut_applied': c['haircut_applied'],
            'edge_exec_haircut_c': c['edge_exec_haircut_c'],
            'liq_gamma': c['liq_gamma'],
            'lambda_home': mr['lambda_home'], 'lambda_away': mr['lambda_away'],
            'lambda_total': mr['lambda_total'],
            'form_home': mr['form_home'], 'form_away': mr['form_away'],
            'gates': c['gates'],
        } for c in cands
    ],
    'rejected_after_books': [
        {'question': r['question'], 'side': r['side'], 'edge_exec_c': r['edge_exec_c'],
         'failed_gates': r['failed_gates']} for r in rejected
    ],
    'notes': 'Caveat: model 1X2 (H .390/D .263/A .338) is materially closer than market (Sevilla .52/Draw .28/Osasuna .22) - divergence driven by Sevilla elevated xGA; both candidates are away-team-total overs (Osasuna scoring), which do not require an Osasuna result. Osasuna report no new injuries; Sevilla missing Marcão (CB) supports away-scoring view.',
}
json.dump(cand_out, open(OUTDIR + '/laliga_candidates.json', 'w'), indent=1)
print('decision:', cand_out['decision'])
for c in cand_out['candidates']:
    print('rank %d: %s [%s] ask=%s exit_bid=%s model=%s wv=%+.2fc exec=%+.2fc vspr=%.2fc liq=%.0f gates=%s' % (
        c['rank'], c['question'], c['side'], c['entry_ask_vwap250'], c['exit_bid_ref'],
        c['model_median'], c['edge_worst_variant_c'], c['edge_exec_c'], c['var_spread_c'], c['liq_gamma'],
        all(c['gates'].values())))
for r in cand_out['rejected_after_books']:
    print('rejected:', r['question'], r['side'], 'edge=%s' % r['edge_exec_c'], r['failed_gates'])
print('saved laliga_scan.json + laliga_candidates.json')
