import json, urllib.request, urllib.parse, time

BASE = 'https://gamma-api.polymarket.com'

def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            if i == tries - 1: raise
            time.sleep(2)

def events(params):
    out = []; offset = 0
    while True:
        p = dict(params); p['offset'] = offset; p['limit'] = 100
        batch = get(BASE + '/events?' + urllib.parse.urlencode(p))
        out.extend(batch)
        if len(batch) < 100: return out
        offset += 100
        if offset > 1500: return out

res = {}
sweeps = {
    'ucl_nobounds': {'tag_slug': 'champions-league', 'closed': 'false', 'order': 'volume24hr', 'ascending': 'false'},
    'ucl_tag_ucl': {'tag_slug': 'ucl', 'closed': 'false', 'order': 'volume24hr', 'ascending': 'false'},
    'nba_props': {'q': 'player', 'closed': 'false', 'order': 'volume24hr', 'ascending': 'false'},
    'ufc333': {'q': 'ufc 333', 'closed': 'false', 'order': 'volume24hr', 'ascending': 'false'},
}
for name, p in sweeps.items():
    try:
        ev = events(p)
        res[name] = ev
        print(name, len(ev), flush=True)
    except Exception as e:
        print(name, 'ERR', e, flush=True)
    time.sleep(0.4)

json.dump(res, open('/home/ubuntu/paper-sim/round5/raw/discover2.json', 'w'))

summary = []
for name, evs in res.items():
    for e in evs:
        liq = 0.0
        try: liq = sum(float(m.get('liquidityNum') or 0) for m in e.get('markets', []))
        except: pass
        summary.append({'sweep': name, 'title': e.get('title'), 'slug': e.get('slug'),
                        'end': e.get('endDate'), 'vol24': e.get('volume24hr'),
                        'liq_sum': round(liq, 0), 'n_markets': len(e.get('markets', []))})
json.dump(summary, open('/home/ubuntu/paper-sim/round5/raw/discover2_summary.json', 'w'), indent=1)

# filter interesting
print('--- UCL events ending Oct 20-24 ---')
seen = set()
for s in summary:
    if s['sweep'] in ('ucl_nobounds', 'ucl_tag_ucl') and s['end'] and '2026-10-2' in s['end'][:10] and s['slug'] not in seen:
        seen.add(s['slug'])
        print('%-58s end=%s liq=%6.0f n=%d' % (s['slug'][:58], s['end'][:16], s['liq_sum'], s['n_markets']))
print('--- NBA player/near events Oct 19-25 ---')
seen = set()
for s in summary:
    if s['sweep'] == 'nba_props' and s['end'] and '2026-10-' in s['end'][:10] and s['slug'] not in seen:
        seen.add(s['slug'])
        print('%-58s end=%s liq=%6.0f n=%d' % (s['slug'][:58], s['end'][:16], s['liq_sum'], s['n_markets']))
print('--- UFC events ---')
seen = set()
for s in summary:
    if s['sweep'] == 'ufc333' and s['slug'] not in seen:
        seen.add(s['slug'])
        print('%-58s end=%s liq=%6.0f n=%d' % (s['slug'][:58], (s['end'] or '')[:16], s['liq_sum'], s['n_markets']))
