import json, urllib.request, urllib.parse, time

BASE_G='https://gamma-api.polymarket.com'
def get(url):
    req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

out={'ts':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'markets':{},'books':{}}

def market_by_slug(slug):
    try:
        d=get(BASE_G+'/markets?slug='+slug)
        return d[0] if d else None
    except Exception as e:
        return {'error':str(e)}

slugs=[
 'which-party-will-win-the-senate-in-2026',
 'which-party-will-win-the-house-in-2026',
 'us-x-iran-ceasefire-continues-through-october-31-20260917',
 'iowa-senate-election-winner',
 'texas-senate-election-winner',
 'ohio-senate-election-winner',
]
for s in slugs:
    m=market_by_slug(s)
    out['markets'][s]=m
    if m and 'error' not in m:
        print(s,'|',m.get('question','?')[:60],'| px=',m.get('outcomePrices'),'| closed=',m.get('closed'),'| active=',m.get('active'),'| end=',m.get('endDate'),'| umaResolutionStatus=',m.get('umaResolutionStatus'),'| acceptingOrders=',m.get('acceptingOrders'))
    else:
        print(s,'ERR',m)
    time.sleep(1.2)

json.dump(out,open('/home/ubuntu/paper-sim/round29/raw/positions_markets.json','w'),indent=1)
print('saved')
