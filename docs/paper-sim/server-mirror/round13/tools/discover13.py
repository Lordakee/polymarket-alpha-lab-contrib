"""Round-13 soccer discovery: Polymarket soccer events, markets Oct 23-29."""
import json, urllib.request, urllib.parse, time

BASE='https://gamma-api.polymarket.com'
def get(url, tries=6):
    last=None
    for i in range(tries):
        try:
            req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as r: return json.load(r)
        except Exception as e:
            last=e; time.sleep(2.5+2*i)
    raise last

LO='2026-10-23T00:00:00Z'; HI='2026-10-29T23:59:59Z'

def sweep(order):
    out=[]; offset=0
    while True:
        url=BASE+'/events/pagination?'+urllib.parse.urlencode({
            'limit':100,'tag':'soccer','active':'true','closed':'false',
            'order':order,'ascending':'false','offset':offset})
        resp=get(url)
        batch=resp.get('data') if isinstance(resp,dict) else resp
        out.extend(batch)
        if len(batch)<100: return out
        offset+=100
        if offset>=2000: return out
        time.sleep(0.8)

def in_window(ev):
    sd=str(ev.get('startDate') or '')
    if LO[:10] <= sd[:10] <= HI[:10]: return True
    for m in (ev.get('markets') or []):
        g=str(m.get('gameStartTime') or '')
        if LO[:10] <= g[:10] <= HI[:10]: return True
    return False

seen={}
for order in ('volume24hr','liquidity'):
    try: evs=sweep(order)
    except Exception as e:
        print('SWEEP ERR',order,repr(e)); continue
    n=0
    for e in evs:
        eid=str(e.get('id'))
        if not in_window(e): continue
        n+=1
        slim={
          'id':eid,'title':e.get('title'),'slug':e.get('slug'),
          'startDate':e.get('startDate'),'endDate':e.get('endDate'),
          'liq':e.get('liquidityNum'),'vol24':e.get('volume24hr'),
          'vol':e.get('volume'),'tags':[t.get('slug') for t in (e.get('tags') or [])],
          'markets':[]}
        for m in (e.get('markets') or []):
            g=str(m.get('gameStartTime') or '')
            if not (LO[:10] <= g[:10] <= HI[:10]): continue
            slim['markets'].append({
              'id':str(m.get('id')),'q':m.get('question'),'slug':m.get('slug'),
              'group':m.get('groupItemTitle'),'type':m.get('marketType'),
              'outcomes':m.get('outcomes'),'prices':m.get('outcomePrices'),
              'tokens':m.get('clobTokenIds'),'line':m.get('line') or m.get('handicap'),
              'gameStartTime':m.get('gameStartTime'),
              'liq':m.get('liquidityNum'),'vol24':m.get('volume24hr'),
              'bestBid':m.get('bestBid'),'bestAsk':m.get('bestAsk'),
              'spread':m.get('spread'),'closed':m.get('closed'),'active':m.get('active')})
        if slim['markets']:
            seen[eid]=slim
    print('order=%s total=%d in_window=%d'%(order,len(evs),n))
    time.sleep(0.5)

evs=list(seen.values())
evs.sort(key=lambda e: -(e.get('liq') or 0))
print('unique window events:', len(evs))
for e in evs:
    print('  %-58s liq=%9s vol24=%9s nmk=%d tags=%s start=%s'%(
        str(e['title'])[:58], e.get('liq'), e.get('vol24'), len(e['markets']),
        ','.join([t for t in (e.get('tags') or []) if t in ('epl','premier-league','la-liga','laliga','serie-a','bundesliga','ligue-1','ligue1','eredivisie','primeira-liga','champions-league','europa-league','mls','brazil-serie-a','laliga-santander','soccer')][:4]), str(e.get('startDate'))[:16]))
json.dump(evs, open('/home/ubuntu/paper-sim/round13/raw/events_window.json','w'), indent=1)
print('saved events_window.json')
