import json, math, urllib.request, time, re

RAW = '/home/ubuntu/paper-sim/round10/raw'
XG = json.load(open(RAW + '/xg_understat_10.json'))
FM = json.load(open(RAW + '/fixt_markets10.json'))
LEAGUES = ['EPL', 'La_liga', 'Serie_A', 'Bundesliga', 'Ligue_1']

def get(url, tries=3, timeout=20):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(1.5)

def ratings_for(lg, LASTW, PRIOR, mode):
    d25 = XG['%s_2025' % lg]; d26 = XG['%s_2026' % lg]
    ms = [m for m in d25['dates'] if m.get('isResult')]
    bh = sum(float(m['xG']['h']) for m in ms) / len(ms)
    ba = sum(float(m['xG']['a']) for m in ms) / len(ms)
    lgf = (bh + ba) / 2.0
    last = {}
    for t in d25['teams'].values():
        h = t['history']
        last[t['title']] = (sum(float(x['xG']) for x in h) / len(h), sum(float(x['xGA']) for x in h) / len(h))
    r = {}
    for t in d26['teams'].values():
        h = t['history']; name = t['title']
        if not h:
            continue
        cf = sum(float(x['xG']) for x in h) / len(h)
        ca = sum(float(x['xGA']) for x in h) / len(h)
        nc = len(h)
        if mode == 'cur':
            fn, a = cf, ca
        elif mode == 'last':
            fn, a = last.get(name, (lgf, lgf))
        else:
            lf, la_ = last.get(name, (lgf, lgf))
            fn = (nc * cf + LASTW * 38 * lf + PRIOR * lgf) / (nc + LASTW * 38 + PRIOR)
            a = (nc * ca + LASTW * 38 * la_ + PRIOR * lgf) / (nc + LASTW * 38 + PRIOR)
        r[name] = (fn / lgf, a / lgf)
    return bh, ba, lgf, r

TEAM_LEAGUE = {}
TEAM_TITLES = set()
for lg in LEAGUES:
    for t in XG['%s_2026' % lg]['teams'].values():
        TEAM_LEAGUE[t['title']] = lg
        TEAM_TITLES.add(t['title'])

def resolve(name):
    if name in TEAM_LEAGUE:
        return name
    for t in TEAM_TITLES:
        if name.lower() in t.lower() or t.lower() in name.lower():
            return t
    return None

FIX = [
    ('HOF-LYO UEL', 'Hoffenheim', 'Lyon', 'uel-hof-lyo-2026-10-22'),
    ('JUV-REN UEL', 'Juventus', 'Rennes', 'uel-juv-ren1-2026-10-22'),
    ('BOU-MIL UEL', 'Bournemouth', 'Milan', 'uel-bou-mil1-2026-10-22'),
    ('ASM-SCF UEL', 'Monaco', 'Freiburg', 'col-asm-scf-2026-10-22'),
]

SWEEPS = [('blend w=.5 p=8 rho0', 0.5, 8, 0.0, 'blend'), ('blend w=.5 p=8 DC', 0.5, 8, -0.08, 'blend'),
          ('blend w=1.0 p=8', 1.0, 8, 0.0, 'blend'), ('blend w=.25 p=8', 0.25, 8, 0.0, 'blend'),
          ('blend w=.5 p=16', 0.5, 16, 0.0, 'blend'), ('blend w=.5 p=4', 0.5, 4, 0.0, 'blend'),
          ('current-only', None, None, 0.0, 'cur'), ('last-only', None, None, 0.0, 'last'),
          ('cross-shrink .8', 0.5, 8, 0.0, 'blend'), ('cross-shrink 1.1', 0.5, 8, 0.0, 'blend')]

_cache = {}
def ratings_cached(lg, LASTW, PRIOR, mode):
    key = (lg, LASTW, PRIOR, mode)
    if key not in _cache:
        _cache[key] = ratings_for(lg, LASTW, PRIOR, mode)
    return _cache[key]

def game_lams(home, away, LASTW, PRIOR, rho, mode, shrink=1.0):
    lgh = TEAM_LEAGUE.get(home); lga = TEAM_LEAGUE.get(away)
    if lgh is None or lga is None:
        return None
    bh1, ba1, lgf1, r1 = ratings_cached(lgh, LASTW, PRIOR, mode)
    bh2, ba2, lgf2, r2 = ratings_cached(lga, LASTW, PRIOR, mode)
    if home not in r1 or away not in r2:
        return None
    if lgh == lga:
        bh = (bh1 + bh2) / 2.0; ba = (ba1 + ba2) / 2.0
    else:
        bh = (bh1 + ba2) / 2.0; ba = (bh2 + ba1) / 2.0
    ah, dh = r1[home]; aa, da = r2[away]
    return bh * (ah ** shrink) * (da ** shrink), ba * (aa ** shrink) * (dh ** shrink), (lgh, lga)

def pois(l, k):
    return math.exp(-l) * l ** k / math.factorial(k)

def grid(lh, la, N=10, rho=0.0):
    g = [[pois(lh, i) * pois(la, j) for j in range(N + 1)] for i in range(N + 1)]
    if rho:
        g[0][0] *= max(1 - lh * la * rho, .01); g[0][1] *= max(1 + lh * rho, .01)
        g[1][0] *= max(1 + la * rho, .01); g[1][1] *= max(1 - rho, .01)
    s = sum(sum(r) for r in g)
    return [[v / s for v in row] for row in g]

BASE = {}
for lg in LEAGUES:
    n = h_ = d_ = a_ = 0
    for se in ['2025', '2026']:
        for m in XG['%s_%s' % (lg, se)]['dates']:
            if m.get('isResult'):
                gh, ga = int(m['goals']['h']), int(m['goals']['a'])
                n += 1; h_ += 1 if gh > ga else 0; d_ += 1 if gh == ga else 0; a_ += 1 if ga > gh else 0
    BASE[lg] = {'h': h_ / n, 'd': d_ / n, 'a': a_ / n}

def mkt_probs(g):
    ph = pd = pa = btts = 0.0
    ou = {}
    hm2 = am2 = 0.0
    for i in range(len(g)):
        for j in range(len(g)):
            p = g[i][j]
            if i > j: ph += p
            elif i == j: pd += p
            else: pa += p
            if i >= 1 and j >= 1: btts += p
            if i - j >= 2: hm2 += p
            if j - i >= 2: am2 += p
            tot = i + j
            for line in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]:
                if tot > line:
                    ou[line] = ou.get(line, 0.0) + p
    return ph, pd, pa, btts, ou, hm2, am2

def book(tid):
    for i in range(3):
        try:
            return get('https://clob.polymarket.com/book?token_id=' + tid, timeout=15)
        except Exception:
            if i == 2:
                return {'err': 'fetch'}
            time.sleep(1.2)

def ask(b, dollars=400.0):
    asks = sorted(b.get('asks', []), key=lambda l: float(l['price']))
    if not asks:
        return None, None
    best = float(asks[0]['price'])
    cash = 0.0; sh = 0.0
    for l in asks:
        p = float(l['price']); sz = float(l['size'])
        take = min(sz, (dollars - cash) / p)
        if take <= 0:
            break
        cash += take * p; sh += take
        if cash >= dollars - 1e-9:
            break
    return best, round(cash / sh, 4) if sh > 0 else best

MKT = {}
for label, home, away, pfx in FIX:
    for m in FM.get(pfx, []):
        MKT[(label, m['id'])] = m

def find_mkt(label, home, away, kind, line=None, team=None):
    for (lb, mid), m in MKT.items():
        if lb != label:
            continue
        q = m['q']
        if kind == '1x2h' and q == 'Will %s win on 2026-10-22?' % home_full(label):
            return mid
        if kind == '1x2d' and q.endswith('end in a draw?'):
            return mid
        if kind == '1x2a' and q == 'Will %s win on 2026-10-22?' % away_full(label):
            return mid
        if kind == 'ou' and q.endswith(': O/U %s' % line):
            return mid
        if kind == 'btts' and q.endswith(': Both Teams to Score'):
            return mid
        if kind == 'sph' and q.startswith('Spread: %s (-1.5)' % home_full(label)):
            return mid
        if kind == 'spa' and q.startswith('Spread: %s (-1.5)' % away_full(label)):
            return mid
    return None

FULL = {'HOF-LYO UEL': ('TSG 1899 Hoffenheim', 'Olympique Lyonnais'),
        'JUV-REN UEL': ('Juventus FC', 'Stade Rennais FC 1901'),
        'BOU-MIL UEL': ('AFC Bournemouth', 'AC Milan'), 'ASM-SCF UEL': ('AS Monaco FC', 'SC Freiburg')}
def home_full(label): return FULL[label][0]
def away_full(label): return FULL[label][1]

IDMETA = {}
def meta_for(mid):
    if mid in IDMETA:
        return IDMETA[mid]
    m = get('https://gamma-api.polymarket.com/markets/' + mid)
    toks = m.get('clobTokenIds')
    if isinstance(toks, str):
        toks = json.loads(toks)
    outs = m.get('outcomes')
    if isinstance(outs, str):
        outs = json.loads(outs)
    IDMETA[mid] = {'outcomes': outs, 'tokens': toks, 'liq': m.get('liquidityNum'), 'q': m.get('question'),
                   'desc': (m.get('description') or '')[:700], 'closed': m.get('closed')}
    time.sleep(0.12)
    return IDMETA[mid]

def ask_for(mid, label_out):
    d = meta_for(mid)
    if not d or not d.get('tokens'):
        return None, None, None
    tok = d['tokens'][d['outcomes'].index(label_out)] if label_out in d['outcomes'] else d['tokens'][0]
    b = book(tok); time.sleep(0.1)
    best, vwap = ask(b)
    return best, vwap, d.get('liq')

out = {}
flags = []
for label, home_raw, away_raw, pfx in FIX:
    home = resolve(home_raw); away = resolve(away_raw)
    print('== %s | understat: %s (%s) vs %s (%s)' % (label, home, TEAM_LEAGUE.get(home), away, TEAM_LEAGUE.get(away)), flush=True)
    if home is None or away is None:
        print('   TEAMS NOT FOUND IN UNDERSTAT', flush=True)
        continue
    variants = {}
    for name, LASTW, PRIOR, rho, mode in SWEEPS:
        shr = 0.8 if name.startswith('cross-shrink .8') else (1.1 if name.startswith('cross-shrink 1.1') else 1.0)
        lm = game_lams(home, away, LASTW, PRIOR, rho, mode, shr)
        if lm is None:
            continue
        lh, la, (lgh, lga) = lm
        ph, pd, pa, btts, ou, hm2, am2 = mkt_probs(grid(lh, la, 10, rho))
        if lgh == lga:
            bh0, bd0, ba0 = BASE[lgh]['h'], BASE[lgh]['d'], BASE[lgh]['a']
        else:
            bh0 = (BASE[lgh]['h'] + BASE[lga]['a']) / 2; bd0 = (BASE[lgh]['d'] + BASE[lga]['d']) / 2; ba0 = (BASE[lgh]['a'] + BASE[lga]['h']) / 2
        variants[name] = {'ou': ou, 'btts': btts, 'ph': 0.7 * ph + 0.3 * bh0, 'pd': 0.7 * pd + 0.3 * bd0, 'pa': 0.7 * pa + 0.3 * ba0,
                          'hm2': hm2, 'am2': am2, 'lh': lh, 'la': la}
    base = list(variants.values())[0]

    def rng(f):
        vs = [f(v) for v in variants.values()]
        return min(vs), max(vs)

    o25m, o25x = rng(lambda v: v['ou'][2.5])
    b_mn, b_mx = rng(lambda v: v['btts'])
    phm, phx = rng(lambda v: v['ph']); pdm, pdx = rng(lambda v: v['pd']); pam, pax = rng(lambda v: v['pa'])
    hmm, hmx = rng(lambda v: v['hm2']); amm, amx = rng(lambda v: v['am2'])
    print('   lam=%.2f/%.2f | OU2.5 [%.3f-%.3f] BTTS [%.3f-%.3f] H/D/A [%.3f-%.3f/%.3f-%.3f/%.3f-%.3f] H-1.5 [%.3f-%.3f] A-1.5 [%.3f-%.3f]' % (
        base['lh'], base['la'], o25m, o25x, b_mn, b_mx, phm, phx, pdm, pdx, pam, pax, hmm, hmx, amm, amx), flush=True)
    out[label] = {'lam': [base['lh'], base['la']]}

    checks = []
    for line in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]:
        mid = find_mkt(label, home, away, 'ou', line)
        if mid:
            checks.append(('O/U %.1f OVER' % line, mid, 'Over', rng(lambda v, L=line: v['ou'][L])))
            checks.append(('O/U %.1f UNDER' % line, mid, 'Under', rng(lambda v, L=line: 1 - v['ou'][L])))
    mid = find_mkt(label, home, away, 'btts')
    if mid:
        checks.append(('BTTS YES', mid, 'Yes', (b_mn, b_mx)))
        checks.append(('BTTS NO', mid, 'No', (1 - b_mx, 1 - b_mn)))
    for nm, kind, mnmx in [('H -1.5', 'sph', (hmm, hmx)), ('A -1.5', 'spa', (amm, amx))]:
        mid = find_mkt(label, home, away, kind)
        if mid:
            checks.append(('%s COVER' % nm, mid, 'Yes', mnmx))
    for nm, kind, mnmx in [('1X2 H', '1x2h', (phm, phx)), ('1X2 D', '1x2d', (pdm, pdx)), ('1X2 A', '1x2a', (pam, pax))]:
        mid = find_mkt(label, home, away, kind)
        if mid:
            checks.append(('%s YES' % nm, mid, 'Yes', mnmx))
    for nm, mid, side, (mn, mx) in checks:
        best, vwap, lq = ask_for(mid, side)
        if best is None:
            print('   %-16s NO BOOK' % nm, flush=True)
            continue
        edge = mn - best
        fl = 'FLAG' if edge >= 0.05 else 'no'
        if edge >= 0.05:
            flags.append((label, nm, round(edge, 3), best, mn, mx))
        out[label][nm] = {'ask': best, 'vwap': vwap, 'rng': [round(mn, 3), round(mx, 3)], 'edge': round(edge, 3)}
        print('   %-16s model [%.3f-%.3f] ask %.3f vwap %.3f | edge %+.3f %s' % (nm, mn, mx, best, vwap or 0, edge, fl), flush=True)

json.dump({'out': out, 'flags': flags, 'meta': {k: {'q': v['q'], 'desc': v['desc']} for k, v in IDMETA.items()}},
          open(RAW + '/model_round10.json', 'w'), indent=1)
print()
print('FLAGS >= +5c:', flags or 'NONE')
