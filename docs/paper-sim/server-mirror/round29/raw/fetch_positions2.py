import json, urllib.request, time

BASE_G='https://gamma-api.polymarket.com'
def get(url):
    req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

out={'ts':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'events':{}}

def ev_by_slug(slug):
    try:
        d=get(BASE_G+'/events?slug='+slug)
        return d[0] if d else None
    except Exception as e:
        return {'error':str(e)}

for slug in ['which-party-will-win-the-senate-in-2026','which-party-will-win-the-house-in-2026','iowa-senate-election-winner','texas-senate-election-winner','ohio-senate-election-winner','us-iran-ceasefire-continues-throughptptpt']:
    ev=ev_by_slug(slug)
    out['events'][slug]=ev
    if ev and 'error' not in ev:
        print('EV:',ev.get('title','?')[:60],'| id=',ev.get('id'))
        for m in ev.get('markets',[]):
            q=m.get('question','?')
            if any(t in q.lower() for t in ['democrat','republican','party','continues through october 31','continues through november 30']):
                print('   ',q[:75],'| px=',m.get('outcomePrices'),'| closed=',m.get('closed'),'| end=',m.get('endDate'),'| vol24=',m.get('volume24hr'))
    else:
        print(slug,'->',ev if ev else 'NONE')
    time.sleep(1.2)

json.dump(out,open('/home/ubuntu/paper-sim/round29/raw/positions_events.json','w'),indent=1)
print('saved')
