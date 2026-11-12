"""Round-20 Serie A: edge table vs fresh Gamma mids -> CLOB shortlist."""
import json

d = json.load(open('/home/ubuntu/paper-sim/round20/raw/seriea_model20.json'))
rows = []
for base, rec in d['matches'].items():
    for q, m in rec['markets'].items():
        kind = m['kind']
        if kind not in ('total', 'btts', 'teamtotal'):
            continue
        liq = m['liq'] or 0
        mid = m['mid']
        if mid is None or liq < 3000:
            continue
        e0 = m['p0_med'] - mid          # edge side0 (Over)
        e1 = (1 - m['p0_med']) - (1 - mid)  # = -e0 (Under edge vs complement mid)
        rows.append({'match': base, 'q': q, 'kind': kind, 'liq': liq, 'mid': mid,
                     'bid': m['bid'], 'ask': m['ask'],
                     'p0_med': m['p0_med'], 'p0_min': m['p0_min'], 'p0_max': m['p0_max'],
                     'var_spread': m['var_spread'],
                     'r19_p0': m['r19_p0_med'], 'r19_vs': m['r19_var_spread'],
                     'd_p0': m['delta_p0_med'], 'd_vs': m['delta_var_spread'],
                     'edge_over': round(e0, 4), 'edge_under': round(-e0, 4),
                     'in_window': rec['in_window'], 'tokens': m['tokens'], 'id': m['id']})

rows.sort(key=lambda r: -max(abs(r['edge_over']), abs(r['edge_under'])))
print('%-44s %-38s %7s %6s %6s %6s %6s %6s  %6s %6s' % ('match', 'market', 'liq', 'mid', 'p0', 'vsprd', 'eOv', 'eUn', 'd_p0', 'd_vs'))
for r in rows:
    print('%-44s %-38s %7d %6.3f %6.4f %6.4f %+6.3f %+6.3f  %+6.3f %+6.3f' % (
        r['match'][:44], r['q'].split(': ')[-1][:38], r['liq'], r['mid'], r['p0_med'], r['var_spread'],
        r['edge_over'], r['edge_under'], r['d_p0'] if r['d_p0'] is not None else 0, r['d_vs'] if r['d_vs'] is not None else 0))

json.dump(rows, open('/home/ubuntu/paper-sim/round20/raw/seriea_edges20.json', 'w'), indent=1)
print('saved seriea_edges20.json rows=', len(rows))
