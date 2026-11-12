import json, urllib.request, time

# ESPN pickcenter: EPL Oct 17-19 + NBA Oct 20-21 season-openers check
URLS = {
    'epl_1017': 'https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard?dates=20261017',
    'epl_1018': 'https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard?dates=20261018',
    'epl_1019': 'https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard?dates=20261019',
    'nba_1020': 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=20261020',
    'nba_1021': 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=20261021',
}

def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

out = {}
for name, url in URLS.items():
    try:
        d = get(url)
        out[name] = d
        evs = d.get('events', [])
        print('==', name, len(evs), 'events', flush=True)
        for e in evs:
            for c in e.get('competitions', []):
                for o in c.get('odds', []):
                    prov = (o.get('provider') or {}).get('name')
                    print('  %-45s %s O/U line=%s O=%s U=%s ML=%s/%s status=%s' % (
                        e.get('shortName'), prov, o.get('overUnder'),
                        o.get('overOdds', {}).get('moneyLine') if isinstance(o.get('overOdds'), dict) else o.get('overOdds'),
                        o.get('underOdds', {}).get('moneyLine') if isinstance(o.get('underOdds'), dict) else o.get('underOdds'),
                        (o.get('awayTeamOdds') or {}).get('moneyLine'),
                        (o.get('homeTeamOdds') or {}).get('moneyLine'),
                        e.get('status', {}).get('type', {}).get('state')))
    except Exception as ex:
        print(name, 'ERR', repr(ex), flush=True)
    time.sleep(0.5)

json.dump(out, open('/home/ubuntu/paper-sim/round5/raw/espn.json', 'w'))
print('saved espn.json')
