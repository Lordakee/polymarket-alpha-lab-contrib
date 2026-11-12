"""Round-27 xG refresh: Understat fetch incl. Sunday Nov-1 results.
Paper-only research data fetch. Writes round27/raw/xg_understat_27.json."""
import json, urllib.request, gzip, time

LEAGUES = ['EPL', 'La_liga', 'Serie_A', 'Bundesliga', 'Ligue_1']
SEASONS = ['2025', '2026']
OUT = '/home/ubuntu/paper-sim/round27/raw/xg_understat_27.json'

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

snap = {}
for lg in LEAGUES:
    for se in SEASONS:
        url = 'https://understat.com/getLeagueData/' + lg + '/' + se
        ref = 'https://understat.com/league/' + lg + '/' + se
        for attempt in range(4):
            try:
                d = get(url, ref)
                snap[lg + '_' + se] = d
                teams = d.get('teams', {})
                n_hist = sum(len(t.get('history', [])) for t in teams.values())
                last = max((h['date'] for t in teams.values() for h in t.get('history', [])), default=None)
                print('OK', lg, se, 'teams=', len(teams), 'matches_recorded=', n_hist // 2, 'last=', last, flush=True)
                break
            except Exception as e:
                print('ERR attempt', attempt, lg, se, repr(e), flush=True)
                time.sleep(3.0 + 2 * attempt)
        else:
            raise SystemExit('FAILED ' + lg + '_' + se)
        time.sleep(1.0)

with open(OUT, 'w') as f:
    json.dump(snap, f)
print('saved', OUT)
