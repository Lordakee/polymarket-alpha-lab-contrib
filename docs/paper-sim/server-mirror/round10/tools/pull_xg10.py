import json, urllib.request, gzip, time

def get(url, referer):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36',
                                               'X-Requested-With': 'XMLHttpRequest', 'Referer': referer, 'Accept-Encoding': 'gzip'})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
        if r.headers.get('Content-Encoding') == 'gzip':
            data = gzip.decompress(data)
        return json.loads(data.decode())

out = {}
for lg in ['EPL', 'La_liga', 'Serie_A', 'Bundesliga', 'Ligue_1']:
    for se in ['2025', '2026']:
        try:
            d = get('https://understat.com/getLeagueData/%s/%s' % (lg, se), 'https://understat.com/league/%s/%s' % (lg, se))
            out['%s_%s' % (lg, se)] = d
            teams = d.get('teams', {})
            n = sum(len(t.get('history', [])) for t in teams.values())
            print('OK', lg, se, 'teams=', len(teams), 'matches=', n // 2, flush=True)
        except Exception as e:
            print('ERR', lg, se, repr(e), flush=True)
        time.sleep(0.8)

json.dump(out, open('/home/ubuntu/paper-sim/round10/raw/xg_understat_10.json', 'w'))
print('saved', list(out.keys()))

# name check for our fixtures
for key, want in [('Bundesliga_2026', 'Hoffenheim'), ('Ligue_1_2026', 'Lyon'), ('Serie_A_2026', None), ('EPL_2026', 'Bournemouth')]:
    if key not in out:
        continue
    names = sorted(out[key]['teams'].keys())
    if want:
        print(key, [n for n in names if want.lower() in n.lower()])
if 'Serie_A_2026' in out:
    names = sorted(out['Serie_A_2026']['teams'].keys())
    print('Serie_A:', [n for n in names if 'ilan' in n or 'Juvent' in n or 'Atalanta' in n])
if 'Ligue_1_2026' in out:
    names = sorted(out['Ligue_1_2026']['teams'].keys())
    print('Ligue_1:', [n for n in names if 'yon' in n or 'enn' in n or 'Monaco' in n])
