import json, urllib.request, urllib.parse, time

BASE = 'https://gamma-api.polymarket.com'
def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            if i==tries-1: raise
            time.sleep(2)

# Search for ETH daily markets (closed and open)
for closed in ['true','false']:
    params = {'search':'ETH above','closed':closed,'limit':30,'order':'endDate','ascending':'false'}
    try:
        res = get(BASE+'/events?'+urllib.parse.urlencode(params))
        print(f'--- ETH above, closed={closed}: {len(res)} events')
        for e in res[:20]:
            print(e.get('title','?')[:80],'|',e.get('endDate','?')[:19],'| closed:',e.get('closed'))
            for m in e.get('markets',[])[:3]:
                omp = m.get('outcomePrices','')
                print('   ',m.get('question','?')[:70],'->',omp)
    except Exception as ex:
        print('ERR',ex)
    time.sleep(0.3)
