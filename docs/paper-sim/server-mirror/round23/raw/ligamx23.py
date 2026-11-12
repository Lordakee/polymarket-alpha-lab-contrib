"""Round-23: fetch Liga MX in-window event markets (generic tags) + build DK devig comparison
for non-Big-5 notables and Ligue 1 DK context."""
import json, time, urllib.request, urllib.parse
from datetime import datetime, timezone

RAW = '/home/ubuntu/paper-sim/round23/raw'

def get(url, tries=5):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.load(r)
        except Exception as e:
            last = e; time.sleep(1.5 + i)
    raise last

def norm(ts):
    s = str(ts or '').strip()
    if not s: return ''
    try:
        if s.endswith('Z'): s = s[:-1] + '+00:00'
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception:
        return s

LO = '2026-10-30T00:00:00Z'; HI = '2026-11-03T03:00:00Z'

cands = json.load(open(RAW + '/ligamx_candidates23.json'))
evs = json.load(open(RAW + '/events_window23.json'))
known = {e['id'] for e in evs}
n = 0
for c in cands:
    eid = c['id']
    if 'M15' in str(c['title']): continue
    try:
        d = get('https://gamma-api.polymarket.com/events/%s' % eid)
    except Exception as e:
        print('ERR event', eid, repr(e)); continue
    mk = []
    for m in (d.get('markets') or []):
        g = norm(m.get('gameStartTime'))
        if not g or not (LO <= g <= HI): continue
        mk.append({'id': str(m.get('id')), 'q': m.get('question'), 'slug': m.get('slug'),
                   'outcomes': m.get('outcomes'), 'prices': m.get('outcomePrices'),
                   'tokens': m.get('clobTokenIds'), 'line': m.get('line') or m.get('handicap'),
                   'gameStartTime': m.get('gameStartTime'), 'liq': m.get('liquidityNum'),
                   'vol24': m.get('volume24hr'), 'bestBid': m.get('bestBid'), 'bestAsk': m.get('bestAsk'),
                   'closed': m.get('closed'), 'active': m.get('active'), 'spread': m.get('spread'),
                   'group': m.get('groupItemTitle'), 'type': m.get('marketType')})
    if not mk:
        print('no in-window markets for', c['title']); continue
    se = {'id': str(d.get('id')), 'title': d.get('title'), 'slug': d.get('slug'),
          'startDate': d.get('startDate'), 'endDate': d.get('endDate'),
          'liq': d.get('liquidityNum'), 'vol24': d.get('volume24hr'), 'vol': d.get('volume'),
          'tags': [t.get('slug') for t in (d.get('tags') or [])], 'markets': mk, 'league_hint': 'liga-mx'}
    if eid not in known:
        evs.append(se); known.add(eid); n += 1
    print('liga-mx %-46s vol24=%9s nmk=%3d ko=%s' % (str(se['title'])[:46], se.get('vol24'), len(mk),
          min((m.get('gameStartTime') for m in mk), default='')))
    time.sleep(1.0)

json.dump(evs, open(RAW + '/events_window23.json', 'w'), indent=1)
print('added', n, 'liga-mx events; total', len(evs))

# ------- DK devig comparison -------
def am2prob(s):
    s = str(s).strip()
    if s.startswith('-'):
        v = float(s[1:]); return v / (100 + v)
    if s.startswith('+'):
        v = float(s[1:]); return 100.0 / (100 + v)
    return None

espn = json.load(open(RAW + '/espn_odds_full23.json'))
# note: espn_odds_full23.json crashed before saving; rebuild odds from espn_fixtures23.json structure is partial.
# re-fetch full odds safely now
targets = [
    ('fra.1', '20261030'), ('fra.1', '20261031'), ('fra.1', '20261101'), ('fra.1', '20261102'),
    ('ned.1', '20261031'), ('ned.1', '20261101'),
    ('por.1', '20261030'), ('por.1', '20261031'), ('por.1', '20261101'), ('por.1', '20261102'),
    ('sco.1', '20261101'), ('sco.1', '20261031'),
    ('mex.1', '20261031'), ('mex.1', '20261101'), ('mex.1', '20261102'),
    ('bra.1', '20261030'), ('bra.1', '20261031'), ('bra.1', '20261101'), ('bra.1', '20261102'),
]
rows = []
for code, day in targets:
    try:
        d = get('https://site.api.espn.com/apis/site/v2/sports/soccer/%s/scoreboard?dates=%s' % (code, day))
    except Exception as e:
        print('ERR', code, day, repr(e)); time.sleep(1.5); continue
    for ev in d.get('events', []):
        comp = ev['competitions'][0]
        o = {}
        odds_list = comp.get('odds') or []
        if odds_list: o = odds_list[0] or {}
        tot = o.get('total') or {}
        def close(side):
            c = ((tot.get(side) or {}).get('close') or {})
            return c.get('line'), c.get('odds')
        row = {'league': code, 'date': ev.get('date'), 'name': ev.get('name'),
               'home': None, 'away': None,
               'details': o.get('details'), 'provider': (o.get('provider') or {}).get('name'),
               'draw_ml': (o.get('drawOdds') or {}).get('moneyLine'),
               'ou_line': o.get('overUnder'),
               'over_odds': close('over')[1], 'over_line': close('over')[0],
               'under_odds': close('under')[1], 'under_line': close('under')[0]}
        for c in comp.get('competitors', []):
            row[c.get('homeAway')] = c['team']['displayName']
        rows.append(row)
    time.sleep(1.0)
json.dump(rows, open(RAW + '/espn_odds_full23.json', 'w'), indent=1)
print('saved espn_odds_full23.json rows=', len(rows))
