import json, urllib.request, gzip, time, os

OUT = '/home/ubuntu/paper-sim/round2/raw/xg/'
os.makedirs(OUT, exist_ok=True)
LEAGUES = ['EPL','La_liga','Serie_A','Bundesliga','Ligue_1']
SEASONS = ['2025','2026']

def get(url, referer):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': referer,
        'Accept-Encoding': 'gzip',
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
        if r.headers.get('Content-Encoding') == 'gzip':
            data = gzip.decompress(data)
        return json.loads(data.decode())

for lg in LEAGUES:
    for se in SEASONS:
        url = 'https://understat.com/getLeagueData/' + lg + '/' + se
        ref = 'https://understat.com/league/' + lg + '/' + se
        fn = OUT + '%s_%s.json' % (lg, se)
        try:
            d = get(url, ref)
            with open(fn, 'w') as f:
                json.dump(d, f)
            teams = d.get('teams', {})
            n_played = len([m for m in d.get('dates', []) if m.get('isResult')])
            print('OK', lg, se, 'teams=', len(teams), 'played_matches=', n_played)
        except Exception as e:
            print('ERR', lg, se, e)
        time.sleep(1.0)
