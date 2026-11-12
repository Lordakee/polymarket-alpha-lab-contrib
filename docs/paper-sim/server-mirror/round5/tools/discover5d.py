import json, urllib.request, urllib.parse, time

def get(url, tries=3, timeout=25):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36',
                'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except Exception:
            if i == tries - 1: raise
            time.sleep(1.5)

FIXTURES = [
    ('BOU-SUN', 'Bournemouth', 'Sunderland'),
    ('MIL-ATA', 'AC Milan', 'Atalanta'),
    ('LEE-MUN', 'Leeds', 'Manchester United'),
    ('NFO-ARS', 'Nottingham Forest', 'Arsenal'),
    ('BHA-CRY', 'Brighton', 'Crystal Palace'),
    ('JUV-LAZ', 'Juventus', 'Lazio'),
    ('ANG-OM',  'Angers', 'Marseille'),
]

out = {}
for tag, h, a in FIXTURES:
    q = urllib.parse.quote('%s vs %s' % (h, a))
    try:
        evs = get('https://gamma-api.polymarket.com/events?search=%s&limit=10' % q)
    except Exception as e:
        print(tag, 'search err', repr(e)); continue
    picked = None
    for ev in evs:
        gs = ev.get('startDate') or ''
        if '2026-10-1' in gs or '2026-10-2' in gs or ev.get('closed'):
            picked = ev; break
    if picked is None and evs: picked = evs[0]
    if picked is None:
        print(tag, 'NO EVENT'); continue
    mk = []
    for m in picked.get('markets', []):
        toks = m.get('clobTokenIds')
        if isinstance(toks, str): toks = json.loads(toks)
        outs = m.get('outcomes')
        if isinstance(outs, str): outs = json.loads(outs)
        mk.append({'id': m.get('id'), 'q': m.get('question'), 'slug': m.get('slug'),
                   'outcomes': outs, 'tokens': toks, 'liq': m.get('liquidityNum'),
                   'closed': m.get('closed'), 'active': m.get('active')})
    out[tag] = {'title': picked.get('title'), 'slug': picked.get('slug'),
                'start': picked.get('startDate'), 'markets': mk}
    print('==', tag, picked.get('title'), picked.get('startDate'), 'n_markets=', len(mk))
    for m in mk:
        print('   ', m['id'], (m['q'] or '')[:80])
    time.sleep(0.4)

json.dump(out, open('/home/ubuntu/paper-sim/round5/raw/discover5d.json','w'), indent=1)
print('saved discover5d.json')
