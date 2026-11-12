#!/usr/bin/env python3
"""Round-29 crypto sub-scan (PAPER ONLY). Fetches fresh books, Binance data,
runs gamma scan for barrier markets. Writes round29/raw/crypto_scan.json ONLY."""
import json, math, re, time, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta

OUT = '/home/ubuntu/paper-sim/round29/raw/crypto_scan.json'
NOW = datetime.now(timezone.utc)

def get(url, timeout=25, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (paper-sim r29)'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            if i == tries - 1:
                return {'_error': str(e), '_url': url}
            time.sleep(1.5 * (i + 1))

def norm_cdf(x):
    return 0.5 * math.erfc(-x / math.sqrt(2.0))

def phi(x):
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)

# ---- first-passage touch probability (drifted GBM, reflection form) ----
def touch_down(S, K, T_days, sig_d, mu_log):
    if T_days <= 0 or K >= S: return 1.0 if K >= S else 0.0
    b = math.log(K / S); sq = sig_d * math.sqrt(T_days)
    t1 = norm_cdf((b - mu_log * T_days) / sq)
    t2 = math.exp(2 * mu_log * b / (sig_d ** 2)) * norm_cdf((b + mu_log * T_days) / sq)
    return min(1.0, t1 + t2)

def touch_up(S, K, T_days, sig_d, mu_log):
    if T_days <= 0 or K <= S: return 1.0 if K <= S else 0.0
    a = math.log(K / S); sq = sig_d * math.sqrt(T_days)
    t1 = norm_cdf((mu_log * T_days - a) / sq)
    t2 = math.exp(-2 * mu_log * a / (sig_d ** 2)) * norm_cdf(-(mu_log * T_days + a) / sq)
    return min(1.0, t1 + t2)

def probs_both(kind, S, K, T, sig):
    muA = 0.0
    muB = -0.5 * sig ** 2
    f = touch_down if kind == 'dn' else touch_up
    return {'A': round(f(S, K, T, sig, muA), 4), 'B': round(f(S, K, T, sig, muB), 4)}

# ---- vol from 6h klines: RMS log-ret * sqrt(4) = daily ----
def vol_windows(kl, windows={'7d': 28, '30d': 120, '60d': 240}):
    # drop last (partial) bar
    bars = kl[:-1]
    closes = [float(b[4]) for b in bars]
    rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
    out = {}
    for w, n in windows.items():
        r = rets[-n:] if len(rets) >= n else rets
        rms = math.sqrt(sum(x * x for x in r) / len(r))
        out[w] = round(rms * math.sqrt(4), 5)
    out['n_bars_used'] = len(rets)
    return out

def book_walk(book, shares):
    bids = sorted(book.get('bids', []), key=lambda x: -float(x['price']))
    rem = shares; cash = 0.0; fills = []
    for lvl in bids:
        px = float(lvl['price']); sz = float(lvl['size'])
        take = min(rem, sz)
        cash += take * px; rem -= take; fills.append([px, take])
        if rem <= 1e-9: break
    return {'realizable_cash': round(cash, 2), 'filled': round(shares - rem, 2),
            'avg_px': round(cash / (shares - rem), 4) if rem < shares else None,
            'fully_filled': rem <= 1e-6, 'fills_top': fills[:6], 'unfilled': round(max(0, rem), 2)}

res = {'generated_at': NOW.isoformat(), 'mode': 'PAPER ONLY - round 29 crypto sub-scan, team AT CAP (monitoring + report-only)'}

# ================= 1. Binance spot + klines =================
spots = {}
for sym in ['ETHUSDT', 'BTCUSDT']:
    t = get(f'https://api.binance.com/api/v3/ticker/price?symbol={sym}')
    spots[sym[:3]] = float(t['price']) if 'price' in t else None
res['spot_binance'] = spots

klines6 = {}
vols = {}
for sym in ['ETHUSDT', 'BTCUSDT']:
    kl = get(f'https://api.binance.com/api/v3/klines?symbol={sym}&interval=6h&limit=250')
    klines6[sym[:3]] = kl
    vols[sym[:3]] = vol_windows(kl)
res['realized_vol_daily_6h'] = vols

# recent lows from 6h bars (last 10 days) + 1h bars for finer low
eth6 = klines6['ETH']
lows10d = [(float(b[3]), datetime.fromtimestamp(b[0] / 1000, tz=timezone.utc).isoformat()) for b in eth6[-40:]]
mn10 = min(lows10d)
eth1h = get('https://api.binance.com/api/v3/klines?symbol=ETHUSDT&interval=1h&limit=240')
lows1h = [(float(b[3]), datetime.fromtimestamp(b[0] / 1000, tz=timezone.utc).isoformat()) for b in eth1h]
mn1h = min(lows1h)
first_touch_2250 = next((ts for lo, ts in lows1h if lo <= 2250.0), None)
last_time_le_2250 = None
for lo, ts in lows1h:
    if lo <= 2250.0: last_time_le_2250 = ts
res['eth_recent_lows'] = {
    'low_10d_6h': mn10, 'low_10d_1h': mn1h,
    'first_1h_bar_le_2250': first_touch_2250, 'last_1h_bar_le_2250': last_time_le_2250,
    'bars_below_2250_last_10d_1h': sum(1 for lo, _ in lows1h if lo <= 2250.0),
    'bars_below_2000_last_10d_1h': sum(1 for lo, _ in lows1h if lo <= 2000.0),
}
btc6 = klines6['BTC']
res['btc_low_10d'] = min([(float(b[3]), datetime.fromtimestamp(b[0] / 1000, tz=timezone.utc).isoformat()) for b in btc6[-40:]])

# ================= 2. Held positions: fresh CLOB books =================
HELD = {
    'ETH2000_YES': ('84768145019786095547717415732823502270141145470320952547313245070010555237775', 1208.0),
    'ETH2000_NO':  ('41139993928652620342595776605433147455405569646745899886663605344607611434891', None),
    'BTC65K_YES':  ('53780045235418715931128205720209124033878539466833083429441668150974549326823', None),
    'BTC65K_NO':   ('104072675121616169708481552608019889218004323979484070212305769583143217407441', 384.6),
}
held_books = {}
for k, (aid, sh) in HELD.items():
    b = get(f'https://clob.polymarket.com/book?token_id={aid}')
    entry = {'asset_id': aid, 'timestamp': b.get('timestamp'), 'hash': b.get('hash')}
    bids = b.get('bids', []); asks = b.get('asks', [])
    if isinstance(bids, list) and bids:
        entry['best_bid'] = float(bids[0]['price']); entry['bid_sz'] = float(bids[0]['size'])
    if isinstance(asks, list) and asks:
        entry['best_ask'] = float(asks[0]['price']); entry['ask_sz'] = float(asks[0]['size'])
    if entry.get('best_bid') is not None and entry.get('best_ask') is not None:
        entry['mid'] = round((entry['best_bid'] + entry['best_ask']) / 2, 4)
        entry['spread_c'] = round(entry['best_ask'] - entry['best_bid'], 3)
    if sh:
        entry['bid_walk'] = book_walk(b, sh)
    held_books[k] = entry
    time.sleep(0.25)
res['held_books'] = held_books

# gamma last trade / resolution for held markets
GAMMA_IDS = {'ETH2250': '3866000', 'ETH2000': '3865999', 'BTC65K': None}
for name, gid in GAMMA_IDS.items():
    if gid:
        m = get(f'https://gamma-api.polymarket.com/markets/{gid}')
        GAMMA_IDS[name] = {'gid': gid, 'q': m.get('question'), 'closed': m.get('closed'),
                           'resolved': m.get('outcomePrices'), 'umaResolutionStatus': m.get('umaResolutionStatus')}
res['held_gamma'] = GAMMA_IDS

json.dump(res, open('/tmp/r29_part1.json', 'w'), indent=1)
print('PART1 OK', json.dumps({'spot': spots, 'vols': vols, 'eth_low': mn1h}, default=str))
