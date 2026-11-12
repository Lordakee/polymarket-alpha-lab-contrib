"""Round-23 EPL Understat xG refresh (early-entry scan, Thu Oct 29).

Prior base round18/raw/xg_understat_18.json is La_liga-only and EPL data there was
through Oct 23. This refresh pulls current EPL season (2026 = 2026-27) plus prior
season (2025) for the blend, capturing Oct 24-26 results:
ARS 2-0 EVE, AVL 2-1 MCI, CHE 0-2 TOT, HUL 1-1 BRE, MUN 0-3 BOU, SUN 0-0 LEE,
CP 0-2 NEW, LIV 2-0 BHA, COV 0-1 FUL.
Output: /home/ubuntu/paper-sim/round23/raw/xg_epl_23.json
"""
import json, urllib.request, gzip, time

LEAGUE = 'EPL'
SEASONS = ['2025', '2026']
OUT = '/home/ubuntu/paper-sim/round23/raw/xg_epl_23.json'

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
for se in SEASONS:
    key = '%s_%s' % (LEAGUE, se)
    for attempt in range(4):
        try:
            d = get('https://understat.com/getLeagueData/%s/%s' % (LEAGUE, se),
                    'https://understat.com/league/%s/%s' % (LEAGUE, se))
            out[key] = d
            teams = d.get('teams', {})
            played = [m for m in d.get('dates', []) if m.get('isResult')]
            last = max((m['datetime'] for m in played), default='?')
            print('OK', key, 'teams=%d recorded_matches=%d last_played=%s' % (len(teams), len(played), last))
            # show the newest few results to verify Oct 24-26 capture
            newest = sorted(played, key=lambda m: m['datetime'])[-9:]
            tmap = {tid: t['title'] for tid, t in teams.items()}
            for m in newest:
                print('   %s  %s %s-%s %s' % (m['datetime'][:10], tmap.get(m['h']), m['goals']['h'], m['goals']['a'], tmap.get(m['a'])))
            break
        except Exception as e:
            print('ERR attempt', attempt + 1, key, repr(e))
            time.sleep(3 + 2 * attempt)
    time.sleep(1.2)

json.dump(out, open(OUT, 'w'))
print('saved', OUT, 'keys=', sorted(out.keys()))
