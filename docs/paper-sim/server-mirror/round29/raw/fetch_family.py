import json, urllib.request, time
def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=30) as r: return json.load(r)
ev=get('https://gamma-api.polymarket.com/events/1038648')
print('EVENT:',ev.get('title'))
for m in ev.get('markets',[]):
    try: px=json.loads(m.get('outcomePrices','[]'))
    except: px=[]
    print(f"{m.get('question','?')[:55]:57} px={px} closed={m.get('closed')} resolved={m.get('resolved')} resolvedBy={m.get('resolvedBy')} end={m.get('endDate')}")
json.dump(ev,open('/home/ubuntu/paper-sim/round29/raw/ceasefire_event_full.json','w'),indent=1)
