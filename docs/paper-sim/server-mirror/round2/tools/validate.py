import json, math
from collections import defaultdict

RAW = '/home/ubuntu/paper-sim/round2/raw/xg/'
LEAGUES = ['EPL', 'La_liga', 'Serie_A', 'Bundesliga', 'Ligue_1']

def load(lg, se):
    return json.load(open(RAW + '%s_%s.json' % (lg, se)))

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
    return ph, pd, pa, o25

# ---------- B1) walk-forward totals + dog calibration on 2026/27 played ----------
print('=== B1) Walk-forward calibration, 2026/27 played (last-season ratings, no lookahead) ===')
tot_all = {'n': 0, 'model_o25': 0.0, 'real_overs': 0}
dog_all = {'n': 0, 'model_dog': 0.0, 'real_dogwin': 0}
for lg in LEAGUES:
    d25 = load(lg, '2025'); d26 = load(lg, '2026')
    ms = [m for m in d25['dates'] if m.get('isResult')]
    bh = sum(float(m['xG']['h']) for m in ms) / len(ms)
    ba = sum(float(m['xG']['a']) for m in ms) / len(ms)
    lgf = (bh + ba) / 2
    last = {}
    for t in d25['teams'].values():
        h = t['history']
        last[t['title']] = (sum(float(x['xG']) for x in h) / len(h), sum(float(x['xGA']) for x in h) / len(h))
    n = 0; mo = 0.0; ro = 0; mdog = 0.0; rdog = 0
    bins = defaultdict(lambda: [0.0, 0])
    for m in d26['dates']:
        if not m.get('isResult'): continue
        h_, a_ = m['h']['title'], m['a']['title']
        if h_ not in last or a_ not in last: continue
        lh = bh * (last[h_][0] / lgf) * (last[a_][1] / lgf)
        la = ba * (last[a_][0] / lgf) * (last[h_][1] / lgf)
        ph, pd, pa, o25 = outs(grid(lh, la))
        gh, ga = int(m['goals']['h']), int(m['goals']['a'])
        tot = gh + ga
        n += 1
        mo += o25; ro += 1 if tot >= 3 else 0
        dog_p = min(ph, pa)
        dog_won = (gh < ga) if ph >= pa else (gh > ga)
        mdog += dog_p; rdog += 1 if dog_won else 0
        b = min(int(o25 * 10), 9)
        bins[b][0] += o25; bins[b][1] += 1
    print('  %-10s n=%3d  O2.5: model=%.3f realized=%.3f   dogwin: model=%.3f realized=%.3f' % (
        lg, n, mo / n, ro / n, mdog / n, rdog / n))
    tot_all['n'] += n; tot_all['model_o25'] += mo; tot_all['real_overs'] += ro
    dog_all['n'] += n; dog_all['model_dog'] += mdog; dog_all['real_dogwin'] += rdog
print('  TOTAL      n=%3d  O2.5: model=%.3f realized=%.3f   dogwin: model=%.3f realized=%.3f' % (
    tot_all['n'], tot_all['model_o25'] / tot_all['n'], tot_all['real_overs'] / tot_all['n'],
    dog_all['model_dog'] / dog_all['n'], dog_all['real_dogwin'] / dog_all['n']))

# ---------- B2) same with CURRENT-season ratings (in-sample but shows environment capture) ----------
print()
print('=== B2) Current-season ratings predicting played 2026/27 (in-sample; environment check) ===')
for lg in LEAGUES:
    d26 = load(lg, '2026')
    d25 = load(lg, '2025')
    ms25 = [m for m in d25['dates'] if m.get('isResult')]
    bh = sum(float(m['xG']['h']) for m in ms25) / len(ms25)
    ba = sum(float(m['xG']['a']) for m in ms25) / len(ms25)
    lgf = (bh + ba) / 2
    # iterative: ratings from all played games (in-sample)
    cur = {}
    for t in d26['teams'].values():
        h = t['history']
        if not h: continue
        cur[t['title']] = (sum(float(x['xG']) for x in h) / len(h), sum(float(x['xGA']) for x in h) / len(h))
    n = 0; mo = 0.0; ro = 0
    for m in d26['dates']:
        if not m.get('isResult'): continue
        h_, a_ = m['h']['title'], m['a']['title']
        if h_ not in cur or a_ not in cur: continue
        lh = bh * (cur[h_][0] / lgf) * (cur[a_][1] / lgf)
        la = ba * (cur[a_][0] / lgf) * (cur[h_][1] / lgf)
        ph, pd, pa, o25 = outs(grid(lh, la))
        n += 1; mo += o25; ro += 1 if int(m['goals']['h']) + int(m['goals']['a']) >= 3 else 0
    print('  %-10s n=%3d  O2.5: model=%.3f realized=%.3f' % (lg, n, mo / n, ro / n))

# ---------- C) team deep-dives for flagged fixtures ----------
print()
print('=== C) Team deep-dives (2026/27: P, W-D-L, GF-GA, xG-xGA per game | 2025/26 xG-xGA pg) ===')
def team_stats(lg, name):
    d26 = load(lg, '2026'); d25 = load(lg, '2025')
    t26 = next((t for t in d26['teams'].values() if t['title'] == name), None)
    t25 = next((t for t in d25['teams'].values() if t['title'] == name), None)
    if t26 is None:
        return None
    h = t26['history']
    if not h:
        return (name, 0, '0-0-0', 0, 0, None, None)
    pts = sum(int(x['pts']) for x in h)
    w = sum(1 for x in h if x['result'] == 'w'); dr = sum(1 for x in h if x['result'] == 'd'); l = sum(1 for x in h if x['result'] == 'l')
    gf = sum(int(x['scored']) for x in h); ga = sum(int(x['missed']) for x in h)
    xg = sum(float(x['xG']) for x in h) / len(h); xga = sum(float(x['xGA']) for x in h) / len(h)
    ppg = None; xg25 = xga25 = None
    if t25 is not None and t25['history']:
        hh = t25['history']
        ppg = sum(int(x['pts']) for x in hh)
        xg25 = sum(float(x['xG']) for x in hh) / len(hh)
        xga25 = sum(float(x['xGA']) for x in hh) / len(hh)
    # last 5 results
    last5 = [x['result'] for x in h[-5:]]
    return (name, len(h), '%d-%d-%d' % (w, dr, l), gf, ga, xg, xga, pts, ppg, xg25, xga25, ''.join(last5))

DIVES = [
    ('EPL', 'Coventry'), ('EPL', 'Newcastle United'),
    ('La_liga', 'Levante'), ('La_liga', 'Sevilla'),
    ('Serie_A', 'Torino'), ('Serie_A', 'Udinese'),
    ('Serie_A', 'Atalanta'), ('Serie_A', 'Venezia'),
    ('Bundesliga', 'Schalke 04'), ('Bundesliga', 'Mainz 05'),
    ('La_liga', 'Espanyol'), ('La_liga', 'Atletico Madrid'),
    ('Serie_A', 'Roma'), ('La_liga', 'Real Madrid'),
    ('Ligue_1', 'Lyon'), ('EPL', 'Crystal Palace'),
    ('EPL', 'Arsenal'), ('Ligue_1', 'Lille'),
    ('EPL', 'Tottenham'),
]
for lg, nm in DIVES:
    s = team_stats(lg, nm)
    if s is None:
        print('  %-22s NOT FOUND in %s 2026/27' % (nm, lg)); continue
    if len(s) == 6:
        print('  %-22s no matches yet' % nm); continue
    name, ng, wdl, gf, ga, xg, xga, pts, ppg, xg25, xga25, l5 = s
    print('  %-10s %-22s n=%2d %s GF-GA %2d-%2d xG %.2f xGA %.2f pts=%2d | 25/26: pts=%s xG %.2f xGA %.2f | L5 %s' % (
        lg, name, ng, wdl, gf, ga, xg, xga, pts, ppg, xg25 if xg25 else -1, xga25 if xga25 else -1, l5))

# league tables top/bottom for context
print()
print('=== D) Current tables (top 6 + bottom 3 per league, by points) ===')
for lg in LEAGUES:
    d26 = load(lg, '2026')
    rows = []
    for t in d26['teams'].values():
        h = t['history']
        if not h: continue
        rows.append((sum(int(x['pts']) for x in h), sum(int(x['scored']) for x in h) - sum(int(x['missed']) for x in h), t['title']))
    rows.sort(key=lambda r: (-r[0], -r[1]))
    tops = ', '.join('%s %d' % (r[2], r[0]) for r in rows[:6])
    bots = ', '.join('%s %d' % (r[2], r[0]) for r in rows[-3:])
    print('  %-10s TOP: %s | BOTTOM: %s' % (lg, tops, bots))
