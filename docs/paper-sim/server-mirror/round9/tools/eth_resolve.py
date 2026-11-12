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
# search events directly
for q in ['Ethereum above on October 20','ETH October 20','Ethereum October 20 2400']:
    params={'search':q,'limit':15,'closed':'true'}
    try:
        res=get(BASE+'/events?'+urllib.parse.urlencode(params))
        for e in res:
            t=e.get('title','')
            if 'ctober' in t or 'ETH' in t.upper():
                print('EV:',t[:70],'end:',(e.get('endDate') or '')[:19])
                for m in e.get('markets',[]):
                    print('   Q:',m.get('question','')[:75],'| px:',m.get('outcomePrices'),'| resolved:',m.get('resolved'),'| closed:',m.get('closed'))
    except Exception as ex: print('ERR',q,ex)
    time.sleep(0.4)
