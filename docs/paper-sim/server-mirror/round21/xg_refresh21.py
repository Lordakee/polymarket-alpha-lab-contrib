"""Round-21 Serie A Wed sub-scan xG refresh: adds Tue Oct-27 Serie A round
(Sassuolo 2-6 Lazio, Roma 4-2 Cagliari, Torino 1-3 Como). Prior base r20 file ended Oct-26."""
import json, urllib.request, gzip, time

LEAGUES = ['Serie_A']
SEASONS = ['2025','2026']
OUT = '/home/ubuntu/paper-sim/round21/raw/xg_understat_21.json'

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

# seed all leagues from r20 file (EPL/Bundesliga/Ligue_1/La_liga unchanged)
seed = json.load(open('/home/ubuntu/paper-sim/round20/raw/xg_understat_20.json'))
out = dict(seed)
print('seeded %d leagues from r20 file' % len(seed))

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
