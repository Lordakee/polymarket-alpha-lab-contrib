"""ROUND-44B fetch part 2: per-condId Dec-31 refresh, intraday klines, CLOB books.

PAPER ONLY, no DB writes. ids=/condition_ids list params are broken on Gamma;
single condition_id works. CLOB books fetched for the ETH-2000 primary and the
barrier-table / candidate markets selected from Gamma events + refreshed
standalone markets.
"""
import json, urllib.request, urllib.parse, time, datetime, os, re

RAW = '/home/ubuntu/paper-sim/round44/raw'

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

# ---- 1) Refresh the 83 standalone by-Dec-31 markets, one condId at a time ----
prev = json.load(open('/home/ubuntu/paper-sim/round15/raw/crypto_scan.json'))['classified_markets']
conds = [m['condId'] for m in prev if m.get('condId')]
fresh = {}
for i, c in enumerate(conds):
    try:
        ms = get('https://gamma-api.polymarket.com/markets?condition_ids=' + c)
        for m in ms:
            if m.get('conditionId'):
                fresh[m['conditionId']] = m
    except Exception as ex:
        print('cond', i, 'ERR', ex, flush=True)
    time.sleep(0.35)
json.dump({'fetched_at': NOW.isoformat(), 'markets': fresh},
          open(f'{RAW}/market_refresh_dec31.json', 'w'))
print('fresh dec31-series markets:', len(fresh), flush=True)
open_m = [m for m in fresh.values() if not m.get('closed') and m.get('active')]
print('open+active:', len(open_m), flush=True)

# ---- 2) Intraday klines: 5m since Nov 9 00:00 UTC (touch-window checks) ----
t0 = int(datetime.datetime(2026, 11, 9, tzinfo=datetime.timezone.utc).timestamp() * 1000)
for sym, bn in [('ETH', 'ETHUSDT'), ('BTC', 'BTCUSDT'), ('SOL', 'SOLUSDT'), ('XRP', 'XRPUSDT')]:
    rows, start = [], t0
    while True:
        d = get(f'https://api.binance.com/api/v3/klines?symbol={bn}&interval=5m&startTime={start}&limit=1000')
        if not d:
            break
        for r in d:
            rows.append([r[0] // 1000, float(r[3]), float(r[2]), float(r[1]), float(r[4])])
        if len(d) < 1000:
            break
        start = d[-1][0] + 300 * 1000
        time.sleep(0.3)
    json.dump(rows, open(f'{RAW}/{sym.lower()}_5m_nov9.json', 'w'))
    print(sym, '5m bars today', len(rows),
          'low', min((r[1] for r in rows), default=None),
          'high', max((r[2] for r in rows), default=None), flush=True)

# ---- 3) ETH+BTC 1h klines since Oct 24 (proximity clock, window lows) ----
t0b = int(datetime.datetime(2026, 10, 24, tzinfo=datetime.timezone.utc).timestamp() * 1000)
for sym, bn in [('ETH', 'ETHUSDT'), ('BTC', 'BTCUSDT')]:
    rows, start = [], t0b
    while True:
        d = get(f'https://api.binance.com/api/v3/klines?symbol={bn}&interval=1h&startTime={start}&limit=1000')
        if not d:
            break
        for r in d:
            rows.append([r[0] // 1000, float(r[3]), float(r[2]), float(r[1]), float(r[4])])
        if len(d) < 1000:
            break
        start = d[-1][0] + 3600 * 1000
        time.sleep(0.3)
    json.dump(rows, open(f'{RAW}/{sym.lower()}_1h_oct24.json', 'w'))
    print(sym, '1h bars since Oct24', len(rows), 'low', min(r[1] for r in rows),
          'high', max(r[2] for r in rows), flush=True)

print('DONE fetch44b', flush=True)
