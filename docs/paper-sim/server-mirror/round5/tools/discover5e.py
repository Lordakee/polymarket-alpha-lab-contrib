import json, urllib.request, urllib.parse, time

BASE = 'https://gamma-api.polymarket.com'
def get(url, tries=4):
    last=None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            last=e; time.sleep(2.5)
    raise last

seen = {}
def harvest(name, params):
    for off in range(0, 2200, 100):
        p = dict(params); p['offset']=off; p['limit']=100
        try:
            batch = get(BASE+'/events?'+urllib.parse.urlencode(p))
        except Exception as e:
            if off==0: print(name,'FATAL',e,flush=True); return
            break
        for ev in batch:
            sl = ev.get('slug') or ''
            if not sl or sl in seen: continue
            # game date encoded in slug
            gd = None
            for dt in ['2026-10-18','2026-10-19','2026-10-20','2026-10-21','2026-10-22']:
                if dt in sl: gd = dt; break
            if gd is None: continue
            mk=[]
            for m in ev.get('markets', []):
                toks = m.get('clobTokenIds')
                if isinstance(toks, str):
                    try: toks = json.loads(toks)
                    except: toks = None
                outs = m.get('outcomes')
                if isinstance(outs, str):
                    try: outs = json.loads(outs)
                    except: outs = None
                mk.append({'id': m.get('id'), 'q': m.get('question'), 'slug': m.get('slug'),
                           'outcomes': outs, 'tokens': toks, 'liq': m.get('liquidityNum'),
                           'vol24': m.get('volume24hr'), 'closed': m.get('closed'), 'active': m.get('active')})
            seen[sl] = {'title': ev.get('title'), 'slug': sl, 'gamedate': gd,
                        'liq': ev.get('liquidityNum') or 0, 'vol24': ev.get('volume24hr'),
                        'tags': [t.get('slug') for t in (ev.get('tags') or [])], 'markets': mk}
        if len(batch) < 100: break
        time.sleep(0.3)
    print(name,'done',flush=True)

harvest('soccer_liq', {'tag_slug':'soccer','closed':'false','order':'liquidity','ascending':'false'})
time.sleep(1)
harvest('ucl', {'tag_slug':'champions-league','closed':'false','order':'liquidity','ascending':'false'})
time.sleep(1)
harvest('ucl2', {'tag_slug':'uefa-champions-league','closed':'false','order':'liquidity','ascending':'false'})

rows = sorted(seen.values(), key=lambda e: (e['gamedate'], -(e['liq'] or 0)))
print()
for e in rows:
    types=set()
    for m in e['markets']:
        q=(m['q'] or '').lower()
        if 'over/under' in q and ('2.5' in q or 'goals' in q): types.add('OU')
        elif 'total goals' in q: types.add('OU')
        if 'both teams' in q or 'btts' in q: types.add('BTTS')
        if 'spread' in q: types.add('SPRD')
        if q.startswith('will '): types.add('1X2')
    print('%s %-48s liq=%9d v24=%10d mk=%2d %s' % (e['gamedate'], e['title'][:48], e['liq'] or 0, e['vol24'] or 0, len(e['markets']), ','.join(sorted(types))))
json.dump(rows, open('/home/ubuntu/paper-sim/round5/raw/discover5e.json','w'), indent=1)
print('saved', len(rows), 'events')
