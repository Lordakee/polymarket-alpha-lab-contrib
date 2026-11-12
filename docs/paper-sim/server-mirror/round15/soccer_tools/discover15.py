"""Round-15 soccer discovery: Polymarket events kicking off Oct 24-27 (weekend+Monday,
inclusive). Sweeps tag_slug=soccer (both orders) first; per-league sweeps (epl,
la-liga, serie-a, bundesliga, ligue-1) as guaranteed Big-5 backstop; extra liquid
non-Big-5 tags for report-only. STRICT window filter on market gameStartTime.
Saves round15/raw/events_window.json.
"""
import json, urllib.request, urllib.parse, time

BASE = 'https://gamma-api.polymarket.com'
LO = '2026-10-24T00:00:00Z'
HI = '2026-10-27T23:59:59Z'

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
        if offset >= 3000: return out
        time.sleep(0.7)

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
    sd = norm(ev.get('startDate'))
    if LO[:10] <= sd[:10] <= HI[:10]: return True
    for m in (ev.get('markets') or []):
        g = norm(m.get('gameStartTime'))
        if LO <= g <= HI: return True
    return False

SWEEPS = [
    ('tag_slug', 'soccer', 'volume24hr'),
    ('tag_slug', 'soccer', 'liquidity'),
    ('tag_slug', 'epl', 'volume24hr'),
    ('tag_slug', 'la-liga', 'volume24hr'),
    ('tag_slug', 'serie-a', 'volume24hr'),
    ('tag_slug', 'bundesliga', 'volume24hr'),
    ('tag_slug', 'ligue-1', 'volume24hr'),
    ('tag_slug', 'championship', 'volume24hr'),
    ('tag_slug', 'efl-championship', 'volume24hr'),
    ('tag_slug', 'champions-league', 'volume24hr'),
    ('tag_slug', 'europa-league', 'volume24hr'),
    ('tag_slug', 'eredivisie', 'volume24hr'),
    ('tag_slug', 'primeira-liga', 'volume24hr'),
    ('tag_slug', 'mls', 'volume24hr'),
    ('tag_slug', 'brazil-serie-a', 'volume24hr'),
]

seen = {}
for param, value, order in SWEEPS:
    evs = None
    for attempt in (1, 2):
        try:
            evs = sweep(order, param, value); break
        except Exception as e:
            print('SWEEP ERR(try %d)' % attempt, param, value, order, repr(e))
            time.sleep(15)
    if evs is None:
        print('SWEEP FAILED for', param, value, order); continue
    n = 0
    for e in evs:
        if not in_window(e): continue
        eid = str(e.get('id'))
        n += 1
        slim = {
          'id': eid, 'title': e.get('title'), 'slug': e.get('slug'),
          'startDate': e.get('startDate'), 'endDate': e.get('endDate'),
          'liq': e.get('liquidityNum'), 'vol24': e.get('volume24hr'),
          'vol': e.get('volume'),
          'tags': [t.get('slug') for t in (e.get('tags') or [])],
          'markets': []}
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
        if not slim['markets']:
            # event startDate in window but no market kickoff in window: keep header only
            slim['markets'] = []
        seen[eid] = slim
    print('sweep %-14s %-12s total=%4d in_window=%d (unique so far %d)' % (value, order, len(evs), n, len(seen)), flush=True)
    time.sleep(0.6)

evs = list(seen.values())
evs.sort(key=lambda e: -(e.get('liq') or 0))
print('unique window events:', len(evs))
BIG5 = ('epl','premier-league','la-liga','laliga','serie-a','bundesliga','ligue-1','ligue1')
for e in evs:
    tags = set(e.get('tags') or [])
    tagstr = ','.join([t for t in tags if t in BIG5 + ('championship','champions-league','europa-league','eredivisie','primeira-liga','mls','brazil-serie-a','soccer','ucl','uel')][:4])
    print('  %-58s liq=%9s vol24=%9s nmk=%d tags=%s start=%s' % (
        str(e['title'])[:58], e.get('liq'), e.get('vol24'), len(e['markets']), tagstr, str(e.get('startDate'))[:16]))
json.dump(evs, open('/home/ubuntu/paper-sim/round15/raw/events_window.json', 'w'), indent=1)
print('saved events_window.json')
