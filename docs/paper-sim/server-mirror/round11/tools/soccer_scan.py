import json, urllib.request, urllib.parse, time

BASE='https://gamma-api.polymarket.com'
def get(url,tries=3):
    for i in range(tries):
        try:
            req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as r: return json.load(r)
        except Exception as e:
            if i==tries-1: raise
            time.sleep(2)

def events(params):
    out=[]; offset=0
    while True:
        p=dict(params); p['offset']=offset; p['limit']=100
        batch=get(BASE+'/events?'+urllib.parse.urlencode(p))
        out.extend(batch)
        if len(batch)<100: return out
        offset+=100
        if offset>1500: return out

res={}
# broad soccer sweep covering UEL tomorrow + weekend leagues + UCL MD4 early
for name,p in {
  'soccer_wk':{'tag_slug':'soccer','closed':'false','order':'volume24hr','ascending':'false','end_date_min':'2026-10-21T00:00:00Z','end_date_max':'2026-10-27T23:59:00Z'},
  'soccer_all':{'tag_slug':'soccer','closed':'false','order':'volume24hr','ascending':'false','end_date_min':'2026-10-27T00:00:00Z','end_date_max':'2026-11-03T23:59:00Z'},
}.items():
    try: res[name]=events(p)
    except Exception as e: res[name]=[]; print(name,'ERR',e)
    print('='*12,name,len(res[name]))
    for e in res[name][:80]:
        st=str(e.get('startDate'))[:16]
        vol=e.get('volume24hr') or 0
        print('  %-58s start=%s vol24=%8d mkts=%d'%(str(e.get('title'))[:58],st,vol,len(e.get('markets') or [])))
    time.sleep(0.3)
json.dump(res,open('/home/ubuntu/paper-sim/round11/raw/soccer_scan.json','w'))
print('saved')
