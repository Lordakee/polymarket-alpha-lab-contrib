import json, urllib.request, urllib.parse, time
def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=30) as r: return json.load(r)
out={}
# search events by candidate/race keywords
for q in ['kansas-senate-election-winner','alaska-senate-election-winner','maine-senate-election-winner','michigan-senate-election-winner']:
    try:
        d=get('https://gamma-api.polymarket.com/events?slug='+q)
        ev=d[0] if d else None
        if ev:
            mkts=[]
            for m in ev.get('markets',[]):
                try: px=json.loads(m.get('outcomePrices','[]'))
                except: px=[]
                if px and px[0] not in (None,'0','1'):
                    mkts.append({'q':m.get('question')[:70],'px':px,'bid':m.get('bestBid'),'ask':m.get('bestAsk'),'v24':m.get('volume24hr'),'liq':m.get('liquidityNum'),'end':m.get('endDate')})
            out[q]={'ev':ev.get('title'),'mkts':mkts}
            print('==',q)
            for m in mkts[:6]:
                print('  ',m['q'],'| px',m['px'],'| bid/ask',m['bid'],m['ask'],'| v24',m['v24'],'| liq',m['liq'])
    except Exception as e:
        print(q,'ERR',str(e)[:60])
    time.sleep(1.2)
# Fed December hike market
try:
    d=get('https://gamma-api.polymarket.com/markets?slug=will-the-fed-increase-interest-rates-by-25-bps-after-the-december-2026-meeting')
    m=d[0] if d else {}
    out['fed_dec_hike']=m
    print('== fed dec hike')
    print(m.get('question'),'| px',m.get('outcomePrices'),'| bid/ask',m.get('bestBid'),m.get('bestAsk'),'| v24',m.get('volume24hr'),'| liq',m.get('liquidityNum'),'| end',m.get('endDate'))
    print('desc:',(m.get('description') or '')[:600])
except Exception as e:
    print('fed ERR',e)
json.dump(out,open('/home/ubuntu/paper-sim/round29/raw/race_fed_markets.json','w'),indent=1)
