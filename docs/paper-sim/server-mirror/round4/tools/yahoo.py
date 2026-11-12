import json, urllib.request, time

def yahoo(sym, interval='1d', rng='3mo'):
    url='https://query1.finance.yahoo.com/v8/finance/chart/%s?interval=%s&range=%s' % (sym, interval, rng)
    req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as r: return json.load(r)

out={}
for sym in ['BTC-USD','PAXG-USD','CL=F','SPY','^VIX','GC=F','ETH-USD']:
    try:
        out[sym]=yahoo(sym,'1d','3mo'); print('OK',sym, flush=True)
    except Exception as e: print('ERR',sym,e, flush=True)
    time.sleep(0.5)
# intraday for spot freshness
for sym in ['BTC-USD','PAXG-USD','CL=F','SPY','^VIX']:
    try:
        out[sym+'_60m']=yahoo(sym,'60m','5d'); print('OK',sym,'60m', flush=True)
    except Exception as e: print('ERR',sym,'60m',e, flush=True)
    time.sleep(0.5)
json.dump(out, open('/home/ubuntu/paper-sim/round4/raw/yahoo.json','w'))
# quick spot + vol summary
import math
def rvol(sym, days):
    d=out[sym]['chart']['result'][0]
    ts=d['timestamp']; q=d['indicators']['quote'][0]['close']
    rows=[(t,c) for t,c in zip(ts,q) if c is not None]
    rows=rows[-(days+1):]
    rets=[math.log(rows[i+1][1]/rows[i][1]) for i in range(len(rows)-1)]
    mu=sum(rets)/len(rets); var=sum((r-mu)**2 for r in rets)/(len(rets)-1)
    sd=var**0.5
    ann=sd*math.sqrt(365)
    return rows[-1][1], rows[-1][0], ann, len(rets)
import datetime
for sym in ['BTC-USD','PAXG-USD','CL=F','SPY','ETH-USD','GC=F']:
    for days in (10,21,63):
        try:
            px,ts,ann,n=rvol(sym,days)
            print('%-10s %2dd spot %-10.2f (as of %s UTC) rvol %.1f%% (n=%d)' % (sym,days,px,datetime.datetime.utcfromtimestamp(ts).strftime('%m-%d %H:%M'),ann*100,n))
        except Exception as e: print(sym,days,'ERR',e)
d=out['^VIX']['chart']['result'][0]
q=d['indicators']['quote'][0]['close']; ts=d['timestamp']
last=[(t,c) for t,c in zip(ts,q) if c is not None][-1]
print('VIX last close %.2f at %s' % (last[1], datetime.datetime.utcfromtimestamp(last[0]).strftime('%m-%d %H:%M')))
d5=out['^VIX_60m']['chart']['result'][0]
q5=d5['indicators']['quote'][0]['close']; t5=d5['timestamp']
l5=[(t,c) for t,c in zip(t5,q5) if c is not None][-1]
print('VIX latest  %.2f at %s UTC' % (l5[1], datetime.datetime.utcfromtimestamp(l5[0]).strftime('%m-%d %H:%M')))
for sym in ['BTC-USD','PAXG-USD','CL=F','SPY']:
    d5=out[sym+'_60m']['chart']['result'][0]
    q5=d5['indicators']['quote'][0]['close']; t5=d5['timestamp']
    l5=[(t,c) for t,c in zip(t5,q5) if c is not None][-1]
    lo=[c for c in d5['indicators']['quote'][0]['low'] if c is not None]
    print('%-10s latest %-10.2f at %s UTC | 5d low %.2f' % (sym,l5[1],datetime.datetime.utcfromtimestamp(l5[0]).strftime('%m-%d %H:%M'),min(lo)))
