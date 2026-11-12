"""Round-18 Understat xG refresh: must include Sun Oct-25 La Liga results
(Sociedad 2-1 Levante, Celta 0-0 Betis, Athletic 4-0 Getafe, Barca 1-2 RM)."""
import json, urllib.request, gzip, time
LEAGUES = ['La_liga']  # only La Liga modelable this window (Liga 2 not on Understat)
SEASONS = ['2025', '2026']
OUT = '/home/ubuntu/paper-sim/round18/raw/xg_understat_18.json'
def get(url, referer):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest', 'Referer': referer, 'Accept-Encoding': 'gzip'})
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
            played = [m for m in d['dates'] if m.get('isResult')]
            last = max((m['datetime'] for m in played), default='?')
            print('OK', lg, se, 'teams=%d recorded=%d last_played=%s' % (len(d.get('teams', {})), len(played), last))
        except Exception as e:
            print('ERR', lg, se, repr(e))
        time.sleep(1.0)
json.dump(out, open(OUT, 'w'))
print('saved', OUT)
