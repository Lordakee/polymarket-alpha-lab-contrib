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

disc = json.load(open('/home/ubuntu/paper-sim/round5/raw/discover1.json'))

# ETH weekly scan — any event mentioning Ethereum + Oct 19-25 window
print('--- ETH events ending 2026-10-19..26 ---')
eth_week_slugs = []
for e in disc.get('eth_tag', []):
    ed = (e.get('endDate') or '')[:10]
    t = (e.get('title') or '')
    if '2026-10-19' <= ed <= '2026-10-26':
        print('%-60s end=%s n=%d' % ((e.get('slug') or '')[:60], ed, len(e.get('markets', []))))
        eth_week_slugs.append(e.get('slug'))

# NBA tag events Oct 19-25
print('--- NBA tag events ---')
for e in disc.get('nba_tag', []):
    ed = (e.get('endDate') or '')[:16]
    print('%-58s end=%s n=%2d vol24=%s' % ((e.get('slug') or '')[:58], ed, len(e.get('markets', [])), e.get('volume24hr')))

slugs = {
    'spy_touch_oct': 'what-price-will-spy-hit-in-october-2026',
    'spy_week': 'what-price-will-spy-hit-week-of-october-19-2026',
}
ufc = ['ufc-ale14-mov-2026-10-24', 'ufc-mer-pet-2026-10-24', 'ufc-ale22-riz-2026-10-24',
       'ufc-abu2-cam7-2026-10-24', 'ufc-col12-asacho-2026-10-24', 'ufc-ram10-lon-2026-10-24',
       'ufc-aza-dom-2026-10-24', 'ufc-aar8-los-2026-10-24', 'ufc-gra-nur-2026-10-24',
       'ufc-nik2-abd8-2026-10-24', 'ufc-avagae-jac7-2026-10-24']
for s in ufc:
    slugs['ufc_' + s] = s
for s in eth_week_slugs:
    if s and 'best-performing' not in s:
        slugs['ethw_' + s] = s

out = json.load(open('/home/ubuntu/paper-sim/round5/raw/secondary_detail2.json'))
for name, slug in slugs.items():
    if name in out: continue
    try:
        ev = get(BASE + '/events?slug=' + urllib.parse.quote(slug))
        if ev:
            out[name] = {'slug': slug, 'event': ev[0]}
            print('OK ', name, (ev[0].get('title') or '')[:60])
        else:
            print('EMPTY ', name)
    except Exception as e:
        print('ERR', name, e)
    time.sleep(0.4)
json.dump(out, open('/home/ubuntu/paper-sim/round5/raw/secondary_detail3.json', 'w'))
print('saved', len(out))

def toks(m):
    ids = m.get('clobTokenIds'); outs = m.get('outcomes')
    if not ids or not outs: return None
    try:
        ids = json.loads(ids) if isinstance(ids, str) else ids
        outs = json.loads(outs) if isinstance(outs, str) else outs
    except: return None
    return list(zip(outs, ids))

sel = []
for name, d in out.items():
    e = d['event']
    for m in e.get('markets', []):
        if m.get('closed'): continue
        git = (m.get('groupItemTitle') or '').strip().lower()
        q = ((m.get('question') or '') + ' | ' + git).strip()[:120]
        t = toks(m)
        if not t: continue
        keep = False
        if name.startswith('ucl_'):
            if git in ('o/u 1.5', 'o/u 2.5', 'o/u 3.5'):
                keep = True
        elif name.startswith('ufc_'):
            keep = True  # all markets: win/method/etc
        elif name.startswith(('spy_', 'ethw_')):
            keep = True
        if keep:
            for side, tid in t:
                sel.append({'event': name, 'slug': d['slug'], 'q': q, 'id': m.get('id'),
                            'side': side, 'token': tid, 'liq': m.get('liquidityNum'),
                            'desc': (m.get('description') or '')[:1700]})
json.dump(sel, open('/home/ubuntu/paper-sim/round5/raw/secondary_sel3.json', 'w'), indent=1)
print('selected tokens:', len(sel))

def book(tid):
    url = 'https://clob.polymarket.com/book?token_id=' + tid
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36',
        'Accept': 'application/json'})
    for i in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.load(r)
        except Exception as ex:
            if i == 2: return {'err': str(ex)}
            time.sleep(1.5)

books = json.load(open('/home/ubuntu/paper-sim/round5/raw/secondary_books2.json'))
have = set(books.keys())
for s in sel:
    if s['token'] in have: continue
    b = book(s['token'])
    books[s['token']] = {'meta': {k: s[k] for k in ('event', 'q', 'side', 'id', 'slug')}, 'book': b, 'desc': s['desc']}
    time.sleep(0.22)
json.dump(books, open('/home/ubuntu/paper-sim/round5/raw/secondary_books3.json', 'w'))
okc = sum(1 for b in books.values() if 'err' not in b['book'])
print('books total', okc, '/', len(books))
