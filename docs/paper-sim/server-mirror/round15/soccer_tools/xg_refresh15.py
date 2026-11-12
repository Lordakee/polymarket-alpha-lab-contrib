"""Round-15 Understat xG refresh: capture Fri Oct-23 games (IPS-FOR, ALA-MAL, etc.).

Prior refresh (round13) had data through Oct 19; this one should include Oct 23
Friday fixtures. Output: round15/raw/xg_understat_15.json
"""
import json, urllib.request, gzip, time

LEAGUES = ['EPL','La_liga','Serie_A','Bundesliga','Ligue_1']
SEASONS = ['2025','2026']
OUT = '/home/ubuntu/paper-sim/round15/raw/xg_understat_15.json'

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

out = {}
for lg in LEAGUES:
    for se in SEASONS:
        try:
            d = get('https://understat.com/getLeagueData/%s/%s' % (lg, se),
                    'https://understat.com/league/%s/%s' % (lg, se))
            out['%s_%s' % (lg, se)] = d
            teams = d.get('teams', {})
            played = [m for m in d['dates'] if m.get('isResult')]
            last = max((m['datetime'] for m in played), default='?')
            print('OK', lg, se, 'teams=%d recorded_matches=%d last_played=%s' % (len(teams), len(played), last))
        except Exception as e:
            print('ERR', lg, se, repr(e))
        time.sleep(1.0)

json.dump(out, open(OUT, 'w'))
print('saved', OUT, 'keys=', sorted(out.keys()))
