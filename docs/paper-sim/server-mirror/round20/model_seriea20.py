"""Round-20 Serie A sub-scan model: same 10-variant xG-Poisson methodology as r15/r19,
xG refreshed with Sun Oct-25 Serie A round + Mon Oct-26 (PSG-Lyon, Sevilla-Osasuna).
Adds teamtotal modeling (r19 extension) and per-market delta vs r19 model output."""
import json, math, re, time
from collections import defaultdict

RAW = '/home/ubuntu/paper-sim/round20/raw'
XG = json.load(open(RAW + '/xg_understat_20.json'))
RHO_DC = -0.1

NAME_MAP = {'Torino FC': 'Torino', 'AC Monza': 'Monza', 'Cagliari Calcio': 'Cagliari',
 'Bologna FC 1909': 'Bologna', 'Como 1907': 'Como', 'US Sassuolo Calcio': 'Sassuolo',
 'SSC Napoli': 'Napoli', 'AS Roma': 'Roma', 'SS Lazio': 'Lazio',
 'Parma Calcio 1913': 'Parma Calcio 1913', 'FC Internazionale Milano': 'Inter',
 'ACF Fiorentina': 'Fiorentina', 'Atalanta BC': 'Atalanta', 'Frosinone Calcio': 'Frosinone',
 'Genoa CFC': 'Genoa', 'Venezia FC': 'Venezia', 'US Lecce': 'Lecce', 'Juventus FC': 'Juventus',
 'Udinese Calcio': 'Udinese', 'AC Milan': 'AC Milan', 'Inter Milan': 'Inter'}

WINDOW_GAMES = [
 ('US Sassuolo Calcio vs. SS Lazio', True),
 ('AS Roma vs. Cagliari Calcio', True),
 ('Torino FC vs. Como 1907', True),
 ('AC Milan vs. Bologna FC 1909', True),
 ('Parma Calcio 1913 vs. Udinese Calcio', True),
 ('Venezia FC vs. FC Internazionale Milano', True),
 ('Genoa CFC vs. Juventus FC', True),
 ('AC Monza vs. SSC Napoli', True),
 ('Frosinone Calcio vs. US Lecce', False),
 ('ACF Fiorentina vs. Atalanta BC', False),
]

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

TEAM_LEAGUE = {}
for lg in ['EPL', 'La_liga', 'Serie_A', 'Bundesliga', 'Ligue_1']:
    for t in load(lg, '2026')['teams'].values(): TEAM_LEAGUE[t['title']] = lg

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
    lgh = TEAM_LEAGUE.get(hn); lga = TEAM_LEAGUE.get(an)
    if lgh is None or lga is None or lgh != lga: return None
    bh1, ba1, lgf1, r1 = ratings_for(lgh, LASTW, PRIOR, mode)
    ah, dh = r1.get(hn, (1.0, 1.0)); aa, da = r1.get(an, (1.0, 1.0))
    return bh1 * (ah ** shrink) * (da ** shrink), ba1 * (aa ** shrink) * (dh ** shrink)

def med(v):
    s = sorted(v); n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0

RE_SPREAD = re.compile(r'^Spread: (.+) \((-?\d+(?:\.\d+)?)\)$')
RE_OU = re.compile(r'^(.*) O/U (\d+(?:\.\d+)?)$')

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

evs = json.load(open(RAW + '/events_sea_20.json'))
groups = {}
for e in evs:
    t = str(e.get('title') or '')
    base = t.split(' - ')[0].strip()
    if ' vs. ' not in base: continue
    groups.setdefault(base, {'markets': [], 'vol24': 0})
    groups[base]['markets'].extend(e.get('markets') or [])
    groups[base]['vol24'] += e.get('vol24') or 0

r19 = json.load(open('/home/ubuntu/paper-sim/round19/raw/soccer_scan.json'))
r19m = r19['model']

scan = {'generated_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'scan': 'seriea', 'round': 20, 'paper_only': True,
        'xg_base': 'round20/raw/xg_understat_20.json (Serie_A through 2026-10-25 19:45 incl Sun Oct-25 round; Ligue_1 incl PSG 2-0 Lyon; La_liga incl Sevilla 2-0 Osasuna)',
        'r19_xg_base': 'round15/raw/xg_understat_15.json (Serie_A through 2026-10-24 18:45)',
        'matches': {}}

for base, inwin in WINDOW_GAMES:
    home_pm, away_pm = [x.strip() for x in base.split(' vs. ')]
    grp = groups.get(base)
    if not grp:
        print('MISSING EVENT', base); continue
    mkts = {}; kickoff = ''
    for m in grp['markets']:
        if m.get('closed'): continue
        q = (m.get('q') or ''); gst = str(m.get('gameStartTime') or '')
        if gst and (not kickoff or gst > kickoff): kickoff = gst
        cls = classify(q, base, home_pm, away_pm)
        if cls[0] in ('other', 'half', 'corners', 'cards', 'exactscore', 'ml'): continue
        if cls[0] == 'total':
            kteam, kline = None, cls[1]
        else:
            kteam, kline = cls[1], cls[2]
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
        if lam is None: per = None; break
        lh, la = lam
        per.append({'name': name, 'lh': lh, 'la': la, 'o': variant_outputs(lh, la, rho)})
    if per is None:
        print(base, 'MODEL MISS'); continue
    lam_h = med([v['lh'] for v in per]); lam_a = med([v['la'] for v in per])
    r19rec = r19m.get(base) or {}
    dlh = round(lam_h - r19rec['lambda_home'], 3) if r19rec.get('lambda_home') is not None else None
    dla = round(lam_a - r19rec['lambda_away'], 3) if r19rec.get('lambda_away') is not None else None
    rec = {'kickoff': kickoff, 'in_window': inwin, 'vol24': grp['vol24'],
           'lambda_home': round(lam_h, 3), 'lambda_away': round(lam_a, 3),
           'r19_lambda_home': r19rec.get('lambda_home'), 'r19_lambda_away': r19rec.get('lambda_away'),
           'delta_lambda_home': dlh, 'delta_lambda_away': dla,
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
                m = o['marg'] if team == home_pm else {(-k): vv for k, vv in o['marg'].items()}
                need = -line
                qs.append(sum(p for k, p in m.items() if k > need + 1e-9))
            else:
                qs = None; break
        if not qs: continue
        q_med, q_min, q_max = med(qs), min(qs), max(qs)
        spread = q_max - q_min
        pr = mkt['prices'] or []
        p0 = float(pr[0]) if pr else None
        r19mm = (r19rec.get('markets') or {}).get(q)
        rec['markets'][q] = {'kind': kind, 'id': mkt['id'], 'outcomes': mkt['outcomes'], 'liq': mkt['liq'],
            'bid': mkt['bid'], 'ask': mkt['ask'],
            'mid': (round((mkt['bid'] + mkt['ask']) / 2, 3) if (mkt['bid'] is not None and mkt['ask'] is not None) else p0),
            'p0_med': round(q_med, 4), 'p0_min': round(q_min, 4), 'p0_max': round(q_max, 4),
            'var_spread': round(spread, 4), 'qs_variants': [round(x, 4) for x in qs],
            'tokens': mkt['tokens'],
            'r19_p0_med': r19mm.get('p0_med') if r19mm else None,
            'r19_var_spread': r19mm.get('var_spread') if r19mm else None,
            'delta_p0_med': round(q_med - r19mm['p0_med'], 4) if (r19mm and r19mm.get('p0_med') is not None) else None,
            'delta_var_spread': round(spread - r19mm['var_spread'], 4) if (r19mm and r19mm.get('var_spread') is not None) else None}
    scan['matches'][base] = rec
    print('%-46s %s lh=%.3f(%+.3f) la=%.3f(%+.3f) mkts=%d' % (base, kickoff[:16], lam_h, dlh or 0, lam_a, dla or 0, len(rec['markets'])))

json.dump(scan, open(RAW + '/seriea_model20.json', 'w'), indent=1)
print('saved seriea_model20.json')
