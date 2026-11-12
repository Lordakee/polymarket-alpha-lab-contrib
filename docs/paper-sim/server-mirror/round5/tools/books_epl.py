import json, urllib.request, time

sel = json.load(open('/home/ubuntu/paper-sim/round5/raw/epl_ou_sel.json'))

# match-total O/U only: question is "<teams>: O/U X.5 O/U X.5" — groupItemTitle == "O/U X.5"
match_total = [s for s in sel if s['q'].split(':')[-1].strip().startswith('O/U')]
print('match-total OU markets:', len(match_total))

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
descs = {}
for s in match_total:
    b = book(s['token'])
    books[s['token']] = {'meta': {k: s[k] for k in ('event', 'q', 'side', 'id', 'slug')}, 'book': b}
    descs.setdefault(s['q'].split(':')[1].strip() if ':' in s['q'] else s['q'], s['desc'])
    time.sleep(0.25)
json.dump(books, open('/home/ubuntu/paper-sim/round5/raw/epl_ou_books.json', 'w'))
ok = sum(1 for b in books.values() if 'err' not in b['book'])
print('books fetched', ok, '/', len(books))

def top(b):
    bb = b['book']
    if 'err' in bb: return 'ERR'
    bids = sorted(bb.get('bids', []), key=lambda l: -float(l['price']))[:3]
    asks = sorted(bb.get('asks', []), key=lambda l: float(l['price']))[:3]
    bstr = ' '.join('%s*%d' % (l['price'], float(l['size'])) for l in bids)
    astr = ' '.join('%s*%d' % (l['price'], float(l['size'])) for l in asks)
    return 'B[%s] A[%s]' % (bstr, astr)

for s in match_total:
    if s['side'].lower().startswith('over'):
        print('%-40s %-38s %s' % (s['event'], s['q'][:38], top(books[s['token']])))

# dump one full resolution description
print()
print('=== SAMPLE RESOLUTION DESCRIPTION (O/U 2.5) ===')
for s in match_total:
    if 'O/U 2.5' in s['q'] and s['side'].lower().startswith('over'):
        print('EVENT:', s['event'])
        print(s['desc'])
        break
