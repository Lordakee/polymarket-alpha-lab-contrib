import json, urllib.request, time, datetime

FX = json.load(open('/home/ubuntu/paper-sim/round2/raw/fixtures.json'))
CLOB = 'https://clob.polymarket.com'

def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'research/0.1'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

now = datetime.datetime.now(datetime.timezone.utc)
print('UTC now:', now.isoformat())

TARGETS = [
    ('sea-tor-udi-2026-10-12', 'Torino-Udinese'),
    ('lal-lev-sev-2026-10-12', 'Levante-Sevilla'),
    ('bun-s04-mai-2026-10-17', 'Schalke-Mainz (rejected-check)'),
]

out = {}
for slug, label in TARGETS:
    fx = FX[slug]
    # main 1X2 markets + more-markets O/U 2.5 + BTTS
    picks = []
    for m in fx['family'].get(slug, {}).get('markets', []):
        picks.append(('MAIN', m))
    for m in fx['family'].get(slug + '-more-markets', {}).get('markets', []):
        g = str(m['group'] or '')
        if g in ('O/U 2.5', 'Both Teams to Score') or g.startswith('O/U 3.5') or g.startswith('O/U 1.5'):
            picks.append(('MORE', m))
    print()
    print('=== %s (%s) kickoff %s' % (label, slug, fx['game_start']))
    for kind, m in picks:
        toks = m['tokens']
        try:
            toks = json.loads(toks) if isinstance(toks, str) else toks
        except Exception:
            pass
        if not toks:
            continue
        oc = m['outcomes'] or []
        row = {'q': m['q'], 'outcomes': oc, 'gamma_bid': m['bestBid'], 'gamma_ask': m['bestAsk'],
               'tokens': toks, 'books': []}
        for tok in toks:
            try:
                b = get(CLOB + '/book?token_id=' + tok)
                bids = sorted(b.get('bids', []), key=lambda x: -float(x['price']))[:4]
                asks = sorted(b.get('asks', []), key=lambda x: float(x['price']))[:4]
                row['books'].append({'bids': bids, 'asks': asks})
            except Exception as e:
                row['books'].append({'err': str(e)})
            time.sleep(0.25)
        out['%s|%s' % (slug, m['id'])] = row
        b0 = row['books'][0]
        bb = b0['bids'][0]['price'] + ' x' + str(b0['bids'][0]['size']) if b0.get('bids') else '-'
        ba = b0['asks'][0]['price'] + ' x' + str(b0['asks'][0]['size']) if b0.get('asks') else '-'
        print('  %-4s %-58s out0=%-6s bid=%-22s ask=%s' % (kind, str(m['group'] or m['q'])[:58], oc[0] if oc else '?', bb, ba))
        if b0.get('bids'):
            print('       bid depth:', [(x['price'], x['size']) for x in b0['bids']])
        if b0.get('asks'):
            print('       ask depth:', [(x['price'], x['size']) for x in b0['asks']])

json.dump(out, open('/home/ubuntu/paper-sim/round2/raw/final_books.json', 'w'), indent=1)
print()
print('saved final_books.json')
