#!/usr/bin/env python3
"""Round-29 crypto scan part 2: gamma barrier-market scan + touch probs + MTM.
Writes round29/raw/crypto_scan.json (final, merged). PAPER ONLY."""
import json, math, re, time, urllib.request, urllib.parse
from datetime import datetime, timezone

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

def touch_down(S, K, T, sig, mu):
    if T <= 0: return 1.0
    if K >= S: return 1.0
    b = math.log(K / S); sq = sig * math.sqrt(T)
    return min(1.0, norm_cdf((b - mu * T) / sq) + math.exp(2 * mu * b / sig**2) * norm_cdf((b + mu * T) / sq))

def touch_up(S, K, T, sig, mu):
    if T <= 0: return 1.0
    if K <= S: return 1.0
    a = math.log(K / S); sq = sig * math.sqrt(T)
    return min(1.0, norm_cdf((mu * T - a) / sq) + math.exp(-2 * mu * a / sig**2) * norm_cdf(-(mu * T + a) / sq))

def probs_both(kind, S, K, T, sig):
    f = touch_down if kind == 'dn' else touch_up
    return {'A': round(f(S, K, T, sig, 0.0), 4), 'B': round(f(S, K, T, sig, -0.5 * sig**2), 4)}

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

res = json.load(open('/tmp/r29_part1.json'))
res['generated_at'] = NOW.isoformat()
S_ETH = res['spot_binance']['ETH']; S_BTC = res['spot_binance']['BTC']
SIG = {'ETH': res['realized_vol_daily_6h']['ETH'], 'BTC': res['realized_vol_daily_6h']['BTC']}

# ---- refetch held books, corrected best bid/ask ----
HELD = [
 ('84768145019786095547717415732823502270141145470320952547313245070010555237775', 1208.0, 0.265, 320.0, 'ETH-dip-2000 YES', '3865999'),
 ('104072675121616169708481552608019889218004323979484070212305769583143217407441', 384.6, 0.78, 300.0, 'BTC-dip-65k NO', None),
]
mtm = []
for aid, sh, avg, cost, name, gid in HELD:
    b = get('https://clob.polymarket.com/book?token_id=' + aid)
    bb, ba, mid = best(b)
    bids_sorted = sorted(b.get('bids', []), key=lambda x: -float(x['price']))
    asks_sorted = sorted(b.get('asks', []), key=lambda x: float(x['price']))
    e = {'name': name, 'asset_id': aid, 'best_bid': bb, 'best_ask': ba, 'mid': mid,
         'bid_sz_top': float(bids_sorted[0]['size']) if bids_sorted else None,
         'ask_sz_top': float(asks_sorted[0]['size']) if asks_sorted else None,
         'book_ts': b.get('timestamp')}
    e['bid_walk'] = book_walk(b, sh)
    if gid:
        g = get('https://gamma-api.polymarket.com/markets/' + gid)
        try: e['gamma_last'] = json.loads(g.get('outcomePrices', '[]'))
        except Exception: e['gamma_last'] = None
        e['liq'] = g.get('liquidityNum'); e['vol'] = g.get('volumeNum')
    else:
        g = get('https://gamma-api.polymarket.com/markets?condition_id=0xfd7fcadffdf6a454c940569d4e1e6a9cc8e8682b70b5eb5e7fbbe76bb1844c1c')
        if isinstance(g, list) and g:
            g0 = [m for m in g if '65,000' in (m.get('question') or '')]
            g0 = g0[0] if g0 else None
            if g0:
                try: e['gamma_last'] = json.loads(g0.get('outcomePrices', '[]'))
                except Exception: e['gamma_last'] = None
                e['liq'] = g0.get('liquidityNum'); e['vol'] = g0.get('volumeNum')
            else:
                e['gamma_last'] = None; e['liq'] = None; e['vol'] = None
    unrl = round(e['bid_walk']['realizable_cash'] - cost, 2)
    mtm.append({'name': name, 'shares': sh, 'avg': avg, 'cost': cost,
                'bid': bb, 'ask': ba, 'mid': mid,
                'gamma_last_yes': (e.get('gamma_last') or [None, None])[0],
                'realizable_cash_bid_walk': e['bid_walk']['realizable_cash'],
                'walk_avg_px': e['bid_walk']['avg_px'],
                'unrealized_bid': unrl, 'unrealized_bid_pct': round(100 * unrl / cost, 1),
                'mark_to_mid': round(mid * sh, 2), 'liq': e.get('liq'), 'vol': e.get('vol'),
                '_detail': e})
    time.sleep(0.3)
res['positions_mtm'] = mtm

# ---- settled ETH2250 record ----
res['settled'] = {'ETH2250_YES': {'shares': 2555.0, 'cost': 1250.0, 'payout': 2555.0,
    'realized_pnl': 1305.0, 'resolution': 'YES (gamma 3866000 resolved [1,0])',
    'note': 'ETH first printed <=2250 on the 2026-10-29 20:00 UTC 1h bar; low since touch 2174.08 (2026-10-30 01:00 UTC); zero 1h bars <=2000 in last 10d.'}}

# ---- touch horizons for held ----
T_dec31 = (datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc) - NOW).total_seconds() / 86400
horizons = {}
for label, dt in [('Fri_Nov7_2359', datetime(2026, 11, 7, 23, 59, tzinfo=timezone.utc)),
                  ('Sat_Nov14_2359', datetime(2026, 11, 14, 23, 59, tzinfo=timezone.utc)),
                  ('Tue_Dec1_2359', datetime(2026, 12, 1, 23, 59, tzinfo=timezone.utc)),
                  ('Dec31_2359', datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc))]:
    T = (dt - NOW).total_seconds() / 86400
    horizons[label] = {'days': round(T, 2),
        'ETH_2000': {w: probs_both('dn', S_ETH, 2000.0, T, SIG['ETH'][w]) for w in ['7d', '30d', '60d']},
        'BTC_65k_yes': {w: probs_both('dn', S_BTC, 65000.0, T, SIG['BTC'][w]) for w in ['7d', '30d', '60d']}}
res['touch_horizons'] = horizons
res['T_dec31_days'] = round(T_dec31, 2)

# ---- gamma barrier-market scan ----
MONTHS = {m: i + 1 for i, m in enumerate(['January','February','March','April','May','June','July','August','September','October','November','December'])}
def parse_end(q):
    m = re.search(r'by ([A-Z][a-z]+) (\d{1,2}), (\d{4})', q)
    if m:
        mo = MONTHS.get(m.group(1))
        if mo:
            return datetime(int(m.group(3)), mo, int(m.group(2)), 23, 59, 59, tzinfo=timezone.utc)
    return None

cands = {}
def add_event_markets(ev):
    for m in ev.get('markets', []):
        q = m.get('question', '')
        if not q or m.get('closed'):
            continue
        low = q.lower()
        kind = None
        if re.search(r'dip to|drop to|fall to|touch', low):
            kind = 'dn'
        elif re.search(r'reach|hit|rise to|climb to', low):
            kind = 'up'
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
        end = parse_end(q)
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
        sym = 'BTC' if ('bitcoin' in low or ' btc ' in low) else ('ETH' if ('ethereum' in low or 'ether' in low) else None)
        if sym not in ('BTC', 'ETH'):
            continue
        cands[m.get('conditionId') or q] = {
            'q': q, 'sym': sym, 'kind': kind, 'K': K, 'liq': liq, 'vol': m.get('volumeNum'),
            'end': end.isoformat(), 'T_days': round((end - NOW).total_seconds() / 86400, 2),
            'yes_token': toks[0], 'no_token': toks[1],
            'condId': m.get('conditionId')}

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
print('candidates:', len(cands))

rows = []
for cid, c in cands.items():
    S = S_ETH if c['sym'] == 'ETH' else S_BTC
    p = {'7d': probs_both(c['kind'], S, c['K'], c['T_days'], SIG[c['sym']]['7d']),
         '30d': probs_both(c['kind'], S, c['K'], c['T_days'], SIG[c['sym']]['30d']),
         '60d': probs_both(c['kind'], S, c['K'], c['T_days'], SIG[c['sym']]['60d'])}
    c['pA_pB'] = p
    rows.append(c)
rows.sort(key=lambda x: -(x['liq'] or 0))
res['candidates_fair'] = rows

# CLOB books for ALL candidates (>=10k liq) -> executable edges
for c in rows:
    b = get('https://clob.polymarket.com/book?token_id=' + c['yes_token'])
    if not isinstance(b, dict) or '_error' in b or 'bids' not in b:
        c['yes_bid'] = c['yes_ask'] = None
        continue
    bb, ba, mid = best(b)
    c['yes_bid'] = bb; c['yes_ask'] = ba; c['yes_mid'] = mid
    time.sleep(0.25)

table = []
for c in rows:
    if c.get('yes_ask') is None or c.get('yes_bid') is None:
        continue
    fairB = c['pA_pB']['30d']['B']; fairA = c['pA_pB']['30d']['A']
    yes_bid, yes_ask = c['yes_bid'], c['yes_ask']
    no_bid, no_ask = round(1 - yes_ask, 3), round(1 - yes_bid, 3)
    edge_yes_buy = round(fairB - yes_ask, 4)
    edge_no_buy = round((1 - fairB) - no_ask, 4)
    table.append({'q': c['q'], 'sym': c['sym'], 'kind': 'touch_' + c['kind'], 'K': c['K'],
                  'T_days': c['T_days'], 'pA_30d': fairA, 'pB_30d': fairB,
                  'pB_7d': c['pA_pB']['7d']['B'], 'pB_60d': c['pA_pB']['60d']['B'],
                  'fair_yes': fairB, 'yes_bid': yes_bid, 'yes_ask': yes_ask,
                  'no_bid': no_bid, 'no_ask': no_ask,
                  'edge_buy_yes': edge_yes_buy, 'edge_buy_no': edge_no_buy,
                  'best_edge_side': 'YES' if max(edge_yes_buy, edge_no_buy) == edge_yes_buy else 'NO',
                  'best_edge': round(max(edge_yes_buy, edge_no_buy), 4),
                  'liq': c['liq'], 'condId': c.get('condId')})
qual = [t for t in table if t['best_edge'] >= 0.08 and t['liq'] >= 10000]
qual.sort(key=lambda x: -x['best_edge'])
res['report_only_table_all'] = table
res['report_only_qualifying'] = qual

json.dump(res, open(OUT, 'w'), indent=1, default=str)
print('WROTE', OUT)
print('qualifying >=8c:', len(qual))
for t in qual[:12]:
    print('  %+.3f %s | %s | fair %.3f bid/ask %s/%s liq %.0f' % (t['best_edge'], t['best_edge_side'], t['q'][:58], t['fair_yes'], t['yes_bid'], t['yes_ask'], t['liq']))
print('--- MTM ---')
for m in mtm:
    print(' ', m['name'], 'bid', m['bid'], 'ask', m['ask'], '| realizable', m['realizable_cash_bid_walk'], '@ avg', m['walk_avg_px'], '| unrl', m['unrealized_bid'], '(', m['unrealized_bid_pct'], '% ) | mark_to_mid', m['mark_to_mid'])
