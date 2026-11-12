"""Round-15 ESPN scoreboard sweep for Big-5 leagues, Oct 23-27 (Fri results + weekend fixtures)."""
import json, os, time, urllib.request

OUT = '/home/ubuntu/paper-sim/round15/raw/espn'
def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=25) as r: return json.load(r)
        except Exception as e:
            if i == tries - 1: return {'err': repr(e)}
            time.sleep(1.5)

LEAGUES = ['eng.1', 'esp.1', 'ita.1', 'ger.1', 'fra.1']
DATES = ['20261023', '20261024', '20261025', '20261026', '20261027']
summary = {}
for lg in LEAGUES:
    for dt in DATES:
        u = 'https://site.api.espn.com/apis/site/v2/sports/soccer/%s/scoreboard?dates=%s' % (lg, dt)
        d = get(u)
        fn = os.path.join(OUT, '%s_%s.json' % (lg, dt))
        json.dump(d, open(fn, 'w'))
        evs = d.get('events') or []
        if d.get('err'):
            print('%-16s %s ERR %s' % (lg, dt, d['err'][:60])); continue
        for e in evs:
            comp = e.get('competitions', [{}])[0]
            status = (comp.get('status') or {}).get('type') or {}
            teams = []
            inj = 0
            for c in comp.get('competitors', []):
                teams.append((c.get('team') or {}).get('displayName', '?'))
                inj += len(c.get('injuries') or [])
            try:
                odds = (comp.get('odds') or [{}])[0] or {}
            except Exception:
                odds = {}
            ou = odds.get('overUnder')
            key = '%s | %s vs %s' % (dt, teams[0] if teams else '?', teams[1] if len(teams) > 1 else '?')
            summary[key] = {'league': lg, 'date': dt, 'status': status.get('name'), 'state': status.get('state'),
                            'detail': status.get('shortDetail'), 'injuries_listed': inj, 'ou_line': ou,
                            'score': [(c.get('score')) for c in comp.get('competitors', [])],
                            'venue': (comp.get('venue') or {}).get('fullName'), 'id': e.get('id')}
            print('%-6s %s %-30s vs %-28s st=%-10s inj=%d OU=%s' % (
                lg, dt, teams[0][:30] if teams else '?', teams[1][:28] if len(teams) > 1 else '?',
                status.get('state'), inj, ou))
        time.sleep(0.3)
json.dump(summary, open(OUT + '/summary.json', 'w'), indent=1)
print('saved summary.json events=', len(summary))
