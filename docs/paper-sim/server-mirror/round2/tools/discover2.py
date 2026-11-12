import json, subprocess, time, os, datetime

TAGS = ['soccer','epl','premier-league','ucl','champions-league','europa-league','la-liga','serie-a','bundesliga','ligue-1','mls','world-cup','conference-league','fa-cup','efl','copa-libertadores','brasileirao','liga-mx']
BASE = 'https://gamma-api.polymarket.com/events'
OUT = '/home/ubuntu/paper-sim/round2/raw/'
os.makedirs(OUT, exist_ok=True)

def get(url):
    for attempt in range(3):
        try:
            r = subprocess.run(['curl','-s','--max-time','25','--compressed','-H','User-Agent: research/0.1', url],
                               capture_output=True, timeout=30)
            if r.returncode == 0 and r.stdout:
                return json.loads(r.stdout.decode())
        except Exception:
            pass
        time.sleep(1.5)
    return None

all_events = {}
tag_of = {}
for tag in TAGS:
    offset = 0
    n = 0
    stale = 0
    while True:
        url = (BASE + '?tag_slug=' + tag + '&closed=false&end_date_min=2026-10-11'
               + '&end_date_max=2026-10-20&limit=100&offset=' + str(offset)
               + '&order=volume24hr&ascending=false')
        batch = get(url)
        if batch is None:
            print(tag, 'offset', offset, 'FAILED after retries')
            break
        if not batch: break
        for ev in batch:
            eid = ev.get('id')
            if eid not in all_events:
                all_events[eid] = ev
                tag_of[eid] = tag
        n += len(batch)
        if len(batch) < 100:
            break
        offset += 100
        if offset > 900: break
        time.sleep(0.3)
    print('tag=' + tag + ' fetched=' + str(n) + ' unique_total=' + str(len(all_events)))

with open(OUT + 'events_open_dated.json','w') as f:
    json.dump(list(all_events.values()), f)

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
with open(OUT + 'events_summary_dated.json','w') as f:
    json.dump(rows, f, indent=1)
print()
print('NEAR-DATED SOCCER EVENTS (end 2026-10-11..20), liq>=50k:')
for r in rows:
    if r['liq_sum'] >= 50000:
        print(format(r['liq_sum'],',.0f').rjust(12), 'v24='+format(r['vol24_sum'],',.0f').rjust(10), 'nmk='+str(r['n_markets']).rjust(3), 'gs='+str(r['game_start'])[:16].ljust(17), 'end='+str(r['end_min']).ljust(11), '['+str(r['discover_tag'])+']', r['slug'][:64])
