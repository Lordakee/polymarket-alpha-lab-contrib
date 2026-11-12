"""Round-23 Ligue 1 full-slate model: 10-variant xG-Poisson (same methodology as r15/r18/r19/r21),
xG refreshed with Oct 23-25 Ligue 1 round (Brest-Nice, Toulouse-Troyes, Lens-PFC, Monaco-Lille,
Angers-Lorient, Auxerre-Le Mans, Marseille-Le Havre, Rennes-Strasbourg, PSG-Lyon).
match_winner SUSPENDED; spreads flagged-only (blowout-tail rule)."""
import json, math, re, time
from collections import defaultdict

RAW = '/home/ubuntu/paper-sim/round23/raw'
XG = json.load(open(RAW + '/xg_understat_ligue_23.json'))
RHO_DC = -0.1

NAME_MAP = {
 'Le Havre AC': 'Le Havre', 'Paris Saint-Germain FC': 'Paris Saint Germain',
 'OGC Nice': 'Nice', 'Stade Rennais FC 1901': 'Rennes', 'Lille OSC': 'Lille',
 'Racing Club de Lens': 'Lens', 'ES Troyes AC': 'Troyes', 'Le Mans FC': 'Le Mans',
 'RC Strasbourg Alsace': 'Strasbourg', 'AJ Auxerre': 'Auxerre',
 'Olympique Lyonnais': 'Lyon', 'Angers SCO': 'Angers', 'Paris FC': 'Paris FC',
 'AS Monaco FC': 'Monaco', 'Olympique de Marseille': 'Marseille',
 'Toulouse FC': 'Toulouse', 'FC Lorient': 'Lorient', 'Stade Brestois 29': 'Brest'}

def load(lg, se):
    return XG['%s_%s' % (lg, se)]

_c = {}
def ratings_for(lg, LASTW, PRIOR, mode):
    key = (lg, LASTW, PRIOR, mode)
    if key in _c: return _c[key]
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
        if mode == 'cur': f, a = cf, ca
        elif mode == 'last': f, a = last.get(name, (lgf, lgf))
        else:
            lf, la_ = last.get(name, (lgf, lgf))
            f = (nc * cf + LASTW * 38 * lf + PRIOR * lgf) / (nc + LASTW * 38 + PRIOR)
            a = (nc * ca + LASTW * 38 * la_ + PRIOR * lgf) / (nc + LASTW * 38 + PRIOR)
        r[name] = (f / lgf, a / lgf)
    _c[key] = (bh, ba, lgf, r)
    return _c[key]

SWEEPS = [('blend w=.5 p=8 rho0', 0.5, 8, 0.0, 'blend'), ('blend w=.5 p=8 DC', 0.5, 8, RHO_DC, 'blend'),
 ('blend w=1.0 p=8', 1.0, 8, 0.0, 'blend'), ('blend w=.25 p=8', 0.25, 8, 0.0, 'blend'),
 ('blend w=.5 p=16', 0.5, 16, 0.0, 'blend'), ('blend w=.5 p=4', 0.5, 4, 0.0, 'blend'),
 ('current-only', None, None, 0.0, 'cur'), ('last-only', None, None, 0.0, 'last'),
 ('cross-shrink .8', 0.5, 8, 0.0, 'blend'), ('cross-shrink 1.1', 0.5, 8, 0.0, 'blend')]

def pois(l, k): return math.exp(-l) * l ** k / math.factorial(k)

def gridf(lh, la, N=10, rho=0.0):
    g = [[pois(lh, i) * pois(la, j) for j in range(N + 1)] for i in range(N + 1)]
    if rho:
        g[0][0] *= max(1 - lh * la * rho, .01); g[0][1] *= max(1 + lh * rho, .01)
        g[1][0] *= max(1 + la * rho, .01); g[1][1] *= max(1 - rho, .01)
    s = sum(sum(r_) for r_ in g)
    return [[v / s for v in row] for row in g]

def variant_outputs(lh, la, rho):
    g = gridf(lh, la, 10, rho)
    ph = sum(g[i][j] for i in range(11) for j in range(11) if i > j)
    pd = sum(g[i][i] for i in range(11)); pa = 1.0 - ph - pd
    tot = defaultdict(float); btts = 0.0
    hg = defaultdict(float); ag = defaultdict(float); marg = defaultdict(float)
    for i in range(11):
        for j in range(11):
            p = g[i][j]; tot[i + j] += p
            if i >= 1 and j >= 1: btts += p
            hg[i] += p; ag[j] += p; marg[i - j] += p
    return {'H': ph, 'D': pd, 'A': pa, 'btts': btts, 'tot': dict(tot), 'hg': dict(hg), 'ag': dict(ag), 'marg': dict(marg)}

def tail(d, n): return sum(v for k, v in d.items() if k >= n)

def lambdas(home, away, LASTW, PRIOR, mode, shrink=1.0):
    hn = NAME_MAP.get(home); an = NAME_MAP.get(away)
    if hn is None or an is None: return None
    bh1, ba1, lgf1, r1 = ratings_for('Ligue_1', LASTW, PRIOR, mode)
    ah, dh = r1.get(hn, (1.0, 1.0)); aa, da = r1.get(an, (1.0, 1.0))
    return bh1 * (ah ** shrink) * (da ** shrink), ba1 * (aa ** shrink) * (dh ** shrink)

def med(v):
    s = sorted(v); n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0

RE_SPREAD = re.compile(r'^Spread: (.+) \((-?\d+(?:\.\d+)?)\)$')
RE_OU = re.compile(r'^(.*) O/U (\d+(?:\.\d+)*)$')

def classify(q, base, home_pm, away_pm):
    q = (q or '').strip()
    if '1st Half' in q or '2nd Half' in q: return ('half', None, None)
    if 'orners' in q: return ('corners', None, None)
    if 'Yellow Card' in q or 'Red Card' in q or 'Booking' in q: return ('cards', None, None)
    if 'Exact Score' in q or 'exact score' in q: return ('exactscore', None, None)
    if q == base + ': Both Teams to Score': return ('btts', None, None)
    if q.startswith('Will ') and (' win on ' in q or 'end in' in q): return ('ml', None, None)
    mm = RE_SPREAD.match(q)
    if mm: return ('spread', mm.group(1), float(mm.group(2)))
    mm = RE_OU.match(q)
    if mm and q == base + ': O/U ' + mm.group(2): return ('total', float(mm.group(2)), None)
    mm = RE_OU.match(q)
    if mm:
        g1 = mm.group(1)
        for tm in (home_pm, away_pm):
            if g1 == base + ': ' + tm:
                return ('teamtotal', tm, float(mm.group(2)))
    return ('other', None, None)

evs = json.load(open(RAW + '/events_window23.json'))
ligue = [e for e in evs if 'ligue-1' in (e.get('tags') or [])]
groups = {}
for e in ligue:
    t = str(e.get('title') or '')
    base = t.split(' - ')[0].strip()
    if ' vs. ' not in base: continue
    groups.setdefault(base, {'markets': [], 'vol24': 0})
    groups[base]['markets'].extend(e.get('markets') or [])
    groups[base]['vol24'] += e.get('vol24') or 0

print('Ligue 1 event groups:', len(groups))
scan = {'generated_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'scan': 'ligue_rest', 'round': 23, 'paper_only': True,
        'xg_base': 'round23/raw/xg_understat_ligue_23.json (Ligue_1 through 2026-10-25 19:45Z: full Oct 23-25 round incl PSG 2-0 Lyon xG 1.03-0.47, Monaco 1-1 Lille, Marseille 4-3 Le Havre, Rennes 3-0 Strasbourg, Lens 2-1 PFC, Toulouse 0-0 Troyes, Angers 0-0 Lorient, Auxerre 1-1 Le Mans, Brest 1-2 Nice)',
        'variants': [s[0] for s in SWEEPS],
        'match_winner': 'SUSPENDED', 'spread_policy': 'ALL spreads flagged-only (blowout-tail rule)',
        'gates': 'liq>=$5k; var spread<=6c; entry 0.10-0.92; books: exec edge>=+5c AND worst-variant edge>=+4c ($250 VWAP ask, filled)',
        'matches': {}}

shortlist = []
for base in sorted(groups):
    home_pm, away_pm = [x.strip() for x in base.split(' vs. ')]
    grp = groups[base]
    mkts = {}; kickoff = ''
    for m in grp['markets']:
        if m.get('closed'): continue
        q = (m.get('q') or ''); gst = str(m.get('gameStartTime') or '')
        if gst and (not kickoff or gst > kickoff): kickoff = gst
        cls = classify(q, base, home_pm, away_pm)
        if cls[0] in ('other', 'half', 'corners', 'cards', 'exactscore', 'ml'): continue
        if cls[0] == 'total': kteam, kline = None, cls[1]
        else: kteam, kline = cls[1], cls[2]
        prices = m.get('prices')
        if isinstance(prices, str): prices = json.loads(prices)
        toks = m.get('tokens')
        if isinstance(toks, str): toks = json.loads(toks)
        outs = m.get('outcomes')
        if isinstance(outs, str): outs = json.loads(outs)
        mkts[q] = {'id': str(m['id']), 'kind': cls[0], 'team': kteam, 'line': kline, 'outcomes': outs,
                   'prices': prices, 'tokens': toks, 'liq': m.get('liq'), 'bid': m.get('bestBid'), 'ask': m.get('bestAsk')}
    per = []
    for name, LASTW, PRIOR, rho, mode in SWEEPS:
        shrink = 0.8 if name.startswith('cross-shrink .8') else (1.1 if name.startswith('cross-shrink 1.1') else 1.0)
        lam = lambdas(home_pm, away_pm, LASTW, PRIOR, mode, shrink)
        lh, la = lam
        per.append({'name': name, 'lh': lh, 'la': la, 'o': variant_outputs(lh, la, rho)})
    lam_h = med([v['lh'] for v in per]); lam_a = med([v['la'] for v in per])
    rec = {'kickoff': kickoff, 'vol24': grp['vol24'],
           'lambda_home': round(lam_h, 3), 'lambda_away': round(lam_a, 3),
           'model_1x2_med': {'H': round(med([v['o']['H'] for v in per]), 4),
                             'D': round(med([v['o']['D'] for v in per]), 4),
                             'A': round(med([v['o']['A'] for v in per]), 4)},
           'markets': {}}
    for q, mkt in mkts.items():
        kind, team, line = mkt['kind'], mkt['team'], mkt['line']
        qs = []
        for v in per:
            o = v['o']
            if kind == 'total': qs.append(tail(o['tot'], int(math.floor(line + 1e-9)) + 1))
            elif kind == 'btts': qs.append(o['btts'])
            elif kind == 'teamtotal':
                n = int(math.floor(line + 1e-9)) + 1
                qs.append(tail(o['hg'] if team == home_pm else o['ag'], n))
            elif kind == 'spread':
                mm = o['marg'] if team == home_pm else {(-k): vv for k, vv in o['marg'].items()}
                need = -line
                qs.append(sum(p for k, p in mm.items() if k > need + 1e-9))
        q_med, q_min, q_max = med(qs), min(qs), max(qs)
        spread_v = q_max - q_min
        pr = mkt['prices'] or []
        p0 = float(pr[0]) if pr else None
        bid, ask = mkt['bid'], mkt['ask']
        mid = round((bid + ask) / 2, 3) if (bid is not None and ask is not None) else p0
        rec['markets'][q] = {'kind': kind, 'id': mkt['id'], 'outcomes': mkt['outcomes'], 'liq': mkt['liq'],
            'bid': bid, 'ask': ask, 'mid': mid,
            'p0_med': round(q_med, 4), 'p0_min': round(q_min, 4), 'p0_max': round(q_max, 4),
            'var_spread': round(spread_v, 4), 'qs_variants': [round(x, 4) for x in qs],
            'tokens': mkt['tokens']}
        # shortlist pre-book gates (candidate-eligible kinds only)
        if kind in ('total', 'btts', 'teamtotal'):
            liq = mkt['liq'] or 0
            e0 = q_med - mid          # buy side0 (Over / Yes)
            e1 = mid - q_med          # buy side1 (Under / No)
            best_side, best_edge = (0, e0) if e0 >= e1 else (1, e1)
            ok_core = (liq >= 5000 and spread_v <= 0.06 and mid is not None and 0.10 <= mid <= 0.92 and best_edge >= 0.025)
            ok_near = (liq >= 5000 and best_edge >= 0.035 and mid is not None and 0.10 <= mid <= 0.92)  # near-miss doc even if var fails
            if ok_core or ok_near:
                shortlist.append({'match': base, 'kickoff': kickoff, 'q': q, 'kind': kind, 'team': team,
                    'line': line, 'id': mkt['id'], 'liq': liq, 'bid': bid, 'ask': ask, 'mid': mid,
                    'q0_med': round(q_med, 4), 'qs_variants': [round(x, 4) for x in qs],
                    'var_spread': round(spread_v, 4), 'side': best_side,
                    'mid_edge': round(best_edge, 4), 'tokens': mkt['tokens'],
                    'core_pass': ok_core})
    scan['matches'][base] = rec
    print('%-52s %s lh=%.3f la=%.3f 1X2=%.2f/%.2f/%.2f mkts=%d' % (base, kickoff[:16], lam_h, lam_a,
          rec['model_1x2_med']['H'], rec['model_1x2_med']['D'], rec['model_1x2_med']['A'], len(rec['markets'])))

json.dump(scan, open(RAW + '/ligue_model23.json', 'w'), indent=1)
shortlist.sort(key=lambda s: (not s['core_pass'], -s['mid_edge']))
json.dump(shortlist, open(RAW + '/ligue_shortlist23.json', 'w'), indent=1)
print()
print('shortlist entries:', len(shortlist), '(core pass:', sum(1 for s in shortlist if s['core_pass']), ')')
for s in shortlist:
    print('  %s %-66s liq=%8.0f mid=%.3f edge=%+.4f var=%.4f side=%d %s' % (
        'CORE' if s['core_pass'] else 'near', s['q'][:66], s['liq'], s['mid'], s['mid_edge'], s['var_spread'], s['side'], s['match'][:26]))
print('saved ligue_model23.json + ligue_shortlist23.json')
