import json, math
from collections import defaultdict

RAW = '/home/ubuntu/paper-sim/round2/raw/xg/'
FX = json.load(open('/home/ubuntu/paper-sim/round2/raw/fixtures.json'))

LEAGUES = ['EPL', 'La_liga', 'Serie_A', 'Bundesliga', 'Ligue_1']

def load(lg, se):
    return json.load(open(RAW + '%s_%s.json' % (lg, se)))

# ---------- league environment ----------
print('=== A) League environment (2025/26 full vs 2026/27 to date) ===')
env = {}
for lg in LEAGUES:
    env[lg] = {}
    for se in ['2025', '2026']:
        d = load(lg, se)
        ms = [m for m in d['dates'] if m.get('isResult') and m.get('xG') and m['xG'].get('h')]
        xg = sum(float(m['xG']['h']) + float(m['xG']['a']) for m in ms) / len(ms)
        hxg = sum(float(m['xG']['h']) for m in ms) / len(ms)
        axg = sum(float(m['xG']['a']) for m in ms) / len(ms)
        gl = sum(int(m['goals']['h']) + int(m['goals']['a']) for m in ms) / len(ms)
        env[lg][se] = {'xg': xg, 'hxg': hxg, 'axg': axg, 'goals': gl, 'n': len(ms)}
        print('  %-10s %s/%s: n=%3d goals=%.2f xG=%.2f (home %.2f / away %.2f)' % (
            lg, se[:4], int(se[:4]) + 1, len(ms), gl, xg, hxg, axg))

# ---------- ratings ----------
_cache = {}
def ratings_for(lg, LASTW, PRIOR, mode):
    key = (lg, LASTW, PRIOR, mode)
    if key in _cache:
        return _cache[key]
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
        h = t['history']
        name = t['title']
        if not h:
            continue
        cf = sum(float(x['xG']) for x in h) / len(h)
        ca = sum(float(x['xGA']) for x in h) / len(h)
        nc = len(h)
        if mode == 'cur':
            f, a = cf, ca
        elif mode == 'last':
            if name in last:
                f, a = last[name][0], last[name][1]
            else:
                f, a = lgf, lgf   # promoted/no-prior side: league mean (disclosed weakness)
        else:
            lf, la_ = last.get(name, (lgf, lgf))
            f = (nc * cf + LASTW * 38 * lf + PRIOR * lgf) / (nc + LASTW * 38 + PRIOR)
            a = (nc * ca + LASTW * 38 * la_ + PRIOR * lgf) / (nc + LASTW * 38 + PRIOR)
        r[name] = (f / lgf, a / lgf)
    _cache[key] = (bh, ba, lgf, r)
    return _cache[key]

# variant family (round-1 provenance)
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
    ph = sum(g[i][j] for i in range(len(g)) for j in range(len(g)) if i > j)
    pd = sum(g[i][i] for i in range(len(g)))
    pa = sum(g[i][j] for i in range(len(g)) for j in range(len(g)) if i < j)
    ptot = defaultdict(float)
    for i in range(len(g)):
        for j in range(len(g)):
            ptot[i + j] += g[i][j]
    o25 = sum(v for t, v in ptot.items() if t >= 3)
    btts = sum(g[i][j] for i in range(1, len(g)) for j in range(1, len(g)))
    return ph, pd, pa, o25, btts

# team -> league lookup
TEAM_LEAGUE = {}
for lg in LEAGUES:
    d26 = load(lg, '2026')
    for t in d26['teams'].values():
        TEAM_LEAGUE[t['title']] = lg
ALL2025 = set()
for lg in LEAGUES:
    for t in load(lg, '2025')['teams'].values():
        ALL2025.add(t['title'])

def model_game(home, away, LASTW, PRIOR, rho, mode, cross, shrink=1.0):
    """Returns (ph, pd, pa, o25, btts, lh, la) or None if a team is unratable."""
    if not cross:
        lg = TEAM_LEAGUE.get(home)
        if lg is None or TEAM_LEAGUE.get(away) != lg:
            return None
        bh, ba, lgf, r = ratings_for(lg, LASTW, PRIOR, mode)
        if home not in r or away not in r:
            return None
        ah, dh = r[home]
        aa, da = r[away]
        lh = bh * (ah ** shrink) * (da ** shrink)
        la = ba * (aa ** shrink) * (dh ** shrink)
    else:
        lgh = TEAM_LEAGUE.get(home)
        lga = TEAM_LEAGUE.get(away)
        if lgh is None or lga is None:
            return None
        bh1, ba1, lgf1, r1 = ratings_for(lgh, LASTW, PRIOR, mode)
        bh2, ba2, lgf2, r2 = ratings_for(lga, LASTW, PRIOR, mode)
        if home not in r1 or away not in r2:
            return None
        bh = (bh1 + bh2) / 2.0
        ba = (ba1 + ba2) / 2.0
        ah, dh = r1[home]
        aa, da = r2[away]
        lh = bh * (ah ** shrink) * (da ** shrink)
        la = ba * (aa ** shrink) * (dh ** shrink)
    g = grid(lh, la, 10, rho)
    ph, pd, pa, o25, btts = outs(g)
    return ph, pd, pa, o25, btts, lh, la

# ---------- market extraction ----------
def f(x):
    try:
        return float(x)
    except Exception:
        return None

def market_quotes(slug):
    """Returns dict: {'1':(bid,ask), 'X':(bid,ask), '2':(bid,ask), 'O25':(bid,ask), 'U25':cost, 'BTTS':(bid,ask)}"""
    fx = FX[slug]
    q = {}
    for m in fx['family'].get(slug, {}).get('markets', []):
        grp = str(m['group'] or '')
        oc = m['outcomes'] or []
        if oc == ['Yes', 'No'] and ('Draw (' in str(m['q'])):
            q['X'] = (f(m['bestBid']), f(m['bestAsk']))
        elif oc == ['Yes', 'No'] and len(grp) < 60:
            # home or away win: match by title contains
            title_home = fx['home'].split()[0].lower()
            title_away = fx['away'].split()[0].lower()
            gl = grp.lower()
            if any(w in gl for w in ['draw', 'coventry city fc', 'nottingham forest']) and 'Draw' in grp:
                pass
            if grp.startswith('Draw'):
                q['X'] = (f(m['bestBid']), f(m['bestAsk']))
            else:
                # heuristic: match group name to home/away understat name fragments
                if _name_match(grp, fx['home']):
                    q['1'] = (f(m['bestBid']), f(m['bestAsk']))
                elif _name_match(grp, fx['away']):
                    q['2'] = (f(m['bestBid']), f(m['bestAsk']))
    more = fx['family'].get(slug + '-more-markets', {}).get('markets', [])
    for m in more:
        grp = str(m['group'] or '')
        oc = m['outcomes'] or []
        if grp == 'O/U 2.5' and oc == ['Over', 'Under']:
            q['O25'] = (f(m['bestBid']), f(m['bestAsk']))
        elif grp == 'Both Teams to Score' and oc == ['Yes', 'No']:
            q['BTTS'] = (f(m['bestBid']), f(m['bestAsk']))
    return q

def _name_match(grp, understat_name):
    gl = grp.lower()
    un = understat_name.lower()
    parts = [p for p in un.split() if len(p) > 2]
    if not parts:
        return False
    # most distinctive part matching
    return any(p in gl for p in parts)

# ---------- run the sweep ----------
print()
print('=== B) Model vs market sweep (cost = executable: YES/Over at ask, NO/Under at 1-bid) ===')
results = []
for slug, fx in sorted(FX.items(), key=lambda kv: str(kv[1]['game_start'])):
    home, away, cross = fx['home'], fx['away'], fx['cross']
    q = market_quotes(slug)
    # variants: for cross games add shrink variant
    variants = list(SWEEPS)
    if cross:
        variants = variants + [('cross-shrink .8', 0.5, 8, 0.0, 'blend')]
    per_market = defaultdict(dict)   # market -> variant -> p
    lambdas = {}
    for name, LASTW, PRIOR, rho, mode in variants:
        shr = 0.8 if name.startswith('cross-shrink') else 1.0
        out = model_game(home, away, LASTW, PRIOR, rho, mode, cross, shr)
        if out is None:
            per_market = None
            break
        ph, pd, pa, o25, btts, lh, la = out
        per_market['1'][name] = ph
        per_market['X'][name] = pd
        per_market['2'][name] = pa
        per_market['O25'][name] = o25
        per_market['U25'][name] = 1 - o25
        per_market['BTTS'][name] = btts
        lambdas[name] = (lh, la)
    if per_market is None:
        print('%-32s SKIP (unratable side: %s vs %s)' % (slug, home, away))
        continue
    # edges
    rows = []
    for mk in ['1', 'X', '2', 'O25', 'U25', 'BTTS']:
        if mk not in q or mk not in per_market:
            continue
        bid, ask = q[mk]
        if bid is None or ask is None:
            continue
        if mk in ('U25',):
            cost = 1 - bid          # buy Under = sell Over at bid
            p_of_cost_side = 'U25'
        else:
            cost = ask
        ps = per_market[mk]
        edges = {n: p - cost for n, p in ps.items()}
        cons = min(edges.values())
        cent = ps['blend w=.5 p=8 rho0']
        rows.append((mk, bid, ask, cost, cent, min(ps.values()), max(ps.values()), cons))
    lam_c = lambdas.get('blend w=.5 p=8 rho0')
    lam_range = (min(a + b for a, b in lambdas.values()), max(a + b for a, b in lambdas.values()))
    results.append({'slug': slug, 'home': home, 'away': away, 'cross': cross,
                    'game_start': fx['game_start'], 'q': q, 'rows': rows,
                    'lam_central': lam_c, 'lam_range': lam_range})

# print all fixtures
for r in results:
    gs = str(r['game_start'])[:16]
    print()
    print('%-32s %s vs %-18s %s %s' % (r['slug'], r['home'], r['away'], gs, 'CROSS' if r['cross'] else ''))
    if r['lam_central']:
        print('   lambda central %.2f/%.2f (total range %.2f-%.2f)' % (r['lam_central'][0], r['lam_central'][1], r['lam_range'][0], r['lam_range'][1]))
    for mk, bid, ask, cost, cent, lo, hi, cons in r['rows']:
        mark = ' <<< EDGE' if cons >= 0.06 else ''
        print('   %-5s bid=%-6s ask=%-6s cost=%.3f  model=%.3f [%.3f-%.3f]  edge_cons=%+.3f%s' % (
            mk, bid, ask, cost, cent, lo, hi, cons, mark))

json.dump(results, open('/home/ubuntu/paper-sim/round2/raw/sweep_results.json', 'w'), indent=1, default=str)
print()
print('saved sweep_results.json')
print()
print('=== C) FLAGGED (conservative edge >= +6c) ===')
for r in results:
    for mk, bid, ask, cost, cent, lo, hi, cons in r['rows']:
        if cons >= 0.06:
            print('%-32s %-5s cost=%.3f model=%.3f [%.3f-%.3f] cons=%+.3f  (%s vs %s)' % (
                r['slug'], mk, cost, cent, lo, hi, cons, r['home'], r['away']))
