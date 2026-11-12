"""Round-16 Bundesliga + Ligue 1 model scan.

Window: 2026-10-24T11:20Z .. 2026-10-25T03:00Z.
10-variant xG-Poisson (same SWEEPS as round-15).
match_winner not shortlisted. Held Lens totals excluded.
Spread lines with abs(line) >= 2.5 (need a 3+ goal margin) are flagged, not shortlisted.
"""
import json, math, re, time
from collections import defaultdict

RAW15 = '/home/ubuntu/paper-sim/round15/raw'
RAW = '/home/ubuntu/paper-sim/round16/raw'
XG = json.load(open(RAW15 + '/xg_understat_15.json'))
EV = json.load(open(RAW + '/bund_events_window.json'))['events']
LEAGUES = ['EPL', 'La_liga', 'Serie_A', 'Bundesliga', 'Ligue_1']
RHO_DC = -0.1
BIG5_SLUGS = {'bundesliga', 'ligue-1'}

NAME_MAP = {
 'VfB Stuttgart': 'VfB Stuttgart',
 'Borussia Monchengladbach': 'Borussia M.Gladbach',
 'Borussia Mönchengladbach': 'Borussia M.Gladbach',
 'RB Leipzig': 'RasenBallsport Leipzig',
 'SV 07 Elversberg': 'Elversberg',
 'SC Paderborn 07': 'Paderborn',
 'Hamburger SV': 'Hamburger SV',
 '1. FC Koln': 'FC Cologne',
 '1. FC Köln': 'FC Cologne',
 'FC Schalke 04': 'Schalke 04',
 'FC Augsburg': 'Augsburg',
 '1. FC Union Berlin': 'Union Berlin',
 '1. FSV Mainz 05': 'Mainz 05',
 'SV Werder Bremen': 'Werder Bremen',
 'BV Borussia 09 Dortmund': 'Borussia Dortmund',
 'Eintracht Frankfurt': 'Eintracht Frankfurt',
 'TSG 1899 Hoffenheim': 'Hoffenheim',
 'Bayer 04 Leverkusen': 'Bayer Leverkusen',
 'SC Freiburg': 'Freiburg',
 'FC Bayern Munchen': 'Bayern Munich',
 'FC Bayern München': 'Bayern Munich',
 'FC St. Pauli': 'St. Pauli',
 'Stade Brestois 29': 'Brest',
 'OGC Nice': 'Nice',
 'Racing Club de Lens': 'Lens',
 'Paris FC': 'Paris FC',
 'Angers SCO': 'Angers',
 'FC Lorient': 'Lorient',
 'Toulouse FC': 'Toulouse',
 'ES Troyes AC': 'Troyes',
 'Olympique de Marseille': 'Marseille',
 'Le Havre AC': 'Le Havre',
 'AS Monaco FC': 'Monaco',
 'Lille OSC': 'Lille',
 'Paris Saint-Germain FC': 'Paris Saint Germain',
 'Olympique Lyonnais': 'Lyon',
 'Stade Rennais FC 1901': 'Rennes',
 'RC Strasbourg Alsace': 'Strasbourg',
 'AJ Auxerre': 'Auxerre',
 'Le Mans FC': 'Le Mans',
 'FC Metz': 'Metz',
}
LEAGUE_TAG = {'bundesliga': 'Bundesliga', 'ligue-1': 'Ligue_1'}
HELD_TOTAL = {'Racing Club de Lens vs. Paris FC'}

_cache = {}

def load(lg, se):
    return XG['%s_%s' % (lg, se)]

def ratings_for(lg, LASTW, PRIOR, mode):
    key = (lg, LASTW, PRIOR, mode)
    if key in _cache:
        return _cache[key]
    d25 = load(lg, '2025')
    d26 = load(lg, '2026')
    ms = [m for m in d25['dates'] if m.get('isResult')]
    bh = sum(float(m['xG']['h']) for m in ms) / len(ms)
    ba = sum(float(m['xG']['a']) for m in ms) / len(ms)
    lgf = (bh + ba) / 2.0
    last = {}
    for t in d25['teams'].values():
        h = t['history']
        if not h:
            continue
        last[t['title']] = (sum(float(x['xG']) for x in h) / len(h),
                            sum(float(x['xGA']) for x in h) / len(h))
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
    ('blend w=.5 p=8 DC', 0.5, 8, RHO_DC, 'blend'),
    ('blend w=1.0 p=8', 1.0, 8, 0.0, 'blend'),
    ('blend w=.25 p=8', 0.25, 8, 0.0, 'blend'),
    ('blend w=.5 p=16', 0.5, 16, 0.0, 'blend'),
    ('blend w=.5 p=4', 0.5, 4, 0.0, 'blend'),
    ('current-only', None, None, 0.0, 'cur'),
    ('last-only', None, None, 0.0, 'last'),
    ('cross-shrink .8', 0.5, 8, 0.0, 'blend'),
    ('cross-shrink 1.1', 0.5, 8, 0.0, 'blend'),
]

def pois(l, k):
    return math.exp(-l) * (l ** k) / math.factorial(k)

def grid(lh, la, N=10, rho=0.0):
    g = [[pois(lh, i) * pois(la, j) for j in range(N + 1)] for i in range(N + 1)]
    if rho:
        g[0][0] *= max(1 - lh * la * rho, .01)
        g[0][1] *= max(1 + lh * rho, .01)
        g[1][0] *= max(1 + la * rho, .01)
        g[1][1] *= max(1 - rho, .01)
    s = sum(sum(row) for row in g)
    return [[v / s for v in row] for row in g]

TEAM_LEAGUE = {}
for lg in LEAGUES:
    for t in load(lg, '2026')['teams'].values():
        TEAM_LEAGUE[t['title']] = lg

def lambdas(home_pm, away_pm, LASTW, PRIOR, mode, shrink=1.0):
    hn = NAME_MAP.get(home_pm)
    an = NAME_MAP.get(away_pm)
    if hn is None or an is None:
        return None
    lgh = TEAM_LEAGUE.get(hn)
    lga = TEAM_LEAGUE.get(an)
    if lgh is None or lga is None or lgh != lga:
        return None
    bh1, ba1, lgf1, r1 = ratings_for(lgh, LASTW, PRIOR, mode)
    ah, dh = r1.get(hn, (1.0, 1.0))
    aa, da = r1.get(an, (1.0, 1.0))
    lh = bh1 * (ah ** shrink) * (da ** shrink)
    la = ba1 * (aa ** shrink) * (dh ** shrink)
    return lh, la, lgh

def variant_outputs(lh, la, rho):
    g = grid(lh, la, 10, rho)
    ph = sum(g[i][j] for i in range(11) for j in range(11) if i > j)
    pd_ = sum(g[i][i] for i in range(11))
    pa = 1.0 - ph - pd_
    tot = defaultdict(float)
    btts = 0.0
    marg = defaultdict(float)
    for i in range(11):
        for j in range(11):
            p = g[i][j]
            tot[i + j] += p
            if i >= 1 and j >= 1:
                btts += p
            marg[i - j] += p
    return {'H': ph, 'D': pd_, 'A': pa, 'btts': btts, 'tot': dict(tot), 'marg': dict(marg)}

def tail(d, n):
    return sum(v for k, v in d.items() if k >= n)

def recent_form(name_us):
    lg = TEAM_LEAGUE.get(name_us)
    if lg is None:
        return None
    def _hist(se):
        for t in load(lg, se)['teams'].values():
            if t.get('title') == name_us:
                return t.get('history') or []
        return []
    h = _hist('2026')
    if len(h) < 3:
        h = _hist('2025')
    if not h:
        return None
    last5 = h[-5:]
    gp = len(last5)
    gf = sum(int(x.get('scored') or 0) for x in last5)
    ga = sum(int(x.get('missed') or 0) for x in last5)
    xgf = sum(float(x.get('xG') or 0) for x in last5)
    xga = sum(float(x.get('xGA') or 0) for x in last5)
    o25 = sum(1 for x in last5 if (int(x.get('scored') or 0) + int(x.get('missed') or 0)) >= 3)
    btts_h = sum(1 for x in last5 if int(x.get('scored') or 0) >= 1 and int(x.get('missed') or 0) >= 1)
    return {'gp': gp, 'gf': gf, 'ga': ga, 'gpg_team': round((gf + ga) / gp, 2),
            'xg_pg': round((xgf + xga) / gp, 2), 'o25_hits': o25, 'btts_hits': btts_h,
            'last_date': str(last5[-1].get('date') or '')[:10]}

def med(v):
    s = sorted(v)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0

def model_match(home_pm, away_pm):
    per = []
    for name, LASTW, PRIOR, rho, mode in SWEEPS:
        if name.startswith('cross-shrink .8'):
            shrink = 0.8
        elif name.startswith('cross-shrink 1.1'):
            shrink = 1.1
        else:
            shrink = 1.0
        lam = lambdas(home_pm, away_pm, LASTW, PRIOR, mode, shrink)
        if lam is None:
            return None
        lh, la, lg = lam
        per.append({'name': name, 'lh': lh, 'la': la, 'lg': lg, 'o': variant_outputs(lh, la, rho)})
    return per

RE_SPREAD = re.compile(r'^Spread: (.+) \((-?\d+(?:\.\d+)?)\)$')
RE_TT = re.compile(r'^(.+): (.+) O/U (\d+(?:\.\d+)?)$')
RE_OU = re.compile(r'^(.+): O/U (\d+(?:\.\d+)?)$')

def classify(m, base, home_pm, away_pm):
    q = (m.get('q') or '').strip()
    low = q.lower()
    if ('halftime' in low or 'second half' in low or 'first half' in low
            or '1st half' in low or '2nd half' in low):
        return ('half', None, None)
    if 'orner' in low:
        return ('corners', None, None)
    if 'card' in low or 'booking' in low:
        return ('cards', None, None)
    if 'exact score' in low:
        return ('exactscore', None, None)
    if 'both teams to score' in low:
        return ('btts', None, None)
    if q.startswith('Will ') and (' win on ' in q or 'end in a draw' in q):
        return ('ml', None, None)
    mm = RE_SPREAD.match(q)
    if mm:
        return ('spread', mm.group(1), float(mm.group(2)))
    mm = RE_TT.match(q)
    if mm and mm.group(1) == base and mm.group(2) in (home_pm, away_pm):
        return ('teamtotal', mm.group(2), float(mm.group(3)))
    mm = RE_OU.match(q)
    if mm and mm.group(1) == base:
        return ('total', float(mm.group(2)), None)
    return ('other', None, None)

def quant(variants, kind, a1, a2, home_pm, away_pm):
    out = []
    for v in variants:
        o = v['o']
        if kind == 'total':
            n = int(math.floor(a1 + 1e-9)) + 1
            out.append(tail(o['tot'], n))
        elif kind == 'btts':
            out.append(o['btts'])
        elif kind == 'spread':
            line = a2
            if a1 == home_pm:
                m = o['marg']
            elif a1 == away_pm:
                m = {-(k): p for k, p in o['marg'].items()}
            else:
                return None
            need = -line
            out.append(sum(p for k, p in m.items() if k > need + 1e-9))
        else:
            return None
    return out

groups = {}
for e in EV:
    slugs = set(e.get('league_slugs') or [])
    if not (slugs & BIG5_SLUGS):
        continue
    base = (e.get('title') or '').split(' - ')[0].strip()
    if ' vs. ' not in base:
        continue
    g = groups.setdefault(base, {'events': [], 'slugs': set(), 'vol24': 0.0})
    g['events'].append(e)
    g['slugs'] |= slugs
    g['vol24'] += e.get('vol24') or 0

unmapped = set()
matches = []
for base, grp in groups.items():
    home_pm, away_pm = [x.strip() for x in base.split(' vs. ')]
    if home_pm not in NAME_MAP:
        unmapped.add(home_pm)
    if away_pm not in NAME_MAP:
        unmapped.add(away_pm)
    lgslug = (grp['slugs'] & BIG5_SLUGS).pop()
    mkts = {}
    kickoff = ''
    for e in grp['events']:
        for m in e.get('markets') or []:
            if m.get('closed'):
                continue
            gst = str(m.get('gameStartTime') or '')
            if gst and (not kickoff or gst < kickoff):
                kickoff = gst
            cls = classify(m, base, home_pm, away_pm)
            if cls[0] == 'other':
                continue
            prices = m.get('prices')
            if isinstance(prices, str):
                prices = json.loads(prices)
            toks = m.get('tokens')
            if isinstance(toks, str):
                toks = json.loads(toks)
            outs = m.get('outcomes')
            if isinstance(outs, str):
                outs = json.loads(outs)
            key = (cls[0], str(cls[1]), str(cls[2]) if cls[2] is not None else '', m.get('q'))
            mkts[key] = {
                'id': str(m['id']), 'q': m.get('q'), 'cls': cls, 'outcomes': outs,
                'prices': [float(x) for x in prices] if prices else [],
                'tokens': toks, 'liq': m.get('liq') or 0,
                'vol24': m.get('vol24'), 'bid': m.get('bestBid'), 'ask': m.get('bestAsk'),
            }
    matches.append({
        'base': base, 'home': home_pm, 'away': away_pm,
        'league': LEAGUE_TAG[lgslug], 'kickoff': kickoff,
        'vol24': grp['vol24'], 'markets': mkts,
    })

print('UNMAPPED', sorted(unmapped))
print('fixtures', len(matches))

scan_matches = []
shortlist = []
flagged = []
skipped = defaultdict(int)
kind_counts = defaultdict(int)

for mt in sorted(matches, key=lambda x: x['kickoff']):
    variants = model_match(mt['home'], mt['away'])
    if variants is None:
        print('MODEL MISS', mt['base'])
        skipped['model_miss'] += 1
        continue
    lam_h = med([v['lh'] for v in variants])
    lam_a = med([v['la'] for v in variants])
    fh = recent_form(NAME_MAP[mt['home']])
    fa = recent_form(NAME_MAP[mt['away']])
    h_vars = [v['o']['H'] for v in variants]
    d_vars = [v['o']['D'] for v in variants]
    a_vars = [v['o']['A'] for v in variants]
    rec = {
        'match': mt['base'], 'league': mt['league'], 'kickoff': mt['kickoff'],
        'vol24': round(mt['vol24'], 1),
        'lambda_home': round(lam_h, 3), 'lambda_away': round(lam_a, 3),
        'lambda_total': round(lam_h + lam_a, 3),
        'p_home_med': round(med(h_vars), 4), 'p_draw_med': round(med(d_vars), 4),
        'p_away_med': round(med(a_vars), 4),
        'p_home_var_spread': round(max(h_vars) - min(h_vars), 4),
        'p_draw_var_spread': round(max(d_vars) - min(d_vars), 4),
        'p_away_var_spread': round(max(a_vars) - min(a_vars), 4),
        'form_home': fh, 'form_away': fa, 'markets': [],
    }
    print('%-52s %s lh=%.2f la=%.2f lT=%.2f 1X2=%.2f/%.2f/%.2f' % (
        mt['base'][:52], mt['kickoff'][:16], lam_h, lam_a, lam_h + lam_a,
        med(h_vars), med(d_vars), med(a_vars)))
    for key, mkt in sorted(mt['markets'].items(), key=lambda kv: kv[1]['q'] or ''):
        kind = mkt['cls'][0]
        a1 = mkt['cls'][1]
        a2 = mkt['cls'][2] if len(mkt['cls']) > 2 else None
        kind_counts[kind] += 1
        if kind not in ('total', 'btts', 'spread'):
            continue
        qs = quant(variants, kind, a1, a2, mt['home'], mt['away'])
        if not qs:
            skipped['quant_none'] += 1
            continue
        q_med, q_min, q_max = med(qs), min(qs), max(qs)
        spread = q_max - q_min
        pr = mkt['prices'] or []
        outs = mkt['outcomes'] or []
        p0 = pr[0] if pr else None
        p1 = pr[1] if len(pr) > 1 else (None if p0 is None else 1 - p0)
        liq = mkt['liq'] or 0
        row = {
            'q': mkt['q'], 'kind': kind, 'id': mkt['id'], 'outcomes': outs,
            'prices': pr, 'liq': liq, 'bid': mkt['bid'], 'ask': mkt['ask'],
            'tokens': mkt['tokens'],
            'p0_med': round(q_med, 4), 'p0_min': round(q_min, 4), 'p0_max': round(q_max, 4),
            'var_spread': round(spread, 4),
            'edge0_mid': None if p0 is None else round(q_med - p0, 4),
            'edge1_mid': None if p1 is None else round((1 - q_med) - p1, 4),
        }
        rec['markets'].append(row)
        blowout = kind == 'spread' and a2 is not None and abs(float(a2)) >= 2.5
        held = mt['base'] in HELD_TOTAL and kind == 'total'
        best_edge = 0.0
        if p0 is not None and p1 is not None:
            best_edge = max(q_med - p0, (1 - q_med) - p1)
        if blowout and best_edge >= 0.04 and liq >= 5000:
            flagged.append({
                'match': mt['base'], 'league': mt['league'], 'kickoff': mt['kickoff'],
                'q': mkt['q'], 'kind': kind, 'why': 'blowout-tail 3+ goal margin, not recommended',
                'prices': pr, 'outcomes': outs, 'p0_med': round(q_med, 4),
                'edge0_mid': row['edge0_mid'], 'edge1_mid': row['edge1_mid'],
                'var_spread': round(spread, 4), 'liq': liq, 'id': mkt['id'],
                'tokens': mkt['tokens'],
            })
        if held:
            flagged.append({
                'match': mt['base'], 'league': mt['league'], 'kickoff': mt['kickoff'],
                'q': mkt['q'], 'kind': kind,
                'why': 'held same-type total (LENS-PFC O/U); no re-bet',
                'prices': pr, 'outcomes': outs, 'p0_med': round(q_med, 4),
                'edge0_mid': row['edge0_mid'], 'edge1_mid': row['edge1_mid'],
                'var_spread': round(spread, 4), 'liq': liq, 'id': mkt['id'],
                'tokens': mkt['tokens'],
            })
        if blowout:
            skipped['blowout'] += 1
            continue
        if held:
            skipped['held_same_type'] += 1
            continue
        if spread > 0.06:
            skipped['spread>6c'] += 1
            continue
        if liq < 5000:
            skipped['illiquid'] += 1
            continue
        if p0 is None or p1 is None:
            skipped['no_price'] += 1
            continue
        if best_edge < 0.04:
            skipped['edge<4c_mid'] += 1
            continue
        shortlist.append({
            'match': mt['base'], 'league': mt['league'], 'kickoff': mt['kickoff'],
            'kind': kind, 'q': mkt['q'], 'id': mkt['id'],
            'side0': outs[0] if outs else '?', 'side1': outs[1] if len(outs) > 1 else '?',
            'mid0': p0, 'mid1': p1,
            'q0_med': round(q_med, 4), 'q0_min': round(q_min, 4), 'q0_max': round(q_max, 4),
            'var_spread': round(spread, 4), 'liq': liq,
            'tokens': mkt['tokens'], 'gamma_bid': mkt['bid'], 'gamma_ask': mkt['ask'],
            'lambda_home': round(lam_h, 3), 'lambda_away': round(lam_a, 3),
            'lambda_total': round(lam_h + lam_a, 3),
            'form_home': fh, 'form_away': fa,
            'edge0_mid': round(q_med - p0, 4), 'edge1_mid': round((1 - q_med) - p1, 4),
            'variants': [{'name': v['name'], 'p0': round(qs[i], 4)} for i, v in enumerate(variants)],
        })
    scan_matches.append(rec)

print('kind counts', dict(kind_counts))
print('gated', dict(skipped))
print('shortlist', len(shortlist), 'flagged', len(flagged))
for s in sorted(shortlist, key=lambda x: -max(x['edge0_mid'], x['edge1_mid'])):
    print('  SL %-40s %-46s mid0=%.3f q=%.3f e0=%+.3f e1=%+.3f spr=%.3f liq=%.0f' % (
        s['match'][:40], s['q'][:46], s['mid0'], s['q0_med'], s['edge0_mid'], s['edge1_mid'],
        s['var_spread'], s['liq']))

nb = []
for e in EV:
    slugs = set(e.get('league_slugs') or [])
    if slugs & BIG5_SLUGS:
        continue
    if slugs & {'ere', 'primeira-liga'}:
        continue
    base = (e.get('title') or '').split(' - ')[0].strip()
    if ' vs. ' not in base:
        continue
    for m in e.get('markets') or []:
        q = m.get('q') or ''
        liq = m.get('liq') or 0
        if liq < 20000:
            continue
        if not (q.startswith('Will ') and (' win on ' in q or 'end in a draw' in q)):
            continue
        prices = m.get('prices')
        if isinstance(prices, str):
            prices = json.loads(prices)
        nb.append({
            'match': base, 'leagues': sorted(slugs), 'q': q,
            'kick': m.get('gameStartTime'), 'liq': liq, 'vol24': m.get('vol24'),
            'prices': prices, 'bid': m.get('bestBid'), 'ask': m.get('bestAsk'),
            'id': m.get('id'),
        })
nb.sort(key=lambda x: -(x['liq'] or 0))

out = {
    'generated_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    'window': ['2026-10-24T11:20:00Z', '2026-10-25T03:00:00Z'],
    'xg_file': 'round15/raw/xg_understat_15.json (Understat through 2026-10-23)',
    'variants': [s[0] for s in SWEEPS],
    'gates': 'var spread<=6c, liq>=$5k; book pass requires worst-variant edge>=+4c and exec edge>=+5c',
    'match_winner': 'SUSPENDED',
    'spread_policy': '3+ goal-margin spreads (abs line >= 2.5) flagged, not recommended; all spreads excluded from candidates',
    'held': 'Racing Club de Lens vs. Paris FC totals held (O1.5); no same-type re-bet',
    'fixture_count': len(scan_matches),
    'matches': scan_matches,
    'shortlist': shortlist,
    'flagged_not_recommended': flagged,
    'gated_out': dict(skipped),
    'non_big5_liquid_ml': nb[:40],
}
json.dump(out, open(RAW + '/bund_ligue_scan.json', 'w'), indent=1)
json.dump(shortlist, open(RAW + '/shortlist_bund.json', 'w'), indent=1)
print('saved bund_ligue_scan.json matches', len(scan_matches), 'nb5_ml', len(nb))
