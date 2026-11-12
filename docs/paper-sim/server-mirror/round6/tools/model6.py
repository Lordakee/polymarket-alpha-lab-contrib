import json, math, urllib.request, urllib.parse, time
from collections import defaultdict

RAW5='/home/ubuntu/paper-sim/round5/raw'
RAW='/home/ubuntu/paper-sim/round6/raw'
XG=json.load(open(RAW5+'/xg_understat_5c.json'))
DISC=json.load(open(RAW+'/discover6.json'))
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

# ---- model core (reused from round5e) ----
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
 ('current-only',None,None,0.0,'cur'),('last-only',None,None,0.0,'last')]

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
    ph=pd=pa=btts=o25=0.0; hm15=am15=hm25=am25=0.0
    for i in range(len(g)):
        for j in range(len(g)):
            p=g[i][j]
            if i>j: ph+=p
            elif i==j: pd+=p
            else: pa+=p
            if i>=1 and j>=1: btts+=p
            if i+j>=3: o25+=p
            if i-j>=2: hm15+=p
            if j-i>=2: am15+=p
            if i-j>=3: hm25+=p
            if j-i>=3: am25+=p
    return ph,pd,pa,btts,o25,hm15,am15,hm25,am25

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

# ---- round 6 fixtures ----
FIX=[
 ('MON-CAG Oct19 SEA', 'sea-mon-cag-2026-10-19', 'Monza','Cagliari'),
 ('PAR-TOR Oct19 SEA', 'sea-par-tor-2026-10-19', 'Parma Calcio 1913','Torino'),
 ('GET-RAY Oct19 LAL', 'lal-get-ray-2026-10-19', 'Getafe','Rayo Vallecano'),
]
ev_by_slug={}
for e in DISC['soccer']:
    ev_by_slug.setdefault(e['slug'],e)

def find_ids(base_slug,home_pm,away_pm):
    ids={}
    main=ev_by_slug.get(base_slug)
    more=ev_by_slug.get(base_slug+'-more-markets')
    if main:
        for m in main.get('markets',[]):
            q=m.get('question') or ''
            if 'draw' in q.lower(): ids['1x2d']=m['id']
            elif home_pm.split()[0].lower() in q.lower() and 'win' in q.lower(): ids['1x2h']=m['id']
            elif away_pm.split()[0].lower() in q.lower() and 'win' in q.lower(): ids['1x2a']=m['id']
    if more:
        for m in more.get('markets',[]):
            q=m.get('question') or ''
            if q.endswith(': O/U 2.5'): ids['ou25']=m['id']
            elif q.endswith(': Both Teams to Score'): ids['btts']=m['id']
            elif q.startswith('Spread:') and q.endswith('(-1.5)'):
                if home_pm.split()[0].lower() in q.lower(): ids['sph15']=m['id']
                elif away_pm.split()[0].lower() in q.lower(): ids['spa15']=m['id']
            elif q.startswith('Spread:') and q.endswith('(-2.5)'):
                if home_pm.split()[0].lower() in q.lower(): ids['sph25']=m['id']
                elif away_pm.split()[0].lower() in q.lower(): ids['spa25']=m['id']
    return ids

ALLIDS={}
for label,slug,h,a in FIX:
    ids=find_ids(slug,h,a)
    print(label,'ids:',ids,flush=True)
    for v in ids.values(): ALLIDS.setdefault(v,None)

META={}
for mid in ALLIDS:
    for i in range(3):
        try:
            m=get('https://gamma-api.polymarket.com/markets/'+mid)
            toks=m.get('clobTokenIds')
            if isinstance(toks,str): toks=json.loads(toks)
            outs=m.get('outcomes')
            if isinstance(outs,str): outs=json.loads(outs)
            META[mid]={'q':m.get('question'),'outcomes':outs,'tokens':toks,'liq':m.get('liquidityNum'),
                       'closed':m.get('closed'),'active':m.get('active')}
            break
        except Exception:
            time.sleep(1.5)
    time.sleep(0.15)
json.dump(META,open(RAW+'/meta6.json','w'))

def two_side(mid):
    d=META.get(mid)
    if not d or not d.get('tokens'): return None
    outs=d.get('outcomes') or ['Yes','No']
    res={}
    for lab,tok in zip(outs,d['tokens']):
        b=book(tok); time.sleep(0.12)
        best,vw=ask(b)
        res[lab]=(best,vw)
    return res

out={}; flags=[]
for label,slug,home,away in FIX:
    ids=find_ids(slug,home,away)
    variants={}
    for name,LASTW,PRIOR,rho,mode in SWEEPS:
        lm=game_lams(home,away,LASTW,PRIOR,rho,mode)
        if lm is None: continue
        lh,la,(lgh,lga)=lm
        ph,pd,pa,btts,o25,hm15,am15,hm25,am25=mkt_probs(grid(lh,la,10,rho))
        if lgh==lga: bh0,bd0,ba0=BASE[lgh]['h'],BASE[lgh]['d'],BASE[lgh]['a']
        else:
            bh0=(BASE[lgh]['h']+BASE[lga]['a'])/2; bd0=(BASE[lgh]['d']+BASE[lga]['d'])/2; ba0=(BASE[lgh]['a']+BASE[lga]['h'])/2
        variants[name]={'o25':o25,'btts':btts,'ph':0.7*ph+0.3*bh0,'pd':0.7*pd+0.3*bd0,'pa':0.7*pa+0.3*ba0,
                        'hm15':hm15,'am15':am15,'hm25':hm25,'am25':am25,'lh':lh,'la':la}
    if not variants:
        print('%-18s TEAMS NOT FOUND'%label); continue
    def rng(k):
        vs=[v[k] for v in variants.values()]; return min(vs),max(vs)
    keys=['o25','btts','ph','pd','pa','hm15','am15','hm25','am25']
    R={k:rng(k) for k in keys}
    base=list(variants.values())[0]
    print('== %-17s lam=%.2f/%.2f | OU [%.3f-%.3f] BTTS [%.3f-%.3f] H/D/A [%d-%d/%d-%d/%d-%d] H-1.5 [%.3f-%.3f] A-1.5 [%.3f-%.3f]'%(
        label,base['lh'],base['la'],R['o25'][0],R['o25'][1],R['btts'][0],R['btts'][1],
        round(R['ph'][0]*100),round(R['ph'][1]*100),round(R['pd'][0]*100),round(R['pd'][1]*100),
        round(R['pa'][0]*100),round(R['pa'][1]*100),R['hm15'][0],R['hm15'][1],R['am15'][0],R['am15'][1]),flush=True)
    out[label]={'lams':[base['lh'],base['la']],'ranges':{k:[round(v,4) for v in R[k]] for k in keys},'mkts':{}}
    if ids.get('ou25'):
        r=two_side(ids['ou25'])
        if r and 'Over' in r:
            ov,vov=r['Over']; un,vun=r.get('Under',(None,None))
            e_o=R['o25'][0]-ov; e_u=(1-R['o25'][1])-un
            out[label]['mkts']['ou25']={'mid':ids['ou25'],'q':META[ids['ou25']]['q'],'liq':META[ids['ou25']]['liq'],
                'over_ask':ov,'over_vwap':vov,'under_ask':un,'under_vwap':vun,
                'model_over':R['o25'],'edge_over':round(e_o,3),'edge_under':round(e_u,3)}
            if e_o>=0.05: flags.append((label,'O/U2.5 OVER',round(e_o,3),ov,ids['ou25']))
            if e_u>=0.05: flags.append((label,'O/U2.5 UNDER',round(e_u,3),un,ids['ou25']))
            print('   O/U2.5  O [%.3f-%.3f] ask %.3f vw %s edge %+.3f | U [%.3f-%.3f] ask %s edge %s'%(R['o25'][0],R['o25'][1],ov,vov,e_o,1-R['o25'][1],1-R['o25'][0],un,round(e_u,3)),flush=True)
    if ids.get('btts'):
        r=two_side(ids['btts'])
        if r and 'Yes' in r:
            ys,vys=r['Yes']; no,vno=r.get('No',(None,None))
            e_y=R['btts'][0]-ys; e_n=(1-R['btts'][1])-no
            out[label]['mkts']['btts']={'mid':ids['btts'],'q':META[ids['btts']]['q'],'liq':META[ids['btts']]['liq'],
                'yes_ask':ys,'yes_vwap':vys,'no_ask':no,'no_vwap':vno,
                'model_yes':R['btts'],'edge_yes':round(e_y,3),'edge_no':round(e_n,3)}
            if e_y>=0.05: flags.append((label,'BTTS YES',round(e_y,3),ys,ids['btts']))
            if e_n>=0.05: flags.append((label,'BTTS NO',round(e_n,3),no,ids['btts']))
            print('   BTTS    Y [%.3f-%.3f] ask %.3f edge %+.3f | N [%.3f-%.3f] ask %s edge %s'%(R['btts'][0],R['btts'][1],ys,e_y,1-R['btts'][1],1-R['btts'][0],no,round(e_n,3)),flush=True)
    for key,mnmx,lab in [('sph15','hm15','H -1.5'),('spa15','am15','A -1.5'),('sph25','hm25','H -2.5'),('spa25','am25','A -2.5')]:
        if ids.get(key):
            r=two_side(ids[key])
            if r and 'Yes' in r:
                ys,vys=r['Yes']; no,vno=r.get('No',(None,None))
                e_y=R[mnmx][0]-ys; e_n=(1-R[mnmx][1])-no
                out[label]['mkts'][key]={'mid':ids[key],'q':META[ids[key]]['q'],'liq':META[ids[key]]['liq'],
                    'yes_ask':ys,'no_ask':no,'model':R[mnmx],'edge_yes':round(e_y,3),'edge_no':round(e_n,3)}
                if e_y>=0.05: flags.append((label,lab+' COVER',round(e_y,3),ys,ids[key]))
                if e_n>=0.05: flags.append((label,lab+' NOCOVER',round(e_n,3),no,ids[key]))
                print('   %-6s cov [%.3f-%.3f] ask %.3f edge %+.3f | nocov ask %s edge %s'%(lab,R[mnmx][0],R[mnmx][1],ys,e_y,no,round(e_n,3)),flush=True)
    for side,midk,mnmx in [('1X2 H','1x2h','ph'),('1X2 D','1x2d','pd'),('1X2 A','1x2a','pa')]:
        if ids.get(midk):
            r=two_side(ids[midk])
            if r and 'Yes' in r:
                ys,vys=r['Yes']
                e_y=R[mnmx][0]-ys
                out[label]['mkts'][side]={'mid':ids[midk],'q':META[ids[midk]]['q'],'liq':META[ids[midk]]['liq'],
                    'yes_ask':ys,'model':R[mnmx],'edge_yes':round(e_y,3)}
                if e_y>=0.05: flags.append((label,side+' BUY',round(e_y,3),ys,ids[midk]))
                print('   %-6s yes [%.3f-%.3f] ask %.3f edge %+.3f'%(side,R[mnmx][0],R[mnmx][1],ys,e_y),flush=True)

print()
print('FLAGS >= +5c (conservative min-of-range vs ask):')
for f in sorted(flags,key=lambda x:-x[2]):
    print('  %-17s %-16s edge +%.3f ask %.3f mid %s'%f)
json.dump(out,open(RAW+'/model6.json','w'),indent=1)
print('saved model6.json')
