"""Round-12 final gate + ranking -> soccer_candidates.json"""
import json

RAW = '/home/ubuntu/paper-sim/round12/raw'
rows = json.load(open(RAW + '/shortlist_books.json'))

def entry_ok(p): return p is not None and 0.10 <= p <= 0.92

cands = []
for r in rows:
    q0 = r['q0_med']
    e0 = r['edge0_exec']; e1 = r['edge1_exec']
    a0 = r['exec_ask0']; a1 = r['exec_ask1']
    best = None
    if e0 is not None and e0 >= 0.05 and entry_ok(a0):
        best = ('side0', r['side0'], a0, e0)
    if e1 is not None and e1 >= 0.05 and entry_ok(a1):
        # pick larger of the two if both pass (they won't both)
        if best is None or e1 > best[3]:
            best = ('side1', r['side1'], a1, e1)
    if best is None: continue
    if r['var_spread'] > 0.08: continue
    if (r['liq'] or 0) < 5000: continue
    side_kind, side_label, ask, edge = best
    tok_i = 0 if side_kind == 'side0' else 1
    toks = r['tokens']
    if isinstance(toks, str): toks = json.loads(toks)
    b = r['books'].get('tok%d' % tok_i, {})
    askinfo = b.get('ask', {}) or {}
    bidinfo = (r['books'].get('tok%d' % (1 - tok_i), {}).get('bid', {}) or {})
    cands.append({
        'match': r['match'], 'league': r['league'], 'kickoff': r['kickoff'],
        'question': r['q'], 'side': side_label, 'entry_ask': ask,
        'exit_bid_ref': bidinfo.get('best'),
        'model_median': round(q0 if side_kind == 'side0' else 1 - q0, 4),
        'model_min': round(r['q0_min'] if side_kind == 'side0' else 1 - r['q0_max'], 4),
        'model_max': round(r['q0_max'] if side_kind == 'side0' else 1 - r['q0_min'], 4),
        'edge_exec': round(edge, 4), 'var_spread': r['var_spread'],
        'liq_gamma': r['liq'], 'book_depth_near2c': askinfo.get('depth_near2c'),
        'book_filled_250': askinfo.get('filled'),
        'market_id': r['id'], 'token_id': toks[tok_i] if tok_i < len(toks) else None,
        'kind': r['kind'],
    })

TYPE_RANK = {'total': 0, 'btts': 1, 'teamtotal': 2, 'spread': 3, 'ml': 4}
cands.sort(key=lambda c: (TYPE_RANK.get(c['kind'], 9), -c['edge_exec']))

# dedupe correlated: keep best per (match, kind) and cap 2 markets per match overall
seen_mk = {}
final = []
for c in cands:
    k1 = (c['match'], c['kind'])
    if k1 in seen_mk: continue
    if seen_mk.get(c['match'], 0) >= 2: continue
    seen_mk[k1] = True
    seen_mk[c['match']] = seen_mk.get(c['match'], 0) + 1
    final.append(c)

print('candidates passing all gates:', len(cands))
for i, c in enumerate(cands):
    print('%2d %-46s %-58s %-28s ask=%.4f med=%.3f edge=%+.3f sprd=%.3f liq=%8d depth2c=%s %s' % (
        i, c['match'][:46], c['question'][:58], str(c['side'])[:28],
        c['entry_ask'], c['model_median'], c['edge_exec'], c['var_spread'],
        c['liq_gamma'] or 0, c['book_depth_near2c'], c['kickoff'][:16]))
print()
print('deduped ranking (max shown 8):')
for i, c in enumerate(final[:8]):
    print('%2d %-46s %-50s %-24s ask=%.4f med=%.3f edge=%+.3f sprd=%.3f liq=%8d %s' % (
        i, c['match'][:46], c['question'][:50], str(c['side'])[:24],
        c['entry_ask'], c['model_median'], c['edge_exec'], c['var_spread'],
        c['liq_gamma'] or 0, c['kickoff'][:16]))

json.dump({'generated_utc': __import__('time').strftime('%Y-%m-%dT%H:%M:%SZ', __import__('time').gmtime()),
           'all_passing': cands, 'ranked': final[:6]},
          open('/home/ubuntu/paper-sim/round12/soccer_candidates.json', 'w'), indent=1)
print()
print('saved soccer_candidates.json')
