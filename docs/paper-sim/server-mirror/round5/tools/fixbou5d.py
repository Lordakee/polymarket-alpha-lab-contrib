import json, math, time, re
from collections import defaultdict
import urllib.request

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

report=RES['report']; flags=[tuple(f) for f in RES['flags'] if not (f[0]=='BOU-SUN' and f[1]=='SPREAD_A_m1.5')]

h,a='Bournemouth','Sunderland'
marg15=[]; marg25=[]; margs=[]
for name,LW,P,rho,mode in SWEEPS:
    shr=0.8 if name=='cs8' else (1.1 if name=='cs11' else 1.0)
    lm=lams(h,a,LW,P,rho,mode,shr)
    lh,la=lm; g=grid(lh,la,10,rho)
    m=defaultdict(float)
    for i in range(len(g)):
        for j in range(len(g)): m[i-j]+=g[i][j]
    marg15.append(sum(v for k,v in m.items() if k>=2))
    marg25.append(sum(v for k,v in m.items() if k>=3))
    margs.append('%.2f/%.2f'%(lh,la))
mn15,md15,mx15=min(marg15),sorted(marg15)[5],max(marg15)
mn25,md25,mx25=min(marg25),sorted(marg25)[5],max(marg25)
print('BOU-SUN P(home by >=2) = [%.4f, %.4f, %.4f]  P(home by >=3) = [%.4f, %.4f, %.4f]'%(mn15,md15,mx15,mn25,md25,mx25))
print('variant lams:', margs)

bm={}
for ev in DISC['BOU-SUN']:
    if ' - More Markets' in (ev['title'] or ''):
        for mm2 in ev['markets']:
            q=mm2['q'] or ''
            if q.startswith('Spread: AFC Bournemouth'):
                bm[float(re.search(r'\((-[\d.]+)\)$',q).group(1))]=mm2
M=report['BOU-SUN']['markets']
for line,mkt in bm.items():
    outs=mkt['outcomes']; toks=mkt['tokens']
    ab,av,aok=ask_side(get('https://clob.polymarket.com/book?token_id='+toks[0])); time.sleep(0.2)
    bb,bv,bok=ask_side(get('https://clob.polymarket.com/book?token_id='+toks[1])); time.sleep(0.2)
    if line==-1.5: mod=[round(mn15,4),round(md15,4),round(mx15,4)]; key='SPREAD_H_m1.5'
    else: mod=[round(mn25,4),round(md25,4),round(mx25,4)]; key='SPREAD_H_m2.5'
    ec=round(mod[0]-ab,4) if ab is not None else None
    ef=round((1-mod[2])-bb,4) if bb is not None else None
    fl='COVER' if (ec is not None and ec>=0.05) else ('FAIL' if (ef is not None and ef>=0.05) else '')
    M[key]={'mid':mkt['id'],'team':'AFC Bournemouth','line':line,'model':mod,
            'cover_ask':ab,'cover_vwap':av,'fail_ask':bb,'fail_vwap':bv,
            'edge_cover':ec,'edge_fail':ef,'flag':fl,'liq':mkt.get('liq')}
    if fl: flags.append(('BOU-SUN',key,fl))
    print('%s Bournemouth %.1f: model[%.3f-%.3f] cov_ask=%s(vwap %s) fail_ask=%s(vwap %s) eCov=%s eFail=%s %s'%(
        key,line,mod[0],mod[2],ab,av,bb,bv,ec,ef,'*** '+fl if fl else ''))
M['SPREAD_A_m1.5']['team']='Sunderland AFC'
M['SPREAD_A_m1.5']['edge_cover']=round(M['SPREAD_A_m1.5']['model'][0]-M['SPREAD_A_m1.5']['cover_ask'],4)
M['SPREAD_A_m1.5']['edge_fail']=round((1-M['SPREAD_A_m1.5']['model'][2])-M['SPREAD_A_m1.5']['fail_ask'],4)
M['SPREAD_A_m2.5']['team']='Sunderland AFC'
M['SPREAD_A_m2.5']['edge_cover']=round(M['SPREAD_A_m2.5']['model'][0]-M['SPREAD_A_m2.5']['cover_ask'],4)
M['SPREAD_A_m2.5']['edge_fail']=round((1-M['SPREAD_A_m2.5']['model'][2])-M['SPREAD_A_m2.5']['fail_ask'],4)
json.dump({'report':report,'flags':[list(f) for f in flags]},open(RAW+'/model_round5d.json','w'),indent=1)
print()
print('FINAL FLAGS:',flags)
