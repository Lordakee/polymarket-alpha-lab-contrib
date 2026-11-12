"""Round-23 Ligue 1 sub-scan xG refresh: Understat Ligue_1 2025 (2025/26) + 2026 (2026/27)."""
import json, urllib.request, gzip, time

OUT = '/home/ubuntu/paper-sim/round23/raw/xg_understat_ligue_23.json'
LEAGUES = ['Ligue_1']
SEASONS = ['2025', '2026']

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

out = {}
for lg in LEAGUES:
    for se in SEASONS:
        url = 'https://understat.com/getLeagueData/' + lg + '/' + se
        ref = 'https://understat.com/league/' + lg + '/' + se
        for attempt in range(4):
            try:
                d = get(url, ref)
                out['%s_%s' % (lg, se)] = d
                teams = d.get('teams', {})
                n_hist = sum(len(t.get('history', [])) for t in teams.values())
                print('OK', lg, se, 'teams=', len(teams), 'matches_recorded=', n_hist // 2)
                break
            except Exception as e:
                print('ERR attempt', attempt + 1, lg, se, repr(e)); time.sleep(3 + attempt * 3)
        time.sleep(1.2)

json.dump(out, open(OUT, 'w'))
print('saved', OUT)

d = out['Ligue_1_2026']
teams = d['teams']
dates = sorted(m['datetime'] for m in d['dates'] if m.get('isResult'))
print()
print('Ligue_1 2026/27 last 12 recorded matches:')
for m in sorted([m for m in d['dates'] if m.get('isResult')], key=lambda m: m['datetime'])[-12:]:
    print('  %s  %s %s-%s %s  xG %s-%s' % (m['datetime'][:16], m['h']['title'], m['goals']['h'], m['goals']['a'], m['a']['title'], m['xG']['h'], m['xG']['a']))
print()
print('Teams:', sorted(t['title'] for t in teams.values()))
print()
print('Per-team summary (2026/27):')
for t in sorted(teams.values(), key=lambda t: t['title']):
    h = t['history']
    if not h:
        print('  %-28s NO MATCHES YET' % t['title']); continue
    xg_for = sum(float(x['xG']) for x in h); xg_ag = sum(float(x['xGA']) for x in h); n = len(h)
    last5 = h[-5:]
    print('  %-28s n=%2d xG/g=%5.2f xGA/g=%5.2f pts=%3d | last5 xG/g=%5.2f xGA/g=%5.2f' % (
        t['title'], n, xg_for / n, xg_ag / n, sum(int(x['pts']) for x in h),
        sum(float(x['xG']) for x in last5) / 5, sum(float(x['xGA']) for x in last5) / 5))
