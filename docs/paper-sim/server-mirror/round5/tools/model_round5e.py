import json, math, urllib.request, time
from collections import defaultdict

RAW='/home/ubuntu/paper-sim/round5/raw'
XG=json.load(open(RAW+'/xg_understat_5c.json'))
DISC=json.load(open(RAW+'/discover5e.json'))
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

def mu(slugs, needle):
    for e in DISC:
        if e['slug'] in slugs:
            for m in e['markets']:
                if (m['q'] or '').endswith(needle):
                    return m['id']
    return None

FIX=[
 ('MOE-HOF Oct18 Bund','Borussia M.Gladbach','Hoffenheim',['bun-moe-hof-2026-10-18','bun-moe-hof-2026-10-18-more-markets'],
   {'1x2h':'5311894','1x2d':'5311896','1x2a':'5311897','sph':'5314041','spa':'5314046','btts':'5314118'}),
 ('PFC-REN Oct18 L1','Paris FC','Rennes',['fl1-pfc-ren-2026-10-18','fl1-pfc-ren-2026-10-18-more-markets'],
   {'1x2h':'5311939','1x2d':'5311941','1x2a':'5311942','sph':'5314271','spa':'5314272','btts':'5314303'}),
 ('LYO-OGC Oct18 L1','Lyon','Nice',['fl1-lyo-ogc-2026-10-18','fl1-lyo-ogc-2026-10-18-more-markets'],
   {'1x2h':'5311944','1x2d':'5311945','1x2a':'5311948','sph':'5314029','spa':'5314030','btts':'5314083'}),
 ('HAC-AJA Oct18 L1','Le Havre','Auxerre',['fl1-hac-aja-2026-10-18','fl1-hac-aja-2026-10-18-more-markets'],
   {'1x2h':'5311912','1x2d':'5311918','1x2a':'5311921','sph':'5314511','spa':'5314512','btts':'5314530'}),
 ('TOT-COV Oct19 EPL','Tottenham','Coventry',['epl-tot-cov-2026-10-19','epl-tot-cov-2026-10-19-more-markets'],
   {'1x2h':'5362507','1x2d':'5362515','1x2a':'5362519','sph':'5364544','spa':'5364546','btts':'5364581'}),
 ('PSG-FCB Oct20 UCL','Paris Saint Germain','Barcelona',['ucl-psg-fcb-2026-10-20','ucl-psg-fcb-2026-10-20-more-markets'],
   {'1x2h':'5409678','1x2d':'5409679','1x2a':'5409680','sph':'5409997','spa':'5409998','btts':'5410016'}),
 ('BAY-ARS Oct21 UCL','Bayern Munich','Arsenal',['ucl-bay-ars-2026-10-21','ucl-bay-ars-2026-10-21-more-markets'],
   {'1x2h':'5436896','1x2d':'5436897','1x2a':'5436898','sph':'5437363','spa':'5437364','btts':'5437382'}),
]
for f in FIX:
    f[4]['ou25']=mu(f[3],': O/U 2.5')

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
        if mode=='cur': fn,a=cf,ca
        elif mode=='last': fn,a=last.get(name,(lgf,lgf))
        else:
            lf,la_=last.get(name,(lgf,lgf))
            fn=(nc*cf+LASTW*38*lf+PRIOR*lgf)/(nc+LASTW*38+PRIOR)
            a=(nc*ca+LASTW*38*la_+PRIOR*lgf)/(nc+LASTW*38+PRIOR)
        r[name]=(fn/lgf,a/lgf)
    _cache[key]=(bh,ba,lgf,r)
    return _cache[key]

TEAM_LEAGUE={}
for lg in LEAGUES:
    for t in load(lg,'2026')['teams'].values(): TEAM_LEAGUE[t['title']]=lg

SWEEPS=[('blend w=.5 p=8 rho0',0.5,8,0.0,'blend'),('blend w=.5 p=8 DC',0.5,8,-0.08,'blend'),
 ('blend w=1.0 p=8',1.0,8,0.0,'blend'),('blend w=.25 p=8',0.25,8,0.0,'blend'),
 ('blend w=.5 p=16',0.5,16,0.0,'blend'),('blend w=.5 p=4',0.5,4,0.0,'blend'),
 ('current-only',None,None,0.0,'cur'),('last-only',None,None,0.0,'last'),
 ('cross-shrink .8',0.5,8,0.0,'blend'),('cross-shrink 1.1',0.5,8,0.0,'blend')]

def pois(l,k): return math.exp(-l)*l**k/math.factorial(k)
def grid(lh,la,N=10,rho=0.0):
    g=[[pois(lh,i)*pois(la,j) for j in range(N+1)] for i in range(N+1)]
    if rho:
        g[0][0]*=max(1-lh*la*rho,.01); g[0][1]*=max(1+lh*rho,.01)
        g[1][0]*=max(1+la*rho,.01); g[1][1]*=max(1-rho,.01)
    s=sum(sum(r) for r in g)
    return [[v/s for v in row] for row in g]

BASE={}
for lg in LEAGUES:
    n=h_=d_=a_=0
    for se in ['2025','2026']:
        for m in load(lg,se)['dates']:
            if m.get('isResult'):
                gh,ga=int(m['goals']['h']),int(m['goals']['a'])
                n+=1; h_+= 1 if gh>ga else 0; d_+= 1 if gh==ga else 0; a_+= 1 if ga>gh else 0
    BASE[lg]={'h':h_/n,'d':d_/n,'a':a_/n}

def mkt_probs(g):
    ph=pd=pa=btts=o25=0.0; hm2=am2=0.0
    for i in range(len(g)):
        for j in range(len(g)):
            p=g[i][j]
            if i>j: ph+=p
            elif i==j: pd+=p
            else: pa+=p
            if i>=1 and j>=1: btts+=p
            if i+j>=3: o25+=p
            if i-j>=2: hm2+=p
            if j-i>=2: am2+=p
    return ph,pd,pa,btts,o25,hm2,am2

def game_lams(home,away,LASTW,PRIOR,rho,mode,shrink=1.0):
    lgh=TEAM_LEAGUE.get(home); lga=TEAM_LEAGUE.get(away)
    if lgh is None or lga is None: return None
    bh1,ba1,lgf1,r1=ratings_for(lgh,LASTW,PRIOR,mode)
    bh2,ba2,lgf2,r2=ratings_for(lga,LASTW,PRIOR,mode)
    if home not in r1 or away not in r2: return None
    if lgh==lga:
        bh=(bh1+bh2)/2.0; ba=(ba1+ba2)/2.0
    else:
        bh=(bh1+ba2)/2.0; ba=(bh2+ba1)/2.0
    ah,dh=r1[home]; aa,da=r2[away]
    return bh*(ah**shrink)*(da**shrink), ba*(aa**shrink)*(dh**shrink), (lgh,lga)

def book(tid):
    for i in range(3):
        try: return get('https://clob.polymarket.com/book?token_id='+tid,timeout=15)
        except Exception:
            if i==2: return {'err':'fetch'}
            time.sleep(1.2)

def ask(b,dollars=400.0):
    asks=sorted(b.get('asks',[]),key=lambda l: float(l['price']))
    if not asks: return None,None
    best=float(asks[0]['price'])
    cash=0.0; sh=0.0
    for l in asks:
        p=float(l['price']); sz=float(l['size'])
        take=min(sz,(dollars-cash)/p)
        if take<=0: break
        cash+=take*p; sh+=take
        if cash>=dollars-1e-9: break
    return best, round(cash/sh,4) if sh>0 else best

IDS={}
for f in FIX:
    for k,mid in f[4].items():
        if mid and mid not in IDS: IDS[mid]=None
for mid in IDS:
    for i in range(3):
        try:
            m=get('https://gamma-api.polymarket.com/markets/'+mid)
            toks=m.get('clobTokenIds')
            if isinstance(toks,str): toks=json.loads(toks)
            outs=m.get('outcomes')
            if isinstance(outs,str): outs=json.loads(outs)
            IDS[mid]={'q':m.get('question'),'outcomes':outs,'tokens':toks,'liq':m.get('liquidityNum'),
                      'closed':m.get('closed'),'active':m.get('active'),'gs':m.get('gameStartTime')}
            break
        except Exception:
            time.sleep(1.5)
    time.sleep(0.15)

def ask_for(mid,label):
    d=IDS.get(mid)
    if not d or not d.get('tokens'): return None,None,None
    tok=None
    if d.get('outcomes') and label in d['outcomes']:
        tok=d['tokens'][d['outcomes'].index(label)]
    else: tok=d['tokens'][0]
    b=book(tok); time.sleep(0.15)
    best,vwap=ask(b)
    return best,vwap,d.get('liq')

out={}
flags=[]
for label,home,away,slugs,ids in FIX:
    variants={}
    for name,LASTW,PRIOR,rho,mode in SWEEPS:
        shr=0.8 if name.startswith('cross-shrink .8') else (1.1 if name.startswith('cross-shrink 1.1') else 1.0)
        lm=game_lams(home,away,LASTW,PRIOR,rho,mode,shr)
        if lm is None: continue
        lh,la,(lgh,lga)=lm
        ph,pd,pa,btts,o25,hm2,am2=mkt_probs(grid(lh,la,10,rho))
        if lgh==lga: bh0,bd0,ba0=BASE[lgh]['h'],BASE[lgh]['d'],BASE[lgh]['a']
        else:
            bh0=(BASE[lgh]['h']+BASE[lga]['a'])/2; bd0=(BASE[lgh]['d']+BASE[lga]['d'])/2; ba0=(BASE[lgh]['a']+BASE[lga]['h'])/2
        variants[name]={'o25':o25,'btts':btts,'ph':0.7*ph+0.3*bh0,'pd':0.7*pd+0.3*bd0,'pa':0.7*pa+0.3*ba0,'hm2':hm2,'am2':am2,'lh':lh,'la':la}
    if not variants:
        print('%-20s TEAMS NOT FOUND'%(label,)); continue
    def rng(k):
        vs=[v[k] for v in variants.values()]; return min(vs),max(vs)
    o_mn,o_mx=rng('o25'); b_mn,b_mx=rng('btts'); phm,phx=rng('ph'); pdm,pdx=rng('pd'); pam,pax=rng('pa'); hmm,hmx=rng('hm2'); amm,amx=rng('am2')
    base=list(variants.values())[0]
    print('== %-18s | lam=%.2f/%.2f | OU [%.3f-%.3f] BTTS [%.3f-%.3f] H/D/A [%d-%d/%d-%d/%d-%d pct] H-1.5 [%.3f-%.3f] A-1.5 [%.3f-%.3f]'%(
        label,base['lh'],base['la'],o_mn,o_mx,b_mn,b_mx,round(phm*100),round(phx*100),round(pdm*100),round(pdx*100),round(pam*100),round(pax*100),hmm,hmx,amm,amx),flush=True)
    out[label]={}
    if ids.get('ou25'):
        ov,vl,lq=ask_for(ids['ou25'],'Over'); un,vl2,lq2=ask_for(ids['ou25'],'Under')
        if ov is not None:
            e_o=o_mn-ov; e_u=(1-o_mx)-un
            out[label]['OU']={'ov':ov,'un':un,'rng':[o_mn,o_mx],'e_o':round(e_o,3),'e_u':round(e_u,3)}
            fl='OVER' if e_o>=0.05 else ('UNDER' if e_u>=0.05 else '')
            if fl: flags.append((label,'OU2.5 '+fl,round(e_o if fl=='OVER' else e_u,3)))
            print('   %-18s O/U2.5 Over  [%.3f-%.3f] ask %.3f edge %+.3f %s'%(label,o_mn,o_mx,ov,e_o,'FLAG' if fl=='OVER' else 'NO'),flush=True)
            print('   %-18s O/U2.5 Under [%.3f-%.3f] ask %.3f edge %+.3f %s'%(label,1-o_mx,1-o_mn,un,e_u,'FLAG' if fl=='UNDER' else 'NO'),flush=True)
    if ids.get('btts'):
        ys,vl,lq=ask_for(ids['btts'],'Yes'); no,vl2,lq2=ask_for(ids['btts'],'No')
        if ys is not None:
            e_y=b_mn-ys; e_n=(1-b_mx)-no
            out[label]['BTTS']={'yes':ys,'no':no,'rng':[b_mn,b_mx],'e_y':round(e_y,3),'e_n':round(e_n,3)}
            fl='YES' if e_y>=0.05 else ('NO' if e_n>=0.05 else '')
            if fl: flags.append((label,'BTTS '+fl,round(e_y if fl=='YES' else e_n,3)))
            print('   %-18s BTTS Yes [%.3f-%.3f] ask %.3f edge %+.3f %s'%(label,b_mn,b_mx,ys,e_y,'FLAG' if fl=='YES' else 'NO'),flush=True)
            print('   %-18s BTTS No  [%.3f-%.3f] ask %.3f edge %+.3f %s'%(label,1-b_mx,1-b_mn,no,e_n,'FLAG' if fl=='NO' else 'NO'),flush=True)
    for side,mid,key,mn,mx in [('H -1.5',ids.get('sph'),'SPH',hmm,hmx),('A -1.5',ids.get('spa'),'SPA',amm,amx)]:
        if mid:
            ys,vl,lq=ask_for(mid,'Yes'); no,vl2,lq2=ask_for(mid,'No')
            if ys is not None:
                e_y=mn-ys; e_n=(1-mx)-no
                out[label][key]={'yes':ys,'no':no,'rng':[mn,mx],'e_y':round(e_y,3),'e_n':round(e_n,3)}
                fl='COVER' if e_y>=0.05 else ('NOCOV' if e_n>=0.05 else '')
                if fl: flags.append((label,side+' '+fl,round(e_y if fl=='COVER' else e_n,3)))
                print('   %-18s %s cover [%.3f-%.3f] ask %.3f edge %+.3f %s'%(label,side,mn,mx,ys,e_y,'FLAG' if fl=='COVER' else 'NO'),flush=True)
                print('   %-18s %s nocov [%.3f-%.3f] ask %.3f edge %+.3f %s'%(label,side,1-mx,1-mn,no,e_n,'FLAG' if fl=='NOCOV' else 'NO'),flush=True)
    for side,mid,mn,mx in [('1X2 H',ids.get('1x2h'),phm,phx),('1X2 D',ids.get('1x2d'),pdm,pdx),('1X2 A',ids.get('1x2a'),pam,pax)]:
        if mid:
            ys,vl,lq=ask_for(mid,'Yes'); no,vl2,lq2=ask_for(mid,'No')
            if ys is not None:
                e_y=mn-ys; e_n=(1-mx)-no
                out[label]['1X2:'+side]={'yes':ys,'rng':[mn,mx],'e_y':round(e_y,3),'e_n':round(e_n,3)}
                fl='BUY' if e_y>=0.05 else ('SELL' if e_n>=0.05 else '')
                if fl: flags.append((label,side+' '+fl,round(e_y if fl=='BUY' else e_n,3)))
                print('   %-18s %s yes [%.3f-%.3f] ask %.3f edge %+.3f %s'%(label,side,mn,mx,ys,e_y,'FLAG' if fl=='BUY' else 'NO'),flush=True)
                print('   %-18s %s no  [%.3f-%.3f] ask %.3f edge %+.3f %s'%(label,side,1-mx,1-mn,no,e_n,'FLAG' if fl=='SELL' else 'NO'),flush=True)
json.dump({'out':out,'flags':flags},open(RAW+'/model_round5e.json','w'),indent=1)
print()
print('FLAGS:',flags or 'NONE')
