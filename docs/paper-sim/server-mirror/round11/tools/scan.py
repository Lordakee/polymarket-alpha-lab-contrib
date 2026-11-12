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
        if offset>1200: return out

sweeps={
 'uel':      {'tag_slug':'europa-league','closed':'false','order':'liquidity','ascending':'false','end_date_min':'2026-10-21T00:00:00Z','end_date_max':'2026-10-25T23:59:00Z'},
 'ucl':      {'tag_slug':'champions-league','closed':'false','order':'liquidity','ascending':'false','end_date_min':'2026-10-21T00:00:00Z','end_date_max':'2026-11-02T23:59:00Z'},
 'epl':      {'tag_slug':'premier-league','closed':'false','order':'liquidity','ascending':'false','end_date_min':'2026-10-21T00:00:00Z','end_date_max':'2026-10-28T23:59:00Z'},
 'seriea':   {'tag_slug':'serie-a','closed':'false','order':'liquidity','ascending':'false','end_date_min':'2026-10-21T00:00:00Z','end_date_max':'2026-10-28T23:59:00Z'},
 'laliga':   {'tag_slug':'la-liga','closed':'false','order':'liquidity','ascending':'false','end_date_min':'2026-10-21T00:00:00Z','end_date_max':'2026-10-28T23:59:00Z'},
 'bundesliga':{'tag_slug':'bundesliga','closed':'false','order':'liquidity','ascending':'false','end_date_min':'2026-10-21T00:00:00Z','end_date_max':'2026-10-28T23:59:00Z'},
 'ligue1':   {'tag_slug':'ligue-1','closed':'false','order':'liquidity','ascending':'false','end_date_min':'2026-10-21T00:00:00Z','end_date_max':'2026-10-28T23:59:00Z'},
 'crypto':   {'tag_slug':'crypto','closed':'false','order':'liquidity','ascending':'false'},
 'eth':      {'tag_slug':'ethereum','closed':'false','order':'liquidity','ascending':'false'},
 'btc':      {'tag_slug':'bitcoin','closed':'false','order':'liquidity','ascending':'false'},
 'nba':      {'tag_slug':'nba','closed':'false','order':'liquidity','ascending':'false','end_date_min':'2026-10-21T00:00:00Z','end_date_max':'2026-10-27T23:59:00Z'},
 'nfl':      {'tag_slug':'nfl','closed':'false','order':'liquidity','ascending':'false','end_date_min':'2026-10-21T00:00:00Z','end_date_max':'2026-10-28T23:59:00Z'},
 'mlb':      {'tag_slug':'mlb','closed':'false','order':'liquidity','ascending':'false'},
 'nhl':      {'tag_slug':'nhl','closed':'false','order':'liquidity','ascending':'false','end_date_min':'2026-10-21T00:00:00Z','end_date_max':'2026-10-28T23:59:00Z'},
 'ufc':      {'tag_slug':'ufc','closed':'false','order':'liquidity','ascending':'false','end_date_min':'2026-10-21T00:00:00Z','end_date_max':'2026-10-28T23:59:00Z'},
 'fomc':     {'tag_slug':'fomc','closed':'false','order':'liquidity','ascending':'false'},
 'brazil':   {'tag_slug':'brazil','closed':'false','order':'liquidity','ascending':'false'},
 'all_liq':  {'closed':'false','order':'liquidity','ascending':'false','end_date_min':'2026-10-21T00:00:00Z','end_date_max':'2026-11-06T23:59:00Z'},
}
res={}
for name,p in sweeps.items():
    try: res[name]=events(p)
    except Exception as e:
        print(name,'ERR',e,flush=True); res[name]=[]
        continue
    print('='*14,name,len(res[name]),'events',flush=True)
    shown=0
    for e in sorted(res[name],key=lambda x:-(x.get('liquidityNum') or 0)):
        liq=e.get('liquidityNum') or 0
        if name in ('crypto','eth','btc') and liq<20000: continue
        if shown>=25: break
        print('  %-62s liq=%9d vol24=%10d start=%s'%(str(e.get('title'))[:62],liq,e.get('volume24hr') or 0,str(e.get('startDate'))[:16]),flush=True)
        shown+=1
    time.sleep(0.3)

json.dump(res,open('/home/ubuntu/paper-sim/round11/raw/scan.json','w'))
print('saved scan.json')
