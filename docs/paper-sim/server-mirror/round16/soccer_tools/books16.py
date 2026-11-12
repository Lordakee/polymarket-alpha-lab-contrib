"""CLOB $250 VWAP for the round-16 shortlist plus the held Lens O1.5 token."""
import json, time, urllib.request

RAW = '/home/ubuntu/paper-sim/round16/raw'
DOLLARS = 250.0

def get(url, tries=4):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.load(r)
        except Exception as e:
            last = e
            time.sleep(1.2 + i)
    return {'err': repr(last)}

def walk(levels, dollars, side):
    if side == 'ask':
        lv = sorted(((float(l['price']), float(l['size'])) for l in levels), key=lambda x: x[0])
    else:
        lv = sorted(((float(l['price']), float(l['size'])) for l in levels), key=lambda x: -x[0])
    if not lv:
        return {'best': None, 'vwap': None, 'filled': False, 'depth_near2c': 0.0}
    best = lv[0][0]
    cash = 0.0
    sh = 0.0
    for p, sz in lv:
        take = min(sz, (dollars - cash) / p) if p > 0 else 0
        if take <= 0:
            break
        cash += take * p
        sh += take
        if cash >= dollars - 1e-9:
            break
    vwap = (cash / sh) if sh > 0 else best
    if side == 'ask':
        near = sum(p * sz for p, sz in lv if p <= best + 0.02)
    else:
        near = sum(p * sz for p, sz in lv if p >= best - 0.02)
    return {'best': round(best, 4), 'vwap': round(vwap, 4),
            'filled': cash >= dollars - 1e-6, 'spent': round(cash, 2),
            'depth_near2c': round(near, 0)}

sl = json.load(open(RAW + '/shortlist_bund.json'))
rows = []
for s in sl:
    toks = s['tokens']
    if isinstance(toks, str):
        toks = json.loads(toks)
    row = dict(s)
    row['books'] = {}
    for i, tok in enumerate(toks[:2]):
        b = get('https://clob.polymarket.com/book?token_id=' + tok)
        if 'err' in b:
            row['books']['tok%d' % i] = {'err': b['err']}
        else:
            row['books']['tok%d' % i] = {
                'ask': walk(b.get('asks', []), DOLLARS, 'ask'),
                'bid': walk(b.get('bids', []), DOLLARS, 'bid'),
                'ts': b.get('timestamp'),
            }
        time.sleep(0.3)
    q0 = s['q0_med']
    qmin = s['q0_min']
    qmax = s['q0_max']
    a0 = (row['books'].get('tok0', {}).get('ask') or {}).get('vwap')
    a1 = (row['books'].get('tok1', {}).get('ask') or {}).get('vwap')
    row['exec_ask0'] = a0
    row['exec_ask1'] = a1
    row['edge0_exec'] = None if a0 is None else round(q0 - a0, 4)
    row['edge1_exec'] = None if a1 is None else round((1 - q0) - a1, 4)
    row['worst0'] = None if a0 is None else round(qmin - a0, 4)
    row['worst1'] = None if a1 is None else round((1 - qmax) - a1, 4)
    rows.append(row)
    print('%-46s ask0=%s e0=%s worst0=%s ask1=%s e1=%s worst1=%s' % (
        s['q'][:46], a0, row['edge0_exec'], row['worst0'], a1, row['edge1_exec'], row['worst1']))

# held Lens O1.5
HELD_TOK = '113478505921291345757646047144512080105023507666947065227710701857377544814788'
b = get('https://clob.polymarket.com/book?token_id=' + HELD_TOK)
held = {'token': HELD_TOK, 'question': 'Racing Club de Lens vs. Paris FC: O/U 1.5', 'side': 'Over', 'entry': 0.81}
if 'err' in b:
    held['err'] = b['err']
else:
    held['ask'] = walk(b.get('asks', []), DOLLARS, 'ask')
    held['bid'] = walk(b.get('bids', []), DOLLARS, 'bid')
    held['ts'] = b.get('timestamp')
print('HELD Lens O1.5 bid', held.get('bid'), 'ask', held.get('ask'))

json.dump({'generated_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
           'shortlist_books': rows, 'held_lens': held},
          open(RAW + '/bund_books.json', 'w'), indent=1)
print('saved bund_books.json')
