import json, urllib.request, urllib.parse, sys, time

BASE = 'https://gamma-api.polymarket.com/events/pagination'
TAGS = ['pop-culture','movies','oscars','grammys','emmys','celebrity','music',
        'video-games','gaming','game-awards','top-netflix','album-release',
        'space','spacex','outer-space','space-travel','space-exploration',
        'tech','tech-releases','tech-news','big-tech','ai','ai-releases','ai-rankings',
        'business','weather','weather-science','metaverse','entertainment','culture','nobel-prize']
CUTOFF_END = '2027-01-22T23:59:59Z'
seen = {}
tag_counts = {}

def fetch(tag, offset, limit=100):
    params = {'limit': limit, 'offset': offset, 'order': 'volume24hr',
              'ascending': 'false', 'closed': 'false', 'active': 'true'}
    if tag:
        params['tag_slug'] = tag
    url = BASE + '?' + urllib.parse.urlencode(params)
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={'User-Agent':'paper-sim-scan/15'})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            sys.stderr.write('retry %s %s %d: %s\n' % (attempt, tag, offset, e))
            time.sleep(2)
    return None

def passes(ev):
    if ev.get('closed') or not ev.get('active'): return False
    end = ev.get('endDate') or ''
    if not end: return False
    if end > CUTOFF_END: return False
    vol = float(ev.get('volume') or 0)
    liq = float(ev.get('liquidity') or 0)
    return (vol >= 50000) or (liq >= 25000)

for tag in TAGS + [None]:
    label = tag or 'all'
    collected = 0
    for page in range(4):
        data = fetch(tag, page*100)
        if not data or not data.get('data'): break
        evs = data['data']
        for ev in evs:
            collected += 1
            if passes(ev):
                eid = ev['id']
                if eid not in seen:
                    cp = dict(ev)
                    cp['_tags_found'] = [label]
                    seen[eid] = cp
                elif label not in seen[eid]['_tags_found']:
                    seen[eid]['_tags_found'].append(label)
        if len(evs) < 100: break
        time.sleep(0.2)
    tag_counts[label] = collected
    sys.stderr.write('tag %s: scanned %d, kept cumulative %d\n' % (label, collected, len(seen)))

out = {'fetched_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
       'tag_counts': tag_counts,
       'cutoff_end': CUTOFF_END,
       'kept': len(seen),
       'events': list(seen.values())}
with open('/home/ubuntu/paper-sim/round15/raw/ent_scan.json','w') as f:
    json.dump(out, f)
print(json.dumps({'tag_counts': tag_counts, 'kept': len(seen)}))
