import json, math
from collections import defaultdict

XG15 = json.load(open('/home/ubuntu/paper-sim/round15/raw/xg_understat_15.json'))
RHO_DC = -0.1

def load(xgd, lg, se): return xgd['%s_%s' % (lg, se)]

def ratings_for(xgd, lg, LASTW, PRIOR, mode, cache):
    key=(lg,LASTW,PRIOR,mode)
    if key in cache: return cache[key]
    d25 = load(xgd,lg,'2025'); d26 = load(xgd,lg,'2026')
    ms=[m for m in d25['dates'] if m.get('isResult')]
    bh=sum(float(m['xG']['h']) for m in ms)/len(ms); ba=sum(float(m['xG']['a']) for m in ms)/len(ms)
    lgf=(bh+ba)/2.0
    last={}
    for t in d25['teams'].values():
        h=t['history']; last[t['title']]=(sum(float(x['xG']) for x in h)/len(h), sum(float(x['xGA']) for x in h)/len(h))
    r={}
    for t in d26['teams'].values():
        h=t['history']; name=t['title']
        if not h: continue
        cf=sum(float(x['xG']) for x in h)/len(h); ca=sum(float(x['xGA']) for x in h)/len(h); nc=len(h)
        if mode=='cur': f,a=cf,ca
        elif mode=='last': f,a=last.get(name,(lgf,lgf))
        else:
            lf,la_=last.get(name,(lgf,lgf))
            f=(nc*cf+LASTW*38*lf+PRIOR*lgf)/(nc+LASTW*38+PRIOR)
            a=(nc*ca+LASTW*38*la_+PRIOR*lgf)/(nc+LASTW*38+PRIOR)
        r[name]=(f/lgf,a/lgf)
    cache[key]=(bh,ba,lgf,r)
    return cache[key]

SWEEPS=[('blend w=.5 p=8 rho0',0.5,8,0.0,'blend'),('blend w=.5 p=8 DC',0.5,8,RHO_DC,'blend'),
 ('blend w=1.0 p=8',1.0,8,0.0,'blend'),('blend w=.25 p=8',0.25,8,0.0,'blend'),
 ('blend w=.5 p=16',0.5,16,0.0,'blend'),('blend w=.5 p=4',0.5,4,0.0,'blend'),
 ('current-only',None,None,0.0,'cur'),('last-only',None,None,0.0,'last'),
 ('cross-shrink .8',0.5,8,0.0,'blend'),('cross-shrink 1.1',0.5,8,0.0,'blend')]

TEAM_LEAGUE={}
for lg in ['EPL','La_liga','Serie_A','Bundesliga','Ligue_1']:
    for t in load(XG15,lg,'2026')['teams'].values(): TEAM_LEAGUE[t['title']]=lg

def lambdas(xgd, home, away, LASTW, PRIOR, mode, shrink=1.0):
    lgh=TEAM_LEAGUE.get(home); lga=TEAM_LEAGUE.get(away)
    if lgh is None or lga is None or lgh!=lga: return None
    bh1,ba1,lgf1,r1=ratings_for(xgd,lgh,LASTW,PRIOR,mode,{})
    ah,dh=r1.get(home,(1.0,1.0)); aa,da=r1.get(away,(1.0,1.0))
    return bh1*(ah**shrink)*(da**shrink), ba1*(aa**shrink)*(dh**shrink)

def med(v):
    s=sorted(v); n=len(s)
    return s[n//2] if n%2 else (s[n//2-1]+s[n//2])/2.0

cache={}
for home,away,rh,ra in [('Roma','Cagliari',2.266,0.971),('Torino','Como',1.298,1.736),
                        ('Sassuolo','Lazio',None,None),('Inter','Venezia',None,None)]:
    lhs=[];las=[]
    for name,LASTW,PRIOR,rho,mode in SWEEPS:
        shrink=0.8 if name.startswith('cross-shrink .8') else (1.1 if name.startswith('cross-shrink 1.1') else 1.0)
        l=lambdas(XG15,home,away,LASTW,PRIOR,mode,shrink)
        if l is None: print(home,away,'MISS',name); break
        lhs.append(l[0]); las.append(l[1])
    else:
        print('%s vs %s: lh_med=%.3f (r19 %s) la_med=%.3f (r19 %s)'%(home,away,med(lhs),rh,med(las),ra))
