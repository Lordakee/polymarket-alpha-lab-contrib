import json, math, urllib.request, time, re
from collections import defaultdict

RAW = '/home/ubuntu/paper-sim/round5/raw'
XG = json.load(open(RAW + '/xg_understat_5c.json'))
DISC = json.load(open(RAW + '/discover5d3.json'))
LEAGUES = ['EPL','La_liga','Serie_A','Bundesliga','Ligue_1']

def load(lg, se): return XG['%s_%s' % (lg, se)]

# ---------- ratings infrastructure (identical to round-5c) ----------
_cache = {}
def ratings_for(lg, LASTW, PRIOR, mode):
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
        last[t['title']]=(sum(float(x['xG']) for x in h)/len(h), sum(float(x['xGA']) for x in h)/len(h))
    r={}
    for t in d26['teams'].values():
        h=t['history']; name=t['title']
        if not h: continue
        cf=sum(float(x['xG']) for x in h)/len(h)
        ca=sum(float(x['xGA']) for x in h)/len(h)
        nc=len(h)
        if mode=='cur': f,a=cf,ca
        elif mode=='last': f,a=last.get(name,(lgf,lgf))
        else:
            lf,la_=last.get(name,(lgf,lgf))
            f=(nc*cf+LASTW*38*lf+PRIOR*lgf)/(nc+LASTW*38+PRIOR)
            a=(nc*ca+LASTW*38*la_+PRIOR*lgf)/(nc+LASTW*38+PRIOR)
        r[name]=(f/lgf,a/lgf)
    _cache[key]=(bh,ba,lgf,r)
    return _cache[key]

SWEEPS = [
    ('blend w=.5 p=8 rho0', 0.5, 8, 0.0, 'blend'),
    ('blend w=.5 p=8 DC',   0.5, 8, -0.08, 'blend'),
    ('blend w=1.0 p=8',     1.0, 8, 0.0, 'blend'),
    ('blend w=.25 p=8',     0.25, 8, 0.0, 'blend'),
    ('blend w=.5 p=16',     0.5, 16, 0.0, 'blend'),
    ('blend w=.5 p=4',      0.5, 4, 0.0, 'blend'),
    ('current-only',        None, None, 0.0, 'cur'),
    ('last-only',           None, None, 0.0, 'last'),
    ('cross-shrink .8',     0.5, 8, 0.0, 'blend'),
    ('cross-shrink 1.1',    0.5, 8, 0.0, 'blend'),
]

def pois(l,k): return math.exp(-l)*l**k/math.factorial(k)
def grid(lh,la,N=10,rho=0.0):
    g=[[pois(lh,i)*pois(la,j) for j in range(N+1)] for i in range(N+1)]
    if rho:
        g[0][0]*=max(1-lh*la*rho,.01); g[0][1]*=max(1+lh*rho,.01)
        g[1][0]*=max(1+la*rho,.01); g[1][1]*=max(1-rho,.01)
    s=sum(sum(r) for r in g)
    return [[v/s for v in row] for row in g]

TEAM_LEAGUE={}
for lg in LEAGUES:
    for t in load(lg,'2026')['teams'].values(): TEAM_LEAGUE[t['title']]=lg
def find_team(sub):
    for name,lg in TEAM_LEAGUE.items():
        if sub.lower()==name.lower(): return name,lg
    for name,lg in TEAM_LEAGUE.items():
        if sub.lower() in name.lower(): return name,lg
    return None,None

def lams(home,away,LASTW,PRIOR,rho,mode,shrink=1.0):
    hn,lgh=find_team(home); an_,lga=find_team(away)
    if lgh is None or lga is None or lgh!=lga: return None
    bh1,ba1,lgf1,r1=ratings_for(lgh,LASTW,PRIOR,mode)
    bh2,ba2,lgf2,r2=ratings_for(lga,LASTW,PRIOR,mode)
    if hn not in r1 or an_ not in r2: return None
    bh=(bh1+bh2)/2.0; ba=(ba1+ba2)/2.0
    ah,dh=r1[hn]; aa,da=r2[an_]
    return bh*(ah**shrink)*(da**shrink), ba*(aa**shrink)*(dh**shrink)

# ---------- league 1X2 base rates (realized, 2025+2026 understat) ----------
BASE={}
for lg in LEAGUES:
    n=h_=d_=a_=0
    for se in ['2025','2026']:
        for m in load(lg,se)['dates']:
            if m.get('isResult'):
                gh,ga=int(m['goals']['h']),int(m['goals']['a'])
                n+=1; h_+= 1 if gh>ga else 0; d_+= 1 if gh==ga else 0; a_+= 1 if ga>gh else 0
    BASE[lg]={'h':h_/n,'d':d_/n,'a':a_/n,'n':n}
    print('BASE %-10s n=%4d H=%.3f D=%.3f A=%.3f' % (lg,n,h_/n,d_/n,a_/n))

# ---------- market probabilities from grid ----------
def market_probs(g):
    ph=pd=pa=btts=o25=0.0
    marg=defaultdict(float)
    for i in range(len(g)):
        for j in range(len(g)):
            p=g[i][j]
            if i>j: ph+=p
            elif i==j: pd+=p
            else: pa+=p
            if i>=1 and j>=1: btts+=p
            if i+j>=3: o25+=p
            marg[i-j]+=p
    return {'ph':ph,'pd':pd,'pa':pa,'btts':btts,'o25':o25,
            'cov_h15':sum(v for k,v in marg.items() if k>=2),
            'cov_h25':sum(v for k,v in marg.items() if k>=3),
            'cov_a15':sum(v for k,v in marg.items() if k<=-2),
            'cov_a25':sum(v for k,v in marg.items() if k<=-3)}

def o25_1h(lh,la,share=0.45,rho=0.0):
    g=grid(lh*share,la*share,8,rho)
    return sum(g[i][j] for i in range(len(g)) for j in range(len(g)) if i+j>=3)

# ---------- fixtures ----------
FIX = {
 'BOU-SUN': ('Bournemouth','Sunderland','EPL'),
 'MIL-ATA': ('AC Milan','Atalanta','Serie_A'),
 'LEE-MUN': ('Leeds','Manchester United','EPL'),
 'NFO-ARS': ('Nottingham Forest','Arsenal','EPL'),
 'BHA-CRY': ('Brighton','Crystal Palace','EPL'),
 'JUV-LAZ': ('Juventus','Lazio','Serie_A'),
 'ANG-OM':  ('Angers','Marseille','Ligue_1'),
}

def pick(tag):
    evs = DISC[tag]
    sel = {'btts':None,'h1ou25':None,'ou25':None,'spreads':{}, 'x1':{}}
    main_done=False
    for ev in evs:
        title = ev['title'] or ''
        for m in ev['markets']:
            q = m['q'] or ''
            if ' - ' not in title:
                if 'end in a draw' in q.lower():
                    sel['x1'][m['id']] = {'q':q,'role':'draw','team':None,'m':m}
                elif 'win on 2026-10-18' in q:
                    team = q.split(' win ')[0].replace('Will ','')
                    role = 'home' if team.lower().startswith(tag.split('-')[0].lower()[:4]) else 'away'
                    sel['x1'][m['id']] = {'q':q,'role':role,'team':team,'m':m}
            if ' - More Markets' in title:
                if 'Both Teams to Score' in q and 'Half' not in q:
                    sel['btts']=m
                if re.search(r': 1st Half O/U 2\.5$', q) and 'Corners' not in q:
                    sel['h1ou25']=m
                if re.search(r': O/U 2\.5$', q) and 'Corners' not in q and '1st' not in q and '2nd' not in q:
                    sel['ou25']=m
                mm = re.match(r'Spread: (.+) \((-[\d.]+)\)$', q)
                if mm:
                    line = float(mm.group(2))
                    if line in (-1.5,-2.5):
                        sel['spreads'][m['id']] = {'q':q,'team':mm.group(1),'line':line,'m':m}
    return sel

# ---------- clob books ----------
def get(url, tries=3, timeout=20):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except Exception:
            if i==tries-1: raise
            time.sleep(1.2)

def book(tid):
    for i in range(3):
        try:
            return get('https://clob.polymarket.com/book?token_id=' + tid, timeout=15)
        except Exception:
            if i==2: return {'err':'fetch'}
            time.sleep(1.0)

def ask_side(b, dollars=400.0):
    asks = sorted(b.get('asks',[]), key=lambda l: float(l['price']))
    if not asks: return None,None,False
    best=float(asks[0]['price'])
    cash=0.0; sh=0.0
    for l in asks:
        p=float(l['price']); sz=float(l['size'])
        take=min(sz,(dollars-cash)/p)
        if take<=0: break
        cash+=take*p; sh+=take
        if cash>=dollars-1e-9: break
    vwap=(cash/sh) if sh>0 else best
    return best, round(vwap,4), cash>=dollars-1e-6

DOLLARS=400.0
print()
report={}
flags=[]
for tag,(h,a,lg) in FIX.items():
    sel = pick(tag)
    row={'tag':tag,'home':h,'away':a,'league':lg,'markets':{}}
    vps=[]
    for name,LASTW,PRIOR,rho,mode in SWEEPS:
        shr=0.8 if name.startswith('cross-shrink .8') else (1.1 if name.startswith('cross-shrink 1.1') else 1.0)
        lm=lams(h,a,LASTW,PRIOR,rho,mode,shr)
        if lm is None: continue
        lh,la=lm
        g=grid(lh,la,10,rho)
        mp=market_probs(g)
        mp['o25_1h']=o25_1h(lh,la,0.45,rho)
        base=BASE[lg]
        fav_is_home = mp['ph']>=mp['pa']
        pdraw_c = 0.7*mp['pd'] + 0.3*base['d']
        if fav_is_home:
            pdog_c=0.7*mp['pa']+0.3*base['a']; pfav_c=1-pdraw_c-pdog_c
            mp['ph_c'],mp['pa_c']=pfav_c,pdog_c
        else:
            pdog_c=0.7*mp['ph']+0.3*base['h']; pfav_c=1-pdraw_c-pdog_c
            mp['ph_c'],mp['pa_c']=pdog_c,pfav_c
        mp['pd_c']=pdraw_c
        mp['lh'],mp['la']=round(lh,3),round(la,3)
        vps.append((name,mp))
    if not vps:
        print(tag,'MODEL FAIL (team not found)'); continue
    def rng(key):
        vals=[mp[key] for _,mp in vps]; return (min(vals),sorted(vals)[len(vals)//2],max(vals))
    row['lam_base']='%.2f/%.2f'%(vps[0][1]['lh'],vps[0][1]['la'])
    row['n_variants']=len(vps)

    def price(m_obj, side_name):
        outs = m_obj['outcomes']; toks = m_obj['tokens']
        if side_name not in outs: return None,None,None
        tok = toks[outs.index(side_name)]
        bb = book(tok); time.sleep(0.15)
        return ask_side(bb, DOLLARS)

    # A. BTTS
    m=sel.get('btts')
    if m:
        yb,yv,yok=price(m,'Yes'); nb,nv,nok=price(m,'No')
        mn,md,mx=rng('btts')
        ey = mn-yb if yb is not None else None
        en = (1-mx)-nb if nb is not None else None
        fl = 'YES' if (ey is not None and ey>=0.05) else ('NO' if (en is not None and en>=0.05) else '')
        row['markets']['BTTS']={'mid':m['id'],'model':[round(mn,4),round(md,4),round(mx,4)],
            'yes_ask':yb,'no_ask':nb,'yes_vwap':yv,'no_vwap':nv,
            'edge_yes':round(ey,4) if ey is not None else None,
            'edge_no':round(en,4) if en is not None else None,'flag':fl,'liq':m.get('liq'),'vol24':m.get('vol24')}
        if fl: flags.append((tag,'BTTS',fl))
    # B. 1H O/U 2.5
    m=sel.get('h1ou25')
    if m:
        ob,ov,ook=price(m,'Over'); ub,uv,uok=price(m,'Under')
        mn,md,mx=rng('o25_1h')
        eo = mn-ob if ob is not None else None
        eu = (1-mx)-ub if ub is not None else None
        fl = 'OVER' if (eo is not None and eo>=0.05) else ('UNDER' if (eu is not None and eu>=0.05) else '')
        row['markets']['1H_OU25']={'mid':m['id'],'model':[round(mn,4),round(md,4),round(mx,4)],
            'over_ask':ob,'under_ask':ub,'over_vwap':ov,'under_vwap':uv,
            'edge_over':round(eo,4) if eo is not None else None,'edge_under':round(eu,4) if eu is not None else None,
            'flag':fl,'liq':m.get('liq'),'vol24':m.get('vol24')}
        if fl: flags.append((tag,'1H_OU25',fl))
    # C. Spreads -1.5 / -2.5 both teams
    for mid,s in sel['spreads'].items():
        team=s['team']; line=s['line']
        is_home_side = team.lower().startswith(h.lower()[:8])
        keyname = 'SPREAD_%s_%s' % ('H' if is_home_side else 'A', str(line).replace('-','m'))
        yb,yv,yok=price(s['m'],'Yes'); nb,nv,nok=price(s['m'],'No')
        mk = ('cov_h' if is_home_side else 'cov_a') + ('15' if abs(line)==1.5 else '25')
        mn,md,mx=rng(mk)
        ey = mn-yb if yb is not None else None
        en = (1-mx)-nb if nb is not None else None
        fl = 'YES' if (ey is not None and ey>=0.05) else ('NO' if (en is not None and en>=0.05) else '')
        row['markets'][keyname]={'mid':mid,'team':team,'line':line,'model':[round(mn,4),round(md,4),round(mx,4)],
            'yes_ask':yb,'no_ask':nb,'edge_yes':round(ey,4) if ey is not None else None,
            'edge_no':round(en,4) if en is not None else None,'flag':fl,'liq':s['m'].get('liq')}
        if fl: flags.append((tag,keyname,fl))
    # D. 1X2 corrected
    for mid,xx in sel['x1'].items():
        role=xx['role']
        mk={'home':'ph_c','draw':'pd_c','away':'pa_c'}[role]
        yb,yv,yok=price(xx['m'],'Yes')
        mn,md,mx=rng(mk)
        ey=mn-yb if yb is not None else None
        fl='YES' if (ey is not None and ey>=0.05) else ''
        row['markets']['X1_%s'%role]={'mid':mid,'q':xx['q'],'model':[round(mn,4),round(md,4),round(mx,4)],
            'ask':yb,'vwap':yv,'edge':round(ey,4) if ey is not None else None,'flag':fl,'liq':xx['m'].get('liq')}
        if fl: flags.append((tag,'X1_%s'%role,fl))
    # bonus: full O/U 2.5 for BOU-SUN (position refresh)
    if tag=='BOU-SUN' and sel.get('ou25'):
        m=sel['ou25']
        ob,ov,ook=price(m,'Over'); ub,uv,uok=price(m,'Under')
        mn,md,mx=rng('o25')
        row['markets']['OU25_POS']={'mid':m['id'],'model':[round(mn,4),round(md,4),round(mx,4)],
            'over_ask':ob,'under_ask':ub,'over_vwap':ov,'under_vwap':uv,'liq':m.get('liq')}
    report[tag]=row
    print('%-8s lam=%s nvar=%d mkts=%s' % (tag,row['lam_base'],len(vps),sorted(row['markets'].keys())))

json.dump({'report':report,'flags':flags}, open(RAW+'/model_round5d.json','w'), indent=1)
print()
print('FLAGS:', flags if flags else 'NONE')
print('saved model_round5d.json')
