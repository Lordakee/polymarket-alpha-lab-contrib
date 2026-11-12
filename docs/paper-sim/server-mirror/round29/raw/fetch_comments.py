import json, urllib.request, time
def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=25) as r: return json.load(r)
tries=[
 'https://gamma-api.polymarket.com/comments?market=4641065&limit=50&sort=NEWEST',
 'https://gamma-api.polymarket.com/comments?marketId=4641065',
 'https://data-api.polymarket.com/comments?market=4641065',
]
for u in tries:
    try:
        d=get(u)
        print('OK',u)
        print(json.dumps(d)[:4000])
        json.dump(d,open('/home/ubuntu/paper-sim/round29/raw/pm_comments.json','w'),indent=1)
        break
    except Exception as e:
        print('ERR',u,str(e)[:80])
    time.sleep(1.2)
