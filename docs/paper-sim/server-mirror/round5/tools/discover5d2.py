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

sweeps = {
 'epl':  {'tag_slug':'epl','closed':'false','order':'volume24hr','ascending':'false','end_date_min':'2026-10-17T00:00:00Z','end_date_max':'2026-10-20T23:59:59Z'},
 'epl2': {'tag_slug':'premier-league','closed':'false','order':'volume24hr','ascending':'false','end_date_min':'2026-10-17T00:00:00Z','end_date_max':'2026-10-20T23:59:59Z'},
 'serie':{'tag_slug':'serie-a','closed':'false','order':'volume24hr','ascending':'false','end_date_min':'2026-10-17T00:00:00Z','end_date_max':'2026-10-20T23:59:59Z'},
 'l1':   {'tag_slug':'ligue-1','closed':'false','order':'volume24hr','ascending':'false','end_date_min':'2026-10-17T00:00:00Z','end_date_max':'2026-10-20T23:59:59Z'},
}
res = {}
for name, p in sweeps.items():
    try:
        res[name] = events(p)
        print(name, len(res[name]), flush=True)
    except Exception as e:
        print(name, 'ERR', e, flush=True)
    time.sleep(0.4)

TARGETS = {
 'BOU-SUN': ('Bournemouth','Sunderland'),
 'MIL-ATA': ('Milan','Atalanta'),
 'LEE-MUN': ('Leeds','Manchester United'),
 'NFO-ARS': ('Nottingham','Arsenal'),
 'BHA-CRY': ('Brighton','Crystal Palace'),
 'JUV-LAZ': ('Juventus','Lazio'),
 'ANG-OM':  ('Angers','Marseille'),
}
out = {}
for tag,(h,a) in TARGETS.items():
    for name, evs in res.items():
        for ev in evs:
            t = (ev.get('title') or '')
            if h.lower() in t.lower() and a.lower() in t.lower() and ' vs' in t:
                mk = []
                for m in ev.get('markets', []):
                    toks = m.get('clobTokenIds')
                    if isinstance(toks, str): toks = json.loads(toks)
                    outs = m.get('outcomes')
                    if isinstance(outs, str): outs = json.loads(outs)
                    mk.append({'id': m.get('id'), 'q': m.get('question'), 'slug': m.get('slug'),
                               'outcomes': outs, 'tokens': toks, 'liq': m.get('liquidityNum'),
                               'vol24': m.get('volume24hr'), 'closed': m.get('closed'), 'active': m.get('active')})
                out[tag] = {'title': t, 'slug': ev.get('slug'), 'start': ev.get('startDate'), 'markets': mk}
                print('==', tag, t, 'start=', ev.get('startDate'), 'n=', len(mk), flush=True)
                break
        if tag in out: break

for tag, ev in out.items():
    print('--', tag, ev['title'])
    for m in ev['markets']:
        print('   %-9s %s' % (m['id'], (m['q'] or '')[:95]))
json.dump(out, open('/home/ubuntu/paper-sim/round5/raw/discover5d2.json','w'), indent=1)
print('saved', len(out), 'events')
