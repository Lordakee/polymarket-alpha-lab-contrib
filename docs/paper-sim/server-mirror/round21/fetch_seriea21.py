"""Round-21 Serie A Wed sub-scan: Gamma tag_slug=sea sweep, window Oct 28 01:15 -> Oct 29 01:15 UTC."""
import json, urllib.request, urllib.parse, time

BASE='https://gamma-api.polymarket.com'
LO='2026-10-28T00:00:00Z'; HI='2026-10-30T00:00:00Z'
WINLO='2026-10-28T01:15:00Z'; WINHI='2026-10-29T01:15:00Z'

def get(url, tries=8):
    last=None
    for i in range(tries):
        try:
            req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as r: return json.load(r)
        except Exception as e:
            last=e; time.sleep(2.5+2*i)
    raise last

def sweep(param, value):
    out=[]; offset=0
    while True:
        url=BASE+'/events/pagination?'+urllib.parse.urlencode({
            'limit':100,param:value,'active':'true','closed':'false',
            'order':'volume24hr','ascending':'false','offset':offset})
        resp=get(url)
        batch=resp.get('data') if isinstance(resp,dict) else resp
        out.extend(batch)
        if len(batch)<100: return out
        offset+=100
        if offset>=3000: return out
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

seen={}
for value in ['sea','serie-a']:
    evs=sweep('tag_slug',value)
    n=0
    for e in evs:
        mks=(e.get('markets') or [])
        gst=[norm(m.get('gameStartTime')) for m in mks]
        gst=[g for g in gst if g]
        inwin=any(LO<=g<=HI for g in gst)
        if not inwin: continue
        eid=str(e.get('id')); n+=1
        slim={'id':eid,'title':e.get('title'),'slug':e.get('slug'),
          'startDate':e.get('startDate'),'liq':e.get('liquidityNum'),
          'vol24':e.get('volume24hr'),'vol':e.get('volume'),
          'tags':[t.get('slug') for t in (e.get('tags') or [])],'markets':[]}
        for m in mks:
            g=norm(m.get('gameStartTime'))
            if not (LO<=g<=HI): continue
            in_window = WINLO<=g<=WINHI
            slim['markets'].append({
              'id':str(m.get('id')),'q':m.get('question'),'slug':m.get('slug'),
              'group':m.get('groupItemTitle'),'outcomes':m.get('outcomePrices') and m.get('outcomes'),
              'prices':m.get('outcomePrices'),'tokens':m.get('clobTokenIds'),
              'line':m.get('line') or m.get('handicap'),'gameStartTime':m.get('gameStartTime'),
              'liq':m.get('liquidityNum'),'vol24':m.get('volume24hr'),
              'bestBid':m.get('bestBid'),'bestAsk':m.get('bestAsk'),
              'spread':m.get('spread'),'closed':m.get('closed'),'active':m.get('active'),
              'in_window':in_window})
        slim['outcomes_raw']=None
        seen[eid]=slim
    print('sweep',value,'total',len(evs),'in_fetch_window',n,'unique',len(seen),flush=True)
    time.sleep(1.0)

evs=list(seen.values())
evs.sort(key=lambda e:-(e.get('liq') or 0))
for e in evs:
    iw=any(m.get('in_window') for m in e['markets'])
    print('%-58s liq=%9s vol24=%9s nmk=%2d inwin=%s tags=%s' % (str(e['title'])[:58],e.get('liq'),e.get('vol24'),len(e['markets']),iw,e.get('tags')))
json.dump(evs, open('/home/ubuntu/paper-sim/round21/raw/events_sea_21.json','w'), indent=1)
print('saved events_sea_21.json', len(evs))
