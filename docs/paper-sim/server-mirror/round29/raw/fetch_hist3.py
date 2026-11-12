import json, urllib.request, time, datetime
def get(url):
    req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r: return json.load(r)
tok='67102598924726349989742049657609063097299442010642912942032681022413402597017'
end=int(time.time()); start=end-10*3600
h=get(f'https://clob.polymarket.com/prices-history?market={tok}&startTs={start}&endTs={end}&fidelity=1')
pts=h.get('history',[])
print('points:',len(pts))
prev=None
for p in pts:
    if prev is None or abs(p['p']-prev)>0.02:
        print(datetime.datetime.fromtimestamp(p['t'],datetime.timezone.utc).strftime('%m-%d %H:%M'),p['p'])
    prev=p['p']
json.dump(h,open('/home/ubuntu/paper-sim/round29/raw/ceasefire_hist_1m.json','w'),indent=1)
