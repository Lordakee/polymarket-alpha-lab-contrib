import json, urllib.request, time, datetime

def get(url):
    req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

out={}
b=json.load(open('/home/ubuntu/paper-sim/round29/raw/ceasefire_hist_book.json'))['ceasefire_book']
bids=sorted(b['bids'],key=lambda x:-float(x['price']))[:5]
asks=sorted(b['asks'],key=lambda x:float(x['price']))[:5]
print('best bids:',[(x['price'],x['size']) for x in bids])
print('best asks:',[(x['price'],x['size']) for x in asks])
print('last:',b.get('last_trade_price'))
time.sleep(1.0)
tok='67102598924726349989742049657609063097299442010642912942032681022413402597017'
end=int(time.time()); start=end-8*86400
try:
    h=get(f'https://clob.polymarket.com/prices-history?market={tok}&startTs={start}&endTs={end}&fidelity=60')
    out['hist']=h
    pts=h.get('history',[])
    print('points:',len(pts))
    for p in pts[::8]:
        print(datetime.datetime.utcfromtimestamp(p['t']).strftime('%m-%d %H:%M'),p['p'])
except Exception as e:
    print('hist ERR',e)
json.dump(out,open('/home/ubuntu/paper-sim/round29/raw/ceasefire_hist2.json','w'),indent=1)
