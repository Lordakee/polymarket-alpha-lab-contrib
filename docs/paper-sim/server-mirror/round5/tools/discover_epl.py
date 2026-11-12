import json, urllib.request, urllib.parse, time

BASE='https://gamma-api.polymarket.com'
def get(url, tries=3):
    for i in range(tries):
        try:
            req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
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
        if offset>2000: return out

res={}
sweeps={
 # PRIMARY: EPL weekend fixtures Oct 17-20
 'epl_tag': {'tag_slug':'epl','closed':'false','order':'volume24hr','ascending':'false','end_date_min':'2026-10-16T00:00:00Z','end_date_max':'2026-10-21T00:00:00Z'},
 'epl_tag2': {'tag_slug':'premier-league','closed':'false','order':'volume24hr','ascending':'false','end_date_min':'2026-10-16T00:00:00Z','end_date_max':'2026-10-21T00:00:00Z'},
 # SECONDARY: UCL MD3 Oct 21-22
 'ucl_tag': {'tag_slug':'champions-league','closed':'false','order':'volume24hr','ascending':'false','end_date_min':'2026-10-20T00:00:00Z','end_date_max':'2026-10-24T00:00:00Z'},
 # NBA opening week
 'nba_tag': {'tag_slug':'nba','closed':'false','order':'volume24hr','ascending':'false','end_date_min':'2026-10-19T00:00:00Z','end_date_max':'2026-10-25T00:00:00Z'},
 # UFC oct 24
 'ufc_search': {'q':'ufc','closed':'false','order':'volume24hr','ascending':'false'},
 # SPY october
 'spy_search': {'q':'spy','closed':'false','order':'volume24hr','ascending':'false'},
 # ETH weekly Oct 19-25
 'eth_tag': {'tag_slug':'ethereum','closed':'false','order':'volume24hr','ascending':'false'},
}
for name,p in sweeps.items():
    try:
        ev=events(p)
        res[name]=ev
        print(name, len(ev), flush=True)
    except Exception as e:
        print(name,'ERR',e, flush=True)
    time.sleep(0.4)
json.dump(res, open('/home/ubuntu/paper-sim/round5/raw/discover1.json','w'))

summary=[]
for name,evs in res.items():
    for e in evs:
        liq=0.0
        try: liq=sum(float(m.get('liquidityNum') or 0) for m in e.get('markets',[]))
        except: pass
        summary.append({'sweep':name,'title':e.get('title'),'slug':e.get('slug'),
          'start':e.get('startDate'),'end':e.get('endDate'),'vol24':e.get('volume24hr'),
          'liq_sum':round(liq,0),'n_markets':len(e.get('markets',[])),'id':e.get('id')})
json.dump(summary, open('/home/ubuntu/paper-sim/round5/raw/discover1_summary.json','w'), indent=1)
print('done', len(summary))
