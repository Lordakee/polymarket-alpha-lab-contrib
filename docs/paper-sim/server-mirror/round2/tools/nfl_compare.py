import json, math

D = json.load(open('/home/ubuntu/paper-sim/round2/raw/other_details.json'))
E = json.load(open('/home/ubuntu/paper-sim/round2/raw/espn_nfl.json'))

# DK info keyed by (away, home) abbrev
DK = {}
for dt in E:
    for ev in E[dt].get('events', []):
        comp = ev['competitions'][0]
        od = comp.get('odds', [])
        if not od: continue
        o = od[0]
        name = ev.get('name') or ''
        parts = name.split(' at ')
        if len(parts) != 2: continue
        DK[(parts[0][:3].upper(), parts[1][:3].upper())] = {
            'spread': o.get('spread'), 'ou': o.get('overUnder'),
            'details': o.get('details'), 'date': ev.get('date')[:16],
            'lastMod': o.get('lastModified') or comp.get('date')}

# DK spread sign: details string says e.g. 'PIT -3'
import re
def dk_line(details):
    m = re.match(r'([A-Z]+) (-?\d+\.?\d*)', details or '')
    if not m: return None
    return m.group(1), float(m.group(2))

GAMES = [
  ('nfl-buf-la-2026-10-13','Bills','Rams'),
  ('nfl-sea-den-2026-10-16','Seahawks','Broncos'),
  ('nfl-dal-gb-2026-10-19','Cowboys','Packers'),
  ('nfl-car-phi-2026-10-18','Panthers','Eagles'),
  ('nfl-pit-tb-2026-10-18','Steelers','Buccaneers'),
  ('nfl-hou-jax-2026-10-18','Texans','Jaguars'),
  ('nfl-chi-atl-2026-10-18','Bears','Falcons'),
  ('nfl-bal-cle-2026-10-18','Ravens','Browns'),
  ('nfl-ten-ind-2026-10-18','Titans','Colts'),
  ('nfl-nyj-ne-2026-10-18','Jets','Patriots'),
  ('nfl-no-nyg-2026-10-18','Saints','Giants'),
  ('nfl-ari-la-2026-10-18','Cardinals','Rams'),
  ('nfl-lac-kc-2026-10-18','Chargers','Chiefs'),
  ('nfl-buf-lv-2026-10-18','Bills','Raiders'),
  ('nfl-was-sf-2026-10-20','Commanders','49ers'),
]
ABBR = {('Bills','Rams'):('BUF','LAR'),('Seahawks','Broncos'):('SEA','DEN'),('Cowboys','Packers'):('DAL','GB'),
        ('Panthers','Eagles'):('CAR','PHI'),('Steelers','Buccaneers'):('PIT','TB'),('Texans','Jaguars'):('HOU','JAX'),
        ('Bears','Falcons'):('CHI','ATL'),('Ravens','Browns'):('BAL','CLE'),('Titans','Colts'):('TEN','IND'),
        ('Jets','Patriots'):('NYJ','NE'),('Saints','Giants'):('NO','NYG'),('Cardinals','Rams'):('ARI','LAR'),
        ('Chargers','Chiefs'):('LAC','KC'),('Bills','Raiders'):('BUF','LV'),('Commanders','49ers'):('WSH','SF')}

def norm_cdf(x, mu=0, sig=13.7):
    return 0.5 * (1 + math.erf((x - mu) / (sig * math.sqrt(2))))

print('%-24s %-14s %-14s %-8s %-8s %-8s' % ('game','DK line','DK ML est','PM ML','PM spread-fair','gap'))
for slug, a, h in GAMES:
    ev = D[slug]
    aa, hh = ABBR[(a, h)]
    dk = DK.get((aa, hh))
    if not dk: print(slug, 'NO DK'); continue
    team, ln = dk_line(dk['details'])
    # PM ML
    ml = None; spreads = {}
    for m in ev['markets']:
        q = str(m['q'])
        if q == '%s vs. %s' % (a, h):
            try: ml = ((float(m['bestBid']) or 0) + (float(m['bestAsk']) or 0)) / 2
            except Exception: pass
            ml_out = m['outcomes']
        if q.startswith('Spread: '):
            mm = re.match(r'Spread: (\w[\w\s]*?) \(-(\d+\.5)\)', q)
            if mm and m['bestBid'] and m['bestAsk']:
                try:
                    mid = (float(m['bestBid']) + float(m['bestAsk'])) / 2
                    if float(m['bestAsk']) - float(m['bestBid']) <= 0.06:
                        spreads[(mm.group(1), float(mm.group(2)))] = mid
                except Exception: pass
    # PM fair line: find spread quote closest to 0.5 cover prob (home team perspective)
    # compute P(fav covers -x) for each quote
    pm_fair = None
    best = 999
    for (t, x), p in spreads.items():
        # p = P(t wins by > x). If t is home: P(margin_home > x)
        # fair line where cover prob = 0.5
        d = abs(p - 0.5)
        if d < best: best = d; pm_fair = (t, x, round(p, 3))
    # DK spread -> ML (normal, sigma 13.7, no home adjustment since spread already includes it)
    if team and ln is not None:
        # P(fav wins) = P(margin_fav > 0) where margin_fav ~ N(ln, 13.7)
        p_fav_win = norm_cdf(ln, 0, 13.7)
    else:
        p_fav_win = None
    pm_ml_fav = None
    if ml is not None and ml_out and ml_out[0] == a:
        pm_ml_fav = 1 - ml if team == hh else ml
    elif ml is not None:
        pm_ml_fav = ml if team == hh else 1 - ml
    gap = None
    if p_fav_win and pm_ml_fav: gap = round((pm_ml_fav - p_fav_win) * 100, 1)
    print('%-24s %-14s %-14s %-8s %-14s %s' % (
        '%s@%s' % (aa, hh), dk['details'], ('%.3f' % p_fav_win) if p_fav_win else '?',
        ('%.3f' % pm_ml_fav) if pm_ml_fav is not None else '?', pm_fair, ('%+.1fc' % gap) if gap is not None else '?'))
