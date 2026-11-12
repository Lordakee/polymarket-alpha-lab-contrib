import json, urllib.request, time

def get(url, tries=3, hdrs=None):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=hdrs or {'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            if i==tries-1: raise
            time.sleep(2)

out={}
for sym in ['ETH-USD','BTC-USD']:
    for rng,iv in [('3mo','1d'),('1mo','1h'),('5d','15m')]:
        u='https://query1.finance.yahoo.com/v8/finance/chart/%s?range=%s&interval=%s'%(sym,rng,iv)
        try:
            out['%s_%s_%s'%(sym,rng,iv)]=get(u, hdrs={'User-Agent':'Mozilla/5.0'})
            m=out['%s_%s_%s'%(sym,rng,iv)]['chart']['result'][0]['meta']
            print(sym,rng,iv,'px=',m.get('regularMarketPrice'),'lo24=',m.get('regularMarketDayLow'),'hi24=',m.get('regularMarketDayHigh'), flush=True)
        except Exception as e:
            print('ERR',sym,rng,iv,repr(e), flush=True)
        time.sleep(0.5)

json.dump(out, open('/home/ubuntu/paper-sim/round9/raw/yahoo_crypto9.json','w'))
print('saved')
