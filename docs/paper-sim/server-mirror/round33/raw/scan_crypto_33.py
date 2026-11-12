#!/usr/bin/env python3
"""Round-33 crypto/econ scan (PAPER ONLY, team AT CAP, report-only).
Adapted from round-29 scan. Writes /home/ubuntu/paper-sim/round33/raw/crypto_scan.json
Sections: spot/vol (Binance), held MTM (fresh CLOB books w/ sanity retry), touch horizons,
gamma barrier scan (BTC/ETH, liq>=10k, executable edges), econ quick scan (fed/oil/geo).

2026-11-04 fix (codex review finding #4): all touch/terminal probabilities and
conservative edges now come from the canonical papersim library (crypto_model)
instead of inline copies. The pre-fix inline formulas had (a) a sign error in
the touch_up reflection exponent (-2*mu*a instead of +2*mu*a), (b) a double
half-variance subtraction in close_above (callers already pass total log drift),
and (c) YES/NO edges priced off convention B alone instead of the per-side
conservative bounds min(pA,pB) / 1-max(pA,pB). Future rounds must copy THIS
import-based pattern, never re-derive the formulas inline."""
import json, math, re, sys, time, urllib.request
from datetime import datetime, timezone

# Canonical model import (single source of truth for the math).
_LIB_SRC = '/home/ubuntu/polymarket-alpha-lab/src'
if _LIB_SRC not in sys.path:
    sys.path.insert(0, _LIB_SRC)
from polymarket_alpha_lab.papersim.crypto_model import (
    TouchProbability, conservative_edges, terminal_probability, touch_probability)

OUT = '/home/ubuntu/paper-sim/round33/raw/crypto_scan.json'
NOW = datetime.now(timezone.utc)

def get(url, timeout=25, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (paper-sim r33)'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            if i == tries - 1:
                return {'_error': str(e), '_url': url}
            time.sleep(1.5 * (i + 1))

def get_text(url, timeout=25, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (paper-sim r33)'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode()
        except Exception:
            if i == tries - 1:
                return None
            time.sleep(1.5 * (i + 1))

def probs_both(kind, S, K, T, sig):
    """A/B YES-side probabilities from the canonical library (crypto_model).

    Convention A: zero log drift (median-flat). Convention B: mean-flat
    (mu_log = -sigma^2/2). 'close' markets resolve on the terminal print,
    so YES(above) = 1 - P(S_T <= K) from terminal_probability; touch
    markets use touch_probability (direction inferred from barrier vs
    spot, exactly the r19 semantics including the already-touched 1.0
    shortcuts below, which the library intentionally leaves to callers).
    """
    if kind == 'close':
        term = terminal_probability(spot=S, sigma_daily=sig, barrier=K,
                                    horizon_hours=T * 24.0, asset='scan')
        return {'A': round(1.0 - term.convention_a, 4),
                'B': round(1.0 - term.convention_b, 4)}
    if T <= 0:
        return {'A': 1.0, 'B': 1.0}
    if kind == 'dn' and K >= S:
        return {'A': 1.0, 'B': 1.0}
    if kind == 'up' and K <= S:
        return {'A': 1.0, 'B': 1.0}
    tp = touch_probability(spot=S, sigma_daily=sig, barrier=K,
                           horizon_hours=T * 24.0, asset='scan')
    return {'A': round(tp.convention_a, 4), 'B': round(tp.convention_b, 4)}

def vol_windows(kl, windows={'7d': 28, '30d': 120, '60d': 240}):
    bars = kl[:-1]  # drop partial bar
    closes = [float(b[4]) for b in bars]
    rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
    out = {}
    for w, n in windows.items():
        r = rets[-n:] if len(rets) >= n else rets
        rms = math.sqrt(sum(x * x for x in r) / len(r))
        out[w] = round(rms * math.sqrt(4), 5)  # 6h -> daily
    out['n_bars_used'] = len(rets)
    return out

def book_walk(book, shares):
    bids = sorted(book.get('bids', []), key=lambda x: -float(x['price']))
    rem = shares; cash = 0.0; fills = []
    for lvl in bids:
        px = float(lvl['price']); sz = float(lvl['size'])
        take = min(rem, sz); cash += take * px; rem -= take; fills.append([px, take])
        if rem <= 1e-9: break
    filled = shares - rem
    return {'realizable_cash': round(cash, 2), 'filled': round(filled, 2),
            'avg_px': round(cash / filled, 4) if filled > 0 else None,
            'fully_filled': rem <= 1e-6, 'fills_top': fills[:6], 'unfilled': round(max(0.0, rem), 2)}

def best(book):
    bids = [float(x['price']) for x in book.get('bids', [])]
    asks = [float(x['price']) for x in book.get('asks', [])]
    bb = max(bids) if bids else None
    ba = min(asks) if asks else None
    return bb, ba, (round((bb + ba) / 2, 4) if bb is not None and ba is not None else None)

def fetch_book(aid, sane=True):
    """Fetch CLOB book; retry when stub-like (spread >0.35 or 0.01/0.99 corners)."""
    last = None
    for att in range(4):
        b = get('https://clob.polymarket.com/book?token_id=' + aid)
        last = b
        if isinstance(b, dict) and b.get('bids') and b.get('asks'):
            bb, ba, _ = best(b)
            if not sane or (bb is not None and ba is not None and bb >= 0.02 and ba <= 0.98 and ba - bb <= 0.35):
                return b, att + 1, 'ok'
        time.sleep(1.5 + att)
    return last, 0, 'stub_like_or_empty'

res = {'generated_at': NOW.isoformat(),
       'mode': 'PAPER ONLY - round 33 crypto/econ monitoring scan, team AT CAP (report-only)'}

# ================= 1. Binance spot + vol =================
spots = {}
for sym in ['ETHUSDT', 'BTCUSDT']:
    t = get('https://api.binance.com/api/v3/ticker/price?symbol=%s' % sym)
    spots[sym[:3]] = float(t['price']) if isinstance(t, dict) and 'price' in t else None
res['spot_binance'] = spots
S_ETH, S_BTC = spots['ETH'], spots['BTC']

klines6 = {}; vols = {}
for sym in ['ETHUSDT', 'BTCUSDT']:
    kl = get('https://api.binance.com/api/v3/klines?symbol=%s&interval=6h&limit=250' % sym)
    klines6[sym[:3]] = kl
    vols[sym[:3]] = vol_windows(kl)
res['realized_vol_daily_6h'] = vols
SIG = {'ETH': vols['ETH'], 'BTC': vols['BTC']}

eth1h = get('https://api.binance.com/api/v3/klines?symbol=ETHUSDT&interval=1h&limit=240')
lows1h = [(float(b[3]), datetime.fromtimestamp(b[0] / 1000, tz=timezone.utc).isoformat()) for b in eth1h]
lows10d6h = [(float(b[3]), datetime.fromtimestamp(b[0] / 1000, tz=timezone.utc).isoformat()) for b in klines6['ETH'][-40:]]
last_le = lambda th: [ts for lo, ts in lows1h if lo <= th]
res['eth_recent_lows'] = {
    'low_10d_6h': min(lows10d6h), 'low_10d_1h': min(lows1h),
    'first_1h_bar_le_2000': (last_le(2000.0) or [None])[0],
    'last_1h_bar_le_2000': (last_le(2000.0) or [None])[-1],
    'bars_below_2000_last_10d_1h': sum(1 for lo, _ in lows1h if lo <= 2000.0),
}
btc6 = klines6['BTC']
res['btc_low_10d'] = min([(float(b[3]), datetime.fromtimestamp(b[0] / 1000, tz=timezone.utc).isoformat()) for b in btc6[-40:]])
print('spot', spots, 'vol', {k: {w: v[w] for w in ['7d', '30d', '60d']} for k, v in vols.items()}, flush=True)

# ================= 2. Held positions MTM =================
HELD = [
    ('ETH-dip-2000 YES', '84768145019786095547717415732823502270141145470320952547313245070010555237775',
     1208.0, 0.265, 320.0, '3865999', None),
    ('BTC-dip-65k NO', '104072675121616169708481552608019889218004323979484070212305769583143217407441',
     384.6, 0.78, 300.0, None, '0xfd7fcadffdf6a454c940569d4e1e6a9cc8e8682b70b5eb5e7fbbe76bb1844c1c'),
]
INVERSE = {  # cross-check books
    'ETH-dip-2000 YES': '41139993928652620342595776605433147455405569646745899886663605344607611434891',
    'BTC-dip-65k NO': '53780045235418715931128205720209124033878539466833083429441668150974549326823',
}
mtm = []
for name, aid, sh, avg, cost, gid, condid in HELD:
    b, atts, state = fetch_book(aid)
    bb, ba, mid = best(b)
    e = {'name': name, 'asset_id': aid, 'book_state': state, 'fetch_attempts': atts,
         'best_bid': bb, 'best_ask': ba, 'mid': mid, 'book_ts': b.get('timestamp') if isinstance(b, dict) else None,
         'bid_walk': book_walk(b, sh) if isinstance(b, dict) else None}
    inv, iatts, istate = fetch_book(INVERSE[name], sane=False)
    ibb, iba, _ = best(inv)
    e['inverse_book'] = {'best_bid': ibb, 'best_ask': iba, 'state': istate,
                         'implied_own_bid': round(1 - iba, 3) if iba is not None else None}
    # gamma meta
    g = None
    if gid:
        g = get('https://gamma-api.polymarket.com/markets/' + gid)
    elif condid:
        gl = get('https://gamma-api.polymarket.com/markets?condition_id=' + condid)
        if isinstance(gl, list) and gl:
            g = gl[0]
    if isinstance(g, dict) and g.get('id'):
        try: e['gamma_last'] = json.loads(g.get('outcomePrices') or '[]')
        except Exception: e['gamma_last'] = None
        e['gamma_q'] = g.get('question'); e['closed'] = g.get('closed')
        e['liq'] = g.get('liquidityNum'); e['vol24'] = g.get('volumeNum')
    unrl = round(e['bid_walk']['realizable_cash'] - cost, 2) if e.get('bid_walk') else None
    mtm.append({'name': name, 'shares': sh, 'avg': avg, 'cost': cost,
                'bid': bb, 'ask': ba, 'mid': mid,
                'gamma_last_yes': (e.get('gamma_last') or [None, None])[0],
                'realizable_cash_bid_walk': e['bid_walk']['realizable_cash'] if e.get('bid_walk') else None,
                'walk_avg_px': e['bid_walk']['avg_px'] if e.get('bid_walk') else None,
                'unrealized_bid': unrl,
                'unrealized_bid_pct': round(100 * unrl / cost, 1) if unrl is not None else None,
                'mark_to_mid': round(mid * sh, 2) if mid else None,
                'liq': e.get('liq'), 'vol': e.get('vol24'), '_detail': e})
    time.sleep(0.3)
res['positions_mtm'] = mtm

# ================= 3. Touch horizons for held =================
def horizons_for(sym, K, kind):
    S = S_ETH if sym == 'ETH' else S_BTC
    out = {}
    for label, dt in [('Fri_Nov7_2359', datetime(2026, 11, 7, 23, 59, tzinfo=timezone.utc)),
                      ('Sat_Nov14_2359', datetime(2026, 11, 14, 23, 59, tzinfo=timezone.utc)),
                      ('Tue_Dec1_2359', datetime(2026, 12, 1, 23, 59, tzinfo=timezone.utc)),
                      ('Dec31_2359', datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc))]:
        T = (dt - NOW).total_seconds() / 86400
        out[label] = {'days': round(T, 2),
                      **{w: probs_both(kind, S, K, T, SIG[sym][w]) for w in ['7d', '30d', '60d']}}
    return out
res['touch_horizons'] = {'ETH_2000_touch_yes': horizons_for('ETH', 2000.0, 'dn'),
                         'BTC_65k_touch_yes': horizons_for('BTC', 65000.0, 'dn')}
res['T_dec31_days'] = round((datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc) - NOW).total_seconds() / 86400, 2)

# ================= 4. Gamma barrier/level scan (BTC/ETH) =================
MONTHS = {m: i + 1 for i, m in enumerate(['January','February','March','April','May','June','July','August','September','October','November','December'])}
def parse_end(q, mend):
    m = re.search(r'by ([A-Z][a-z]+) (\d{1,2}), (\d{4})', q)
    if m and m.group(1) in MONTHS:
        return datetime(int(m.group(3)), MONTHS[m.group(1)], int(m.group(2)), 23, 59, 59, tzinfo=timezone.utc)
    if mend:
        try:
            dt = datetime.fromisoformat(mend.replace('Z', '+00:00'))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return None
    return None

def classify(q):
    low = q.lower()
    if re.search(r'dip to|drop to|fall to|dip below|drop below|fall below|touch', low):
        return 'dn'
    if re.search(r'hit|reach|rise to|climb to|rally to|surge to', low):
        return 'up'
    if re.search(r'\b(above|below|over|under|higher|lower) than\b', low):
        return 'close'
    return None

cands = {}
def add_event_markets(ev):
    for m in ev.get('markets', []):
        q = m.get('question', '')
        if not q or m.get('closed'):
            continue
        kind = classify(q)
        if not kind:
            continue
        mm = re.search(r'\$([\d,]+(?:\.\d+)?)\s*([kKmM])?\b', q)
        if not mm:
            continue
        K = float(mm.group(1).replace(',', ''))
        if mm.group(2):
            K *= 1000 if mm.group(2).lower() == 'k' else 1000000
        if K <= 0:
            continue
        low = q.lower()
        sym = 'BTC' if ('bitcoin' in low or ' btc ' in low) else ('ETH' if ('ethereum' in low or 'ether' in low) else None)
        if sym not in ('BTC', 'ETH'):
            continue
        end = parse_end(q, m.get('endDate'))
        if end is None or end <= NOW:
            continue
        try:
            toks = json.loads(m.get('clobTokenIds', '[]'))
        except Exception:
            toks = []
        if len(toks) != 2:
            continue
        liq = m.get('liquidityNum') or 0
        if liq < 10000:
            continue
        cands[m.get('conditionId') or q] = {
            'q': q, 'sym': sym, 'kind': kind, 'K': K, 'liq': liq, 'vol': m.get('volumeNum'),
            'T_days': round((end - NOW).total_seconds() / 86400, 2),
            'yes_token': toks[0], 'condId': m.get('conditionId')}

for tag in ['bitcoin', 'ethereum', 'crypto']:
    for off in [0, 100, 200, 300, 400]:
        d = get('https://gamma-api.polymarket.com/events?tag_slug=%s&closed=false&limit=100&offset=%d' % (tag, off))
        if not isinstance(d, list):
            break
        for ev in d:
            add_event_markets(ev)
        if len(d) < 100:
            break
        time.sleep(0.2)
res['scan_stats'] = {'n_candidate_markets_liq_ge_10k': len(cands)}
print('crypto candidates:', len(cands), flush=True)

rows = []
for cid, c in cands.items():
    S = S_ETH if c['sym'] == 'ETH' else S_BTC
    c['pA_pB'] = {'7d': probs_both(c['kind'], S, c['K'], c['T_days'], SIG[c['sym']]['7d']),
                  '30d': probs_both(c['kind'], S, c['K'], c['T_days'], SIG[c['sym']]['30d']),
                  '60d': probs_both(c['kind'], S, c['K'], c['T_days'], SIG[c['sym']]['60d'])}
    rows.append(c)
rows.sort(key=lambda x: -(x['liq'] or 0))

for c in rows:
    b = get('https://clob.polymarket.com/book?token_id=' + c['yes_token'])
    if not isinstance(b, dict) or '_error' in b or not b.get('bids') or not b.get('asks'):
        c['yes_bid'] = c['yes_ask'] = None
        continue
    bb, ba, mid = best(b)
    c['yes_bid'] = bb; c['yes_ask'] = ba; c['yes_mid'] = mid
    time.sleep(0.2)

table = []
for c in rows:
    if c.get('yes_ask') is None or c.get('yes_bid') is None:
        continue
    fairB = c['pA_pB']['30d']['B']; fairA = c['pA_pB']['30d']['A']
    yes_bid, yes_ask = c['yes_bid'], c['yes_ask']
    no_bid, no_ask = round(1 - yes_ask, 3), round(1 - yes_bid, 3)
    # Per-side conservative edges via the canonical library (2026-10-30 audit
    # fix): fair_yes = min(pA,pB), fair_no = 1 - max(pA,pB); neither side can
    # be overstated regardless of drift convention. Never price YES off B alone.
    ce = conservative_edges(
        TouchProbability(asset=c['sym'], barrier=c['K'],
                         horizon_hours=c['T_days'] * 24.0,
                         convention_a=fairA, convention_b=fairB),
        yes_ask=yes_ask, no_ask=no_ask)
    fair_yes = round(ce.fair_yes, 4)
    edge_yes_buy = round(ce.edge_yes, 4)
    edge_no_buy = round(ce.edge_no, 4)
    table.append({'q': c['q'], 'sym': c['sym'], 'kind': c['kind'], 'K': c['K'],
                  'T_days': c['T_days'], 'pA_30d': fairA, 'pB_30d': fairB,
                  'pB_7d': c['pA_pB']['7d']['B'], 'pB_60d': c['pA_pB']['60d']['B'],
                  'fair_yes': fair_yes, 'fair_no': round(ce.fair_no, 4),
                  'yes_bid': yes_bid, 'yes_ask': yes_ask,
                  'no_bid': no_bid, 'no_ask': no_ask,
                  'edge_buy_yes': edge_yes_buy, 'edge_buy_no': edge_no_buy,
                  'best_edge_side': 'YES' if max(edge_yes_buy, edge_no_buy) == edge_yes_buy else 'NO',
                  'best_edge': round(max(edge_yes_buy, edge_no_buy), 4),
                  'liq': c['liq'], 'condId': c.get('condId')})
qual = [t for t in table if t['best_edge'] >= 0.08 and t['liq'] >= 10000]
qual.sort(key=lambda x: -x['best_edge'])
res['candidates_table_all'] = table
res['report_only_qualifying'] = qual
print('crypto qual >=8c:', len(qual), flush=True)

# ================= 5. Econ quick scan (fed / oil / geopolitics) =================
ECON_SLUGS = ['federal-reserve', 'oil', 'crude-oil', 'geopolitics', 'middle-east', 'iran',
              'russia', 'ukraine', 'us-economy', 'recession', 'inflation', 'china']
def bucket(q):
    low = q.lower()
    if re.search(r'\bfed\b|fomc|interest rate|rate (hike|cut)|powell|basis points|bps', low):
        return 'fed'
    if re.search(r'\boil\b|wti|crude|opec|brent|gasoline', low):
        return 'oil'
    return 'geopolitics'

econ = {}
def add_econ(ev, slug):
    for m in ev.get('markets', []):
        q = m.get('question', '')
        if not q or m.get('closed'):
            continue
        end = parse_end(q, m.get('endDate'))
        if end is None or end <= NOW:
            continue
        liq = m.get('liquidityNum') or 0
        if liq < 10000:
            continue
        try:
            toks = json.loads(m.get('clobTokenIds', '[]'))
        except Exception:
            toks = []
        if len(toks) != 2:
            continue
        econ[m.get('conditionId') or q] = {
            'q': q, 'bucket': bucket(q), 'slug': slug, 'liq': liq, 'vol': m.get('volumeNum'),
            'T_days': round((end - NOW).total_seconds() / 86400, 2), 'end': end.isoformat(),
            'yes_token': toks[0], 'event_title': ev.get('title'),
            'lastTrade': m.get('lastTradePrice'), 'condId': m.get('conditionId')}

for slug in ECON_SLUGS:
    for off in [0, 100]:
        d = get('https://gamma-api.polymarket.com/events?tag_slug=%s&closed=false&limit=100&offset=%d' % (slug, off))
        if not isinstance(d, list):
            break
        for ev in d:
            add_econ(ev, slug)
        if len(d) < 100:
            break
        time.sleep(0.2)
print('econ candidates:', len(econ), flush=True)

# WTI baseline from stooq CL.F (front-month continuous)
wti = {'source': 'stooq cl.f daily'}
csv_txt = get_text('https://stooq.com/q/d/l/?s=cl.f&i=d')
if csv_txt and 'Close' in csv_txt:
    lines = [l for l in csv_txt.strip().splitlines()[1:] if l.strip()]
    closes = []
    for l in lines[-120:]:
        p = l.split(',')
        try: closes.append((p[0], float(p[4])))
        except Exception: pass
    if len(closes) >= 40:
        px = [c for _, c in closes]
        rets = [math.log(px[i] / px[i - 1]) for i in range(1, len(px))]
        wti['spot'] = px[-1]; wti['asof'] = closes[-1][0]
        wti['vol_30d_daily'] = round(math.sqrt(sum(r * r for r in rets[-30:]) / len(rets[-30:])), 5)
        wti['vol_60d_daily'] = round(math.sqrt(sum(r * r for r in rets[-60:]) / len(rets[-60:])), 5)
        wti['n'] = len(px)
res['wti_baseline'] = wti

erows = sorted(econ.values(), key=lambda x: -(x['liq'] or 0))[:24]
for c in erows:
    b = get('https://clob.polymarket.com/book?token_id=' + c['yes_token'])
    if not isinstance(b, dict) or '_error' in b or not b.get('bids') or not b.get('asks'):
        c['yes_bid'] = c['yes_ask'] = None
        continue
    bb, ba, mid = best(b)
    c['yes_bid'] = bb; c['yes_ask'] = ba; c['yes_mid'] = mid
    # oil barrier model where applicable
    if c['bucket'] == 'oil' and wti.get('spot') and re.search(r'hit (high|low)|high \$|low \$|(above|below) \$', c['q'].lower()):
        mm = re.search(r'\$([\d,]+(?:\.\d+)?)', c['q'])
        if mm:
            K = float(mm.group(1).replace(',', ''))
            lowq = c['q'].lower()
            kind = 'dn' if re.search(r'low \$|below \$|hit low|dip', lowq) else 'up'
            if re.search(r'\bhigh \$\d', lowq) and 'above' in lowq: kind = 'close'
            sig = wti.get('vol_30d_daily')
            if sig:
                c['oil_fair'] = probs_both(kind, wti['spot'], K, c['T_days'], sig)
    time.sleep(0.2)
res['econ_scan'] = erows

json.dump(res, open(OUT, 'w'), indent=1, default=str)
print('WROTE', OUT, flush=True)
print('--- MTM ---')
for m in mtm:
    print(' ', m['name'], 'bid', m['bid'], 'ask', m['ask'], '| realizable', m['realizable_cash_bid_walk'],
          '| unrl', m['unrealized_bid'], '(', m['unrealized_bid_pct'], '% ) | mark_to_mid', m['mark_to_mid'])
print('--- QUAL >=8c (report-only) ---')
for t in qual[:12]:
    print('  %+.3f %s | %s | fair %.3f b/a %s/%s liq %.0f' % (t['best_edge'], t['best_edge_side'], t['q'][:60], t['fair_yes'], t['yes_bid'], t['yes_ask'], t['liq']))
