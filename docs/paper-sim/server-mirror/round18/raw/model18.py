"""Round-18 La Liga model: Sevilla FC vs CA Osasuna (Mon Oct 26 20:00Z), 10-variant
xG-Poisson per round15/17 methodology, on refreshed xg_understat_18.json (98 matches,
includes Sun Oct-25 results). Eligible candidate kinds: full-match O/U totals,
BTTS, team totals (both directions). Spread/blowout = flagged-only. match_winner
SUSPENDED. 1st/2nd-half = report-only this round."""
import json, math, re, time
from collections import defaultdict

RAW = '/home/ubuntu/paper-sim/round18/raw'
XG = json.load(open(RAW + '/xg_understat_18.json'))
LG = 'La_liga'
RHO_DC = -0.1
NAME_MAP = {'Sevilla FC': 'Sevilla', 'CA Osasuna': 'Osasuna'}
BASE = 'Sevilla FC vs. CA Osasuna'
HOME_PM, AWAY_PM = 'Sevilla FC', 'CA Osasuna'

def load(se): return XG['%s_%s' % (LG, se)]

_cache = {}
def ratings_for(LASTW, PRIOR, mode):
    key = (LASTW, PRIOR, mode)
    if key in _cache: return _cache[key]
    d25 = load('2025'); d26 = load('2026')
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
    _cache[key] = (bh, ba, lgf, r)
    return _cache[key]

SWEEPS = [
    ('blend w=.5 p=8 rho0', 0.5, 8, 0.0, 'blend'),
    ('blend w=.5 p=8 DC',   0.5, 8, RHO_DC, 'blend'),
    ('blend w=1.0 p=8',     1.0, 8, 0.0, 'blend'),
    ('blend w=.25 p=8',     0.25, 8, 0.0, 'blend'),
    ('blend w=.5 p=16',     0.5, 16, 0.0, 'blend'),
    ('blend w=.5 p=4',      0.5, 4, 0.0, 'blend'),
    ('current-only',        None, None, 0.0, 'cur'),
    ('last-only',           None, None, 0.0, 'last'),
    ('cross-shrink .8',     0.5, 8, 0.0, 'blend'),
    ('cross-shrink 1.1',    0.5, 8, 0.0, 'blend'),
]

def pois(l, k): return math.exp(-l) * l ** k / math.factorial(k)

def grid(lh, la, N=10, rho=0.0):
    g = [[pois(lh, i) * pois(la, j) for j in range(N + 1)] for i in range(N + 1)]
    if rho:
        g[0][0] *= max(1 - lh * la * rho, .01); g[0][1] *= max(1 + lh * rho, .01)
        g[1][0] *= max(1 + la * rho, .01); g[1][1] *= max(1 - rho, .01)
    s = sum(sum(r) for r in g)
    return [[v / s for v in row] for row in g]

def variant_outputs(lh, la, rho):
    g = grid(lh, la, 10, rho)
    ph = sum(g[i][j] for i in range(11) for j in range(11) if i > j)
    pd_ = sum(g[i][i] for i in range(11))
    pa = 1.0 - ph - pd_
    tot = defaultdict(float); btts = 0.0
    hg = defaultdict(float); ag = defaultdict(float); marg = defaultdict(float)
    for i in range(11):
        for j in range(11):
            p = g[i][j]
            tot[i + j] += p
            if i >= 1 and j >= 1: btts += p
            hg[i] += p; ag[j] += p; marg[i - j] += p
    return {'H': ph, 'D': pd_, 'A': pa, 'btts': btts, 'tot': dict(tot), 'hg': dict(hg), 'ag': dict(ag), 'marg': dict(marg)}

def tail(d, n): return sum(v for k, v in d.items() if k >= n)

def recent_form(name_us):
    def _hist(se):
        for t in load(se)['teams'].values():
            if t.get('title') == name_us: return t.get('history') or []
        return []
    h = _hist('2026')
    if len(h) < 3: h = _hist('2025')
    if not h: return None
    last5 = h[-5:]
    gp = len(last5)
    gf = sum(int(x.get('scored') or 0) for x in last5)
    ga = sum(int(x.get('missed') or 0) for x in last5)
    o25 = sum(1 for x in last5 if (int(x.get('scored') or 0) + int(x.get('missed') or 0)) >= 3)
    btts = sum(1 for x in last5 if int(x.get('scored') or 0) >= 1 and int(x.get('missed') or 0) >= 1)
    scores = ['%d-%d' % (int(x.get('scored') or 0), int(x.get('missed') or 0)) for x in last5]
    return {'gp': gp, 'gf': gf, 'ga': ga, 'gpg_team': round((gf + ga) / gp, 2),
            'o25_hits': o25, 'btts_hits': btts, 'scores': scores}

hn, an = NAME_MAP[HOME_PM], NAME_MAP[AWAY_PM]
variants = []
for name, LASTW, PRIOR, rho, mode in SWEEPS:
    shrink = 0.8 if name.startswith('cross-shrink .8') else (1.1 if name.startswith('cross-shrink 1.1') else 1.0)
    bh, ba, lgf, r1 = ratings_for(LASTW, PRIOR, mode)
    ah, dh = r1.get(hn, (1.0, 1.0)); aa, da = r1.get(an, (1.0, 1.0))
    lh = bh * (ah ** shrink) * (da ** shrink)
    la = ba * (aa ** shrink) * (dh ** shrink)
    variants.append({'name': name, 'lh': lh, 'la': la, 'o': variant_outputs(lh, la, rho)})

def med(v):
    s = sorted(v); n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0

def quant(kind, a1, a2):
    out = []
    for v in variants:
        o = v['o']
        if kind == 'total':
            n = int(math.floor(a1 + 1e-9)) + 1
            out.append(tail(o['tot'], n))
        elif kind == 'btts':
            out.append(o['btts'])
        elif kind == 'teamtotal':
            if a1 == HOME_PM: out.append(tail(o['hg'], int(math.floor(a2 + 1e-9)) + 1))
            else: out.append(tail(o['ag'], int(math.floor(a2 + 1e-9)) + 1))
        elif kind == 'spread':
            line = a2
            m = o['marg'] if a1 == HOME_PM else dict([(-k, v) for k, v in o['marg'].items()])
            need = -line
            out.append(sum(p for k, p in m.items() if k > need + 1e-9))
        else: return None
    return out

RE_TOTAL = re.compile('^' + re.escape(BASE) + r': O/U (\d+(?:\.\d+)?)$')
RE_TT = re.compile('^' + re.escape(BASE) + r': (' + re.escape(HOME_PM) + '|' + re.escape(AWAY_PM) + r') O/U (\d+(?:\.\d+)?)$')
RE_SPREAD = re.compile(r'^(?:1st Half |2nd Half )?Spread: (.+) \((-?\d+(?:\.\d+)?)\)$')

def classify(q):
    if '1st Half' in q or '2nd Half' in q: return ('half', None, None)
    if 'orners' in q: return ('corners', None, None)
    if 'Yellow Card' in q or 'Red Card' in q or 'Booking' in q: return ('cards', None, None)
    if 'Exact Score' in q or 'exact score' in q: return ('exactscore', None, None)
    if 'Team to Score' in q or 'score first' in q: return ('other', None, None)
    if q == BASE + ': Both Teams to Score': return ('btts', None, None)
    if q.startswith('Will ') and (' win on ' in q or 'end in' in q): return ('ml', None, None)
    mm = RE_TOTAL.match(q)
    if mm: return ('total', float(mm.group(1)), None)
    mm = RE_TT.match(q)
    if mm: return ('teamtotal', mm.group(1), float(mm.group(2)))
    mm = RE_SPREAD.match(q)
    if mm: return ('spread', mm.group(1), float(mm.group(2)))
    return ('other', None, None)

evs = json.load(open(RAW + '/events_window.json'))
mkts = {}; kickoff = ''
kind_counts = defaultdict(int)
for e in evs:
    if 'la-liga' not in (e.get('tags') or []): continue
    for m in e.get('markets') or []:
        if m.get('closed'): continue
        q = (m.get('q') or '').strip()
        gst = str(m.get('gameStartTime') or '')
        if gst and (not kickoff or gst > kickoff): kickoff = gst
        cls = classify(q)
        kind_counts[cls[0]] += 1
        if cls[0] in ('other', 'exactscore', 'corners', 'cards'): continue
        prices = m.get('prices'); prices = json.loads(prices) if isinstance(prices, str) else prices
        toks = m.get('tokens'); toks = json.loads(toks) if isinstance(toks, str) else toks
        outs = m.get('outcomes'); outs = json.loads(outs) if isinstance(outs, str) else outs
        mkts[q] = {'id': str(m['id']), 'q': q, 'cls': cls, 'outcomes': outs, 'prices': prices,
                   'tokens': toks, 'liq': m.get('liq'), 'vol24': m.get('vol24'),
                   'bid': m.get('bestBid'), 'ask': m.get('bestAsk')}

lam_h = med([v['lh'] for v in variants]); lam_a = med([v['la'] for v in variants])
fh, fa = recent_form(hn), recent_form(an)
m1x2 = {'H': med([v['o']['H'] for v in variants]), 'D': med([v['o']['D'] for v in variants]),
        'A': med([v['o']['A'] for v in variants])}
print('%s  lh=%.3f la=%.3f lT=%.2f  1X2 H/D/A = %.3f/%.3f/%.3f' % (BASE, lam_h, lam_a, lam_h + lam_a, m1x2['H'], m1x2['D'], m1x2['A']))
print('form home:', json.dumps(fh))
print('form away:', json.dumps(fa))
print('kind_counts:', dict(kind_counts))

rec = {'match': BASE, 'league': 'La_liga', 'kickoff': kickoff,
       'lambda_home': round(lam_h, 3), 'lambda_away': round(lam_a, 3),
       'lambda_total': round(lam_h + lam_a, 2), 'lambda_1h_total': round(0.44 * (lam_h + lam_a), 2),
       'model_1x2_med': {k: round(v, 4) for k, v in m1x2.items()},
       'form_home': fh, 'form_away': fa, 'markets': {}}
shortlist = []; flagged_spreads = []; skipped = defaultdict(int)
ELIGIBLE = ('total', 'btts', 'teamtotal')
for q, mkt in mkts.items():
    kind, a1, a2 = mkt['cls']
    liq = mkt['liq'] or 0
    pr = mkt['prices'] or []
    p0 = float(pr[0]) if pr else None
    qs = quant(kind, a1, a2)
    if qs is not None:
        q_med, q_min, q_max = med(qs), min(qs), max(qs)
        spread = q_max - q_min
    else:
        q_med = q_min = q_max = None; spread = None
    rec['markets'][q] = {'kind': kind, 'id': mkt['id'], 'outcomes': mkt['outcomes'], 'prices': pr,
                         'liq': liq, 'vol24': mkt['vol24'], 'bid': mkt['bid'], 'ask': mkt['ask'],
                         'tokens': mkt['tokens'],
                         'p0_med': None if q_med is None else round(q_med, 4),
                         'p0_min': None if q_min is None else round(q_min, 4),
                         'p0_max': None if q_max is None else round(q_max, 4),
                         'var_spread': None if spread is None else round(spread, 4)}
    if kind == 'ml':
        skipped['match_winner_SUSPENDED'] += 1; continue
    if kind == 'spread':
        flagged_spreads.append({'q': q, 'liq': liq, 'bid': mkt['bid'], 'ask': mkt['ask'],
                                'p0_med': None if q_med is None else round(q_med, 4),
                                'p0_min': None if q_min is None else round(q_min, 4),
                                'p0_max': None if q_max is None else round(q_max, 4),
                                'var_spread': None if spread is None else round(spread, 4),
                                'tokens': mkt['tokens'], 'outcomes': mkt['outcomes']})
        continue
    if kind == 'half':
        skipped['half_report_only'] += 1; continue
    if kind not in ELIGIBLE: continue
    if liq < 5000: skipped['illiquid(<5k)'] += 1; continue
    if p0 is None: skipped['no_price'] += 1; continue
    if spread > 0.08: skipped['model_uncertain(>8c prelim)'] += 1; continue
    e0 = q_med - p0
    if abs(e0) >= 0.04:
        shortlist.append({'match': BASE, 'kind': kind, 'q': q, 'id': mkt['id'],
                          'outcomes': mkt['outcomes'], 'tokens': mkt['tokens'],
                          'mid': p0, 'bid': mkt['bid'], 'ask': mkt['ask'], 'liq': liq, 'vol24': mkt['vol24'],
                          'q0_med': round(q_med, 4), 'q0_min': round(q_min, 4), 'q0_max': round(q_max, 4),
                          'var_spread': round(spread, 4),
                          'qs_variants': [round(x, 4) for x in qs],
                          'edge0_mid': round(e0, 4), 'edge1_mid': round(-e0, 4)})
print()
print('gated out (prelim):', dict(skipped))
print('shortlist (|edge vs gamma mid|>=4c):', len(shortlist))
for s in shortlist:
    print('  %-58s mid=%.3f  mod=%.4f [%.4f-%.4f] vspr=%.4f edge_mid=%+.4f liq=%.0f' % (
        s['q'][:58], s['mid'], s['q0_med'], s['q0_min'], s['q0_max'], s['var_spread'], s['edge0_mid'], s['liq']))

out = {'generated_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
       'model_rec': rec, 'shortlist': shortlist, 'flagged_spreads': flagged_spreads,
       'kind_counts': dict(kind_counts), 'gated_out_prelim': dict(skipped),
       'variants': [s[0] for s in SWEEPS]}
json.dump(out, open(RAW + '/model18_out.json', 'w'), indent=1)
json.dump(shortlist, open(RAW + '/shortlist_prelim18.json', 'w'), indent=1)
print('saved model18_out.json + shortlist_prelim18.json')
