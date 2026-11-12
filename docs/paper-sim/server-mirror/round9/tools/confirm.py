import json, urllib.request, time

def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            if i==tries-1: raise
            time.sleep(2)

BASE='https://gamma-api.polymarket.com'
for mid in ['5653747']:
    m=get(BASE+'/markets/%s'%mid)
    print('Q:',m.get('question'))
    print('closed:',m.get('closed'),'| resolved:',m.get('resolved'),'| prices:',m.get('outcomePrices'))
    print('winner:',m.get('winner'),'| umaStatus:',m.get('umaResolutionStatus'))
