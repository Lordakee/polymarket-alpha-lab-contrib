import json, math, urllib.request, urllib.parse, time
from collections import defaultdict

RAW='/home/ubuntu/paper-sim/round8/raw'
import os
XGPATH='/home/ubuntu/paper-sim/round5/raw/xg_understat_5c.json'
XG=json.load(open(XGPATH if os.path.exists(XGPATH) else '/home/ubuntu/paper-sim/round5/raw/xg_understat.json'))
res=json.load(open(RAW+'/discover8.json'))
LEAGUES=['EPL','La_liga','Serie_A','Bundesliga','Ligue_1']
def load(lg,se): return XG['%s_%s'%(lg,se)]

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
    return dict(o25=o25,btts=btts,ph=ph,pd=pd,pa=pa)

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

import unicodedata, re as _re
def norm(s):
    s=unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode()
    return _re.sub(r'[^a-z0-9]','',s.lower())
def team_in(blob,sub): return norm(sub) in norm(blob)

events=[]
for e in res.get('soccer',[]):
    events.append(((e.get('title') or '')+' '+(e.get('slug') or ''), e))

def find_events(hs,as_,gd):
    hits=[]
    for blob,e in events:
        g=None
        for m in e.get('markets') or []:
            if m.get('gameStartTime'): g=m['gameStartTime']; break
        if not g or not g.startswith(gd): continue
        if team_in(blob,hs) and team_in(blob,as_): hits.append(e)
    return hits

TARGETS=[
 # tonight UCL Tue Oct 20 (modelable pairs only)
 ('PSG-FCB Oct20 UCL','Paris Saint Germain','Barcelona',None,'2026-10-20'),
 ('LIV-VIL Oct20 UCL','Liverpool','Villarreal',None,'2026-10-20'),
 ('STU-ATM Oct20 UCL','Stuttgart','Atletico Madrid',None,'2026-10-20'),
 # tomorrow UCL Wed Oct 21
 ('RMA-RBL Oct21 UCL','Real Madrid','Leipzig',None,'2026-10-21'),
 ('BAY-ARS Oct21 UCL','Bayern','Arsenal',None,'2026-10-21'),
 ('COM-MUN Oct21 UCL','Como','Manchester United',None,'2026-10-21'),
 # domestic midweek
 ('LEV-ATH Oct21 LaLiga','Levante','Athletic Club','La_liga','2026-10-21'),
]

for label,hs,as_,dom,gd in TARGETS:
    evs=find_events(hs,as_,gd)
    if not evs:
        print('%-22s NO EVENTS'%(label)); continue
    mkts={}
    liq_sum=0
    for e in evs:
        liq_sum=max(liq_sum,e.get('liquidity') or 0)
        for m in e.get('markets') or []:
            if m.get('closed'): continue
            q=(m.get('question') or m.get('groupItemTitle') or '')
            st=m.get('sportsMarketType'); thr=m.get('groupItemThreshold')
            try: pr=json.loads(m.get('outcomePrices') or '[]')
            except Exception: continue
            liqm=m.get('liquidityNum') or m.get('liquidity') or 0
            cand=(q,pr,m.get('bestBid'),m.get('bestAsk'),liqm,m.get('id'),st,thr)
            ql=q.lower()
            if (st=='total' and thr==2.5) or q.endswith(': O/U 2.5'):
                if liqm>(mkts.get('ou25',(None,)*8)[4] or 0): mkts['ou25']=cand
            elif q.endswith('Both Teams to Score') or st=='btts':
                if liqm>(mkts.get('btts',(None,)*8)[4] or 0): mkts['btts']=cand
            elif ql.startswith('will ') and ' win on ' in ql:
                if team_in(q,hs): 
                    if liqm>(mkts.get('hwin',(None,)*8)[4] or 0): mkts['hwin']=cand
                elif team_in(q,as_):
                    if liqm>(mkts.get('awin',(None,)*8)[4] or 0): mkts['awin']=cand
            elif 'end in a draw' in ql or st=='draw':
                if liqm>(mkts.get('draw',(None,)*8)[4] or 0): mkts['draw']=cand
    hn,lgh=find_team(hs); an,lga=find_team(as_)
    if not hn or not an:
        print('%-22s team not modelable'%(label)); continue
    variants=[]
    for name,LASTW,PRIOR,rho,mode in SWEEPS:
        boosts=[0.0] if dom else [0.0,0.10,0.20]
        for boost in boosts:
            if dom:
                bh1,ba1,lgf1,r1=ratings_for(dom,LASTW,PRIOR,mode)
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
    def rng(k): return (min(v[2][k] for v in variants),max(v[2][k] for v in variants))
    R={k:rng(k) for k in ['o25','btts','ph','pd','pa']}
    print('='*105)
    print('%-22s ev-liq=$%d lam=%.2f/%.2f (variant0)'%(label,liq_sum,variants[0][0],variants[0][1]))
    for key,mk in [('ou25','o25'),('btts','btts'),('hwin','ph'),('draw','pd'),('awin','pa')]:
        c=mkts.get(key); mn,mx=R[mk]
        if not c:
            print('   %-5s NO MARKET  model=[%.3f-%.3f]'%(key,mn,mx)); continue
        q,pr,bb,ba,liqm,mid,st,thr=c
        prs='['+','.join('%s'%x for x in pr)+']'
        print('   %-5s %-46s pr=%s bb=%s ba=%s liq=$%d model=[%.3f-%.3f] id=%s'%(key,q[:46],prs,bb,ba,liqm,mn,mx,mid))
