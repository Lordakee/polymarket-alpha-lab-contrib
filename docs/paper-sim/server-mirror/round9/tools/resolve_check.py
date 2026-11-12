import json, urllib.request, urllib.parse, time

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
# 1) ETH daily markets closed on Oct 20-21
params={'tag_slug':'eth','closed':'true','end_date_min':'2026-10-20T00:00:00Z','end_date_max':'2026-10-22T00:00:00Z','limit':100}
res=get(BASE+'/events?'+urllib.parse.urlencode(params))
print('=== CLOSED ETH events Oct20-21:',len(res))
for e in res:
    for m in e.get('markets',[]):
        q=m.get('question','')
        if 'October 20' in q or 'October 21' in q or 'Oct 20' in q or 'above' in q.lower():
            print('EV:',e.get('title','?')[:60])
            print('  Q:',q[:90])
            print('  resolved:',m.get('resolved'),'| prices:',m.get('outcomePrices'),'| winner:',m.get('umaResolutionStatus',''),'| outcome:',m.get('outcome',''))
