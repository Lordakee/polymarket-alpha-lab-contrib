"""Round-24 EPL delta finalize: gates on fresh CLOB books vs unchanged r23 model.
Writes round24/raw/epl_scan.json + round24/epl_candidates.json."""
import json, time

RAW = '/home/ubuntu/paper-sim/round24/raw'
OUT = '/home/ubuntu/paper-sim/round24'

books = json.load(open(RAW + '/books24.json'))
model = json.load(open(RAW + '/epl_model24.json'))
r23 = json.load(open('/home/ubuntu/paper-sim/round23/epl_candidates.json'))
r23_scan = json.load(open('/home/ubuntu/paper-sim/round23/raw/epl_scan.json'))

NOW = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
GATES = {'var': 0.06, 'worst': 0.04, 'exec': 0.05, 'liq': 5000, 'entry_lo': 0.10, 'entry_hi': 0.92}

# round-23 archived ask per market id (from ranked + runner_ups + near_misses)
r23_ask = {}
for c in (r23['ranked'] + r23.get('runner_ups_same_fixture', []) + r23.get('near_misses', [])):
    r23_ask[str(c.get('market_id'))] = c.get('entry_ask_vwap')

rows = []
for b in books:
    q = b['q']
    for side in (0, 1):
        ask = b.get('exec_ask%d' % side)
        if ask is None: continue
        filled = b.get('fill%d' % side)
        depth = b.get('depth%d' % side)
        qmed = b['q0_med'] if side == 0 else round(1 - b['q0_med'], 4)
        qs = b['qs_variants'] if side == 0 else [round(1 - x, 4) for x in b['qs_variants']]
        worst_model = min(qs)
        exec_edge = round(qmed - ask, 4)
        worst_edge = round(worst_model - ask, 4)
        var = b['var_spread']
        liq = b['liq'] or 0
        fails = []
        if var > GATES['var'] + 1e-9: fails.append('var>6c')
        if worst_edge < GATES['worst'] - 1e-9: fails.append('worst<+4c')
        if exec_edge < GATES['exec'] - 1e-9: fails.append('exec<+5c')
        if liq < GATES['liq']: fails.append('liq<$5k')
        if not (GATES['entry_lo'] <= ask <= GATES['entry_hi']): fails.append('entry outside .10-.92')
        if not filled: fails.append('book no fill $250')
        rows.append({'match': b['match'], 'kickoff': b['kickoff'], 'question': q,
            'kind': b['kind'], 'team': b.get('team'), 'line': b.get('line'),
            'market_id': b['id'], 'side': side,
            'side_name': ('Over/Yes' if side == 0 else 'Under/No'),
            'ask_vwap250': ask, 'exit_bid': b.get('exit_bid%d' % side),
            'depth_near2c': depth, 'gamma_liq': liq,
            'model_median': qmed, 'model_worst': worst_model,
            'edge_exec': exec_edge, 'edge_worst': worst_edge, 'var': var,
            'r23_ask_vwap250': r23_ask.get(str(b['id'])),
            'ask_delta_vs_r23': (round(ask - r23_ask[str(b['id'])], 4) if r23_ask.get(str(b['id'])) else None),
            'qs_variants': b['qs_variants'], 'fails': fails,
            'gate_pass': len(fails) == 0})

passing = [r for r in rows if r['gate_pass']]
passing.sort(key=lambda r: -r['edge_worst'])

HELD = {'5856164': '#48 Brentford-Forest O2.5 Over $250 @ 0.560',
        '5856548': '#49 Hull-Ipswich O2.5 Over $250 @ 0.5274'}

held_rows = {}
for mid, label in HELD.items():
    rr = [r for r in rows if r['market_id'] == mid and r['side'] == 0]
    if rr:
        r = rr[0]
        held_rows[mid] = {'label': label, 'current_ask_vwap250': r['ask_vwap250'],
            'current_exit_bid': r['exit_bid'], 'gamma_mid_now': None,
            'model_median': r['model_median'], 'model_worst': r['model_worst'],
            'edge_exec_now': r['edge_exec'], 'edge_worst_now': r['edge_worst'],
            'unrealized_vs_entry_mid': round(r['model_median'] - (0.560 if mid == '5856164' else 0.5274), 4),
            'mark_bid_vs_entry': round((r['exit_bid'] or 0) - (0.560 if mid == '5856164' else 0.5274), 4),
            'depth_near2c': r['depth_near2c']}

chemun = [r for r in rows if r['market_id'] == '5856824' and r['side'] == 0]
boulee = [r for r in rows if r['market_id'] == '5856401' and r['side'] == 0]

scan = {
  'generated_utc': NOW, 'round': '24-EPL-verify+delta', 'paper_only': True, 'report_only': True,
  'window': '2026-10-30 .. 2026-11-02 (all 10 EPL fixtures, Sat 12:30Z -> Mon 20:00Z)',
  'method': 'VERIFY+DELTA: round-23 10-variant xG-Poisson model probabilities UNCHANGED '
            '(xG base round23/raw/xg_epl_23.json through Oct 25; no EPL matches Oct 26-29, '
            'verified last_played 2026-10-25 16:30Z -> not refreshed); model rebuilt and '
            'lambda-validated 10/10 exact vs round-23 fixtures; fresh Gamma tag_slug=epl '
            'discovery (100 window events) + fresh CLOB $250-VWAP books for 53 shortlist markets.',
  'gates': 'var<=6c; worst-variant exec >= +4c; median exec >= +5c ($250-VWAP ask); liq >= $5k; '
           'entry .10-.92; book fills $250. match_winner deprioritized (none taken); '
           'cross-league match_winner BANNED; spreads flagged-only; max 1 new candidate.',
  'discovery': {'gamma_events_in_window': 100, 'fixtures_modeled': 10,
                'lambda_validation_vs_r23': '10/10 exact',
                'shortlist_markets_booked': len(books)},
  'fixtures': [{'match': m, 'kickoff': v['kickoff'], 'lambda_home': v['lambda_home'],
                'lambda_away': v['lambda_away'], 'model_1x2_med': v['model_1x2_med']}
               for m, v in model['matches'].items()],
  'gate_rows_all': rows,
  'gate_passing': passing,
  'held_verification_books': held_rows,
  'chemun_o35_recheck': chemun[0] if chemun else None,
  'boulee_o25_recheck': boulee[0] if boulee else None,
}
json.dump(scan, open(RAW + '/epl_scan.json', 'w'), indent=1)

print('=== ALL GATE-PASSING MARKETS (fresh books vs unchanged r23 model) ===')
for r in passing:
    tag = ' HELD' if r['market_id'] in HELD else ''
    print('%-64s s%d ask=%.4f exec=%+.4f worst=%+.4f var=%.4f liq=%.0f d2c=%.0f r23ask=%s%s' % (
        r['question'][:64], r['side'], r['ask_vwap250'], r['edge_exec'], r['edge_worst'],
        r['var'], r['gamma_liq'], r['depth_near2c'] or 0, r['r23_ask_vwap250'], tag))
print()
print('=== HELD VERIFY ===')
print(json.dumps(held_rows, indent=1))
print('=== CHE-MUN O3.5 ==='); print(json.dumps(chemun, default=str))
print('=== BOU-LEE O2.5 ==='); print(json.dumps(boulee, default=str))
print()
print('near-misses this round (fail exactly one margin-type gate, exec>=+5c & worst>=+3c):')
for r in rows:
    if not r['gate_pass'] and r['edge_exec'] >= 0.05 and r['edge_worst'] >= 0.03 and len(r['fails']) <= 2:
        print('  %-64s s%d ask=%.4f exec=%+.4f worst=%+.4f var=%.4f fails=%s' % (
            r['question'][:64], r['side'], r['ask_vwap250'], r['edge_exec'], r['edge_worst'], r['var'], r['fails']))
print('saved epl_scan.json')
