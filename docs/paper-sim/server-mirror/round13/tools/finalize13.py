"""Round-13 final gate + ranking -> soccer_candidates.json.

Gates: executable edge >=5c (CLOB VWAP ask for $250), entry price 0.10-0.92,
variant spread <=8c, gamma liquidity >=$5k, book fills $250.
50-50 cancellation haircut: model median in [0.45,0.55] -> edge halved before bar.
Held-fixture-other-type candidates flagged + deprioritized (correlation risk).
match_winner suspended: ml never shortlisted this round.
"""
import json, time

RAW = '/home/ubuntu/paper-sim/round13/raw'
rows = json.load(open(RAW + '/shortlist_books.json'))

def entry_ok(p): return p is not None and 0.10 <= p <= 0.92

def haircut(q_med):
    """50-50 cancellation haircut: near-coinflip model -> halve the edge."""
    return 0.5 if 0.45 <= q_med <= 0.55 else 1.0

cands = []
for r in rows:
    q0 = r['q0_med']
    a0 = r['exec_ask0']; a1 = r['exec_ask1']
    e0 = r['edge0_exec']; e1 = r['edge1_exec']
    side_med0 = q0
    side_med1 = 1 - q0
    h0 = haircut(side_med0); h1 = haircut(side_med1)
    e0h = None if e0 is None else round(e0 * h0, 4)
    e1h = None if e1 is None else round(e1 * h1, 4)
    best = None
    if e0 is not None and e0h is not None and e0h >= 0.05 and entry_ok(a0):
        best = ('side0', r['side0'], a0, e0, e0h, h0)
    if e1 is not None and e1h is not None and e1h >= 0.05 and entry_ok(a1):
        if best is None or e1h > best[4]:
            best = ('side1', r['side1'], a1, e1, e1h, h1)
    if best is None: continue
    if r['var_spread'] > 0.08: continue
    if (r['liq'] or 0) < 5000: continue
    side_kind, side_label, ask, edge, edge_h, h = best
    tok_i = 0 if side_kind == 'side0' else 1
    toks = r['tokens']
    if isinstance(toks, str): toks = json.loads(toks)
    b = r['books'].get('tok%d' % tok_i, {})
    askinfo = b.get('ask', {}) or {}
    bidinfo = (r['books'].get('tok%d' % (1 - tok_i), {}).get('bid', {}) or {})
    if not askinfo.get('filled'): continue  # $250 must be executable
    cands.append({
        'match': r['match'], 'league': r['league'], 'kickoff': r['kickoff'],
        'question': r['q'], 'side': side_label, 'entry_ask': ask,
        'exit_bid_ref': bidinfo.get('best'),
        'model_median': round(q0 if side_kind == 'side0' else 1 - q0, 4),
        'model_min': round(r['q0_min'] if side_kind == 'side0' else 1 - r['q0_max'], 4),
        'model_max': round(r['q0_max'] if side_kind == 'side0' else 1 - r['q0_min'], 4),
        'edge_exec': round(edge, 4), 'haircut': h, 'edge_exec_haircut': edge_h,
        'var_spread': round(r['var_spread'], 4),
        'liq_gamma': r['liq'], 'book_depth_near2c': askinfo.get('depth_near2c'),
        'book_filled_250': askinfo.get('filled'),
        'market_id': r['id'], 'token_id': toks[tok_i] if tok_i < len(toks) else None,
        'kind': r['kind'],
        'held_fixture_other_type': r.get('held_fixture_other_type', False),
    })

TYPE_RANK = {'total': 0, 'btts': 1, 'spread': 2, 'teamtotal': 3}
# held-fixture-other-type candidates rank last (correlation risk with open positions)
cands.sort(key=lambda c: (c.get('held_fixture_other_type', False),
                          TYPE_RANK.get(c['kind'], 9), -c['edge_exec_haircut']))

seen_mk = {}
final = []
for c in cands:
    k1 = (c['match'], c['kind'])
    if k1 in seen_mk: continue
    if seen_mk.get(c['match'], 0) >= 2: continue
    seen_mk[k1] = True
    seen_mk[c['match']] = seen_mk.get(c['match'], 0) + 1
    final.append(c)

print('candidates passing all gates (post-haircut >=5c):', len(cands))
for i, c in enumerate(cands):
    print('%2d %-46s %-56s %-22s ask=%.4f med=%.3f edge=%+.3f hcut=%s eh=%+.3f sprd=%.3f liq=%8d d2c=%s %s%s' % (
        i, c['match'][:46], c['question'][:56], str(c['side'])[:22],
        c['entry_ask'], c['model_median'], c['edge_exec'], c['haircut'], c['edge_exec_haircut'],
        c['var_spread'], c['liq_gamma'] or 0, c['book_depth_near2c'], c['kickoff'][:16],
        ' [HELD-FIXTURE]' if c.get('held_fixture_other_type') else ''))
print()
print('deduped ranking (max 8):')
for i, c in enumerate(final[:8]):
    print('%2d %-46s %-50s %-20s ask=%.4f med=%.3f edge=%+.3f eh=%+.3f liq=%8d %s%s' % (
        i, c['match'][:46], c['question'][:50], str(c['side'])[:20],
        c['entry_ask'], c['model_median'], c['edge_exec'], c['edge_exec_haircut'],
        c['liq_gamma'] or 0, c['kickoff'][:16],
        ' [HELD-FIXTURE]' if c.get('held_fixture_other_type') else ''))

json.dump({'generated_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
           'all_passing': cands, 'ranked': final[:8],
           'notes': 'match_winner suspended (2W-4L). Held fixtures excluded from same-type candidacy; '
                    'held-fixture other-type passes flagged+deprioritized. 50-50 haircut halved edges '
                    'with model median in [0.45,0.55]. Max 2 new positions x $250 per coordinator.'},
          open('/home/ubuntu/paper-sim/round13/soccer_candidates.json', 'w'), indent=1)
print()
print('saved soccer_candidates.json')
