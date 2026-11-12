"""Round-14 ad-hoc 24h soccer discovery: Polymarket soccer events kicking off
2026-10-23T13:10:00Z .. 2026-10-24T13:10:00Z (Friday evening + Saturday early).

Sweeps gamma /events/pagination with tag_slug=soccer (per coordinator) plus
tag=soccer backstop and per-league sweeps (epl, la-liga, ligue-1, bundesliga,
serie-a, championship, serie-b) to guarantee inventory completeness.
Window filter is on market gameStartTime (kickoff), event startDate as fallback.
Saves slim in-window events to round14/raw/soccer24h.json.
"""
import json, urllib.request, urllib.parse, time
from datetime import datetime, timezone

BASE = 'https://gamma-api.polymarket.com'
LO = '2026-10-23T13:10:00Z'
HI = '2026-10-24T13:10:00Z'

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

def norm(ts):
    """Normalize an ISO timestamp to 'YYYY-MM-DDTHH:MM:SSZ' (UTC).''"""
    if not ts: return ''
    s = str(ts).strip()
    try:
        if s.endswith('Z'): s = s[:-1] + '+00:00'
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception:
        return s

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

SWEEPS = [
    ('tag_slug', 'epl', 'volume24hr'),
    ('tag_slug', 'la-liga', 'volume24hr'),
    ('tag_slug', 'ligue-1', 'volume24hr'),
    ('tag_slug', 'bundesliga', 'volume24hr'),
    ('tag_slug', 'serie-a', 'volume24hr'),
    ('tag_slug', 'championship', 'volume24hr'),
    ('tag_slug', 'efl-championship', 'volume24hr'),
    ('tag_slug', 'serie-b', 'volume24hr'),
    ('tag_slug', 'soccer', 'volume24hr'),
    ('tag_slug', 'soccer', 'liquidity'),
]

seen = {}
for param, value, order in SWEEPS:
    evs = None
    for attempt in (1, 2):
        try:
            evs = sweep(order, param, value); break
        except Exception as e:
            print('SWEEP ERR(try %d)' % attempt, param, value, order, repr(e))
            time.sleep(20)
    if evs is None:
        print('SWEEP FAILED for', param, value, order); continue
    n = 0
    for e in evs:
        # STRICT: event is in-window iff at least one market has gameStartTime in window.
        # (event startDate fallback rejected: batch-created weekend sub-events carry
        #  creation timestamps like 13:59:14Z that fake a window hit)
        kws = [norm(m.get('gameStartTime')) for m in (e.get('markets') or [])]
        hit = any(k and LO <= k <= HI for k in kws)
        if not hit: continue
        eid = str(e.get('id'))
        n += 1
        sd = norm(e.get('startDate'))
        prev = seen.get(eid)
        slim = {
            'id': eid, 'title': e.get('title'), 'slug': e.get('slug'),
            'startDate': sd, 'endDate': norm(e.get('endDate')),
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
        if not slim['markets']: slim['markets'] = []
        if prev is not None:
            # merge: union of markets, max liq/vol, union tags
            prev_ids = {mm['id'] for mm in prev['markets']}
            for mm in slim['markets']:
                if mm['id'] not in prev_ids: prev['markets'].append(mm)
            prev['tags'] = sorted(set(prev['tags']) | set(slim['tags']))
            prev['liq'] = max(prev['liq'] or 0, slim['liq'] or 0) or None
            prev['vol24'] = max(prev['vol24'] or 0, slim['vol24'] or 0) or None
        else:
            seen[eid] = slim
    print('sweep %-9s %-13s order=%-11s total=%d in_window=%d' % (param, value, order, len(evs), n))
    time.sleep(0.4)

evs = list(seen.values())
evs.sort(key=lambda e: -(e.get('liq') or 0))
print()
print('unique in-window events:', len(evs))

# inventory: group fixtures by base title (opponents), league tags
LEAGUE_TAGS = ['epl', 'premier-league', 'la-liga', 'laliga', 'ligue-1', 'ligue1',
               'bundesliga', 'serie-a', 'championship', 'serie-b', 'eredivisie',
               'mls', 'primeira-liga', 'brazil-serie-a', 'laliga-santander',
               'efl-championship', 'league-one', 'league-two', 'jupiler', 'austria',
               'switzerland', 'denmark', 'norway', 'sweden', 'finland', 'poland',
               'turkey', 'scotland', 'spl', 'laliga-hypermotion', 'la-liga-2',
               'ligue-2', 'bundesliga-2', '2-bundesliga', 'efl-cup', 'fa-cup',
               'copa-libertadores', 'copa-sudamericana', 'argentina', 'chile',
               'colombia', 'mexico', 'liga-mx', 'japan', 'j-league', 'korea',
               'australia', 'a-league', 'china', 'super-league', 'saudi']
fixtures = {}
for e in evs:
    t = str(e.get('title') or '')
    base = t.split(' - ')[0].strip()
    ko = ''
    for m in e['markets']:
        g = m.get('gameStartTime') or ''
        if g and (not ko or g < ko): ko = g
    if not ko: ko = e.get('startDate') or ''
    lt = [x for x in e['tags'] if x in LEAGUE_TAGS]
    fixtures.setdefault(base, {'kickoff': ko or '??', 'tags': set(), 'events': 0,
                               'nmarkets': 0, 'liq': 0, 'vol24': 0})
    fixtures[base]['events'] += 1
    fixtures[base]['tags'] |= set(lt)
    fixtures[base]['nmarkets'] += len([m for m in e['markets'] if not m.get('closed')])
    fixtures[base]['liq'] = max(fixtures[base]['liq'], e.get('liq') or 0)
    fixtures[base]['vol24'] += e.get('vol24') or 0

print('unique fixtures (by event base title):', len(fixtures))
print()
from collections import Counter
league_count = Counter()
for base, f in fixtures.items():
    lg = ','.join(sorted(f['tags'])) or 'other'
    league_count[lg] += 1
    print('  %-52s ko=%s nmk=%2d liq=%8s vol24=%8s tags=%s' % (
        base[:52], str(f['kickoff'])[:16], f['nmarkets'], f['liq'], round(f['vol24'] or 0), lg))
print()
print('fixture count by league tag:')
for lg, c in sorted(league_count.items(), key=lambda x: -x[1]):
    print('  %-40s %d' % (lg, c))

json.dump(evs, open('/home/ubuntu/paper-sim/round14/raw/soccer24h.json', 'w'), indent=1)
print('saved round14/raw/soccer24h.json')
