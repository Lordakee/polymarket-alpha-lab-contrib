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

# 1. UCL MD3 more-markets events (big + modelable candidates)
ucl_slugs = ['ucl-psg-fcb-2026-10-20-more-markets', 'ucl-stu-atm-2026-10-20-more-markets',
             'ucl-bay-ars-2026-10-21-more-markets', 'ucl-rom-sba-2026-10-20-more-markets',
             'ucl-mnc-aek1-2026-10-20-more-markets', 'ucl-por-psv-2026-10-20-more-markets',
             'ucl-bru-rcl-2026-10-21-more-markets', 'ucl-com-mnu-2026-10-21-more-markets',
             'ucl-sf-bvb-2026-10-20-more-markets', 'ucl-liv-vil-2026-10-20-more-markets',
             'ucl-fen-slp-2026-10-20-more-markets', 'ucl-spo-lin2-2026-10-21-more-markets',
             'ucl-rma-rbl-2026-10-21-more-markets']
# 2. UFC 333
ufc_slugs = ['ufc-333-volkanovski-vs-evloev', 'ufc-333-merab-dvalishvili-vs-petr-yan',
             'ufc-333-pico-vs-keita']
# 3. SPY October + ETH week Oct 19-25
other_slugs = ['what-will-s-p-500-spy-hit-in-october-2026',
               'what-price-will-ethereum-hit-october-19-25-2026',
               'what-price-will-ethereum-hit-week-of-october-19-2026',
               'ethereum-week-of-october-19-25']
allslugs = {}
for s in ucl_slugs: allslugs['ucl_' + s] = s
for s in ufc_slugs: allslugs['ufc_' + s] = s
for i, s in enumerate(other_slugs): allslugs['other%d' % i] = s

out = {}
for name, slug in allslugs.items():
    try:
        ev = get(BASE + '/events?slug=' + urllib.parse.quote(slug))
        if ev:
            out[name] = {'slug': slug, 'event': ev[0]}
            print('OK ', name, (ev[0].get('title') or '')[:60], flush=True)
        else:
            print('EMPTY ', name, flush=True)
    except Exception as e:
        print('ERR', name, e, flush=True)
    time.sleep(0.4)
json.dump(out, open('/home/ubuntu/paper-sim/round5/raw/secondary_detail.json', 'w'))
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
    print('==', name, (e.get('title') or '')[:70])
    for m in e.get('markets', []):
        if m.get('closed'): continue
        q = (m.get('question') or '') + ' ' + (m.get('groupItemTitle') or '')
        t = toks(m)
        if not t: continue
        keep = False
        if name.startswith('ucl_'):
            ql = q.lower()
            if ('o/u 2.5' in ql or 'o/u 1.5' in ql or 'o/u 3.5' in ql) and ('1st half' not in ql and '2nd half' not in ql and ql.count('o/u') == 1):
                # match-total only (no team name in the tail)
                tail = q.split(':')[-1].strip().lower()
                if tail.startswith('o/u'): keep = True
        else:
            keep = True  # ufc/other: keep all for inspection
        if keep:
            for side, tid in t:
                sel.append({'event': name, 'slug': d['slug'], 'q': q.strip()[:110],
                            'id': m.get('id'), 'side': side, 'token': tid,
                            'liq': m.get('liquidityNum'),
                            'desc': (m.get('description') or '')[:1500]})
json.dump(sel, open('/home/ubuntu/paper-sim/round5/raw/secondary_sel.json', 'w'), indent=1)
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
    time.sleep(0.25)
json.dump(books, open('/home/ubuntu/paper-sim/round5/raw/secondary_books.json', 'w'))
okc = sum(1 for b in books.values() if 'err' not in b['book'])
print('books fetched', okc, '/', len(books))
for tid, b in books.items():
    m = b['meta']; bb = b['book']
    if 'err' in bb:
        print('ERR', m['event'], m['q'][:40]); continue
    bids = sorted(bb.get('bids', []), key=lambda l: -float(l['price']))
    asks = sorted(bb.get('asks', []), key=lambda l: float(l['price']))
    b1 = '%s*%d' % (bids[0]['price'], float(bids[0]['size'])) if bids else '-'
    a1 = '%s*%d' % (asks[0]['price'], float(asks[0]['size'])) if asks else '-'
    print('%-30s %-4s %-55s B[%s] A[%s]' % (m['event'][:30], m['side'][:4], m['q'][:55], b1, a1))
