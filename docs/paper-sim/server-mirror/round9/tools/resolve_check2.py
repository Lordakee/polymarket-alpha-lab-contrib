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
# search closed crypto events
for slug in ['crypto','ethereum','cryptocurrency']:
    params={'tag_slug':slug,'closed':'true','end_date_min':'2026-10-19T00:00:00Z','end_date_max':'2026-10-22T00:00:00Z','limit':100}
    try:
        res=get(BASE+'/events?'+urllib.parse.urlencode(params))
        print(f'=== {slug}: {len(res)} closed events')
        for e in res:
            t=e.get('title','')
            for m in e.get('markets',[]):
                q=m.get('question','')
                print('EV:',t[:55],'| Q:',q[:80],'| res:',m.get('resolved'),'| px:',m.get('outcomePrices'))
    except Exception as ex:
        print(slug,'ERR',ex)
    time.sleep(0.3)
