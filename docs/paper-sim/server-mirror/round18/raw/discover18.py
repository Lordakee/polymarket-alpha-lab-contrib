"""Round-18 La Liga sub-scan discovery: gamma tag_slug=la-liga + la-liga-2 (both orders),
strict market gameStartTime window 2026-10-26T02:30Z .. 2026-10-27T02:30Z.
Extra report-only context sweeps: champions-league (UCL Oct 27-28 Spanish teams).
Saves round18/raw/events_window.json (in-window) and round18/raw/context_ucl.json.
"""
import json, urllib.request, urllib.parse, time
from datetime import datetime, timezone

BASE = 'https://gamma-api.polymarket.com'
LO = '2026-10-26T02:30:00Z'
HI = '2026-10-27T02:30:00Z'
UCL_LO = '2026-10-27T00:00:00Z'
UCL_HI = '2026-10-29T00:00:00Z'

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
        if s.endswith('Z'): s = s[:-1] + '+00:00'
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception:
        return s

def slim_ev(e, lo, hi):
    mk = []
    for m in (e.get('markets') or []):
        g = norm(m.get('gameStartTime'))
        if not (lo <= g <= hi): continue
        mk.append({
          'id': str(m.get('id')), 'q': m.get('question'), 'slug': m.get('slug'),
          'group': m.get('groupItemTitle'), 'type': m.get('marketType'),
          'outcomes': m.get('outcomes'), 'prices': m.get('outcomePrices'),
          'tokens': m.get('clobTokenIds'), 'line': m.get('line') or m.get('handicap'),
          'gameStartTime': m.get('gameStartTime'),
          'liq': m.get('liquidityNum'), 'vol24': m.get('volume24hr'),
          'bestBid': m.get('bestBid'), 'bestAsk': m.get('bestAsk'),
          'spread': m.get('spread'), 'closed': m.get('closed'), 'active': m.get('active')})
    return {'id': str(e.get('id')), 'title': e.get('title'), 'slug': e.get('slug'),
            'startDate': e.get('startDate'), 'endDate': e.get('endDate'),
            'liq': e.get('liquidityNum'), 'vol24': e.get('volume24hr'), 'vol': e.get('volume'),
            'tags': [t.get('slug') for t in (e.get('tags') or [])], 'markets': mk}

SWEEPS = [
    ('tag_slug', 'la-liga', 'volume24hr'),
    ('tag_slug', 'la-liga', 'liquidity'),
    ('tag_slug', 'la-liga-2', 'volume24hr'),
    ('tag_slug', 'la-liga-2', 'liquidity'),
    ('tag_slug', 'laliga-2', 'volume24hr'),
    ('tag_slug', 'laliga', 'volume24hr'),
    ('tag_slug', 'segunda-division', 'volume24hr'),
]

seen = {}
for param, value, order in SWEEPS:
    evs = None
    for attempt in (1, 2):
        try:
            evs = sweep(order, param, value); break
        except Exception as e:
            print('SWEEP ERR(try %d)' % attempt, param, value, order, repr(e)); time.sleep(15)
    if evs is None:
        print('SWEEP FAILED for', param, value, order); continue
    n = 0
    for e in evs:
        se = slim_ev(e, LO, HI)
        if not se['markets']: continue
        eid = se['id']
        if eid in seen:
            seen[eid]['markets'] = {m['id']: m for m in seen[eid]['markets'] + se['markets']}.values() if False else seen[eid]['markets']
            for m in se['markets']:
                if m['id'] not in [x['id'] for x in seen[eid]['markets']]:
                    seen[eid]['markets'].append(m)
        else:
            seen[eid] = se; n += 1
    print('sweep %-16s %-11s total=%4d in_window_new=%d (unique %d)' % (value, order, len(evs), n, len(seen)), flush=True)
    time.sleep(0.6)

evs = sorted(seen.values(), key=lambda e: -(e.get('liq') or 0))
print()
print('unique in-window events:', len(evs))
for e in evs:
    tagstr = ','.join([t for t in (e.get('tags') or []) if 'liga' in t or 'soccer' in t or 'spain' in t][:5])
    ko = min((m.get('gameStartTime') for m in e['markets']), default='')
    print('  %-58s liq=%9s vol24=%9s nmk=%3d ko=%s tags=%s' % (
        str(e['title'])[:58], e.get('liq'), e.get('vol24'), len(e['markets']), str(ko)[:19], tagstr))
json.dump(evs, open('/home/ubuntu/paper-sim/round18/raw/events_window.json', 'w'), indent=1)

# UCL context sweep (report-only, outside window)
ucl = {}
for param, value, order in [('tag_slug', 'champions-league', 'volume24hr'), ('tag_slug', 'ucl', 'volume24hr')]:
    try:
        for e in sweep(order, param, value):
            se = slim_ev(e, UCL_LO, UCL_HI)
            if not se['markets']: continue
            ucl.setdefault(se['id'], se)
    except Exception as ex:
        print('UCL sweep err', value, repr(ex))
    time.sleep(0.6)
ucl = sorted(ucl.values(), key=lambda e: -(e.get('vol24') or 0))
print()
print('UCL Oct27-28 context events (report-only):', len(ucl))
for e in ucl[:15]:
    ko = min((m.get('gameStartTime') for m in e['markets']), default='')
    print('  %-58s vol24=%9s nmk=%3d ko=%s' % (str(e['title'])[:58], e.get('vol24'), len(e['markets']), str(ko)[:19]))
json.dump(ucl, open('/home/ubuntu/paper-sim/round18/raw/context_ucl.json', 'w'), indent=1)
print('saved events_window.json + context_ucl.json')
