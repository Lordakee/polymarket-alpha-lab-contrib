import json, urllib.request, gzip, re, time

BASE = 'https://understat.com/league/'
LEAGUES = ['EPL', 'La_liga', 'Serie_A', 'Bundesliga', 'Ligue_1']
out = {}
for lg in LEAGUES:
    for se in ['2025', '2026']:
        url = BASE + lg + '/' + se
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Encoding': 'gzip',
            'Referer': 'https://understat.com/league/' + lg})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
                if r.headers.get('Content-Encoding') == 'gzip' or raw[:2] == b'\x1f\x8b':
                    raw = gzip.decompress(raw)
                html = raw.decode('utf-8', errors='replace')

            def grab2(var):
                m = re.search(r"var\s+" + var + r"\s*=\s*JSON\.parse\('(.*?)'\)", html)
                if not m:
                    return None
                s = m.group(1)
                s = s.encode('utf-8').decode('unicode_escape')
                return json.loads(s)

            teams = grab2('teamsData')
            dates = grab2('datesData')
            n_m = sum(1 for d in dates if d.get('isResult'))
            out['%s_%s' % (lg, se)] = {'teams': teams, 'dates': dates}
            print(lg, se, 'teams', len(teams), 'matches', len(dates), 'results', n_m, flush=True)
        except Exception as e:
            print(lg, se, 'ERR', repr(e), flush=True)
        time.sleep(1.2)
json.dump(out, open('/home/ubuntu/paper-sim/round5/raw/xg_understat.json', 'w'))
print('saved', len(out))
