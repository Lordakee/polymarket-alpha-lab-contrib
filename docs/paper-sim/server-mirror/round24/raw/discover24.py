"""Round-24 EPL delta discovery: Gamma tag_slug=epl events kicking off Oct 30 - Nov 2.
Same sweep shape as round23/raw/discover24 (3 orders, pace >=1s). Window matches the
10-fixture weekend slate (Sat 12:30Z -> Mon 20:00Z)."""
import json, urllib.request, urllib.parse, time

BASE = 'https://gamma-api.polymarket.com'
LO = '2026-10-30T00:00:00Z'
HI = '2026-11-02T23:59:59Z'
OUT = '/home/ubuntu/paper-sim/round24/raw/events_window.json'

def get(url, tries=8):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            last = e; time.sleep(2.5 + 2 * i)
    raise last

def sweep(order, param, value):
    out = []; offset = 0
    while True:
        url = BASE + '/events/pagination?' + urllib.parse.urlencode({
            'limit': 100, param: value, 'active': 'true', 'closed': 'false',
            'order': order, 'ascending': 'false', 'offset': offset})
        resp = get(url)
        batch = resp.get('data') if isinstance(resp, dict) else resp
        out.extend(batch)
        if len(batch) < 100: return out
        offset += 100
        if offset >= 2000: return out
        time.sleep(1.0)

def norm(ts):
    s = str(ts or '').strip()
    if not s: return ''
    try:
        from datetime import datetime, timezone
        if s.endswith('Z'): s = s[:-1] + '+00:00'
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception:
        return s

def in_window(ev):
    for m in (ev.get('markets') or []):
        g = norm(m.get('gameStartTime'))
        if LO <= g <= HI: return True
    return False

SWEEPS = [('tag_slug', 'epl', 'volume24hr'), ('tag_slug', 'epl', 'liquidity'), ('tag_slug', 'epl', 'startDate')]
seen = {}
for param, value, order in SWEEPS:
    try:
        evs = sweep(order, param, value)
    except Exception as e:
        print('SWEEP FAILED', param, value, order, repr(e)); continue
    n = 0
    for e in evs:
        if not in_window(e): continue
        eid = str(e.get('id')); n += 1
        slim = {'id': eid, 'title': e.get('title'), 'slug': e.get('slug'),
          'startDate': e.get('startDate'), 'endDate': e.get('endDate'),
          'liq': e.get('liquidityNum'), 'vol24': e.get('volume24hr'), 'vol': e.get('volume'),
          'tags': [t.get('slug') for t in (e.get('tags') or [])], 'markets': []}
        for m in (e.get('markets') or []):
            g = norm(m.get('gameStartTime'))
            if not (LO <= g <= HI): continue
            slim['markets'].append({
              'id': str(m.get('id')), 'q': m.get('question'), 'slug': m.get('slug'),
              'group': m.get('groupItemTitle'), 'type': m.get('marketType'),
              'outcomes': m.get('outcomes'), 'prices': m.get('outcomePrices'),
              'tokens': m.get('clobTokenIds'), 'line': m.get('line') or m.get('handicap'),
              'gameStartTime': m.get('gameStartTime'),
              'liq': m.get('liquidityNum'), 'vol24': m.get('volume24hr'),
              'bestBid': m.get('bestBid'), 'bestAsk': m.get('bestAsk'),
              'spread': m.get('spread'), 'closed': m.get('closed'), 'active': m.get('active')})
        seen[eid] = slim
    print('sweep %-14s order=%-11s total=%4d in_window=%d (unique %d)' % (value, order, len(evs), n, len(seen)), flush=True)
    time.sleep(1.0)

evs = list(seen.values())
evs.sort(key=lambda e: (min((m.get('gameStartTime') or '') for m in e['markets']) if e['markets'] else str(e.get('startDate') or ''),))
print('unique window events:', len(evs))
for e in evs:
    ko = min((str(m.get('gameStartTime')) for m in e['markets']), default=str(e.get('startDate')))
    print('  %-58s liq=%9s vol24=%10s nmk=%2d kick=%s' % (
        str(e['title'])[:58], e.get('liq'), e.get('vol24'), len(e['markets']), ko[:16]))
json.dump(evs, open(OUT, 'w'), indent=1)
print('saved events_window.json')
