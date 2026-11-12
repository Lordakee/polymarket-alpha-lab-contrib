"""Round-26 scan A discovery v2: /events/pagination sweeps (r23 lineage),
tags sea/la-liga/laliga/serie-a/soccer, strict gameStartTime window filter."""
import json, urllib.request, urllib.parse, time

BASE = 'https://gamma-api.polymarket.com'
LO = '2026-11-01T08:00:00Z'
HI = '2026-11-02T04:00:00Z'
RAW = '/home/ubuntu/paper-sim/round26/raw'

def get(url, tries=8):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            last = e; time.sleep(2.0 + 2 * i)
    raise last

def sweep(extra, cap=3000):
    out = []; offset = 0
    while True:
        p = {'limit': 100, 'closed': 'false', 'order': 'startDate', 'ascending': 'true', 'offset': offset}
        p.update(extra)
        url = BASE + '/events/pagination?' + urllib.parse.urlencode(p)
        d = get(url)
        batch = d.get('data') if isinstance(d, dict) else d
        out.extend(batch)
        if len(batch) < 100:
            return out
        offset += 100
        if offset >= cap:
            return out
        time.sleep(1.0)

def norm(ts):
    s = str(ts or '').strip()
    if not s:
        return ''
    try:
        from datetime import datetime, timezone
        if s.endswith('Z'):
            s = s[:-1] + '+00:00'
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception:
        return s

def slim_event(e):
    slim = {'id': str(e.get('id')), 'title': e.get('title'), 'slug': e.get('slug'),
            'startDate': norm(e.get('startDate')), 'endDate': norm(e.get('endDate')),
            'liq': e.get('liquidityNum'), 'vol24': e.get('volume24hr'),
            'tags': [t.get('slug') for t in (e.get('tags') or [])], 'markets': []}
    for m in (e.get('markets') or []):
        slim['markets'].append({
            'id': str(m.get('id')), 'q': m.get('question'), 'slug': m.get('slug'),
            'group': m.get('groupItemTitle'), 'outcomes': m.get('outcomes'),
            'prices': m.get('outcomePrices'), 'tokens': m.get('clobTokenIds'),
            'line': m.get('line') or m.get('handicap'), 'gameStartTime': norm(m.get('gameStartTime')),
            'liq': m.get('liquidityNum'), 'vol24': m.get('volume24hr'),
            'bestBid': m.get('bestBid'), 'bestAsk': m.get('bestAsk'),
            'spread': m.get('spread'), 'closed': m.get('closed'), 'active': m.get('active')})
    return slim

seen = {}
for tag in ('sea', 'la-liga', 'laliga', 'serie-a', 'soccer'):
    try:
        evs = sweep({'tag_slug': tag})
    except Exception as e:
        print(tag, 'SWEEP FAIL', repr(e)); continue
    kept = 0
    for e in evs:
        eid = str(e.get('id'))
        if eid in seen:
            continue
        s = slim_event(e)
        ks = [m['gameStartTime'] for m in s['markets'] if m['gameStartTime']]
        hit = any(LO <= k <= HI for k in ks) or (LO <= s['startDate'] <= HI)
        if hit:
            seen[eid] = s
            kept += 1
    print('tag', tag, 'swept', len(evs), 'kept new', kept, 'cum', len(seen))

with open(RAW + '/events_window_a.json', 'w') as f:
    json.dump(list(seen.values()), f)
print('total in-window events:', len(seen))
for s in sorted(seen.values(), key=lambda x: x['startDate']):
    print(s['startDate'], '|', s['title'], '| mkts', len(s['markets']))
