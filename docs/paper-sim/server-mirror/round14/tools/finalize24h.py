"""Round-14 24h final gate + ranking -> round14/soccer24h_candidates.json.

Gates (coordinator, 24h ad-hoc scan):
- executable edge >= +5c vs CLOB $250 VWAP ask (buy side only)
- entry price 0.10-0.92
- variant spread <= 8c
- gamma liquidity >= $5k; book must fill $250
- 50-50 cancellation haircut: model median in [0.45,0.55] -> edge halved before bar
- held-fixture rules: same-type + spread-on-held-total already excluded upstream;
  BTTS on held-total fixture allowed but flagged + deprioritized (correlation risk)
- match_winner suspended. Max 2 new positions; $250 full-edge / $150 marginal
  (marginal = post-haircut edge in [5c, 7c) or held-fixture-flagged).
"""
import json, time

RAW = '/home/ubuntu/paper-sim/round14/raw'
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
    # sizing: $250 full edge; $150 marginal (thin post-haircut edge or held-fixture flag)
    marginal = (edge_h < 0.07) or r.get('held_fixture_other_type', False)
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
        'sizing': '$150 (marginal)' if marginal else '$250 (full-edge)',
    })

TYPE_RANK = {'total': 0, 'btts': 1, 'spread': 2}

# Coordinator rule (24h ad-hoc): other types on held fixtures allowed ONLY if
# uncorrelated. BTTS-Yes on an O2.5-Over-held fixture is positively correlated
# (both lose on a low-scoring win, both win in a goalfest) -> HARD EXCLUDE.
excluded_held = [c for c in cands if c.get('held_fixture_other_type', False)]
cands = [c for c in cands if not c.get('held_fixture_other_type', False)]

cands.sort(key=lambda c: (TYPE_RANK.get(c['kind'], 9), -c['edge_exec_haircut']))

seen_mk = {}
final = []
for c in cands:
    k1 = (c['match'], c['kind'])
    if k1 in seen_mk: continue
    if seen_mk.get(c['match'], 0) >= 2: continue
    seen_mk[k1] = True
    seen_mk[c['match']] = seen_mk.get(c['match'], 0) + 1
    final.append(c)
final = final[:2]  # coordinator: max 2 new positions

print('candidates passing all gates (post-haircut >=5c):', len(cands))
for i, c in enumerate(cands):
    print('%2d %-46s %-56s %-22s ask=%.4f med=%.3f edge=%+.3f hcut=%s eh=%+.3f sprd=%.3f liq=%8s d2c=%s %s %s%s' % (
        i, c['match'][:46], c['question'][:56], str(c['side'])[:22],
        c['entry_ask'], c['model_median'], c['edge_exec'], c['haircut'], c['edge_exec_haircut'],
        c['var_spread'], c['liq_gamma'] or 0, c['book_depth_near2c'], c['kickoff'][:16],
        c['sizing'], ' [HELD-FIXTURE]' if c.get('held_fixture_other_type') else ''))
print()
print('final ranking (max 2):')
for i, c in enumerate(final):
    print('%2d %-46s %-50s %-20s ask=%.4f med=%.3f edge=%+.3f eh=%+.3f liq=%8s %s %s%s' % (
        i, c['match'][:46], c['question'][:50], str(c['side'])[:20],
        c['entry_ask'], c['model_median'], c['edge_exec'], c['edge_exec_haircut'],
        c['liq_gamma'] or 0, c['kickoff'][:16], c['sizing'],
        ' [HELD-FIXTURE]' if c.get('held_fixture_other_type') else ''))

json.dump({'generated_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
           'window': '2026-10-23T13:10:00Z..2026-10-24T13:10:00Z',
           'all_passing': cands, 'ranked': final,
           'excluded_held_correlated': excluded_held,
           'notes': '24h ad-hoc soccer scan. match_winner suspended. Held-fixture rules: '
                    'same-type excluded; spread AND BTTS on O2.5-held fixtures excluded as '
                    'correlated (coordinator: other types allowed only if uncorrelated; '
                    'BTTS-Yes correlates with Over-2.5). 50-50 haircut halved edges with '
                    'model median in [0.45,0.55]. Max 2 new positions; $250 full-edge / '
                    '$150 marginal. Empty ranked = honest pass.'},
          open('/home/ubuntu/paper-sim/round14/soccer24h_candidates.json', 'w'), indent=1)
print()
print('saved round14/soccer24h_candidates.json')
