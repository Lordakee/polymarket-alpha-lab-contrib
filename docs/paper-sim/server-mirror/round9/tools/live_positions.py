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
# search open events for our games
searches=['Como Manchester United','Bayern Arsenal','Real Madrid Leipzig','Levante Athletic']
for s in searches:
    params={'search':s,'closed':'false','limit':5}
    try:
        res=get(BASE+'/events?'+urllib.parse.urlencode(params))
        for e in res:
            t=(e.get('title') or '')
            if any(x.lower() in t.lower() for x in s.split()):
                liq=e.get('liquidityNum') or 0
                print('EV:',t[:65],'| end:',(e.get('endDate') or '')[:16],'| liq:',int(liq))
                for m in e.get('markets',[])[:14]:
                    q=m.get('question','') or m.get('groupItemTitle','')
                    pr=json.loads(m.get('outcomePrices') or '[]')
                    vol=m.get('volumeNum') or 0
                    print('   ',q[:70],'| px:',pr,'| vol:',int(vol))
    except Exception as ex: print('ERR',s,ex)
    time.sleep(0.4)
