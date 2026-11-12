"""Round-23: rebuild full ESPN/DK odds table (safe version)."""
import json, time, urllib.request

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
        odds_list = comp.get('odds') or []
        o = (odds_list[0] if odds_list else {}) or {}
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
for r in rows:
    print('%-6s %s %-32s vs %-22s det=%-14s draw=%-5s ou=%-4s o=%-6s u=%-6s' % (
        r['league'], str(r['date'])[:10], str(r['home'])[:32], str(r['away'])[:22],
        r['details'], r['draw_ml'], r['ou_line'], r['over_odds'], r['under_odds']))
