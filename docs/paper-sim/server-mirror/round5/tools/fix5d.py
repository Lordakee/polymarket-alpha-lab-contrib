import json, math, time
from collections import defaultdict

RAW='/home/ubuntu/paper-sim/round5/raw'
XG=json.load(open(RAW+'/xg_understat_5c.json'))
DISC=json.load(open(RAW+'/discover5d3.json'))
RES=json.load(open(RAW+'/model_round5d.json'))
LEAGUES=['EPL','La_liga','Serie_A','Bundesliga','Ligue_1']
def load(lg,se): return XG['%s_%s'%(lg,se)]
_cache={}
def ratings_for(lg,LASTW,PRIOR,mode):
    key=(lg,LASTW,PRIOR,mode)
    if key in _cache: return _cache[key]
    d25=load(lg,'2025'); d26=load(lg,'2026')
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
    _cache[key]=(bh,ba,lgf,r); return _cache[key]
SWEEPS=[('b1',0.5,8,0.0,'blend'),('b2',0.5,8,-0.08,'blend'),('b3',1.0,8,0.0,'blend'),('b4',0.25,8,0.0,'blend'),
        ('b5',0.5,16,0.0,'blend'),('b6',0.5,4,0.0,'blend'),('cur',None,None,0.0,'cur'),('last',None,None,0.0,'last'),
        ('cs8',0.5,8,0.0,'blend'),('cs11',0.5,8,0.0,'blend')]
def pois(l,k): return math.exp(-l)*l**k/math.factorial(k)
def grid(lh,la,N=10,rho=0.0):
    g=[[pois(lh,i)*pois(la,j) for j in range(N+1)] for i in range(N+1)]
    if rho:
        g[0][0]*=max(1-lh*la*rho,.01); g[0][1]*=max(1+lh*rho,.01); g[1][0]*=max(1+la*rho,.01); g[1][1]*=max(1-rho,.01)
    s=sum(sum(r) for r in g); return [[v/s for v in row] for row in g]
TL={}
for lg in LEAGUES:
    for t in load(lg,'2026')['teams'].values(): TL[t['title']]=lg
def find_team(sub):
    for n,l in TL.items():
        if sub.lower()==n.lower(): return n,l
    for n,l in TL.items():
        if sub.lower() in n.lower(): return n,l
    return None,None
def lams(h,a,LW,P,rho,mode,shr=1.0):
    hn,l1=find_team(h); an,l2=find_team(a)
    if l1 is None or l1!=l2: return None
    bh1,ba1,g1,r1=ratings_for(l1,LW,P,mode); bh2,ba2,g2,r2=ratings_for(l2,LW,P,mode)
    if hn not in r1 or an not in r2: return None
    bh=(bh1+bh2)/2; ba=(ba1+ba2)/2
    ah,dh=r1[hn]; aa,da=r2[an]
    return bh*(ah**shr)*(da**shr), ba*(aa**shr)*(dh**shr)
BASE={}
for lg in LEAGUES:
    n=h_=d_=a_=0
    for se in ['2025','2026']:
        for m in load(lg,se)['dates']:
            if m.get('isResult'):
                gh,ga=int(m['goals']['h']),int(m['goals']['a']); n+=1
                h_+=1 if gh>ga else 0; d_+=1 if gh==ga else 0; a_+=1 if ga>gh else 0
    BASE[lg]={'h':h_/n,'d':d_/n,'a':a_/n}

import urllib.request
def get(url,tries=3):
    for i in range(tries):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
            with urllib.request.urlopen(req,timeout=15) as r: return json.load(r)
        except Exception:
            if i==tries-1: raise
            time.sleep(1.0)
def ask_side(b,dollars=400.0):
    asks=sorted(b.get('asks',[]),key=lambda l: float(l['price']))
    if not asks: return None,None,False
    best=float(asks[0]['price']); cash=0.0; sh=0.0
    for l in asks:
        p=float(l['price']); sz=float(l['size']); take=min(sz,(dollars-cash)/p)
        if take<=0: break
        cash+=take*p; sh+=take
        if cash>=dollars-1e-9: break
    return best, round(cash/sh,4) if sh>0 else best, cash>=dollars-1e-6

# missing home-win 1X2 markets
MISS={'BOU-SUN':('Bournemouth','Sunderland','EPL','Bournemouth'),
      'MIL-ATA':('AC Milan','Atalanta','Serie_A','AC Milan'),
      'NFO-ARS':('Nottingham Forest','Arsenal','EPL','Nottingham Forest'),
      'BHA-CRY':('Brighton','Crystal Palace','EPL','Brighton')}
report=RES['report']; flags=list(RES['flags'])
for tag,(h,a,lg,hwin) in MISS.items():
    target=None
    for ev in DISC[tag]:
        if ' - ' in (ev['title'] or ''): continue
        for m in ev['markets']:
            q=m['q'] or ''
            if 'win on 2026-10-18' in q and hwin.lower() in q.lower():
                target=m
    if target is None:
        print(tag,'home market NOT FOUND'); continue
    outs=target['outcomes']; toks=target['tokens']
    tok=toks[outs.index('Yes')]
    b=get('https://clob.polymarket.com/book?token_id='+tok)
    yb,yv,yok=ask_side(b); time.sleep(0.15)
    phs=[]
    for name,LW,P,rho,mode in SWEEPS:
        shr=0.8 if name=='cs8' else (1.1 if name=='cs11' else 1.0)
        lm=lams(h,a,LW,P,rho,mode,shr)
        if lm is None: continue
        lh,la=lm; g=grid(lh,la,10,rho)
        ph=sum(g[i][j] for i in range(len(g)) for j in range(len(g)) if i>j)
        pd=sum(g[i][i] for i in range(len(g))); pa=1-ph-pd
        base=BASE[lg]
        if ph>=pa:
            pd_c=0.7*pd+0.3*base['d']; pa_c=0.7*pa+0.3*base['a']; ph_c=1-pd_c-pa_c
        else:
            pd_c=0.7*pd+0.3*base['d']; ph_c=0.7*ph+0.3*base['h']; pa_c=1-pd_c-ph_c
        phs.append(ph_c)
    mn,md,mx=min(phs),sorted(phs)[len(phs)//2],max(phs)
    ey=mn-yb if yb is not None else None
    fl='YES' if (ey is not None and ey>=0.05) else ''
    report[tag]['markets']['X1_home']={'mid':target['id'],'q':target['q'],'model':[round(mn,4),round(md,4),round(mx,4)],
        'ask':yb,'vwap':yv,'edge':round(ey,4) if ey is not None else None,'flag':fl,'liq':target.get('liq')}
    if fl: flags.append((tag,'X1_home',fl))
    print('%-8s HOME %-42s model[%.3f-%.3f] med %.3f ask=%s edge=%s %s'%(tag,(target['q'] or '')[:42],mn,mx,md,yb,round(ey,4) if ey is not None else None,fl))

json.dump({'report':report,'flags':flags},open(RAW+'/model_round5d.json','w'),indent=1)

# ---------- full table ----------
print(); print('='*110)
for tag,row in report.items():
    print('%s  %s vs %s (%s)  lam=%s  [%d variants]'%(tag,row['home'],row['away'],row['league'],row['lam_base'],row['n_variants']))
    for k in sorted(row['markets'].keys()):
        M=row['markets'][k]
        mod=M.get('model')
        def f(x): return ('%.3f'%x) if isinstance(x,float) else str(x)
        line='  %-16s'%k
        if 'yes_ask' in M:
            line+=' model[%s-%s] med %s | Yask=%s Nask=%s | eY=%s eN=%s %s'%(
                f(mod[0]),f(mod[2]),f(mod[1]),M.get('yes_ask'),M.get('no_ask'),M.get('edge_yes'),M.get('edge_no'),'*** '+M['flag'] if M.get('flag') else '')
        elif 'over_ask' in M:
            line+=' model[%s-%s] med %s | Oask=%s Uask=%s | eO=%s eU=%s %s'%(
                f(mod[0]),f(mod[2]),f(mod[1]),M.get('over_ask'),M.get('under_ask'),M.get('edge_over'),M.get('edge_under'),'*** '+M['flag'] if M.get('flag') else '')
        else:
            line+=' model[%s-%s] med %s | ask=%s | edge=%s %s'%(
                f(mod[0]),f(mod[2]),f(mod[1]),M.get('ask'),M.get('edge'),'*** '+M['flag'] if M.get('flag') else '')
        print(line)
print(); print('ALL FLAGS:',flags)
