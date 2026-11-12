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

# first: what slugs did we find? try direct slug patterns for serie a
slugs_tried = {}
for base in ['serie-a-mil-ata-2026-10-18','serie-a-ac-milan-atalanta-2026-10-18','italy-serie-a-milan-atalanta-2026-10-18']:
    try:
        ev = get(BASE + '/events?slug=' + base)
        print('slug', base, '->', len(ev), ev[0].get('title') if ev else '')
        if ev: slugs_tried[base] = ev[0]
    except Exception as e:
        print('slug', base, 'ERR', e)
    time.sleep(0.4)

# broader: no-tag sweep with title search on soccer events ending soon
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
 'serie2': {'tag_slug':'italian-serie-a','closed':'false','order':'volume24hr','ascending':'false','end_date_min':'2026-10-17T00:00:00Z','end_date_max':'2026-10-20T23:59:59Z'},
 'serie3': {'tag_slug':'serie-a','closed':'false','order':'liquidity','ascending':'false'},
 'soccer': {'tag_slug':'soccer','closed':'false','order':'volume24hr','ascending':'false','end_date_min':'2026-10-17T00:00:00Z','end_date_max':'2026-10-20T23:59:59Z'},
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
 'MIL-ATA': ('Milan','Atalanta'),
 'JUV-LAZ': ('Juventus','Lazio'),
 'BOU-SUN': ('Bournemouth','Sunderland'),
 'NFO-ARS': ('Nottingham','Arsenal'),
 'BHA-CRY': ('Brighton','Crystal Palace'),
 'ANG-OM':  ('Angers','Marseille'),
 'LEE-MUN': ('Leeds','Manchester United'),
}
found = {}
for tag,(h,a) in TARGETS.items():
    found[tag] = []
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
                if not any(x['slug'] == ev.get('slug') for x in found[tag]):
                    found[tag].append({'title': t, 'slug': ev.get('slug'), 'start': ev.get('startDate'), 'markets': mk})
for tag, evs in found.items():
    for ev in evs:
        print('==', tag, '|', ev['title'], '| n=', len(ev['markets']))
json.dump(found, open('/home/ubuntu/paper-sim/round5/raw/discover5d3.json','w'), indent=1)
print('saved discover5d3.json')
