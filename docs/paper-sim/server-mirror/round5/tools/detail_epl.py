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

slugs = {}
for base in ['epl-eve-che-2026-10-17', 'epl-mac-ips-2026-10-17', 'epl-bre-liv-2026-10-17',
             'epl-ful-hul-2026-10-17', 'epl-new-ast-2026-10-17', 'epl-bri-cry-2026-10-18',
             'epl-bou-sun-2026-10-18', 'epl-lee-mun-2026-10-18', 'epl-not-ars-2026-10-18',
             'epl-tot-cov-2026-10-19']:
    slugs[base] = base
    slugs[base + '_mm'] = base + '-more-markets'

out = {}
for name, slug in slugs.items():
    try:
        ev = get(BASE + '/events?slug=' + urllib.parse.quote(slug))
        if ev:
            out[name] = {'slug': slug, 'event': ev[0]}
            print('OK ', name, flush=True)
        else:
            print('EMPTY ', name, flush=True)
    except Exception as e:
        print('ERR', name, e, flush=True)
    time.sleep(0.5)

json.dump(out, open('/home/ubuntu/paper-sim/round5/raw/epl_detail.json', 'w'))
print('saved', len(out))

# extract O/U 2.5 (and 1.5/3.5 for context) markets
sel = []
for name, d in out.items():
    e = d['event']
    for m in e.get('markets', []):
        if m.get('closed'): continue
        q = (m.get('question') or '') + ' ' + (m.get('groupItemTitle') or '')
        if ('O/U 2.5' in q or 'Over/Under 2.5' in q or 'O/U 1.5' in q or 'O/U 3.5' in q
                or ('total goals' in q.lower() and '2.5' in q)):
            ids = m.get('clobTokenIds'); outs = m.get('outcomes')
            try:
                ids = json.loads(ids) if isinstance(ids, str) else ids
                outs = json.loads(outs) if isinstance(outs, str) else outs
            except Exception:
                continue
            if not ids or not outs: continue
            for side, tid in zip(outs, ids):
                sel.append({'event': name, 'slug': d['slug'], 'q': q.strip()[:100],
                            'id': m.get('id'), 'side': side, 'token': tid,
                            'liq': m.get('liquidityNum'),
                            'desc': (m.get('description') or '')})
json.dump(sel, open('/home/ubuntu/paper-sim/round5/raw/epl_ou_sel.json', 'w'), indent=1)
print('OU tokens selected:', len(sel))
for s in sel:
    print('%-24s %-4s %-28s liq=%s' % (s['event'], s['side'], s['q'][:28], s['liq']))
