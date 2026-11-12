"""Supplemental sweep: extra soccer leagues with common Friday/Sat-early fixtures,
plus one more soccer-parent-tag attempt. Merges into round14/raw/soccer24h.json."""
import json, urllib.request, urllib.parse, time
from datetime import datetime, timezone

BASE = 'https://gamma-api.polymarket.com'
LO = '2026-10-23T13:10:00Z'; HI = '2026-10-24T13:10:00Z'
PATH = '/home/ubuntu/paper-sim/round14/raw/soccer24h.json'

def get(url, tries=6):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            last = e; time.sleep(3 + 2 * i)
    raise last

def norm(ts):
    if not ts: return ''
    s = str(ts).strip()
    try:
        if s.endswith('Z'): s = s[:-1] + '+00:00'
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception:
        return s

def sweep(order, value, param='tag_slug'):
    out = []; offset = 0
    while True:
        url = BASE + '/events/pagination?' + urllib.parse.urlencode({
            'limit': 60, param: value, 'active': 'true', 'closed': 'false',
            'order': order, 'ascending': 'false', 'offset': offset})
        resp = get(url)
        batch = resp.get('data') if isinstance(resp, dict) else resp
        out.extend(batch)
        if len(batch) < 60: return out
        offset += 60
        if offset >= 2400: return out
        time.sleep(1.2)

EXTRA = ['ere', 'mls', 'brazil-serie-a', 'scottish-premiership', 'primeira-liga', 'tur',
         'austria-bundesliga', 'switzerland-super-league', 'denmark-superliga',
         'sweden-allsvenskan', 'norway-eliteserien', 'bel1', 'la-liga-2', 'ligue-2',
         'bundesliga-2', 'japan-j-league', 'k-league', 'saudi-professional-league',
         'australian-a-league', 'mex', 'poland-ekstraklasa', 'czechia-fortuna-liga',
         'arg', 'chile-primera', 'colombia-primera-a', 'soccer']

evs = json.load(open(PATH))
seen = {str(e['id']): e for e in evs}
print('existing events:', len(seen))

for value in EXTRA:
    try:
        batch = sweep('volume24hr', value)
    except Exception as e:
        print('SWEEP ERR', value, repr(e)); continue
    n = 0
    for e in batch:
        kws = [norm(m.get('gameStartTime')) for m in (e.get('markets') or [])]
        if not any(k and LO <= k <= HI for k in kws): continue
        eid = str(e.get('id')); n += 1
        if eid in seen: continue
        slim = {
            'id': eid, 'title': e.get('title'), 'slug': e.get('slug'),
            'startDate': norm(e.get('startDate')), 'endDate': norm(e.get('endDate')),
            'liq': e.get('liquidityNum'), 'vol24': e.get('volume24hr'),
            'vol': e.get('volume'),
            'tags': sorted(set([t.get('slug') for t in (e.get('tags') or []) if t.get('slug')])),
            'markets': []}
        for m in (e.get('markets') or []):
            g = norm(m.get('gameStartTime'))
            if g and not (LO <= g <= HI): continue
            slim['markets'].append({
                'id': str(m.get('id')), 'q': m.get('question'), 'slug': m.get('slug'),
                'group': m.get('groupItemTitle'), 'type': m.get('marketType'),
                'outcomes': m.get('outcomes'), 'prices': m.get('outcomePrices'),
                'tokens': m.get('clobTokenIds'), 'line': m.get('line') or m.get('handicap'),
                'gameStartTime': g,
                'liq': m.get('liquidityNum'), 'vol24': m.get('volume24hr'),
                'bestBid': m.get('bestBid'), 'bestAsk': m.get('bestAsk'),
                'spread': m.get('spread'), 'closed': m.get('closed'), 'active': m.get('active')})
        seen[eid] = slim
    print('sweep %-26s total=%4d new_in_window=%d' % (value, len(batch), n))
    time.sleep(1.0)

out = sorted(seen.values(), key=lambda e: -(e.get('liq') or 0))
json.dump(out, open(PATH, 'w'), indent=1)
print('merged total in-window events:', len(out))

# reprint fixture inventory
LEAGUE_TAGS = ['epl','premier-league','la-liga','laliga','ligue-1','bundesliga','serie-a',
               'efl-championship','serie-b','ere','mls','brazil-serie-a','scottish-premiership',
               'primeira-liga','tur','austria-bundesliga','switzerland-super-league',
               'denmark-superliga','sweden-allsvenskan','norway-eliteserien','bel1',
               'la-liga-2','ligue-2','bundesliga-2','japan-j-league','k-league',
               'saudi-professional-league','australian-a-league','mex','poland-ekstraklasa',
               'czechia-fortuna-liga','arg','chile-primera','colombia-primera-a']
fixtures = {}
for e in out:
    t = str(e.get('title') or '')
    base = t.split(' - ')[0].strip()
    ko = ''
    for m in e['markets']:
        g = m.get('gameStartTime') or ''
        if g and (not ko or g < ko): ko = g
    lt = [x for x in e['tags'] if x in LEAGUE_TAGS]
    fixtures.setdefault(base, {'kickoff': ko or '??', 'tags': set(), 'nmarkets': 0, 'vol24': 0})
    fixtures[base]['tags'] |= set(lt)
    fixtures[base]['nmarkets'] += len([m for m in e['markets'] if not m.get('closed')])
    fixtures[base]['vol24'] += e.get('vol24') or 0

from collections import Counter
lc = Counter()
print()
print('unique fixtures:', len(fixtures))
for base, f in sorted(fixtures.items(), key=lambda x: x[1]['kickoff']):
    lg = ','.join(sorted(f['tags'])) or 'other'
    lc[lg] += 1
    print('  %-52s ko=%s nmk=%2d vol24=%8s %s' % (base[:52], str(f['kickoff'])[:16], f['nmarkets'], round(f['vol24'] or 0), lg))
print()
print('fixture count by league tag:')
for lg, c in sorted(lc.items(), key=lambda x: -x[1]):
    print('  %-40s %d' % (lg, c))
