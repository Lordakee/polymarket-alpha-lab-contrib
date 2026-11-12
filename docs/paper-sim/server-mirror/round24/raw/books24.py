"""Round-24 EPL CLOB executable-price pass: $250-VWAP asks/bids + depth for every
shortlist market (both tokens). Gates need exec prices, not Gamma mids.
Pace >= 1s between requests."""
import json, time, urllib.request

RAW = '/home/ubuntu/paper-sim/round24/raw'
DOLLARS = 250.0

def get(url, tries=5):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.load(r)
        except Exception as e:
            last = e; time.sleep(1.5 + i)
    return {'err': repr(last)}

def walk(books, dollars=DOLLARS):
    lv = sorted(((float(l['price']), float(l['size'])) for l in books), key=lambda x: x[0])
    if not lv: return {'best': None, 'vwap': None, 'depth': 0.0}
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
    if not lv: return {'best': None, 'vwap': None, 'depth': 0.0}
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

sl = json.load(open(RAW + '/shortlist24.json'))
print('shortlist entries:', len(sl))
results = []
for s in sl:
    toks = s['tokens']
    if isinstance(toks, str): toks = json.loads(toks)
    row = dict(s); row['books'] = {}
    for i, tok in enumerate(toks[:2]):
        b = get('https://clob.polymarket.com/book?token_id=' + tok)
        if 'err' in b:
            row['books']['tok%d' % i] = {'err': b['err']}
        else:
            row['books']['tok%d' % i] = {
                'ask': walk(b.get('asks', [])),
                'bid': walk_bids(b.get('bids', [])),
                'hash': b.get('hash'), 'ts': b.get('timestamp')}
        time.sleep(1.0)
    b0 = row['books'].get('tok0', {}).get('ask', {}) or {}
    b1 = row['books'].get('tok1', {}).get('ask', {}) or {}
    bid0 = row['books'].get('tok0', {}).get('bid', {}) or {}
    bid1 = row['books'].get('tok1', {}).get('bid', {}) or {}
    q0 = s['q0_med']; qs = s['qs_variants']
    row['exec_ask0'] = b0.get('vwap'); row['exec_ask1'] = b1.get('vwap')
    row['exit_bid0'] = bid0.get('best'); row['exit_bid1'] = bid1.get('best')
    row['depth0'] = b0.get('depth_near2c'); row['depth1'] = b1.get('depth_near2c')
    row['fill0'] = b0.get('filled'); row['fill1'] = b1.get('filled')
    row['edge0_exec'] = round(q0 - b0['vwap'], 4) if b0.get('vwap') else None
    row['edge1_exec'] = round((1 - q0) - b1['vwap'], 4) if b1.get('vwap') else None
    row['worst_var_edge0'] = round(min(qs) - b0['vwap'], 4) if b0.get('vwap') else None
    row['worst_var_edge1'] = round((1 - max(qs)) - b1['vwap'], 4) if b1.get('vwap') else None
    results.append(row)
    print('%-66s ask0=%-7s e0=%-7s wv0=%-7s | ask1=%-7s e1=%-7s wv1=%-7s' % (
        s['q'][:66], b0.get('vwap'), row['edge0_exec'], row['worst_var_edge0'],
        b1.get('vwap'), row['edge1_exec'], row['worst_var_edge1']), flush=True)

json.dump(results, open(RAW + '/books24.json', 'w'), indent=1)
print('saved books24.json')
