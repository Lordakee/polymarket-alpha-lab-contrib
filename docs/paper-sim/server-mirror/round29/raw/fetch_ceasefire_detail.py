import json, urllib.request, time

def get(url):
    req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

out={}
# full market object
m=get('https://gamma-api.polymarket.com/markets/4641065')
out['market']=m
print('Q:',m.get('question'))
print('desc:',(m.get('description') or '')[:2000])
print('uma:',m.get('umaResolutionStatuses'),m.get('umaResolutionStatus'),'closed:',m.get('closed'),'accepting:',m.get('acceptingOrders'))
print('clobTokenIds:',json.loads(m.get('clobTokenIds','[]'))[0][:40],'...')
print('lastTrade:',m.get('lastTradePrice'),'bestBid:',m.get('bestBid'),'bestAsk:',m.get('bestAsk'))
json.dump(out,open('/home/ubuntu/paper-sim/round29/raw/ceasefire_mkt.json','w'),indent=1)
