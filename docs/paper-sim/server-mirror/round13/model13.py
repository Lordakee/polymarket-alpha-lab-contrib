import json, math, datetime, re

RAW = '/home/ubuntu/paper-sim/round13/raw'
NOW = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)

def N(x): return 0.5 * math.erfc(-x / math.sqrt(2.0))

# ---------- spot & realized vol from Coinbase 6h candles ----------
cd = {}
for s in ['ETH', 'BTC']:
    rows = sorted(json.load(open(f'{RAW}/{s.lower()}_candles.json')), key=lambda r: r[0])
    complete = [r for r in rows if (NOW.timestamp() - r[0]) >= 6 * 3600]
    cd[s] = {'rows': rows, 'closes': [r[4] for r in complete],
             'last_complete': complete[-1], 'last_bar': rows[-1]}
SPOT = {s: cd[s]['last_bar'][4] for s in cd}  # live partial-bar close
print('SPOT', SPOT, 'last bar t0', datetime.datetime.fromtimestamp(cd['ETH']['last_bar'][0], datetime.timezone.utc))
print('last complete bar close:', {s: cd[s]['last_complete'][4] for s in cd})

def vol_from(closes, n):
    cs = closes[-n:]
    rs = [math.log(cs[i] / cs[i - 1]) for i in range(1, len(cs))]
    sd6 = math.sqrt(sum(x * x for x in rs) / len(rs))
    return sd6 * math.sqrt(4.0)

VOL = {}
for s in ['ETH', 'BTC']:
    cl = cd[s]['closes']
    VOL[s] = {w: vol_from(cl, n) for w, n in [('7d', 28), ('30d', 120), ('60d', 240), ('87d', 348)]}
    print(s, 'spot=%.2f' % SPOT[s], {k: '%.3f%%' % (v * 100) for k, v in VOL[s].items()})

# ---------- barrier checks (min/max of candle extremes since creation) ----------
CREATED = {'btc65': datetime.datetime(2026, 8, 25, tzinfo=datetime.timezone.utc),
           'btc95': datetime.datetime(2026, 6, 8, tzinfo=datetime.timezone.utc),
           'eth3000': datetime.datetime(2026, 6, 8, tzinfo=datetime.timezone.utc),
           'eth2250': datetime.datetime(2026, 8, 25, tzinfo=datetime.timezone.utc),
           'eth2000': datetime.datetime(2026, 8, 25, tzinfo=datetime.timezone.utc)}
SYMS = {'btc65': 'BTC', 'btc95': 'BTC', 'eth3000': 'ETH', 'eth2250': 'ETH', 'eth2000': 'ETH'}
BARRIER = {'btc65': 65000, 'btc95': 95000, 'eth3000': 3000, 'eth2250': 2250, 'eth2000': 2000}
barrier_checks = {}
for k, dt0 in CREATED.items():
    rows = [r for r in cd[SYMS[k]]['rows'] if r[0] >= dt0.timestamp()]
    lo = min(r[1] for r in rows)
    hi = max(r[2] for r in rows)
    dn = BARRIER[k]
    touched = (lo <= dn) if dn < SPOT[SYMS[k]] else (hi >= dn)
    barrier_checks[k] = {'created': dt0.date().isoformat(),
                         'min_low_since': lo if dn < SPOT[SYMS[k]] else None,
                         'max_high_since': hi if dn > SPOT[SYMS[k]] else None,
                         'touched': touched}
    print(k, 'min_low', lo, 'max_high', hi, 'touched', touched)

# ---------- model ----------
def p_above(S, K, mu, sig, T):
    sigT = sig * math.sqrt(T)
    if sigT <= 0: return 1.0 if S >= K else 0.0
    return N((math.log(S / K) + mu * T) / sigT)

def p_touch_up(a, mu, sig, T):
    sigT = sig * math.sqrt(T)
    if sigT <= 0: return 1.0 if a <= 0 else 0.0
    return N((mu * T - a) / sigT) + math.exp(2 * mu * a / (sig * sig)) * N(-(mu * T + a) / sigT)

def p_touch_dn(x, mu, sig, T): return p_touch_up(x, -mu, sig, T)

def probs(sym, kind, K, T, sig):
    S = SPOT[sym]
    muB = -sig * sig / 2.0
    if kind == 'touch_up':
        if K <= S: return (1.0, 1.0)
        a = math.log(K / S)
        return (p_touch_up(a, 0, sig, T), p_touch_up(a, muB, sig, T))
    if kind == 'touch_dn':
        if K >= S: return (1.0, 1.0)
        x = math.log(S / K)
        return (p_touch_dn(x, 0, sig, T), p_touch_dn(x, muB, sig, T))
    if kind == 'above':
        return (p_above(S, K, 0, sig, T), p_above(S, K, muB, sig, T))
    if kind == 'below':
        pa = (p_above(S, K, 0, sig, T), p_above(S, K, muB, sig, T))
        return (1 - pa[0], 1 - pa[1])
    return (None, None)

DEC31 = datetime.datetime(2026, 12, 31, 23, 59, tzinfo=datetime.timezone.utc)
T_DEC31 = (DEC31 - NOW).total_seconds() / 86400.0
print('T to Dec31 = %.2f d' % T_DEC31)

# ---------- classify events from gamma ----------
d = json.load(open(f'{RAW}/discover13.json'))
seen = set()
evs = []
for slug in d:
    for e in d[slug]:
        if e.get('id') in seen: continue
        seen.add(e.get('id'))
        evs.append(e)
MONTHS = {m: i + 1 for i, m in enumerate(['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'])}
DOLLAR = re.compile(r'\$([\d,]+(?:\.\d+)?)')

def Kval(txt):
    m = DOLLAR.search(txt)
    if not m: return None
    return float(m.group(1).replace(',', ''))

rows = []

def add(sym, kind, K, q, m, ev, resolve_dt, window=None):
    prs = m.get('outcomePrices')
    if isinstance(prs, str):
        try: prs = json.loads(prs)
        except Exception: prs = None
    if not prs: return
    try: p_yes = float(prs[0])
    except Exception: return
    rows.append(dict(sym=sym, kind=kind, K=K, q=q.strip(), p_yes=p_yes,
                     bb=m.get('bestBid'), ba=m.get('bestAsk'), liq=m.get('liquidityNum') or 0,
                     end=(m.get('endDate') or '')[:19], toks=m.get('clobTokenIds'), ev=ev.get('title'),
                     condId=m.get('conditionId'), resolve=resolve_dt.isoformat() if resolve_dt else None, window=window))

RX1 = re.compile(r'^Will (Bitcoin|Ethereum) (dip to|reach|hit) \$([\d,]+(?:\.\d+)?)\s*(k)?\s*(?:first)?\s*(?:in|on|by)?\s*(.*)$')
RX2 = re.compile(r'^Will the price of (Bitcoin|Ethereum) be (above|less than) \$([\d,]+(?:\.\d+)?) on (\w+ \d+)$')
for e in evs:
    for m in (e.get('markets') or []):
        if m.get('closed'): continue
        q = (m.get('question') or '').strip()
        mm = RX1.match(q)
        mq = RX2.match(q)
        if mm:
            sym = 'BTC' if mm.group(1) == 'Bitcoin' else 'ETH'
            verb = mm.group(2)
            K = float(mm.group(3).replace(',', ''))
            if mm.group(4):  # 'k' suffix
                K *= 1000.0
            rest = (mm.group(5) or '').strip()
            kind = 'touch_dn' if verb == 'dip to' else 'touch_up'
            rdt = None
            mMon = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:,\s*(\d{4}))?', rest)
            yr = int(mMon.group(3)) if (mMon and mMon.group(3)) else 2026
            if mMon:
                rdt = datetime.datetime(yr, MONTHS[mMon.group(1)], int(mMon.group(2)), 23, 59, tzinfo=datetime.timezone.utc)
            mRng = re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December) (\d{1,2})-(\d{1,2})', rest)
            if mRng:
                rdt = datetime.datetime(2026, MONTHS[mRng.group(1)], int(mRng.group(3)), 23, 59, tzinfo=datetime.timezone.utc)
            if 'today' in rest.lower(): rdt = NOW + datetime.timedelta(hours=12)
            add(sym, kind, K, q, m, e, rdt, window=rest)
        elif mq:
            sym = 'BTC' if mq.group(1) == 'Bitcoin' else 'ETH'
            kind = 'above' if mq.group(2) == 'above' else 'below'
            K = float(mq.group(3).replace(',', ''))
            parts = mq.group(4).split()
            mth = MONTHS.get(parts[0])
            day = int(parts[1])
            rdt = datetime.datetime(2026, mth, day, 16, 0, tzinfo=datetime.timezone.utc)
            add(sym, kind, K, q, m, e, rdt)

print('classified rows:', len(rows))
SIGTAB = '30d'
out = []
for r in rows:
    if not r.get('resolve') or r['K'] is None: continue
    try: rdt = datetime.datetime.fromisoformat(r['resolve'])
    except Exception: continue
    T = (rdt - NOW).total_seconds() / 86400.0
    if T <= 0 or T > 75: continue
    if r['liq'] < 10000: continue
    pA, pB = probs(r['sym'], r['kind'], r['K'], T, VOL[r['sym']][SIGTAB])
    if pA is None: continue
    fair_yes = min(pA, pB) if r['kind'] in ('touch_up', 'above') else max(pA, pB)
    yes_ask = r['ba'] if r['ba'] is not None else min(1.0, r['p_yes'] + 0.02)
    yes_bid = r['bb'] if r['bb'] is not None else max(0.0, r['p_yes'] - 0.02)
    no_ask = 1.0 - yes_bid
    edge_yes = fair_yes - yes_ask
    edge_no = (1.0 - fair_yes) - no_ask
    agree_yes = (pA > yes_ask and pB > yes_ask)
    agree_no = ((1 - pA) > no_ask and (1 - pB) > no_ask)
    out.append(dict(r=r, T=T, pA=pA, pB=pB, fair_yes=fair_yes, edge_yes=edge_yes, edge_no=edge_no,
                    agree_yes=agree_yes, agree_no=agree_no, yes_ask=yes_ask, yes_bid=yes_bid))
print('kept:', len(out))

table = []
for x in out:
    r = x['r']
    table.append(dict(q=r['q'][:95], sym=r['sym'], kind=r['kind'], K=r['K'], T=round(x['T'], 2),
                      pA=round(x['pA'], 4), pB=round(x['pB'], 4), fair_yes=round(x['fair_yes'], 4),
                      yes_bid=x['yes_bid'], yes_ask=x['yes_ask'], edge_yes=round(x['edge_yes'], 4), edge_no=round(x['edge_no'], 4),
                      agree_yes=x['agree_yes'], agree_no=x['agree_no'], liq=round(r['liq']), ev=r['ev'], condId=r['condId'], toks=r['toks']))

json.dump({'generated_at': NOW.isoformat(), 'spot': SPOT, 'realized_vol_daily': VOL,
           'model': {'vol_source': 'Coinbase 6h candles (complete bars), sqrt-scaled', 'sig_table': SIGTAB,
                     'conventions': ['A: zero-log-drift GBM', 'B: median-flat (mu_log=-sigma^2/2)'],
                     'touch': 'drifted first-passage (reflection principle form)',
                     'fair_buy_convention': 'least-favorable to the side being bought'},
           'barrier_checks': barrier_checks, 'classified_markets': table},
          open(f'{RAW}/crypto_scan.json', 'w'), indent=1)
print('wrote crypto_scan.json with', len(table), 'markets')

print('%-46s %5s %8s %6s %6s %6s %6s %6s %+7s %+7s' % ('market', 'T', 'K', 'pA', 'pB', 'fair', 'bidY', 'askY', 'edgeY', 'edgeN'))
for x in sorted(table, key=lambda z: -max(z['edge_yes'], z['edge_no']))[:30]:
    print('%-46s %5.1f %8.0f %6.3f %6.3f %6.3f %6s %6s %+7.3f %+7.3f' % (
        x['q'][:46], x['T'], x['K'], x['pA'], x['pB'], x['fair_yes'],
        ('%.3f' % x['yes_bid'])[:5] if x['yes_bid'] is not None else '-',
        ('%.3f' % x['yes_ask'])[:5] if x['yes_ask'] is not None else '-', x['edge_yes'], x['edge_no']))
