import json, math, urllib.request, urllib.parse, time
from collections import defaultdict

RAW='/home/ubuntu/paper-sim/round7/raw'
XG=json.load(open('/home/ubuntu/paper-sim/round5/raw/xg_understat.json'))  # refreshed 2026-10-20
res=json.load(open(RAW+'/discover7.json'))
LEAGUES=['EPL','La_liga','Serie_A','Bundesliga','Ligue_1']

def load(lg,se): return XG['%s_%s'%(lg,se)]

def get(url,tries=3,timeout=20):
    for i in range(tries):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
            with urllib.request.urlopen(req,timeout=timeout) as r: return json.load(r)
        except Exception:
            if i==tries-1: raise
            time.sleep(1.5)

# ---------- understat ratings ----------
_cache={}
def ratings_for(lg,LASTW,PRIOR,mode):
    key=(lg,LASTW,PRIOR,mode)
    if key in _cache: return _cache[key]
    d25=load(lg,'2025'); d26=load(lg,'2026')
    ms=[m for m in d25['dates'] if m.get('isResult')]
    bh=sum(float(m['xG']['h']) for m in ms)/len(ms)
    ba=sum(float(m['xG']['a']) for m in ms)/len(ms)
    lgf=(bh+ba)/2.0
    last={}
    for t in d25['teams'].values():
        h=t['history']
        last[t['title']]=(sum(float(x['xG']) for x in h)/len(h),sum(float(x['xGA']) for x in h)/len(h))
    r={}
    for t in d26['teams'].values():
        h=t['history']; name=t['title']
        if not h: continue
        cf=sum(float(x['xG']) for x in h)/len(h)
        ca=sum(float(x['xGA']) for x in h)/len(h)
        nc=len(h)
        if mode=='cur': f,a=cf,ca
        elif mode=='last':
            lf,la_=last.get(name,(lgf,lgf)); f,a=lf,la_
        else:
            lf,la_=last.get(name,(lgf,lgf))
            f=(nc*cf+LASTW*38*lf+PRIOR*lgf)/(nc+LASTW*38+PRIOR)
            a=(nc*ca+LASTW*38*la_+PRIOR*lgf)/(nc+LASTW*38+PRIOR)
        r[name]=(f/lgf,a/lgf)
    _cache[key]=(bh,ba,lgf,r)
    return _cache[key]

SWEEPS=[('blend .5/8 rho0',0.5,8,0.0,'blend'),('blend .5/8 DC',0.5,8,-0.08,'blend'),
 ('blend 1.0/8',1.0,8,0.0,'blend'),('blend .25/8',0.25,8,0.0,'blend'),
 ('blend .5/16',0.5,16,0.0,'blend'),('blend .5/4',0.5,4,0.0,'blend'),
 ('current-only',None,None,0.0,'cur'),('last-only',None,None,0.0,'last')]

TEAM_LEAGUE={}
for lg in LEAGUES:
    for t in load(lg,'2026')['teams'].values(): TEAM_LEAGUE[t['title']]=lg
def find_team(sub):
    for name,lg in TEAM_LEAGUE.items():
        if sub.lower()==name.lower(): return name,lg
    for name,lg in TEAM_LEAGUE.items():
        if sub.lower() in name.lower(): return name,lg
    return None,None

def pois(l,k): return math.exp(-l)*l**k/math.factorial(k)
def grid(lh,la,N=10,rho=0.0):
    g=[[pois(lh,i)*pois(la,j) for j in range(N+1)] for i in range(N+1)]
    if rho:
        g[0][0]*=max(1-lh*la*rho,.01); g[0][1]*=max(1+lh*rho,.01)
        g[1][0]*=max(1+la*rho,.01); g[1][1]*=max(1-rho,.01)
    s=sum(sum(r) for r in g)
    return [[v/s for v in row] for row in g]
def outs_from(g):
    pt=defaultdict(float)
    for i in range(len(g)):
        for j in range(len(g)): pt[i+j]+=g[i][j]
    o25=sum(v for t,v in pt.items() if t>=3)
    ph=sum(g[i][j] for i in range(len(g)) for j in range(len(g)) if i>j)
    pd=sum(g[i][j] for i in range(len(g)) for j in range(len(g)) if i==j)
    pa=1-ph-pd
    btts=sum(g[i][j] for i in range(1,len(g)) for j in range(1,len(g)))
    hm15=sum(g[i][j] for i in range(len(g)) for j in range(len(g)) if i-j>=2)
    am15=1-hm15
    return dict(o25=o25,btts=btts,ph=ph,pd=pd,pa=pa,hm15=hm15,am15=am15)

# ---------- targets ----------
# (label, home_sub, away_sub, domestic league or None for UCL, gamedate)
TARGETS=[
 ('LEV-ATH Oct21 LaLiga','Levante','Athletic Club','La_liga','2026-10-21'),
 ('PSG-FCB Oct20 UCL','Paris Saint Germain','Barcelona',None,'2026-10-20'),
 ('LIV-VIL Oct20 UCL','Liverpool','Villarreal',None,'2026-10-20'),
 ('STU-ATM Oct20 UCL','Stuttgart','Atletico Madrid',None,'2026-10-20'),
 ('RMA-RBL Oct21 UCL','Real Madrid','Leipzig',None,'2026-10-21'),
 ('COM-MUN Oct21 UCL','Como','Manchester United',None,'2026-10-21'),
 ('BAY-ARS Oct21 UCL','Bayern','Arsenal',None,'2026-10-21'),
]

# locate events: gather all soccer events matching both team names on date
import unicodedata, re as _re
def norm(s):
    s=unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode()
    return _re.sub(r'[^a-z0-9]','',s.lower())
def team_in(blob,sub):
    return norm(sub) in norm(blob)

events=[]
for e in res.get('soccer',[]):
    t=(e.get('title') or '')
    sl=(e.get('slug') or '')
    events.append((t,sl,e))

def find_events(hs,as_,gd):
    hits=[]
    for t,sl,e in events:
        blob=t+' '+sl
        g=None
        for m in e.get('markets') or []:
            if m.get('gameStartTime'): g=m['gameStartTime']; break
        if not g or not g.startswith(gd): continue
        if team_in(blob,hs) and team_in(blob,as_): hits.append(e)
    return hits

# classify markets of an event
def mkt_meta(m,e):
    q=(m.get('question') or m.get('groupItemTitle') or '')
    st=m.get('sportsMarketType')
    thr=m.get('groupItemThreshold')
    return q,st,thr

def px(m):
    try: pr=json.loads(m.get('outcomePrices') or '[]')
    except Exception: pr=[]
    bb=m.get('bestBid'); ba=m.get('bestAsk')
    return pr,bb,ba

out_report={}
for label,hs,as_,dom,gd in TARGETS:
    evs=find_events(hs,as_,gd)
    if not evs:
        print('%-20s NO EVENTS'%(label)); continue
    # collect markets
    mkts={'ou25':None,'btts':None,'hwin':None,'draw':None,'awin':None,'hm15':None,'am15':None}
    liq_sum=0
    for e in evs:
        liq_sum=max(liq_sum,e.get('liquidity') or 0)
        for m in e.get('markets') or []:
            if m.get('closed'): continue
            q,st,thr=mkt_meta(m,e)
            ql=q.lower()
            try: pr,bb,ba=px(m)
            except Exception: continue
            liqm=m.get('liquidityNum') or 0
            cand=(m,q,pr,bb,ba,liqm,m.get('clobTokenIds'),m.get('id'))
            if q.endswith(': O/U 2.5') or (st=='total' and thr==2.5): mkts['ou25']=cand
            elif q.endswith('Both Teams to Score'): mkts['btts']=cand
            elif q.endswith('+1.5') and team_in(q,hs): mkts['hm15']=cand
            elif q.endswith('+1.5') and team_in(q,as_): mkts['am15']=cand
            elif q.endswith('-1.5') and team_in(q,hs): mkts['am15']=cand if mkts['am15'] is None or liqm>mkts['am15'][5] else mkts['am15']
            elif q.endswith('-1.5') and team_in(q,as_): mkts['hm15']=cand if mkts['hm15'] is None or liqm>mkts['hm15'][5] else mkts['hm15']
            elif ql.startswith('will ') and ' win on ' in ql and team_in(q,hs): mkts['hwin']=cand
            elif ql.startswith('will ') and ' win on ' in ql and team_in(q,as_): mkts['awin']=cand
            elif 'end in a draw' in ql: mkts['draw']=cand
    # model
    hn,lgh=find_team(hs); an,lga=find_team(as_)
    if not hn or not an:
        print('%-20s team not modelable (%s/%s)'%(label,hs,as_)); continue
    variants=[]
    for name,LASTW,PRIOR,rho,mode in SWEEPS:
        boosts=[0.0] if dom else [0.0,0.10,0.20]
        for boost in boosts:
            if dom:
                bh1,ba1,lgf1,r1=ratings_for(dom,LASTW,PRIOR,mode)
                bh,ba=ba1*0+ (bh1), (ba1)  # same league home/away avgs
                ah,dh=r1[hn]; aa,da=r1[an]
                lh=bh1*ah*da; la=ba1*aa*dh
            else:
                bh1,ba1,lgf1,r1=ratings_for(lgh,LASTW,PRIOR,mode)
                bh2,ba2,lgf2,r2=ratings_for(lga,LASTW,PRIOR,mode)
                bh=(bh1+bh2)/2.0; ba=(ba1+ba2)/2.0
                ah,dh=r1[hn]; aa,da=r2[an]
                lh=bh*ah*da*(1+boost); la=ba*aa*dh*(1+boost)
            g=grid(lh,la,10,rho)
            variants.append((lh,la,outs_from(g)))
    lams=(variants[0][0],variants[0][1])
    def rng(k): return (min(v[2][k] for v in variants),max(v[2][k] for v in variants))
    out_report[label]=dict(liq=liq_sum,lams=lams,mkts=mkts,rng={k:rng(k) for k in ['o25','btts','ph','pd','pa','hm15','am15']})
    print('='*100)
    print('%-20s ev-liq=$%d lam=%.2f/%.2f variants=%d'%(label,liq_sum,lams[0],lams[1],len(variants)))
    for key in ['ou25','btts','hwin','draw','awin','hm15','am15']:
        c=mkts.get(key)
        modelkey={'ou25':'o25','btts':'btts','hwin':'ph','draw':'pd','awin':'pa','hm15':'hm15','am15':'am15'}[key]
        mn,mx=out_report[label]['rng'][modelkey]
        if not c:
            print('   %-5s NO MARKET model=[%.3f-%.3f]'%(key,mn,mx)); continue
        m,q,pr,bb,ba,liqm,ctids,mid=c
        prs='['+','.join('%s'%x for x in pr)+']'
        print('   %-5s mid=%-48s pr=%s bb=%s ba=%s liq=$%d model=[%.3f-%.3f] id=%s'%(key,q[:48],prs,bb,ba,liqm,mn,mx,mid))

json.dump({k:{'lams':v['lams'],'rng':v['rng'],'liq':v['liq'],
              'mkts':{kk:(c[7] if c else None) for kk,c in v['mkts'].items()}} for k,v in out_report.items()},
          open(RAW+'/soccer7_summary.json','w'),indent=1)
print()
print('===== existing positions: Oct19 results from understat =====')
for lg in LEAGUES:
    for m in load(lg,'2026')['dates']:
        if m.get('isResult') and (m.get('datetime') or '').startswith('2026-10-19'):
            ht=m['h']['title'] if isinstance(m.get('h'),dict) else m.get('h')
            at=m['a']['title'] if isinstance(m.get('a'),dict) else m.get('a')
            print('  %-10s %s %s %s-%s %s'%(lg,m['datetime'],ht,m['goals']['h'],m['goals']['a'],at))
