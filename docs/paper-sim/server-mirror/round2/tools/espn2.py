import json, urllib.request, gzip, time

def get(url):
    req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0','Accept-Encoding':'gzip'})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
        if r.headers.get('Content-Encoding') == 'gzip':
            data = gzip.decompress(data)
        return json.loads(data.decode())

# inspect full odds object for MLB/NHL games already pulled
D = json.load(open('/home/ubuntu/paper-sim/round2/raw/espn_odds.json'))
for label in ['mlb_today','nhl_today']:
    print('===', label, 'full odds objects:')
    for ev in D[label].get('events', []):
        comp = ev['competitions'][0]
        if comp.get('odds'):
            o = comp['odds'][0]
            print(' ', ev['name'][:40], json.dumps(o)[:600])
    print()

# NFL per-day
OUT = {}
for dt in ['20261012','20261013','20261015','20261016','20261017','20261018','20261019']:
    url = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=' + dt
    try:
        d = get(url)
        OUT[dt] = d
        for ev in d.get('events', []):
            comp = ev['competitions'][0]
            home = away = None
            for c in comp['competitors']:
                if c.get('home'): home = c['team']['abbreviation']
                else: away = c['team']['abbreviation']
            od = comp.get('odds', [])
            ostr = ''
            if od:
                o = od[0]
                ostr = ' prov=%s spread=%s ou=%s awml=%s hml=%s' % (
                    o.get('provider',{}).get('name'), o.get('spread'), o.get('overUnder'),
                    o.get('awayTeamOdds',{}).get('moneyLine'), o.get('homeTeamOdds',{}).get('moneyLine'))
            print('  %s: %s @ %s%s' % (ev.get('date')[:16], away, home, ostr))
    except Exception as e:
        print('ERR', dt, e)
    time.sleep(0.5)
json.dump(OUT, open('/home/ubuntu/paper-sim/round2/raw/espn_nfl.json','w'), indent=1)
print('saved espn_nfl.json')
