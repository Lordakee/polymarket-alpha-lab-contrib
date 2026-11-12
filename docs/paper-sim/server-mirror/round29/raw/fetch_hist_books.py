import json, urllib.request, time

def get(url):
    req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

out={}
# ceasefire YES token price history (1h, last 8 days)
tok='67102598924726349989742049657609063097299442010642912942032681022413402597017'
try:
    h=get('https://clob.polymarket.com/prices-history?market='+tok+'&interval=6d&fidelity=60')
    out['ceasefire_hist']=h
    pts=h.get('history',[])
    print('ceasefire hist points:',len(pts))
    for p in pts[::6]:
        import datetime
        print(datetime.datetime.utcfromtimestamp(p['t']).strftime('%m-%d %H:%M'),p['p'])
except Exception as e:
    print('hist ERR',e)
time.sleep(1.2)
# ceasefire YES book
try:
    b=get('https://clob.polymarket.com/book?token_id='+tok)
    out['ceasefire_book']=b
    print('BOOK bids top5:',b['bids'][-5:][::-1] if b.get('bids') else None)
    print('BOOK asks top5:',b['asks'][:5] if b.get('asks') else None)
    print('last:',b.get('last_trade_price'))
except Exception as e:
    print('book ERR',e)
json.dump(out,open('/home/ubuntu/paper-sim/round29/raw/ceasefire_hist_book.json','w'),indent=1)
print('saved')
