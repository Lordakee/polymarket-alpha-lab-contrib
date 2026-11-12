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

# --- step 1: find correct slugs for UFC 333, SPY Oct, ETH weekly Oct 19-25 ---
# scan discover1 eth_tag sweep + ufc/spy guesses via public search endpoint
disc = json.load(open('/home/ubuntu/paper-sim/round5/raw/discover1.json'))
found = {'eth_week': [], 'eth_oct': [], 'spy': []}
for e in disc.get('eth_tag', []):
    t = (e.get('title') or '').lower()
    sl = e.get('slug') or ''
    if 'week of october 19' in t or 'october 19-25' in t or 'october-19-25' in sl or 'week-of-october-19' in sl:
        found['eth_week'].append((e.get('title'), sl, e.get('endDate'), len(e.get('markets', []))))
    if 'ethereum' in t and 'october 2026' in t and 'week' not in t:
        found['eth_oct'].append((e.get('title'), sl, e.get('endDate'), len(e.get('markets', []))))
for e in disc.get('spy_search', []):
    t = (e.get('title') or '')
    if 'SPY' in t and 'October' in t and 'Week' not in t:
        found['spy'].append((t, e.get('slug'), e.get('endDate'), len(e.get('markets', []))))
print('ETH week:', found['eth_week'])
print('ETH oct:', found['eth_oct'])
print('SPY oct:', found['spy'])

# UFC: try public search endpoint
try:
    ps = get(BASE + '/public-search?q=' + urllib.parse.quote('UFC 333') + '&limit_per_type=20')
    evs = ps.get('events', []) if isinstance(ps, dict) else []
    print('UFC public-search events:', [(e.get('title'), e.get('slug')) for e in evs][:20])
except Exception as ex:
    print('public-search ERR', repr(ex))

slugs = {}
for t, sl, ed, n in found['eth_week']:
    slugs['eth_week_' + sl] = sl
for t, sl, ed, n in found['spy']:
    slugs['spy_oct'] = sl
# round-4 slug map fallback
try:
    sm = json.load(open('/home/ubuntu/paper-sim/round4/raw/slug_map.json'))
    for k, v in sm.items():
        lk = k.lower()
        if 'ufc' in lk:
            slugs['r4_' + k] = v
except Exception as ex:
    print('slug_map read err', ex)

out = {}
for name, slug in slugs.items():
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

# keep prior UCL detail
sec = json.load(open('/home/ubuntu/paper-sim/round5/raw/secondary_detail.json'))
for k, v in sec.items():
    if k.startswith('ucl_'):
        out[k] = v
json.dump(out, open('/home/ubuntu/paper-sim/round5/raw/secondary_detail2.json', 'w'))
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
            # match-total O/U only: groupItemTitle is exactly "O/U X.5"
            if git in ('o/u 1.5', 'o/u 2.5', 'o/u 3.5'):
                keep = True
        elif name.startswith('eth_week'):
            keep = True  # all markets in weekly event
        elif name.startswith('spy_oct'):
            keep = True  # all rungs
        else:
            keep = True  # UFC all markets
        if keep:
            for side, tid in t:
                sel.append({'event': name, 'slug': d['slug'], 'q': q, 'id': m.get('id'),
                            'side': side, 'token': tid, 'liq': m.get('liquidityNum'),
                            'desc': (m.get('description') or '')[:1600]})
json.dump(sel, open('/home/ubuntu/paper-sim/round5/raw/secondary_sel2.json', 'w'), indent=1)
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

books = {}
for s in sel:
    b = book(s['token'])
    books[s['token']] = {'meta': {k: s[k] for k in ('event', 'q', 'side', 'id', 'slug')}, 'book': b, 'desc': s['desc']}
    time.sleep(0.22)
json.dump(books, open('/home/ubuntu/paper-sim/round5/raw/secondary_books2.json', 'w'))
okc = sum(1 for b in books.values() if 'err' not in b['book'])
print('books fetched', okc, '/', len(books))
