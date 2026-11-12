import json, urllib.request, time, os, datetime

TAGS = ['nfl','mlb','nhl','ufc','mma','boxing','tennis','golf']
BASE = 'https://gamma-api.polymarket.com'
OUT = '/home/ubuntu/paper-sim/round2/raw/'
os.makedirs(OUT, exist_ok=True)

def get(url):
    req = urllib.request.Request(url, headers={'User-Agent':'research/0.1'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

all_events = {}
tag_of = {}
for tag in TAGS:
    offset = 0
    n = 0
    while True:
        url = BASE + '/events?tag_slug=' + tag + '&closed=false&limit=100&offset=' + str(offset) + '&order=volume24hr&ascending=false'
        try:
            batch = get(url)
        except Exception as e:
            print(tag, 'offset', offset, 'ERROR', e); time.sleep(2); continue
        if not batch: break
        for ev in batch:
            eid = ev.get('id')
            if eid not in all_events:
                all_events[eid] = ev; tag_of[eid] = tag
        n += len(batch)
        if len(batch) < 100: break
        offset += 100
        if offset > 1500: break
        time.sleep(0.35)
    print('tag=' + tag + ' fetched=' + str(n) + ' unique_total=' + str(len(all_events)))

with open(OUT + 'events_open_other.json','w') as f:
    json.dump(list(all_events.values()), f)

now = datetime.datetime.now(datetime.timezone.utc)
lo = now - datetime.timedelta(hours=6)
hi = now + datetime.timedelta(days=9)

rows = []
for ev in all_events.values():
    liq = 0.0; vol24 = 0.0; nmk = 0; best_end = ''; gstart = None
    for m in ev.get('markets', []):
        try: liq += float(m.get('liquidityNum') or m.get('liquidity') or 0)
        except Exception: pass
        try: vol24 += float(m.get('volume24hr') or 0)
        except Exception: pass
        nmk += 1
        ed = m.get('endDate') or ''
        if ed and (best_end == '' or ed < best_end): best_end = ed
        g = m.get('gameStartTime')
        if g and (gstart is None or g < gstart): gstart = g
    rows.append({
        'id': ev.get('id'), 'slug': ev.get('slug'), 'title': ev.get('title'),
        'discover_tag': tag_of.get(ev.get('id')), 'n_markets': nmk,
        'liq_sum': round(liq,2), 'vol24_sum': round(vol24,2),
        'end_min': best_end[:10], 'game_start': gstart,
        'tags': [t.get('slug') for t in (ev.get('tags') or [])][:10],
    })
rows.sort(key=lambda r: -r['liq_sum'])
with open(OUT + 'events_summary_other.json','w') as f:
    json.dump(rows, f, indent=1)
print()
print('UTC now:', now.isoformat())
print('OTHER-SPORTS NEAR-DATED (game_start/end within %s..%s), liq>=20k:' % (lo.date(), hi.date()))
for r in rows:
    ts = r['game_start'] or r['end_min']
    inwin = False
    try:
        if r['game_start']:
            dt = datetime.datetime.fromisoformat(r['game_start'].replace('Z','+00:00'))
            inwin = lo <= dt <= hi
    except Exception: pass
    if not inwin and r['end_min']:
        try:
            dt = datetime.datetime.fromisoformat(r['end_min'] + 'T23:59:59+00:00')
            inwin = lo <= dt <= hi
        except Exception: pass
    if inwin and r['liq_sum'] >= 20000:
        print(format(r['liq_sum'],',.0f').rjust(12), 'v24='+format(r['vol24_sum'],',.0f').rjust(10), 'nmk='+str(r['n_markets']).rjust(3), 'gs='+str(r['game_start'])[:16].ljust(17), 'end='+str(r['end_min']).ljust(11), '['+str(r['discover_tag'])+']', r['slug'][:64])
