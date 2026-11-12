"""Round-23 Serie A early sub-scan: Gamma sweep tag_slug=sea, window Oct31 00:00 -> Nov 3 00:00 UTC."""
import json, urllib.request, urllib.parse, time

BASE='https://gamma-api.polymarket.com'
LO='2026-10-31T00:00:00Z'; HI='2026-11-03T00:00:00Z'

def get(url, tries=8):
    last=None
    for i in range(tries):
        try:
            req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as r: return json.load(r)
        except Exception as e:
            last=e; time.sleep(2.0+2*i)
    raise last

def sweep(extra, cap=3000):
    out=[]; offset=0
    while True:
        p={'limit':100,'closed':'false','order':'startDate','ascending':'true','offset':offset}
        p.update(extra)
        url=BASE+'/events/pagination?'+urllib.parse.urlencode(p)
        d=get(url); batch=d.get('data') if isinstance(d,dict) else d
        out.extend(batch)
        if len(batch)<100: return out
        offset+=100
        if offset>=cap: return out
        time.sleep(1.0)

def norm(ts):
    s=str(ts or '').strip()
    if not s: return ''
    try:
        from datetime import datetime, timezone
        if s.endswith('Z'): s=s[:-1]+'+00:00'
        dt=datetime.fromisoformat(s)
        if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception: return s

def slim_event(e):
    mks=(e.get('markets') or [])
    slim={'id':str(e.get('id')),'title':e.get('title'),'slug':e.get('slug'),
      'startDate':norm(e.get('startDate')),'endDate':norm(e.get('endDate')),
      'liq':e.get('liquidityNum'),'vol24':e.get('volume24hr'),'vol':e.get('volume'),
      'tags':[t.get('slug') for t in (e.get('tags') or [])],'markets':[]}
    for m in mks:
        g=norm(m.get('gameStartTime'))
        slim['markets'].append({
          'id':str(m.get('id')),'q':m.get('question'),'slug':m.get('slug'),
          'group':m.get('groupItemTitle'),'outcomes':m.get('outcomes'),
          'prices':m.get('outcomePrices'),'tokens':m.get('clobTokenIds'),
          'line':m.get('line') or m.get('handicap'),'gameStartTime':g,
          'liq':m.get('liquidityNum'),'vol24':m.get('volume24hr'),
          'bestBid':m.get('bestBid'),'bestAsk':m.get('bestAsk'),
          'spread':m.get('spread'),'closed':m.get('closed'),'active':m.get('active')})
    return slim

result={'sea':[], 'soccer_catchall':[]}
seen=set()
for e in sweep({'tag_slug':'sea'}):
    eid=str(e.get('id'))
    if eid in seen: continue
    seen.add(eid)
    s=slim_event(e)
    # keep events with any market kickoff (or startDate) in window
    ks=[m['gameStartTime'] for m in s['markets'] if m['gameStartTime']]
    hit=any(LO<=k<=HI for k in ks) or (LO<=s['startDate']<=HI)
    if hit: result['sea'].append(s)
print('sea events in window:', len(result['sea']))
time.sleep(1.0)
for e in sweep({'tag_slug':'soccer','start_date_min':LO,'start_date_max':HI}):
    eid=str(e.get('id'))
    if eid in seen: continue
    seen.add(eid); result['soccer_catchall'].append(slim_event(e))
print('catchall extra:', len(result['soccer_catchall']))

json.dump(result, open('/home/ubuntu/paper-sim/round23/raw/gamma_sweep23.json','w'), indent=1)
for e in result['sea']:
    print('EVT', e['title'], '| start=', e['startDate'], '| liq=', e['liq'], '| mks=', len(e['markets']))
