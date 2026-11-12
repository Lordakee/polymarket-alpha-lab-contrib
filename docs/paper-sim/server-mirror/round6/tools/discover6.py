import json, urllib.request, urllib.parse, time

BASE = 'https://gamma-api.polymarket.com'
def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            if i == tries-1: raise
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

sweeps = {
 'soccer': {'tag_slug':'soccer','closed':'false','order':'liquidity','ascending':'false',
            'end_date_min':'2026-10-19T00:00:00Z','end_date_max':'2026-10-21T00:00:00Z'},
 'nba':    {'tag_slug':'nba','closed':'false','order':'liquidity','ascending':'false',
            'end_date_min':'2026-10-19T00:00:00Z','end_date_max':'2026-10-22T00:00:00Z'},
 'basketball': {'tag_slug':'basketball','closed':'false','order':'liquidity','ascending':'false',
            'end_date_min':'2026-10-19T00:00:00Z','end_date_max':'2026-10-22T00:00:00Z'},
}
res={}
for name,p in sweeps.items():
    try:
        res[name]=events(p)
        print(name, len(res[name]), flush=True)
    except Exception as e:
        print(name,'ERR',e, flush=True)
    time.sleep(0.5)

json.dump(res, open('/home/ubuntu/paper-sim/round6/raw/discover6.json','w'))

W_LO='2026-10-19T12:00:00Z'  # a bit generous: 13:00Z start but allow pre 1h
W_HI='2026-10-20T02:00:00Z'
def in_win(gs):
    if not gs: return False
    # gs like 2026-10-19T18:30:00Z
    return W_LO <= gs <= W_HI

for name in ['soccer']:
    print('='*20, name, 'in-window games')
    for e in res.get(name,[]):
        gs=None
        for m in e.get('markets',[]):
            if m.get('gameStartTime'): gs=m.get('gameStartTime'); break
        liq=e.get('liquidityNum') or 0
        vol=e.get('volume24hr') or 0
        title=e.get('title'); slug=e.get('slug'); end=e.get('endDate')
        # flag window membership by endDate or gameStartTime
        marker=''
        if in_win(gs): marker='GS-IN-WIN'
        elif end and '2026-10-19' <= end[:10] <= '2026-10-20': marker='END-1920'
        print('%-9s liq=%9d vol24=%9d end=%s gs=%s | %s | %s' % (marker, liq, vol, (end or '')[:16], (gs or '')[11:16], slug, title))
