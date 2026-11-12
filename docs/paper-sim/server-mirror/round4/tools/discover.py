import json, urllib.request, urllib.parse, sys, time

BASE='https://gamma-api.polymarket.com'

def get(url):
    req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def events(params):
    qs=urllib.parse.urlencode(params)
    out=[]
    offset=0
    while True:
        p=dict(params); p['offset']=offset; p['limit']=100
        batch=get(BASE+'/events?'+urllib.parse.urlencode(p))
        out.extend(batch)
        if len(batch)<100: return out
        offset+=100
        if offset>2000: return out

# discovery sweeps: tag-based + search
queries = {
  'btc_tag': {'tag_slug':'bitcoin','closed':'false','order':'volume24hr','ascending':'false'},
  'eth_tag': {'tag_slug':'ethereum','closed':'false','order':'volume24hr','ascending':'false'},
  'crypto_tag': {'tag_slug':'crypto','closed':'false','order':'volume24hr','ascending':'false'},
  'gold_tag': {'tag_slug':'gold','closed':'false','order':'volume24hr','ascending':'false'},
  'oil_tag': {'tag_slug':'oil','closed':'false','order':'volume24hr','ascending':'false'},
  'fed_tag': {'tag_slug':'fed','closed':'false','order':'volume24hr','ascending':'false'},
  'cpi_search': {'q':'CPI','closed':'false','order':'volume24hr','ascending':'false'},
  'fed_search': {'q':'fed rate','closed':'false','order':'volume24hr','ascending':'false'},
  'politics_search': {'q':'election runoff','closed':'false','order':'volume24hr','ascending':'false'},
  'nba_tag': {'tag_slug':'nba','closed':'false','order':'volume24hr','ascending':'false'},
  'epl_search': {'q':'premier league','closed':'false','order':'volume24hr','ascending':'false'},
  'ucl_search': {'q':'champions league','closed':'false','order':'volume24hr','ascending':'false'},
  'soccer_search': {'q':'soccer match','closed':'false','order':'volume24hr','ascending':'false'},
  'nfl_search': {'q':'nfl','closed':'false','order':'volume24hr','ascending':'false'},
  'mlb_search': {'q':'world series','closed':'false','order':'volume24hr','ascending':'false'},
  'nhl_search': {'q':'nhl','closed':'false','order':'volume24hr','ascending':'false'},
  'ufc_search': {'q':'ufc','closed':'false','order':'volume24hr','ascending':'false'},
  'spy_search': {'q':'spy','closed':'false','order':'volume24hr','ascending':'false'},
  'snp_search': {'q':'s&p','closed':'false','order':'volume24hr','ascending':'false'},
  'amap_search': {'q':'amapa','closed':'false'},
  'french_search': {'q':'french','closed':'false','order':'volume24hr','ascending':'false'},
}
res={}
for name,p in queries.items():
    try:
        ev=events(p)
        res[name]=ev
        print(name, len(ev), flush=True)
    except Exception as e:
        print(name,'ERR',e, flush=True)
    time.sleep(0.3)
json.dump(res, open('/home/ubuntu/paper-sim/round4/raw/discover1.json','w'))

# summarize: for each sweep, list event title / slug / end date / vol24 / market count
summary=[]
for name,evs in res.items():
    for e in evs:
        summary.append({'sweep':name,'title':e.get('title'),'slug':e.get('slug'),
          'end':e.get('endDate'),'vol24':e.get('volume24hr'),'liquidity':e.get('liquidity'),
          'n_markets':len(e.get('markets',[])),'id':e.get('id')})
json.dump(summary, open('/home/ubuntu/paper-sim/round4/raw/discover1_summary.json','w'), indent=1)
print('done', len(summary))
