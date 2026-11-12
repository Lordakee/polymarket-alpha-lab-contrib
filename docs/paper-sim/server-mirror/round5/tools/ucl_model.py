import json, math
from collections import defaultdict

# --- NBA market types in opener events ---
det = json.load(open('/home/ubuntu/paper-sim/round5/raw/secondary_detail3.json'))
for k in det:
    if 'nba' not in k and 'bos-det' not in k:
        continue
for k, d in det.items():
    if 'bos-det' in d.get('slug', '') or 'phi-nyk' in d.get('slug', '') or 'okc-sas' in d.get('slug', ''):
        e = d['event']
        print('== NBA', e.get('title'), 'markets:', len(e.get('markets', [])))
        for m in e.get('markets', [])[:40]:
            if m.get('closed'): continue
            print('   -', (m.get('question') or m.get('groupItemTitle') or '')[:85])
        break

# --- UFC resolution text sample ---
books = json.load(open('/home/ubuntu/paper-sim/round5/raw/secondary_books3.json'))
print()
print('===== UFC sample resolution text =====')
shown = 0
for tid, b in books.items():
    m = b['meta']
    if m['event'].startswith('ufc_') and shown < 2:
        if m['q'].startswith('UFC 333:'):
            print('Q:', m['q'][:80])
            print(b.get('desc', '')[:1200])
            print('---')
            shown += 1

# --- UCL model ---
XG = json.load(open('/home/ubuntu/paper-sim/round5/raw/xg_understat.json'))
LEAGUES = ['EPL', 'La_liga', 'Serie_A', 'Bundesliga', 'Ligue_1']

def load(lg, se):
    return XG['%s_%s' % (lg, se)]

_cache = {}
def ratings_for(lg, LASTW, PRIOR, mode):
    key = (lg, LASTW, PRIOR, mode)
    if key in _cache: return _cache[key]
    d25 = load(lg, '2025'); d26 = load(lg, '2026')
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
        if not h: continue
        cf = sum(float(x['xG']) for x in h) / len(h)
        ca = sum(float(x['xGA']) for x in h) / len(h)
        nc = len(h)
        if mode == 'cur':
            f, a = cf, ca
        elif mode == 'last':
            f, a = last.get(name, (lgf, lgf))
        else:
            lf, la_ = last.get(name, (lgf, lgf))
            f = (nc * cf + LASTW * 38 * lf + PRIOR * lgf) / (nc + LASTW * 38 + PRIOR)
            a = (nc * ca + LASTW * 38 * la_ + PRIOR * lgf) / (nc + LASTW * 38 + PRIOR)
        r[name] = (f / lgf, a / lgf)
    _cache[key] = (bh, ba, lgf, r)
    return _cache[key]

SWEEPS = [
    ('blend w=.5 p=8 rho0', 0.5, 8, 0.0, 'blend'),
    ('blend w=.5 p=8 DC',   0.5, 8, -0.08, 'blend'),
    ('blend w=1.0 p=8',     1.0, 8, 0.0, 'blend'),
    ('blend w=.25 p=8',     0.25, 8, 0.0, 'blend'),
    ('blend w=.5 p=16',     0.5, 16, 0.0, 'blend'),
    ('blend w=.5 p=4',      0.5, 4, 0.0, 'blend'),
    ('current-only',        None, None, 0.0, 'cur'),
    ('last-only',           None, None, 0.0, 'last'),
]

def pois(l, k):
    return math.exp(-l) * l ** k / math.factorial(k)

def grid(lh, la, N=10, rho=0.0):
    g = [[pois(lh, i) * pois(la, j) for j in range(N + 1)] for i in range(N + 1)]
    if rho:
        g[0][0] *= max(1 - lh * la * rho, .01)
        g[0][1] *= max(1 + lh * rho, .01)
        g[1][0] *= max(1 + la * rho, .01)
        g[1][1] *= max(1 - rho, .01)
    s = sum(sum(r) for r in g)
    return [[v / s for v in row] for row in g]

def outs(g):
    ptot = defaultdict(float)
    for i in range(len(g)):
        for j in range(len(g)):
            ptot[i + j] += g[i][j]
    return sum(v for t, v in ptot.items() if t >= 3)

TEAM_LEAGUE = {}
for lg in LEAGUES:
    for t in load(lg, '2026')['teams'].values():
        TEAM_LEAGUE[t['title']] = lg

def find_team(sub):
    for name, lg in TEAM_LEAGUE.items():
        if sub.lower() == name.lower():
            return name, lg
    for name, lg in TEAM_LEAGUE.items():
        if sub.lower() in name.lower():
            return name, lg
    return None, None

# UCL fixtures (both sides BIG5 modelable) + PM Over ask
UFIX = [
    ('PSG-FCB 10/20', 'Paris Saint Germain', 'Barcelona', 0.80),
    ('STU-ATM 10/20', 'Stuttgart', 'Atletico Madrid', 0.63),
    ('BAY-ARS 10/21', 'Bayern Munich', 'Arsenal', 0.61),
    ('COM-MNU 10/21', 'Como', 'Manchester United', 0.61),
    ('RMA-RBL 10/21', 'Real Madrid', 'RasenBallsport Leipzig', 0.77),
    ('LIV-VIL 10/20', 'Liverpool', 'Villarreal', 0.65),
]

print()
print('===== UCL MD3 model (boost variants for UCL environment) =====')
for label, h, a, ask in UFIX:
    vals = []
    lam0 = None
    for name, LASTW, PRIOR, rho, mode in SWEEPS:
        for boost in (0.0, 0.10, 0.20):
            hn, lgh = find_team(h); an_, lga = find_team(a)
            if lgh is None or lga is None: break
            bh1, ba1, lgf1, r1 = ratings_for(lgh, LASTW, PRIOR, mode)
            bh2, ba2, lgf2, r2 = ratings_for(lga, LASTW, PRIOR, mode)
            if hn not in r1 or an_ not in r2: break
            bh = (bh1 + bh2) / 2.0; ba = (ba1 + ba2) / 2.0
            ah, dh = r1[hn]; aa, da = r2[an_]
            lh = bh * ah * da * (1 + boost)
            la = ba * aa * dh * (1 + boost)
            g = grid(lh, la, 10, rho)
            vals.append(outs(g))
            if lam0 is None: lam0 = (lh, la)
    if vals:
        mn, mx = min(vals), max(vals)
        med = sorted(vals)[len(vals) // 2]
        print('%-16s lam=%.2f/%.2f (base0) O2.5 med=%.3f range=[%.3f-%.3f] ask=%.2f min-edge %+.3f (n=%d variants incl boost)' % (
            label, lam0[0], lam0[1], med, mn, mx, ask, mn - ask, len(vals)))
