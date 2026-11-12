"""Round-14 24h CLOB executable-price pass: shortlisted markets, both tokens,
$250 executable ask (VWAP), best bid, depth; edge vs model median."""
import json, time, urllib.request, urllib.error

RAW = '/home/ubuntu/paper-sim/round14/raw'
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

sl = json.load(open(RAW + '/shortlist_prelim.json'))
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
        time.sleep(0.25)
    q0 = s['q0_med']
    b0 = row['books'].get('tok0', {}).get('ask', {}) or {}
    b1 = row['books'].get('tok1', {}).get('ask', {}) or {}
    a0 = b0.get('vwap'); a1 = b1.get('vwap')
    row['exec_ask0'] = a0; row['exec_ask1'] = a1
    row['edge0_exec'] = round(q0 - a0, 4) if a0 else None
    row['edge1_exec'] = round((1 - q0) - a1, 4) if a1 else None
    results.append(row)
    e0 = row['edge0_exec']; e1 = row['edge1_exec']
    print('%-44s %-38s ask0=%-7s e0=%-7s ask1=%-7s e1=%-7s' % (
        s['match'][:44], (s['q'][:34] + '..')[:38], a0, e0, a1, e1), flush=True)

json.dump(results, open(RAW + '/shortlist_books.json', 'w'), indent=1)
print('saved shortlist_books.json')
