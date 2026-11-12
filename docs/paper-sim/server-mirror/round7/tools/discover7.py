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
 # soccer window: through Wed Oct 22 games (end Thu morning UTC)
 'soccer':  {'tag_slug':'soccer','closed':'false','order':'liquidity','ascending':'false',
             'end_date_min':'2026-10-20T00:00:00Z','end_date_max':'2026-10-23T12:00:00Z'},
 'ucl':     {'tag_slug':'champions-league','closed':'false','order':'liquidity','ascending':'false',
             'end_date_min':'2026-10-20T00:00:00Z','end_date_max':'2026-10-23T12:00:00Z'},
 'crypto':  {'tag_slug':'crypto','closed':'false','order':'liquidity','ascending':'false'},
 'eth':     {'tag_slug':'ethereum','closed':'false','order':'liquidity','ascending':'false'},
 'btc':     {'tag_slug':'bitcoin','closed':'false','order':'liquidity','ascending':'false'},
 'nba':     {'tag_slug':'nba','closed':'false','order':'liquidity','ascending':'false',
             'end_date_min':'2026-10-20T00:00:00Z','end_date_max':'2026-10-25T00:00:00Z'},
 'nfl':     {'tag_slug':'nfl','closed':'false','order':'liquidity','ascending':'false',
             'end_date_min':'2026-10-20T00:00:00Z','end_date_max':'2026-10-23T00:00:00Z'},
 'fed':     {'tag_slug':'fomc','closed':'false','order':'liquidity','ascending':'false'},
 'econ':    {'tag_slug':'economics','closed':'false','order':'liquidity','ascending':'false'},
 'politics':{'tag_slug':'politics','closed':'false','order':'liquidity','ascending':'false'},
 'mlb':     {'tag_slug':'mlb','closed':'false','order':'liquidity','ascending':'false'},
 'ufc':     {'tag_slug':'ufc','closed':'false','order':'liquidity','ascending':'false'},
 'nhl':     {'tag_slug':'nhl','closed':'false','order':'liquidity','ascending':'false'},
}
res={}
for name,p in sweeps.items():
    for attempt in range(2):
        try:
            res[name]=events(p)
            print(name, len(res[name]), flush=True)
            break
        except Exception as e:
            print(name,'ERR',e, flush=True)
            if attempt==1: res[name]=[]
    time.sleep(0.4)

json.dump(res, open('/home/ubuntu/paper-sim/round7/raw/discover7.json','w'))
print('saved')

# quick summary print
for name in res:
    print('='*15, name)
    shown=0
    for e in sorted(res[name], key=lambda x:-(x.get('liquidityNum') or 0)):
        if shown>=18: break
        liq=e.get('liquidityNum') or 0
        vol24=e.get('volume24hr') or 0
        if name in ('crypto','eth','btc') and liq<30000: continue
        if name in ('nba','nfl','soccer','ucl') and liq<30000: continue
        if name not in ('crypto','eth','btc','nba','nfl','soccer','ucl') and liq<20000: continue
        print('  %-60s liq=%9d vol24=%9d end=%s' % (str(e.get('title'))[:60], liq, vol24, str(e.get('endDate'))[:16]))
        shown+=1
