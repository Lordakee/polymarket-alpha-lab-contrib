import json, math, urllib.request, time
from collections import defaultdict

RAW = '/home/ubuntu/paper-sim/round5/raw'
XG = json.load(open(RAW + '/xg_understat_5c.json'))
LEAGUES = ['EPL','La_liga','Serie_A','Bundesliga','Ligue_1']

# ---------- market data (Gamma by numeric id -> CLOB books) ----------
MIDS = ['5314743','5317024','5314572','5314705','5314885','5316904','5314336','5316843','5314337','5314085']

def get(url, tries=3, timeout=25):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36',
                'Accept': 'application/json'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except Exception:
            if i == tries - 1: raise
            time.sleep(1.5)

mkts = {}
for mid in MIDS:
    try:
        m = get('https://gamma-api.polymarket.com/markets/%s' % mid)
        toks = m.get('clobTokenIds')
        if isinstance(toks, str): toks = json.loads(toks)
        outs = m.get('outcomes')
        if isinstance(outs, str): outs = json.loads(outs)
        mkts[mid] = {
            'q': m.get('question'), 'slug': m.get('slug'),
            'closed': m.get('closed'), 'active': m.get('active'),
            'gameStartTime': m.get('gameStartTime'), 'endDate': m.get('endDate'),
            'outcomes': outs, 'tokens': toks, 'liq': m.get('liquidityNum'),
        }
        print('GAMMA', mid, (m.get('question') or '')[:52], 'start=', m.get('gameStartTime'))
    except Exception as e:
        print('GAMMA ERR', mid, repr(e))
    time.sleep(0.3)

def book(tid):
    for i in range(3):
        try:
            return get('https://clob.polymarket.com/book?token_id=' + tid, timeout=15)
        except Exception:
            if i == 2: return {'err': 'fetch'}
            time.sleep(1.2)

def ask_side(b, dollars=400.0):
    """executable VWAP ask walking the ladder to spend `dollars`; returns (best_ask, vwap, depth_ok)"""
    asks = sorted(b.get('asks', []), key=lambda l: float(l['price']))
    if not asks: return None, None, False
    best = float(asks[0]['price'])
    cash = 0.0; sh = 0.0
    for l in asks:
        p = float(l['price']); sz = float(l['size'])
        take = min(sz, (dollars - cash) / p)
        if take <= 0: break
        cash += take * p; sh += take
        if cash >= dollars - 1e-9: break
    vwap = (cash / sh) if sh > 0 else best
    return best, round(vwap, 4), cash >= dollars - 1e-6

books = {}
for mid, m in mkts.items():
    books[mid] = {}
    for side, tok in zip(m['outcomes'], m['tokens']):
        bb = book(tok)
        books[mid][side] = bb
        time.sleep(0.25)

# ---------- model (identical methodology to round-5b) ----------
def load(lg, se): return XG['%s_%s' % (lg, se)]

print()
for lg in LEAGUES:
    for se in ['2025','2026']:
        d = load(lg, se)
        ms = [m for m in d['dates'] if m.get('isResult') and m.get('xG') and m['xG'].get('h')]
        xg = sum(float(m['xG']['h'])+float(m['xG']['a']) for m in ms)/len(ms)
        gl = sum(int(m['goals']['h'])+int(m['goals']['a']) for m in ms)/len(ms)
        o25 = sum(1 for m in ms if int(m['goals']['h'])+int(m['goals']['a'])>=3)/len(ms)
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

# mid, label, home(understat), away(understat), task YES ask
FIX = [
    ('5314743','UDI-LEC Serie A',      'Udinese','Lecce',            0.475),
    ('5317024','OSA-RAC LaLiga',       'Osasuna','Racing Santander',0.575),
    ('5314572','FIO-COM Serie A',      'Fiorentina','Como',          0.595),
    ('5314705','LOR-MON L1',           'Lorient','Monaco',          0.485),
    ('5314885','ANG-OM L1',            'Angers','Marseille',        0.585),
    ('5316904','MAL-RSO LaLiga',       'Malaga','Real Sociedad',    0.575),
    ('5314336','MIL-ATA Serie A',      'AC Milan','Atalanta',       0.575),
    ('5316843','RMA-SEV LaLiga',       'Real Madrid','Sevilla',     0.695),
    ('5314337','LEV-FRE Bund',         'Leverkusen','Freiburg',     0.675),
    ('5314085','JUV-LAZ Serie A',      'Juventus','Lazio',          0.495),
]

DOLLARS = 400.0
results={}
flags=[]
print()
for mid,label,h,a,task_ask in FIX:
    m = mkts.get(mid)
    ovb = books.get(mid,{}).get('Over',{}); unb = books.get(mid,{}).get('Under',{})
    ov_best,ov_vwap,ov_ok = ask_side(ovb, DOLLARS)
    un_best,un_vwap,un_ok = ask_side(unb, DOLLARS)
    ov_ask = ov_best if ov_best is not None else task_ask
    un_ask = un_best if un_best is not None else round(1-task_ask,3)

    variants={}
    for name,LASTW,PRIOR,rho,mode in SWEEPS:
        shr=0.8 if name.startswith('cross-shrink .8') else (1.1 if name.startswith('cross-shrink 1.1') else 1.0)
        out=model_game(h,a,LASTW,PRIOR,rho,mode,shr)
        if out is None: continue
        o25,o35,o15,lh,la=out
        variants[name]={'o25':round(o25,4),'o35':round(o35,4),'o15':round(o15,4),'lh':round(lh,3),'la':round(la,3)}
    if not variants:
        print('%-20s TEAM NOT FOUND'%label); continue
    vals=[v['o25'] for v in variants.values()]
    o_min,o_max=round(min(vals),4),round(max(vals),4)
    o_med=round(sorted(vals)[len(vals)//2],4)
    u_min=round(1-o_max,4)
    edge_ov=round(o_min-ov_ask,4); edge_un=round(u_min-un_ask,4)
    base=list(variants.values())[0]
    lam=('%.2f/%.2f'%(base['lh'],base['la']))
    results[label]={'mid':mid,'teams':[h,a],'over_ask':ov_ask,'under_ask':un_ask,
        'ov_vwap400':ov_vwap,'un_vwap400':un_vwap,'ov_depth':ov_ok,'un_depth':un_ok,
        'variants':variants,'o25_min':o_min,'o25_max':o_max,'o25_med':o_med,
        'edge_over_min':edge_ov,'edge_under_min':edge_un,'lam':lam,'liq':m.get('liq') if m else None}
    flag = 'OVER' if edge_ov>=0.05 else ('UNDER' if edge_un>=0.05 else '')
    if flag: flags.append((label,flag))
    print('%-20s %s lam=%s O2.5 med=%.3f rng=[%.3f-%.3f] ask O=%.3f U=%.3f | edge(min) O=%+.3f U=%+.3f %s' % (
        label, mid, lam, o_med,o_min,o_max, ov_ask, un_ask, edge_ov, edge_un, '*** '+flag if flag else ''))

json.dump({'markets':mkts,'results':results}, open(RAW+'/model_round5c.json','w'), indent=1)
print()
print('saved model_round5c.json | flags:', flags or 'NONE')
