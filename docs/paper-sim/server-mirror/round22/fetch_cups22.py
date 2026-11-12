"""Round-22 CUPS+RoW sub-scan: Gamma sweep for EFL Cup Thu, DFB-Pokal, Coppa Italia,
Copa del Rey, UECL, + soccer catch-all. Window Oct 29 01:15 -> Oct 30 01:15 UTC."""
import json, urllib.request, urllib.parse, time

BASE='https://gamma-api.polymarket.com'
LO='2026-10-29T00:00:00Z'; HI='2026-10-31T00:00:00Z'
WINLO='2026-10-29T01:15:00Z'; WINHI='2026-10-30T01:15:00Z'

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
        inwin = WINLO<=g<=WINHI if g else (WINLO<=slim['startDate']<=WINHI)
        slim['markets'].append({
          'id':str(m.get('id')),'q':m.get('question'),'slug':m.get('slug'),
          'group':m.get('groupItemTitle'),'outcomes':m.get('outcomes'),
          'prices':m.get('outcomePrices'),'tokens':m.get('clobTokenIds'),
          'line':m.get('line') or m.get('handicap'),'gameStartTime':g,
          'liq':m.get('liquidityNum'),'vol24':m.get('volume24hr'),
          'bestBid':m.get('bestBid'),'bestAsk':m.get('bestAsk'),
          'spread':m.get('spread'),'closed':m.get('closed'),'active':m.get('active'),
          'in_window':inwin})
    return slim

result={}
# 1) catch-all soccer with date filter (all events kicking off in window)
seen=set(); catch=[]
for e in sweep({'tag_slug':'soccer','start_date_min':LO,'start_date_max':HI}):
    eid=str(e.get('id'))
    if eid in seen: continue
    seen.add(eid); catch.append(slim_event(e))
result['soccer_catchall']=catch
print('catchall events in Oct29-31 date range:', len(catch))

# 2) competition tags (for safety, wider date net)
for tag in ['efl-cup','dfb-pokal','copa-del-rey','coppa-italia',
            'uefa-conference-league','conference-league','uecl',
            'carabao-cup','efa-cup','uefa-conference-league-2026',
            'conference-league-2026','dfb-pokal-2026','coppa-italia-2026',
            'copa-del-rey-2026','efl-cup-2026','mls','brasileirao','liga-mx','j-league','a-league']:
    try:
        evs=sweep({'tag_slug':tag})
    except Exception as ex:
        print('tag',tag,'ERR',repr(ex)); continue
    keep=[]
    for e in evs:
        mks=(e.get('markets') or [])
        gst=[norm(m.get('gameStartTime')) for m in mks]
        gst=[g for g in gst if g]
        sd=norm(e.get('startDate'))
        hit=any(LO<=g<=HI for g in gst) or (LO<=sd<=HI)
        if not hit: continue
        s=slim_event(e)
        if s['id'] not in seen: keep.append(s)  # catch-all dedupe only for non-soccer-tag? keep both, dedupe within tag result
        else: keep.append(s)
    result['tag_'+tag]=keep
    print('tag',tag,'events in net:',len(keep))
    time.sleep(1.0)

json.dump(result, open('/home/ubuntu/paper-sim/round22/raw/gamma_sweep22.json','w'), indent=1)
# summary print
for k,v in result.items():
    if not v: continue
    for e in v:
        inw=any(m['in_window'] for m in e['markets']) or (WINLO<=(e['startDate'] or '')<=WINHI)
        if inw:
            print('INWIN[%s] %s | start=%s | liq=%s vol24=%s mks=%d' % (k, e['title'], e['startDate'], e['liq'], e['vol24'], len(e['markets'])))
