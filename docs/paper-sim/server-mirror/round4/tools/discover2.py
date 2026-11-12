import json, urllib.request, urllib.parse, time

BASE='https://gamma-api.polymarket.com'
def get(url):
    req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)
def events(params):
    out=[]; offset=0
    while True:
        p=dict(params); p['offset']=offset; p['limit']=100
        batch=get(BASE+'/events?'+urllib.parse.urlencode(p))
        out.extend(batch)
        if len(batch)<100: return out
        offset+=100
        if offset>1500: return out

sweeps = {
  'nfl_tag': {'tag_slug':'nfl','closed':'false','order':'volume24hr','ascending':'false'},
  'mlb_tag': {'tag_slug':'mlb','closed':'false','order':'volume24hr','ascending':'false'},
  'nhl_tag': {'tag_slug':'nhl','closed':'false','order':'volume24hr','ascending':'false'},
  'ufc_tag': {'tag_slug':'ufc','closed':'false','order':'volume24hr','ascending':'false'},
  'epl_tag': {'tag_slug':'epl','closed':'false','order':'volume24hr','ascending':'false'},
  'ucl_tag': {'tag_slug':'ucl','closed':'false','order':'volume24hr','ascending':'false'},
  'soccer_tag': {'tag_slug':'soccer','closed':'false','order':'volume24hr','ascending':'false'},
  'equities_tag': {'tag_slug':'equities','closed':'false','order':'volume24hr','ascending':'false'},
  'stocks_tag': {'tag_slug':'stocks','closed':'false','order':'volume24hr','ascending':'false'},
  'macro_tag': {'tag_slug':'macro-indicators','closed':'false','order':'volume24hr','ascending':'false'},
  'econ_tag': {'tag_slug':'economy','closed':'false','order':'volume24hr','ascending':'false'},
  'brazil_tag': {'tag_slug':'brazil','closed':'false','order':'volume24hr','ascending':'false'},
  'basketball_tag': {'tag_slug':'basketball','closed':'false','order':'volume24hr','ascending':'false'},
  'hitprice_tag': {'tag_slug':'hit-price','closed':'false','order':'volume24hr','ascending':'false'},
}
res={}
for name,p in sweeps.items():
    for attempt in range(3):
        try:
            ev=events(p); res[name]=ev; print(name,len(ev),flush=True); break
        except Exception as e:
            print(name,'retry',attempt,e,flush=True); time.sleep(3)
    time.sleep(1.0)
json.dump(res, open('/home/ubuntu/paper-sim/round4/raw/discover2.json','w'))
summary=[]
for name,evs in res.items():
    for e in evs:
        summary.append({'sweep':name,'title':e.get('title'),'slug':e.get('slug'),
          'end':e.get('endDate'),'vol24':e.get('volume24hr'),'liquidity':e.get('liquidity'),
          'n_markets':len(e.get('markets',[])),'id':e.get('id')})
json.dump(summary, open('/home/ubuntu/paper-sim/round4/raw/discover2_summary.json','w'), indent=1)
print('done',len(summary))
