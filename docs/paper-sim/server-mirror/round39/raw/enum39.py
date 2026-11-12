"""Round-39A enumeration: Gamma soccer events in window + tag census (paper-only)."""
import json, time, urllib.parse, urllib.request
from datetime import datetime, timezone

BASE = 'https://gamma-api.polymarket.com'
OUT = '/home/ubuntu/paper-sim/round39/raw/events_window_39.json'
LO = '2026-11-06T13:30:00Z'
HI = '2026-11-08T23:59:59Z'

def get(url, tries=6):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (research)'})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            last = e
            time.sleep(2.0 + 2 * i)
    raise last

def norm_ts(ts):
    s = str(ts or '').strip()
    if not s: return ''
    try:
        if s.endswith('Z'): s = s[:-1] + '+00:00'
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception:
        return s

def parse_listy(raw):
    if isinstance(raw, str):
        try: return json.loads(raw)
        except Exception: return []
    return raw or []

def sweep(order, extra_params, max_offset=2000):
    out, offset = [], 0
    while True:
        params = {'limit': 100, 'active': 'true', 'closed': 'false',
                  'order': order, 'ascending': 'false', 'offset': offset}
        params.update(extra_params)
        resp = get(BASE + '/events/pagination?' + urllib.parse.urlencode(params))
        batch = resp.get('data') if isinstance(resp, dict) else resp
        out.extend(batch)
        if len(batch) < 100: return out
        offset += 100
        if offset >= max_offset: return out
        time.sleep(1.0)

def slim_event(e):
    eid = str(e.get('id'))
    tags = [t.get('slug') for t in (e.get('tags') or []) if t.get('slug')]
    slim = {'id': eid, 'title': e.get('title'), 'slug': e.get('slug'), 'tags': tags,
            'liq': e.get('liquidityNum'), 'vol24': e.get('volume24hr'), 'markets': []}
    for m in e.get('markets') or []:
        if m.get('closed'): continue
        slim['markets'].append({
            'id': str(m.get('id')), 'q': m.get('question'), 'slug': m.get('slug'),
            'group': m.get('groupItemTitle'), 'type': m.get('marketType'),
            'outcomes': parse_listy(m.get('outcomes')),
            'prices': parse_listy(m.get('outcomePrices')),
            'tokens': parse_listy(m.get('clobTokenIds')),
            'line': m.get('line') or m.get('handicap'),
            'gameStartTime': norm_ts(m.get('gameStartTime')),
            'liq': m.get('liquidityNum'), 'vol24': m.get('volume24hr'),
            'bestBid': m.get('bestBid'), 'bestAsk': m.get('bestAsk'),
            'spread': m.get('spread'), 'active': m.get('active')})
    kos = [m['gameStartTime'] for m in slim['markets'] if m['gameStartTime']]
    slim['kick'] = min(kos) if kos else ''
    return slim

def in_range(ev, lo, hi):
    kos = [m['gameStartTime'] for m in ev['markets'] if m['gameStartTime']]
    return any(lo <= k <= hi for k in kos)

sweeps = [
    ('date-volume', 'volume24hr', {'start_date_min': LO, 'start_date_max': HI}),
    ('date-liquidity', 'liquidity', {'start_date_min': LO, 'start_date_max': HI}),
    ('tag-soccer-vol', 'volume24hr', {'tag_slug': 'soccer'}),
    ('tag-soccer-liq', 'liquidity', {'tag_slug': 'soccer'}),
    ('tag-primeira', 'volume24hr', {'tag_slug': 'primeira-liga'}),
    ('tag-scottish', 'volume24hr', {'tag_slug': 'scottish-premiership'}),
    ('tag-superlig', 'volume24hr', {'tag_slug': 'super-lig'}),
    ('tag-allsvenskan', 'volume24hr', {'tag_slug': 'allsvenskan'}),
]
seen = {}
for label, order, extra in sweeps:
    try:
        evs = sweep(order, extra)
    except Exception as e:
        print('sweep', label, 'FAILED', repr(e), flush=True)
        continue
    n = 0
    for e in evs:
        try:
            slim = slim_event(e)
        except Exception:
            continue
        if not in_range(slim, LO, HI):
            sd = norm_ts(e.get('startDate'))
            if not (sd and LO <= sd <= HI and slim['markets']):
                continue
        n += 1
        if slim['id'] not in seen:
            seen[slim['id']] = slim
    print('sweep %-16s total=%4d in_window=%d unique=%d' % (label, len(evs), n, len(seen)), flush=True)
    time.sleep(1.0)

events = [e for e in seen.values() if 'soccer' in (e.get('tags') or []) and e.get('kick')]
events.sort(key=lambda e: (e['kick'], e.get('title') or ''))
json.dump(events, open(OUT, 'w'), indent=1)
print('unique soccer events in window:', len(events), '-> saved', OUT)

# tag census among window soccer events
census = {}
for e in events:
    for t in e['tags']:
        census[t] = census.get(t, 0) + 1
for t, c in sorted(census.items(), key=lambda kv: -kv[1]):
    print('%5d %s' % (c, t))
json.dump(census, open('/home/ubuntu/paper-sim/round39/raw/tag_census_39.json', 'w'), indent=1)
