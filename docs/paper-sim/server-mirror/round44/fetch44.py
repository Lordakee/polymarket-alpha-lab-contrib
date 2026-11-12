"""ROUND-44B fetch: crypto paper-sim scan raw inputs. PAPER ONLY, no DB writes.

Fetches: Binance spot + 6h klines (ETH/BTC/SOL/XRP), Gamma market 3865999,
Gamma touch/price events (weekly Nov 9-15, daily Nov 9/10, in-2026/Dec-31
series, SOL/XRP), refreshed by-Dec-31 dip/reach markets from the round15
classified list, and CLOB books for the barrier-table tokens.
"""
import json, urllib.request, urllib.parse, time, datetime, os

RAW = '/home/ubuntu/paper-sim/round44/raw'
os.makedirs(RAW, exist_ok=True)

def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as ex:
            if i == tries - 1:
                raise
            time.sleep(2.5)

NOW = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
print('now', NOW.isoformat(), flush=True)
meta = {'fetched_at': NOW.isoformat()}

# ---- 1) Spot: Binance (fallback Coinbase for ETH/BTC) ----
SPOTS = {'ETH': 'ETHUSDT', 'BTC': 'BTCUSDT', 'SOL': 'SOLUSDT', 'XRP': 'XRPUSDT'}
CB = {'ETH': 'ETH-USD', 'BTC': 'BTC-USD'}
spot, spot_src = {}, {}
for sym, bn in SPOTS.items():
    try:
        d = get(f'https://api.binance.com/api/v3/ticker/price?symbol={bn}')
        spot[sym] = float(d['price']); spot_src[sym] = 'binance'
    except Exception as ex:
        print(sym, 'binance ERR', ex, flush=True)
        d = get(f'https://api.exchange.coinbase.com/products/{CB[sym]}/ticker')
        spot[sym] = float(d['price']); spot_src[sym] = 'coinbase'
    time.sleep(0.4)
print('SPOT', spot, spot_src, flush=True)
json.dump({'fetched_at': NOW.isoformat(), 'spot': spot, 'src': spot_src},
          open(f'{RAW}/spot.json', 'w'))

# ---- 2) Binance 6h klines back to 2026-07-01 (full 87d window + buffer) ----
start0 = int(datetime.datetime(2026, 7, 1, tzinfo=datetime.timezone.utc).timestamp() * 1000)
for sym, bn in SPOTS.items():
    rows_all, start = [], start0
    while True:
        u = (f'https://api.binance.com/api/v3/klines?symbol={bn}&interval=6h'
             f'&startTime={start}&limit=1000')
        d = get(u)
        if not d:
            break
        # [t0_s, low, high, open, close, volume]
        for r in d:
            rows_all.append([r[0] // 1000, float(r[3]), float(r[2]), float(r[1]), float(r[4]), float(r[5])])
        if len(d) < 1000:
            break
        start = d[-1][0] + 6 * 3600 * 1000
        time.sleep(0.4)
    rows_all.sort(key=lambda r: r[0])
    json.dump(rows_all, open(f'{RAW}/{sym.lower()}_candles.json', 'w'))
    print(sym, 'bars', len(rows_all),
          'first', datetime.datetime.fromtimestamp(rows_all[0][0], datetime.timezone.utc),
          'last_bar_t0', datetime.datetime.fromtimestamp(rows_all[-1][0], datetime.timezone.utc),
          'last_close', rows_all[-1][4], flush=True)
    time.sleep(0.4)

# ---- 3) Gamma: primary add-on market 3865999 ----
m = get('https://gamma-api.polymarket.com/markets/3865999')
json.dump(m, open(f'{RAW}/market_3865999.json', 'w'))
print('market 3865999:', m.get('question'), '| active', m.get('active'),
      '| closed', m.get('closed'), '| lastTrade', m.get('lastTradePrice'),
      '| liq', m.get('liquidityNum') or m.get('liquidity'),
      '| end', m.get('endDate'), flush=True)

# ---- 4) Gamma events: weekly/daily touch + annual hit series ----
EVENTS = {
    'ETH_weekly_touch_nov9_15': 1346293,
    'ETH_daily_touch_nov9': 1346295,
    'ETH_in_november': 1292830,
    'ETH_in_2026': 89519,
    'BTC_weekly_touch_nov9_15': 1346285,
    'BTC_daily_touch_nov9': 1346284,
    'BTC_in_november': 1292829,
    'BTC_in_2026': 89502,
    'SOL_weekly_touch_nov9_15': 1346308,
    'SOL_daily_touch_nov9': None,   # discovered below
    'SOL_in_november': 1292831,
    'SOL_in_2026': 89525,
    'XRP_weekly_touch_nov9_15': 1346320,
    'XRP_daily_touch_nov9': 1346319,
    'XRP_in_november': 1292832,
    'XRP_in_2026': 89530,
}
# discover SOL daily touch event id if missing
try:
    d = get('https://gamma-api.polymarket.com/public-search?q=' + urllib.parse.quote('What price will Solana hit on November') + '&limit_per_type=8')
    for e in d.get('events', []):
        t = e.get('title') or ''
        if 'Solana hit on November 9' in t and not e.get('closed'):
            EVENTS['SOL_daily_touch_nov9'] = e.get('id')
            break
except Exception as ex:
    print('sol daily search ERR', ex, flush=True)
time.sleep(0.5)

ev_out = {}
for k, eid in EVENTS.items():
    if eid is None:
        print('event', k, 'NOT FOUND (skipped)', flush=True)
        continue
    try:
        e = get(f'https://gamma-api.polymarket.com/events/{eid}')
        ev_out[k] = e
        ms = e.get('markets', [])
        print('event', k, eid, '|', e.get('title'), '| closed', e.get('closed'),
              '| n_markets', len(ms), flush=True)
    except Exception as ex:
        print('event', k, eid, 'ERR', ex, flush=True)
    time.sleep(0.6)
json.dump(ev_out, open(f'{RAW}/events_touch.json', 'w'))

# ---- 5) Daily terminal price events (Nov 10/11 ETH+BTC, coherence context) ----
term_ids = {}
for q, key in [('Ethereum price on November 10', 'ETH_price_nov10'),
               ('Ethereum price on November 11', 'ETH_price_nov11'),
               ('Bitcoin price on November 10', 'BTC_price_nov10'),
               ('Bitcoin price on November 11', 'BTC_price_nov11')]:
    try:
        d = get('https://gamma-api.polymarket.com/public-search?q=' + urllib.parse.quote(q) + '&limit_per_type=4')
        for e in d.get('events', []):
            if (e.get('title') or '').strip('?') == q and not e.get('closed'):
                term_ids[key] = e.get('id')
                break
    except Exception as ex:
        print('term search', q, 'ERR', ex, flush=True)
    time.sleep(0.5)
term_out = {}
for k, eid in term_ids.items():
    try:
        e = get(f'https://gamma-api.polymarket.com/events/{eid}')
        term_out[k] = e
        print('terminal event', k, eid, '|', e.get('title'), '| n_markets', len(e.get('markets', [])), flush=True)
    except Exception as ex:
        print('terminal event', k, 'ERR', ex, flush=True)
    time.sleep(0.6)
json.dump(term_out, open(f'{RAW}/events_terminal_daily.json', 'w'))

# ---- 6) Refresh by-Dec-31 dip/reach markets from round15 classified list ----
prev = json.load(open('/home/ubuntu/paper-sim/round15/raw/crypto_scan.json'))['classified_markets']
conds = [m['condId'] for m in prev if m.get('condId')]
print('condIds to refresh:', len(conds), flush=True)
fresh = {}
for i in range(0, len(conds), 20):
    batch = conds[i:i + 20]
    try:
        ms = get('https://gamma-api.polymarket.com/markets?condition_ids=' + ','.join(batch))
        for m in ms:
            if m.get('conditionId'):
                fresh[m['conditionId']] = m
    except Exception as ex:
        print('batch', i, 'ERR', ex, flush=True)
    time.sleep(0.8)
json.dump({'fetched_at': NOW.isoformat(), 'markets': fresh},
          open(f'{RAW}/market_refresh_dec31.json', 'w'))
print('fresh dec31-series markets:', len(fresh), flush=True)

print('DONE fetch44', flush=True)
