"""Round-13 soccer scan: Polymarket Big-5 matches Oct 23-29, xG-Poisson (round-5c methodology).

Round-13 changes vs round-12:
- match_winner (1X2/ml) SUSPENDED per coordinator: no ml candidacy at all.
- team totals / corners / cards / halves recorded for new-market detection, not modeled.
- Candidates ONLY from: full-match O/U totals (both sides), BTTS (both), handicap/spread (both sides).
- Held fixtures excluded from same-type candidacy (totals held: IPS-FOR, ALA-MAL, RAY-ELC,
  ARS-EVE, VAL-VIL, SUN-LEE; BTTS held: HUL-BRE). Spread on held fixtures flagged.
"""
import json, math, re, time
from collections import defaultdict

RAW = '/home/ubuntu/paper-sim/round13/raw'
XG = json.load(open(RAW + '/xg_understat_13.json'))
LEAGUES = ['EPL', 'La_liga', 'Serie_A', 'Bundesliga', 'Ligue_1']
RHO_DC = -0.1

NAME_MAP = {
 'Ipswich Town FC':'Ipswich','Nottingham Forest FC':'Nottingham Forest',
 'Aston Villa FC':'Aston Villa','Manchester City FC':'Manchester City',
 'Arsenal FC':'Arsenal','Everton FC':'Everton','Coventry City FC':'Coventry',
 'Fulham FC':'Fulham','Chelsea FC':'Chelsea','Tottenham Hotspur FC':'Tottenham',
 'Liverpool FC':'Liverpool','Brighton & Hove Albion FC':'Brighton',
 'Manchester United FC':'Manchester United','AFC Bournemouth':'Bournemouth',
 'Hull City AFC':'Hull','Brentford FC':'Brentford','Crystal Palace FC':'Crystal Palace',
 'Newcastle United FC':'Newcastle United','Sunderland AFC':'Sunderland',
 'Leeds United FC':'Leeds',
 'Deportivo Alavés':'Alaves','Málaga CF':'Malaga','Rayo Vallecano de Madrid':'Rayo Vallecano',
 'Elche CF':'Elche','Real Racing Club':'Racing Santander',
 'RCD Espanyol de Barcelona':'Espanyol','Valencia CF':'Valencia','Villarreal CF':'Villarreal',
 'Club Atlético de Madrid':'Atletico Madrid','RC Deportivo A Coruña':'Deportivo La Coruna',
 'Athletic Club':'Athletic Club','Getafe CF':'Getafe','RC Celta de Vigo':'Celta Vigo',
 'Real Betis Balompié':'Real Betis','Real Sociedad de Fútbol':'Real Sociedad',
 'Levante UD':'Levante','FC Barcelona':'Barcelona','Real Madrid CF':'Real Madrid',
 'Sevilla FC':'Sevilla','CA Osasuna':'Osasuna',
 'VfB Stuttgart':'VfB Stuttgart','Borussia Mönchengladbach':'Borussia M.Gladbach',
 'RB Leipzig':'RasenBallsport Leipzig','SV 07 Elversberg':'Elversberg',
 'SC Paderborn 07':'Paderborn','Hamburger SV':'Hamburger SV','1. FC Köln':'FC Cologne',
 'FC Schalke 04':'Schalke 04','FC Augsburg':'Augsburg','1. FC Union Berlin':'Union Berlin',
 '1. FSV Mainz 05':'Mainz 05','SV Werder Bremen':'Werder Bremen',
 'BV Borussia 09 Dortmund':'Borussia Dortmund','Eintracht Frankfurt':'Eintracht Frankfurt',
 'TSG 1899 Hoffenheim':'Hoffenheim','Bayer 04 Leverkusen':'Bayer Leverkusen',
 'SC Freiburg':'Freiburg','FC Bayern München':'Bayern Munich',
 'Stade Brestois 29':'Brest','OGC Nice':'Nice','Racing Club de Lens':'Lens',
 'Paris FC':'Paris FC','Angers SCO':'Angers','FC Lorient':'Lorient',
 'Toulouse FC':'Toulouse','ES Troyes AC':'Troyes','Olympique de Marseille':'Marseille',
 'Le Havre AC':'Le Havre','AS Monaco FC':'Monaco','Lille OSC':'Lille',
 'Paris Saint-Germain FC':'Paris Saint Germain','Olympique Lyonnais':'Lyon',
 'Stade Rennais FC 1901':'Rennes','RC Strasbourg Alsace':'Strasbourg',
 'AJ Auxerre':'Auxerre','Le Mans FC':'Le Mans',
 'Torino FC':'Torino','AC Monza':'Monza','Cagliari Calcio':'Cagliari','Bologna FC 1909':'Bologna',
 'Como 1907':'Como','US Sassuolo Calcio':'Sassuolo','SSC Napoli':'Napoli','AS Roma':'Roma',
 'SS Lazio':'Lazio','Parma Calcio 1913':'Parma','Inter Milan':'Inter',
 'ACF Fiorentina':'Fiorentina','Atalanta':'Atalanta','Frosinone Calcio':'Frosinone',
 'Genoa CFC':'Genoa','Venezia FC':'Venezia','US Lecce':'Lecce','Juventus':'Juventus',
 'Udinese Calcio':'Udinese','AC Milan':'Milan',
}
LEAGUE_TAG = {'premier-league':'EPL','epl':'EPL','EPL':'EPL','la-liga':'La_liga','laliga':'La_liga',
              'bundesliga':'Bundesliga','ligue-1':'Ligue_1','ligue1':'Ligue_1'}

# held positions: no NEW same-type markets on these fixtures
HELD_TOTAL = {'Ipswich Town FC vs. Nottingham Forest FC','Deportivo Alavés vs. Málaga CF',
              'Rayo Vallecano de Madrid vs. Elche CF','Arsenal FC vs. Everton FC',
              'Valencia CF vs. Villarreal CF','Sunderland AFC vs. Leeds United FC'}
HELD_BTTS  = {'Hull City AFC vs. Brentford FC'}
HELD_ALL   = HELD_TOTAL | HELD_BTTS

_cache = {}
def load(lg, se): return XG['%s_%s' % (lg, se)]

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

TEAM_LEAGUE = {}
for lg in LEAGUES:
    for t in load(lg, '2026')['teams'].values(): TEAM_LEAGUE[t['title']] = lg

def lambdas(home_pm, away_pm, LASTW, PRIOR, mode, shrink=1.0):
    hn = NAME_MAP.get(home_pm); an = NAME_MAP.get(away_pm)
    if hn is None or an is None: return None
    lgh = TEAM_LEAGUE.get(hn); lga = TEAM_LEAGUE.get(an)
    if lgh is None or lga is None or lgh != lga: return None
    bh1, ba1, lgf1, r1 = ratings_for(lgh, LASTW, PRIOR, mode)
    ah, dh = r1.get(hn, (1.0, 1.0)); aa, da = r1.get(an, (1.0, 1.0))
    lh = bh1 * (ah ** shrink) * (da ** shrink)
    la = ba1 * (aa ** shrink) * (dh ** shrink)
    return lh, la, lgh

def variant_outputs(lh, la, rho):
    g = grid(lh, la, 10, rho)
    ph = sum(g[i][j] for i in range(11) for j in range(11) if i > j)
    pd = sum(g[i][i] for i in range(11))
    pa = 1.0 - ph - pd
    tot = defaultdict(float); btts = 0.0
    hg = defaultdict(float); ag = defaultdict(float); marg = defaultdict(float)
    for i in range(11):
        for j in range(11):
            p = g[i][j]
            tot[i + j] += p
            if i >= 1 and j >= 1: btts += p
            hg[i] += p; ag[j] += p; marg[i - j] += p
    return {'H': ph, 'D': pd, 'A': pa, 'btts': btts, 'tot': dict(tot), 'hg': dict(hg), 'ag': dict(ag), 'marg': dict(marg)}

def tail(d, n):
    return sum(v for k, v in d.items() if k >= n)

evs = json.load(open(RAW + '/events_window.json'))
BIG5_TAGS = set(LEAGUE_TAG)
big5 = [e for e in evs if BIG5_TAGS & set(e.get('tags') or [])]

groups = {}
for e in big5:
    t = str(e.get('title') or '')
    base = t.split(' - ')[0].strip()
    if ' vs. ' not in base: continue
    groups.setdefault(base, {'events': [], 'tags': set(), 'vol24': 0})
    groups[base]['events'].append(e)
    groups[base]['tags'] |= set(e.get('tags') or [])
    groups[base]['vol24'] += e.get('vol24') or 0

RE_SPREAD = re.compile(r'^Spread: (.+) \((-?\d+(?:\.\d+)?)\)$')
RE_OU = re.compile(r'^(.*) O/U (\d+(?:\.\d+)?)$')
RE_TT = re.compile(r'^(.+): O/U (\d+(?:\.\d+)?)$')

def classify(m, base, home_pm, away_pm):
    q = (m.get('q') or '').strip()
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
    mm = RE_TT.match(q)
    if mm and mm.group(1) != base and (mm.group(1) == home_pm or mm.group(1) == away_pm):
        return ('teamtotal', mm.group(1), float(mm.group(2)))
    return ('other', None, None)

def med(v):
    s = sorted(v); n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0

def model_match(home_pm, away_pm):
    per = []
    for name, LASTW, PRIOR, rho, mode in SWEEPS:
        shrink = 0.8 if name.startswith('cross-shrink .8') else (1.1 if name.startswith('cross-shrink 1.1') else 1.0)
        lam = lambdas(home_pm, away_pm, LASTW, PRIOR, mode, shrink)
        if lam is None: return None
        lh, la, lg = lam
        per.append({'name': name, 'lh': lh, 'la': la, 'lg': lg, 'o': variant_outputs(lh, la, rho)})
    return per

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
            if a1 == home_pm: m = o['marg']
            elif a1 == away_pm: m = {-(k): v for k, v in o['marg'].items()}
            else: return None
            need = -line
            out.append(sum(p for k, p in m.items() if k > need + 1e-9))
        else: return None
    return out

matches = []
unmapped = set()
for base, grp in groups.items():
    home_pm, away_pm = [x.strip() for x in base.split(' vs. ')]
    if home_pm not in NAME_MAP: unmapped.add(home_pm)
    if away_pm not in NAME_MAP: unmapped.add(away_pm)
    lg = LEAGUE_TAG.get((grp['tags'] & BIG5_TAGS).pop() if (grp['tags'] & BIG5_TAGS) else '')
    mkts = {}; kickoff = ''
    for e in grp['events']:
        for m in e.get('markets') or []:
            if m.get('closed'): continue
            q = (m.get('q') or '')
            gst = str(m.get('gameStartTime') or '')
            if gst and (not kickoff or gst > kickoff): kickoff = gst
            cls = classify(m, base, home_pm, away_pm)
            if cls[0] == 'other': continue
            prices = m.get('prices')
            if isinstance(prices, str): prices = json.loads(prices)
            toks = m.get('tokens')
            if isinstance(toks, str): toks = json.loads(toks)
            outs = m.get('outcomes')
            if isinstance(outs, str): outs = json.loads(outs)
            key = (cls[0], str(cls[1]), str(cls[2]) if cls[2] is not None else '')
            mkts[key] = {'id': str(m['id']), 'q': q, 'cls': cls, 'outcomes': outs,
                         'prices': prices, 'tokens': toks, 'liq': m.get('liq'),
                         'vol24': m.get('vol24'), 'bid': m.get('bestBid'), 'ask': m.get('bestAsk')}
    matches.append({'base': base, 'home': home_pm, 'away': away_pm, 'league': lg,
                    'kickoff': kickoff, 'vol24': grp['vol24'], 'markets': mkts})

if unmapped: print('UNMAPPED TEAMS:', unmapped)
print('matches with tagged Big-5 events:', len(matches))
matches = [mt for mt in matches if mt['home'] in NAME_MAP and mt['away'] in NAME_MAP and mt['markets']]
print('modelable matches:', len(matches))

scan = {'generated_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'xg_file': 'xg_understat_13.json (refreshed 2026-10-23, data through 2026-10-19; no Big-5 league games Oct 20-22)',
        'variants': [s[0] for s in SWEEPS], 'matches': []}
shortlist = []
skipped = defaultdict(int)
new_market_counts = defaultdict(int)

for mt in sorted(matches, key=lambda x: x['kickoff']):
    variants = model_match(mt['home'], mt['away'])
    if variants is None:
        print('%-46s MODEL MISS (team not in understat 2026)' % mt['base'])
        skipped['model_miss'] += 1
        continue
    lam_h = med([v['lh'] for v in variants]); lam_a = med([v['la'] for v in variants])
    rec = {'match': mt['base'], 'league': mt['league'], 'kickoff': mt['kickoff'],
           'vol24': mt['vol24'], 'lambda_home': round(lam_h, 3), 'lambda_away': round(lam_a, 3),
           'markets': {}}
    for key, mkt in mt['markets'].items():
        kind, a1, a2 = mkt['cls'][0], mkt['cls'][1], (mkt['cls'][2] if len(mkt['cls']) > 2 else None)
        if kind in ('half', 'corners', 'cards', 'exactscore', 'teamtotal', 'ml'):
            new_market_counts[kind] += 1
        qs = quant(variants, kind, a1, a2, mt['home'], mt['away']) if kind in ('total', 'btts', 'spread') else None
        pr = mkt['prices'] or []
        outs = mkt['outcomes'] or []
        liq = mkt['liq'] or 0
        p0 = float(pr[0]) if pr else None
        label = mkt['q']
        if qs is not None:
            q_med, q_min, q_max = med(qs), min(qs), max(qs)
            spread = q_max - q_min
        else:
            q_med = q_min = q_max = None; spread = None
        rec['markets'][label] = {'kind': kind, 'id': mkt['id'], 'q': label, 'outcomes': outs, 'prices': pr,
                'liq': liq, 'vol24': mkt['vol24'], 'bid': mkt['bid'], 'ask': mkt['ask'],
                'tokens': mkt['tokens'],
                'p0_med': None if q_med is None else round(q_med, 4),
                'p0_min': None if q_min is None else round(q_min, 4),
                'p0_max': None if q_max is None else round(q_max, 4),
                'var_spread': None if spread is None else round(spread, 4)}
        if kind not in ('total', 'btts', 'spread'):
            continue  # not candidate-eligible this round
        if liq < 5000: skipped['illiquid(<5k)'] += 1; continue
        if p0 is None: skipped['no_price'] += 1; continue
        if spread > 0.08: skipped['model_uncertain(spread>8c)'] += 1; continue
        if not (0.05 <= p0 <= 0.95 and 0.05 <= 1 - p0 <= 0.95): skipped['extreme_odds'] += 1; continue
        held = (mt['base'] in HELD_TOTAL and kind == 'total') or (mt['base'] in HELD_BTTS and kind == 'btts')
        if held: skipped['held_same_type'] += 1; continue
        held_other = mt['base'] in HELD_ALL
        e0 = q_med - p0
        if abs(e0) >= 0.04:
            shortlist.append({'match': mt['base'], 'league': mt['league'], 'kickoff': mt['kickoff'],
                              'kind': kind, 'held_fixture_other_type': held_other,
                              'side0': outs[0] if outs else '?', 'side1': outs[1] if len(outs) > 1 else '?',
                              'mid': p0, 'q0_med': q_med, 'q0_min': q_min, 'q0_max': q_max,
                              'var_spread': spread, 'liq': liq, 'id': mkt['id'], 'q': label,
                              'tokens': mkt['tokens'],
                              'edge0_mid': round(e0, 4), 'edge1_mid': round(-e0, 4)})
    scan['matches'].append(rec)
    print('%-52s %s lh=%.2f la=%.2f mkts=%d' % (mt['base'][:52], mt['kickoff'][:16], lam_h, lam_a, len(rec['markets'])))

print()
print('non-candidate market-type counts (new-market detection):', dict(new_market_counts))
print('gated out:', dict(skipped))
print('shortlist (|edge|>=4c on gamma mid):', len(shortlist))
json.dump({'scan': scan, 'shortlist': shortlist, 'gated_out': dict(skipped),
           'new_market_counts': dict(new_market_counts)},
          open(RAW + '/soccer_scan.json', 'w'), indent=1)
json.dump(shortlist, open(RAW + '/shortlist_prelim.json', 'w'), indent=1)
print('saved soccer_scan.json + shortlist_prelim.json')
