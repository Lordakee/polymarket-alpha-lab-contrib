import json, math
from collections import defaultdict

XG = json.load(open('/home/ubuntu/paper-sim/round5/raw/xg_understat.json'))
LEAGUES = ['EPL','La_liga','Serie_A','Bundesliga','Ligue_1']

def load(lg, se): return XG['%s_%s' % (lg, se)]

env = {}
for lg in LEAGUES:
    env[lg] = {}
    for se in ['2025','2026']:
        d = load(lg, se)
        ms = [m for m in d['dates'] if m.get('isResult') and m.get('xG') and m['xG'].get('h')]
        xg = sum(float(m['xG']['h'])+float(m['xG']['a']) for m in ms)/len(ms)
        gl = sum(int(m['goals']['h'])+int(m['goals']['a']) for m in ms)/len(ms)
        o25 = sum(1 for m in ms if int(m['goals']['h'])+int(m['goals']['a'])>=3)/len(ms)
        env[lg][se] = {'xg':xg,'goals':gl,'n':len(ms),'o25':o25}
        print('ENV %-10s %s n=%3d goals=%.2f xG=%.2f O2.5=%.3f' % (lg,se,len(ms),gl,xg,o25))

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

def outs(g):
    ptot=defaultdict(float)
    for i in range(len(g)):
        for j in range(len(g)): ptot[i+j]+=g[i][j]
    return (sum(v for t,v in ptot.items() if t>=3), sum(v for t,v in ptot.items() if t>=4),
            sum(v for t,v in ptot.items() if t>=2))

TEAM_LEAGUE={}
for lg in LEAGUES:
    for t in load(lg,'2026')['teams'].values(): TEAM_LEAGUE[t['title']]=lg

def find_team(sub):
    for name,lg in TEAM_LEAGUE.items():
        if sub.lower()==name.lower(): return name,lg
    for name,lg in TEAM_LEAGUE.items():
        if sub.lower() in name.lower(): return name,lg
    return None,None

def model_game(home,away,LASTW,PRIOR,rho,mode,shrink=1.0):
    hn,lgh=find_team(home); an_,lga=find_team(away)
    if lgh is None or lga is None or lgh!=lga: return None
    bh1,ba1,lgf1,r1=ratings_for(lgh,LASTW,PRIOR,mode)
    bh2,ba2,lgf2,r2=ratings_for(lga,LASTW,PRIOR,mode)
    if hn not in r1 or an_ not in r2: return None
    bh=(bh1+bh2)/2.0; ba=(ba1+ba2)/2.0
    ah,dh=r1[hn]; aa,da=r2[an_]
    lh=bh*(ah**shrink)*(da**shrink); la=ba*(aa**shrink)*(dh**shrink)
    o25,o35,o15=outs(grid(lh,la,10,rho))
    return o25,o35,o15,lh,la

# label, home, away, league-note, over_ask, under_ask (CLOB executable 2026-10-17 15:40Z)
FIX = [
    ('BOL-INT 16:00Z Serie A', 'Bologna','Inter', 0.61, 0.40),
    ('BET-BAR 16:30Z LaLiga',  'Betis','Barcelona', 0.80, 0.21),
    ('BAY-RBL 16:30Z Bund',    'Bayern','Leipzig', 0.88, 0.13),
    ('ROM-GEN 18:45Z Serie A', 'Roma','Genoa', 0.51, 0.50),
    ('LIL-BRE 18:45Z L1',      'Lille','Brest', 0.56, 0.45),
    ('VAL-ATH 19:00Z LaLiga',  'Valencia','Athletic', 0.45, 0.56),
    ('BRI-CRY 10/18 EPL',      'Brighton','Crystal Palace', 0.63, 0.38),
    ('BOU-SUN 10/18 EPL',      'Bournemouth','Sunderland', 0.51, 0.50),
    ('LEE-MUN 10/18 EPL',      'Leeds','Manchester United', 0.58, 0.43),
]

results={}
print()
for label,h,a,ov_ask,un_ask in FIX:
    hn,l1=find_team(h); an_,l2=find_team(a)
    results[label]={'teams':[hn,an_],'leagues':[l1,l2],'over_ask':ov_ask,'under_ask':un_ask}
    variants={}
    for name,LASTW,PRIOR,rho,mode in SWEEPS:
        shr=0.8 if name.startswith('cross-shrink .8') else (1.1 if name.startswith('cross-shrink 1.1') else 1.0)
        out=model_game(h,a,LASTW,PRIOR,rho,mode,shr)
        if out is None: continue
        o25,o35,o15,lh,la=out
        variants[name]={'o25':round(o25,4),'o35':round(o35,4),'o15':round(o15,4),'lh':round(lh,3),'la':round(la,3)}
    if not variants:
        print('%-26s TEAM NOT FOUND (%s/%s vs %s/%s)' % (label,h,l1,a,l2)); continue
    vals=[v['o25'] for v in variants.values()]
    o_min,o_max=round(min(vals),4),round(max(vals),4)
    o_med=round(sorted(vals)[len(vals)//2],4)
    u_min=round(1-o_max,4)
    edge_ov=round(o_min-ov_ask,4); edge_un=round(u_min-un_ask,4)
    base=list(variants.values())[0]
    results[label].update(variants=variants,o25_min=o_min,o25_max=o_max,o25_med=o_med,
        edge_over_min=edge_ov,edge_under_min=edge_un,lambda_base=(base['lh'],base['la']))
    flag=' ***OVER***' if edge_ov>=0.05 else (' ***UNDER***' if edge_un>=0.05 else '')
    print('%-26s %-18s/%-18s lam=%.2f/%.2f O2.5 med=%.3f rng=[%.3f-%.3f] ask O=%.2f U=%.2f | edge(min) O=%+.3f U=%+.3f%s' % (
        label,hn,an_,base['lh'],base['la'],o_med,o_min,o_max,ov_ask,un_ask,edge_ov,edge_un,flag))

json.dump(results, open('/home/ubuntu/paper-sim/round5/raw/model_round5b.json','w'), indent=1)
print()
print('saved model_round5b.json')
