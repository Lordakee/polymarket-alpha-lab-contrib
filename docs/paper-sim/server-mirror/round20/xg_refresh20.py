"""Round-20 Serie A sub-scan xG refresh: adds Sun Oct-25 Serie A round + Mon Oct-26
(Sevilla-Osasuna La Liga, PSG-Lyon Ligue 1). Prior base r15 file ended Oct-24."""
import json, urllib.request, gzip, time

LEAGUES = ['Serie_A','Ligue_1','La_liga']
SEASONS = ['2025','2026']
OUT = '/home/ubuntu/paper-sim/round20/raw/xg_understat_20.json'

def get(url, referer):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': referer,
        'Accept-Encoding': 'gzip'})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
        if r.headers.get('Content-Encoding') == 'gzip':
            data = gzip.decompress(data)
        return json.loads(data.decode())

# seed with r15 EPL/Bundesliga (unchanged leagues, avoid refetch)
seed = json.load(open('/home/ubuntu/paper-sim/round15/raw/xg_understat_15.json'))
out = {k: seed[k] for k in seed if k.startswith('EPL') or k.startswith('Bundesliga')}
print('seeded EPL/Bundesliga from r15 file')

for lg in LEAGUES:
    for se in SEASONS:
        try:
            d = get('https://understat.com/getLeagueData/%s/%s' % (lg, se),
                    'https://understat.com/league/%s/%s' % (lg, se))
            out['%s_%s' % (lg, se)] = d
            teams = d.get('teams', {})
            played = [m for m in d['dates'] if m.get('isResult')]
            last = max((m['datetime'] for m in played), default='?')
            print('OK', lg, se, 'teams=%d recorded=%d last=%s' % (len(teams), len(played), last))
        except Exception as e:
            print('ERR', lg, se, repr(e))
        time.sleep(1.2)

json.dump(out, open(OUT, 'w'))
print('saved', OUT)
