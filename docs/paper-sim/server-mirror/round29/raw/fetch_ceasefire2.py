import json, urllib.request, time, datetime
def get(url):
    req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r: return json.load(r)
m=json.load(open('/home/ubuntu/paper-sim/round29/raw/ceasefire_mkt.json'))['market']
print('FULL DESC TAIL:')
print((m.get('description') or '')[1900:])
print('resolutionSource:',m.get('resolutionSource'))
print('events field / footer:',(m.get('events') or '')[:100] if isinstance(m.get('events'),str) else 'n/a')
time.sleep(1.0)
# Nov 30 leg history - find token
m2=get('https://gamma-api.polymarket.com/markets/4713483')
print('NOV30 Q:',m2.get('question'),'px:',m2.get('outcomePrices'),'best:',m2.get('bestBid'),m2.get('bestAsk'))
tok2=json.loads(m2.get('clobTokenIds','[]'))[0]
end=int(time.time()); start=end-5*86400
h=get(f'https://clob.polymarket.com/prices-history?market={tok2}&startTs={start}&endTs={end}&fidelity=60')
pts=h.get('history',[])
print('nov30 points:',len(pts))
prev=None
for p in pts:
    if prev is None or abs(p['p']-prev)>0.05:
        print(datetime.datetime.fromtimestamp(p['t'],datetime.timezone.utc).strftime('%m-%d %H:%M'),p['p'])
    prev=p['p']
json.dump({'m2':m2,'hist':h},open('/home/ubuntu/paper-sim/round29/raw/ceasefire_nov30.json','w'),indent=1)
