import json, urllib.request, urllib.parse, time, datetime

BASE = 'https://gamma-api.polymarket.com'

def get(url, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            last = e
            time.sleep(1.5)
    return None

NOW = datetime.datetime(2026, 10, 21, 11, 15, tzinfo=datetime.timezone.utc)
seen = {}

def harvest(tag):
    found = 0
    for off in range(0, 600, 100):
        p = {'tag_slug': tag, 'closed': 'false', 'order': 'liquidity', 'ascending': 'false', 'offset': off, 'limit': 100}
        b = get(BASE + '/events?' + urllib.parse.urlencode(p))
        if b is None:
            break
        for ev in b:
            sl = ev.get('slug') or ''
            if not sl or sl in seen:
                continue
            end = ev.get('endDate') or ''
            try:
                ed = datetime.datetime.strptime(end[:19], '%Y-%m-%dT%H:%M:%S').replace(tzinfo=datetime.timezone.utc)
            except Exception:
                ed = None
            mk = []
            for m in (ev.get('markets') or []):
                if m.get('closed'):
                    continue
                toks = m.get('clobTokenIds')
                if isinstance(toks, str):
                    try:
                        toks = json.loads(toks)
                    except Exception:
                        toks = None
                outs = m.get('outcomes')
                if isinstance(outs, str):
                    try:
                        outs = json.loads(outs)
                    except Exception:
                        outs = None
                mk.append({'id': m.get('id'), 'q': m.get('question') or m.get('groupItemTitle'), 'slug': m.get('slug'),
                           'outcomes': outs, 'tokens': toks, 'liq': m.get('liquidityNum'), 'vol24': m.get('volume24hr'),
                           'prices': m.get('outcomePrices')})
            seen[sl] = {'title': ev.get('title'), 'slug': sl, 'endDate': end, 'liq': ev.get('liquidityNum') or 0,
                        'vol24': ev.get('volume24hr'), 'ed': ed, 'markets': mk}
            found += 1
        if len(b) < 100:
            break
        time.sleep(0.2)
    print('tag %-28s new=%d total=%d' % (tag, found, len(seen)), flush=True)

TAGS = ['europa-league', 'europa-conference-league', 'uel', 'uefa-europa-league',
        'primeira-liga', 'scottish-premiership', 'efl-championship',
        'fa-cup', 'carabao-cup', 'copa-del-rey', 'dfb-pokal',
        'womens-soccer', 'k-league', 'afcon', 'mls', 'world-cup', 'soccer']
for t in TAGS:
    harvest(t)
    time.sleep(0.3)

out = []
for sl, e in seen.items():
    ed = e.pop('ed')
    if ed is None:
        continue
    if not ((NOW - datetime.timedelta(hours=10)) <= ed <= (NOW + datetime.timedelta(days=8))):
        continue
    e['ed'] = ed.isoformat()
    out.append(e)
out.sort(key=lambda x: -(x['liq'] or 0))
json.dump(out, open('/home/ubuntu/paper-sim/round10/raw/discover10.json', 'w'), indent=1)
print('KEPT events in window:', len(out))
for e in out[:50]:
    print('%-9s %-46s liq=%-8d mk=%d %s' % (e['slug'][:9], (e['title'] or '')[:46], e['liq'] or 0, len(e['markets']), (e['endDate'] or '')[:16]), flush=True)
