"""Round-20 Serie A: CLOB $250-VWAP books for picked markets + near-misses."""
import json, time, urllib.request

RAW = '/home/ubuntu/paper-sim/round20/raw'
DOLLARS = 250.0

def get(url, tries=4):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.load(r)
        except Exception as e:
            last = e; time.sleep(1.5 + i)
    return {'err': repr(last)}

def walk(levels, dollars=DOLLARS):
    lv = sorted(((float(l['price']), float(l['size'])) for l in levels), key=lambda x: x[0])
    if not lv: return {'best': None, 'vwap': None, 'filled': False, 'depth': 0.0}
    best = lv[0][0]
    cash = 0.0; sh = 0.0
    for p, sz in lv:
        take = min(sz, (dollars - cash) / p)
        if take <= 0: break
        cash += take * p; sh += take
        if cash >= dollars - 1e-9: break
    vwap = (cash / sh) if sh > 0 else best
    near = sum(p * sz for p, sz in lv if p <= best + 0.02)
    return {'best': round(best, 4), 'vwap': round(vwap, 4),
            'filled': cash >= dollars - 1e-6, 'depth_near2c': round(near, 0)}

def walk_bids(bids, dollars=DOLLARS):
    lv = sorted(((float(l['price']), float(l['size'])) for l in bids), key=lambda x: -x[0])
    if not lv: return {'best': None, 'vwap': None, 'filled': False, 'depth': 0.0}
    best = lv[0][0]
    cash = 0.0; sh = 0.0
    for p, sz in lv:
        take = min(sz, (dollars - cash) / p)
        if take <= 0: break
        cash += take * p; sh += take
        if cash >= dollars - 1e-9: break
    vwap = (cash / sh) if sh > 0 else best
    near = sum(p * sz for p, sz in lv if p >= best - 0.02)
    return {'best': round(best, 4), 'vwap': round(vwap, 4),
            'filled': cash >= dollars - 1e-6, 'depth_near2c': round(near, 0)}

picks = json.load(open(RAW + '/seriea_pick20.json'))
out = []
for s in picks:
    toks = s['tokens']
    if isinstance(toks, str): toks = json.loads(toks)
    row = dict(s); row['books'] = {}
    for i, tok in enumerate(toks[:2]):
        b = get('https://clob.polymarket.com/book?token_id=' + tok)
        if 'err' in b:
            row['books']['tok%d' % i] = {'err': b['err']}
        else:
            row['books']['tok%d' % i] = {
                'ask': walk(b.get('asks') or []),
                'bid': walk_bids(b.get('bids') or []),
                'ts': b.get('timestamp'), 'hash': b.get('hash')}
        time.sleep(1.1)
    # exec math: tok0=Over, tok1=Under
    b0 = row['books'].get('tok0') or {}; b1 = row['books'].get('tok1') or {}
    a0 = b0.get('ask'); a1 = b1.get('ask')
    row['exec_ask_over'] = a0['vwap'] if a0 and a0.get('filled') else None
    row['exec_ask_under'] = a1['vwap'] if a1 and a1.get('filled') else None
    row['exit_bid_over'] = b0['bid']['vwap'] if b0.get('bid') and b0['bid'].get('filled') else None
    row['exit_bid_under'] = b1['bid']['vwap'] if b1.get('bid') and b1['bid'].get('filled') else None
    p = s['p0_med']; pmin = s['p0_min']; pmax = s['p0_max']
    e = {}
    if row['exec_ask_over'] is not None:
        e['over_exec'] = round(p - row['exec_ask_over'], 4)
        e['over_worst'] = round(pmin - row['exec_ask_over'], 4)
    if row['exec_ask_under'] is not None:
        e['under_exec'] = round((1 - p) - row['exec_ask_under'], 4)
        e['under_worst'] = round((1 - pmax) - row['exec_ask_under'], 4)
    row['edges'] = e
    out.append(row)
    print('%-40s %-30s over: ask=%s exec=%+5s worst=%+5s | under: ask=%s exec=%+5s worst=%+5s' % (
        s['match'][:40], s['q'].split(': ')[-1][:30],
        row['exec_ask_over'], e.get('over_exec'), e.get('over_worst'),
        row['exec_ask_under'], e.get('under_exec'), e.get('under_worst')))

json.dump(out, open(RAW + '/seriea_books20.json', 'w'), indent=1)
print('saved seriea_books20.json', len(out))
