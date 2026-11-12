import json, math, re

D = json.load(open('/home/ubuntu/paper-sim/round2/raw/other_details.json'))

# DK lines decoded from espn_nfl.json (details field): (away, home, fav, line, ou)
DKL = [
 ('BUF','LAR','LAR',3.5,54.5),('SEA','DEN','SEA',3.0,41.5),('HOU','JAX','JAX',3.0,43.5),
 ('CHI','ATL','CHI',3.0,47.5),('BAL','CLE','BAL',3.5,40.5),('TEN','IND','IND',7.0,44.5),
 ('NYJ','NE','NE',7.0,44.5),('NO','NYG','NO',1.5,45.5),('CAR','PHI','PHI',1.5,42.5),
 ('PIT','TB','PIT',3.0,40.5),('ARI','LAR','LAR',12.5,52.5),('LAC','KC','KC',8.5,43.5),
 ('BUF','LV','BUF',6.0,52.5),('DAL','GB','GB',1.5,52.5),('WSH','SF','SF',7.5,50.5),
]
GAMES = [
 ('nfl-buf-la-2026-10-13','Bills','Rams'),('nfl-sea-den-2026-10-16','Seahawks','Broncos'),
 ('nfl-dal-gb-2026-10-19','Cowboys','Packers'),('nfl-car-phi-2026-10-18','Panthers','Eagles'),
 ('nfl-pit-tb-2026-10-18','Steelers','Buccaneers'),('nfl-hou-jax-2026-10-18','Texans','Jaguars'),
 ('nfl-chi-atl-2026-10-18','Bears','Falcons'),('nfl-bal-cle-2026-10-18','Ravens','Browns'),
 ('nfl-ten-ind-2026-10-18','Titans','Colts'),('nfl-nyj-ne-2026-10-18','Jets','Patriots'),
 ('nfl-no-nyg-2026-10-18','Saints','Giants'),('nfl-ari-la-2026-10-18','Cardinals','Rams'),
 ('nfl-lac-kc-2026-10-18','Chargers','Chiefs'),('nfl-buf-lv-2026-10-18','Bills','Raiders'),
 ('nfl-was-sf-2026-10-20','Commanders','49ers'),
]
AB = {('Bills','Rams'):('BUF','LAR'),('Seahawks','Broncos'):('SEA','DEN'),('Cowboys','Packers'):('DAL','GB'),
      ('Panthers','Eagles'):('CAR','PHI'),('Steelers','Buccaneers'):('PIT','TB'),('Texans','Jaguars'):('HOU','JAX'),
      ('Bears','Falcons'):('CHI','ATL'),('Ravens','Browns'):('BAL','CLE'),('Titans','Colts'):('TEN','IND'),
      ('Jets','Patriots'):('NYJ','NE'),('Saints','Giants'):('NO','NYG'),('Cardinals','Rams'):('ARI','LAR'),
      ('Chargers','Chiefs'):('LAC','KC'),('Bills','Raiders'):('BUF','LV'),('Commanders','49ers'):('WSH','SF')}
FULL = {'BUF':'Bills','LAR':'Rams','SEA':'Seahawks','DEN':'Broncos','HOU':'Texans','JAX':'Jaguars','CHI':'Bears',
        'ATL':'Falcons','BAL':'Ravens','CLE':'Browns','TEN':'Titans','IND':'Colts','NYJ':'Jets','NE':'Patriots',
        'NO':'Saints','NYG':'Giants','CAR':'Panthers','PHI':'Eagles','PIT':'Steelers','TB':'Buccaneers',
        'ARI':'Cardinals','LAC':'Chargers','KC':'Chiefs','LV':'Raiders','DAL':'Cowboys','GB':'Packers',
        'WSH':'Commanders','SF':'49ers'}

def phi(z): return 0.5 * (1 + math.erf(z / math.sqrt(2)))

hdr = '%-9s %-10s | %-7s %-7s | %-7s %-11s | %-15s %-6s | %s'
print(hdr % ('game','DK line','DKML137','DKML15','PM ML','PM spr fair','PM tot ctr','DK ou','gap137/gap15'))
for slug, a, h in GAMES:
    aa, hh = AB[(a, h)]
    dk = next(d for d in DKL if d[0] == aa and d[1] == hh)
    _, _, fav, ln, ou = dk
    pml137 = phi(ln / 13.7)
    pml15 = phi(ln / 15.0)
    ev = D[slug]
    ml_mid = None; ml_out = None; ml_exec = None
    spreads = {}; totals = {}
    for m in ev['markets']:
        q = str(m['q'])
        try:
            bb = float(m['bestBid']) if m['bestBid'] not in (None, '') else None
            ba = float(m['bestAsk']) if m['bestAsk'] not in (None, '') else None
        except Exception:
            bb = ba = None
        if q == a + ' vs. ' + h and bb is not None and ba is not None:
            ml_mid = (bb + ba) / 2.0
            ml_out = m['outcomes']
            ml_exec = (bb, ba)
        mm = re.match(r'Spread: ([\w\s]+?) \(-(\d+\.5)\)$', q)
        if mm and bb is not None and ba is not None and (ba - bb) <= 0.05:
            spreads[(mm.group(1).strip(), float(mm.group(2)))] = (bb + ba) / 2.0
        mt = re.match(a + r' vs\. ' + h + r': O/U (\d+\.5)$', q)
        if mt and bb is not None and ba is not None and (ba - bb) <= 0.06:
            totals[float(mt.group(1))] = (bb + ba) / 2.0
    pm_ml_fav = None
    if ml_mid is not None and ml_out:
        fav_full = FULL[fav]
        if ml_out[0] == fav_full:
            pm_ml_fav = ml_mid
        else:
            pm_ml_fav = 1.0 - ml_mid
    pm_sp = None
    best = 9.0
    for (t, x), p in spreads.items():
        if t != FULL[fav]:
            continue
        d = abs(p - 0.5)
        if d < best:
            best = d
            pm_sp = (int(x), round(p, 3))
    pm_tot = None
    best = 9.0
    for t, p in sorted(totals.items()):
        d = abs(p - 0.5)
        if d < best:
            best = d
            pm_tot = (int(t), round(p, 3))
    g137 = g15 = None
    if pm_ml_fav is not None:
        g137 = round((pm_ml_fav - pml137) * 100.0, 1)
        g15 = round((pm_ml_fav - pml15) * 100.0, 1)
    flag = ''
    if g137 is not None and (g137 >= 5 or g137 <= -5):
        flag = '<-- CHECK'
    print(hdr % (
        aa + '@' + hh, '%s -%.1f' % (fav, ln), '%.3f' % pml137, '%.3f' % pml15,
        ('%.3f' % pm_ml_fav) if pm_ml_fav is not None else '?',
        str(pm_sp) if pm_sp else '?',
        str(pm_tot) if pm_tot else '?', ou,
        ('%+.1f/%+.1f %s' % (g137, g15, flag))))
    if ml_exec:
        print('        ML exec bid/ask=%s (outcomes=%s)' % (ml_exec, ml_out))
