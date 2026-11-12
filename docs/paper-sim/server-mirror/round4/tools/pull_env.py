import json, urllib.request, time, re, ast

def fetch(url, hdrs=None):
    h = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'}
    if hdrs: h.update(hdrs)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8', 'ignore')

leagues = ['EPL', 'La_liga', 'Serie_A', 'Bundesliga', 'Ligue_1']
seasons = ['2025', '2026']
xg = {}
for lg in leagues:
    for se in seasons:
        try:
            html = fetch('https://understat.com/league/%s/%s' % (lg, se))
            m2 = re.search(r"teamsData\s*=\s*JSON\.parse\('([^']+)'\)", html)
            if m2:
                s = m2.group(1).encode('utf-16', 'surrogatepass').decode('utf-16')
                xg['%s_%s' % (lg, se)] = json.loads(s)
                print('OK understat', lg, se, len(xg['%s_%s' % (lg, se)]))
            else:
                print('NOPARSE understat', lg, se)
        except Exception as e:
            print('ERR understat', lg, se, e)
        time.sleep(0.8)
json.dump(xg, open('/home/ubuntu/paper-sim/round4/raw/xg_understat.json', 'w'))

espn = {
 'ucl_1014': 'https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.champions/scoreboard?dates=20261014',
 'epl_1017': 'https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard?dates=20261017',
 'epl_1018': 'https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard?dates=20261018',
 'epl_1019': 'https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard?dates=20261019',
 'lal_1017': 'https://site.api.espn.com/apis/site/v2/sports/soccer/esp.1/scoreboard?dates=20261017',
 'lal_1018': 'https://site.api.espn.com/apis/site/v2/sports/soccer/esp.1/scoreboard?dates=20261018',
 'sea_1017': 'https://site.api.espn.com/apis/site/v2/sports/soccer/ita.1/scoreboard?dates=20261017',
 'bun_1017': 'https://site.api.espn.com/apis/site/v2/sports/soccer/ger.1/scoreboard?dates=20261017',
 'nfl_1015': 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=20261015',
 'nfl_1016': 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=20261016',
 'nfl_1018': 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=20261018',
 'nfl_1019': 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=20261019',
 'nhl_1014': 'https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard?dates=20261014',
 'nhl_1015': 'https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard?dates=20261015',
 'mlb_1014': 'https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard?dates=20261014',
}
out = {}
for k, u in espn.items():
    try:
        out[k] = json.loads(fetch(u))
        evs = out[k].get('events', [])
        print('OK', k, len(evs), 'events')
    except Exception as e:
        print('ERR', k, e)
    time.sleep(0.6)
json.dump(out, open('/home/ubuntu/paper-sim/round4/raw/espn.json', 'w'))
