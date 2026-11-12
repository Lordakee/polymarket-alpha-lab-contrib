"""Round-26 scan A: CLOB books for the pre-CLOB shortlist + r25 near-miss recheck rows.
Walks via the library gates.walk_book ($250 ask VWAP + bid best). Pace >= 1.1s."""
import json, time, urllib.request
from polymarket_alpha_lab.papersim import gates

RAW = '/home/ubuntu/paper-sim/round26/raw'

SHORTLIST = [
    ("Elche-Valencia", "over_2.5"),
    ("Elche-Valencia", "over_3.5"),
    ("Lecce-Genoa", "tt_away_over_1.5"),
    ("Lecce-Genoa", "over_2.5"),
    ("Lazio-Cagliari", "tt_away_over_1.5"),
    ("Lazio-Cagliari", "tt_away_over_0.5"),
    ("Juventus-Napoli", "ml_home"),
    ("Juventus-Napoli", "tt_home_over_1.5"),
    ("Athletic-RealSociedad", "ml_home"),
    ("RacingSantander-RealMadrid", "tt_home_over_2.5"),
    ("RacingSantander-RealMadrid", "under_3.5"),
    ("Frosinone-Torino", "over_2.5"),
    ("Frosinone-Torino", "under_3.5"),
    ("Getafe-Sevilla", "ml_home"),
]

def get(url, tries=5):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'research/0.1'})
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.load(r)
        except Exception as e:
            last = e
            time.sleep(1.5 + i)
    return {'__err__': repr(last)}

model = json.load(open(RAW + '/model26_a.json'))
rows = {(r['fixture'], r['key']): r for r in model['rows']}

# market-level token sets: fetch both tokens of each market (entry side + opposite for exit context)
markets = {}
for fx, key in SHORTLIST:
    r = rows.get((fx, key))
    if r is None:
        print('MISSING ROW', fx, key)
        continue
    markets[r['market_id']] = {'fixture': fx, 'key': key, 'q': r['q']}
    # find opposite-side token of same market
    opp = None
    base = key.split('_over')[0].split('_under')[0] if key.startswith('tt_') else None
    if key.startswith('over_'):
        line = key.split('_')[1]
        opp = rows.get((fx, 'under_' + line))
    elif key.startswith('under_'):
        line = key.split('_')[1]
        opp = rows.get((fx, 'over_' + line))
    elif key.startswith('tt_') and '_over_' in key:
        base, line = key.split('_over_')
        opp = rows.get((fx, base + '_under_' + line))
    elif key.startswith('tt_') and '_under_' in key:
        base, line = key.split('_under_')
        opp = rows.get((fx, base + '_over_' + line))
    if opp is not None and opp['market_id'] == r['market_id']:
        markets[r['market_id']]['opp_key'] = opp['key']
        markets[r['market_id']]['opp_token'] = opp['token']
        markets[r['market_id']]['opp_model'] = {
            'med': opp['model_med'], 'min': opp['model_min'], 'max': opp['model_max'],
            'var_spread': opp['var_spread'], 'qs_variants': opp['qs_variants']}

print('markets to fetch:', len(markets))
out = []
for mid, info in markets.items():
    row = rows[(info['fixture'], info['key'])]
    rec = {'fixture': info['fixture'], 'key': info['key'], 'q': info['q'], 'market_id': mid,
           'model': {'med': row['model_med'], 'min': row['model_min'], 'max': row['model_max'],
                     'var_spread': row['var_spread'], 'qs_variants': row['qs_variants'],
                     'liq_gamma': row['liq_gamma'], 'gamma_ask': row['gamma_ask']},
           'fetched_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'books': {}}
    toks = {'side': row['token']}
    if info.get('opp_token'):
        toks['opp'] = info['opp_token']
    for label, tok in toks.items():
        if not tok:
            continue
        b = get('https://clob.polymarket.com/book?token_id=' + tok)
        if '__err__' in b:
            rec['books'][label] = {'err': b['__err__']}
            continue
        asks = [(float(l['price']), float(l['size'])) for l in b.get('asks', [])]
        bids = [(float(l['price']), float(l['size'])) for l in b.get('bids', [])]
        aw = gates.walk_book(asks, side='ask', notional=250.0)
        bw = gates.walk_book(bids, side='bid', notional=250.0)
        rec['books'][label] = {
            'ask_walk': {'best': aw.best, 'vwap': aw.vwap, 'filled': aw.filled, 'filled_notional': aw.filled_notional, 'depth_near2c': aw.depth_near2c},
            'bid_walk': {'best': bw.best, 'vwap': bw.vwap, 'filled': bw.filled, 'depth_near2c': bw.depth_near2c},
            'hash': b.get('hash'), 'ts': b.get('timestamp'),
            'n_levels': {'asks': len(asks), 'bids': len(bids)}}
        time.sleep(1.1)
    out.append(rec)
    eb = rec['books'].get('side', {}).get('ask_walk', {})
    print('%-26s %-18s ask_vwap=%s filled=%s depth2c=%s' % (
        rec['fixture'], rec['key'], eb.get('vwap'), eb.get('filled'), eb.get('depth_near2c')))

json.dump(out, open(RAW + '/books26_a.json', 'w'), indent=1)
print('wrote', RAW + '/books26_a.json', 'records:', len(out))
