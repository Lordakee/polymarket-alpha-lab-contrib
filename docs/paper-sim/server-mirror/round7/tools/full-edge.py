import json, math, datetime, re

RAW='/home/ubuntu/paper-sim/round7/raw'
ys=json.load(open(RAW+'/yahoo_crypto7.json'))
res=json.load(open(RAW+'/discover7.json'))
SPOT0={'ETH':2393.59,'BTC':81539.23}

# ---------- realized vol ----------
def rets(sym,rng,iv):
    r=ys['%s_%s_%s'%(sym,rng,iv)]['chart']['result'][0]
    ts=r['timestamp']; q=r['indicators']['quote'][0]
    cs=[(t,c) for t,c in zip(ts,q['close']) if c is not None]
    out=[]
    for i in range(1,len(cs)):
        if cs[i][0]>cs[i-1][0]:
            out.append(math.log(cs[i][1]/cs[i-1][1]))
    return out, cs[-1]

def vol_per_day(sym):
    out={}
    for rng,iv,ppd,lbl in [('3mo','1d',1.0,'daily_63d'),('1mo','1h',24.0,'hourly_30d'),('5d','15m',96.0,'15m_5d'),('1d','5m',288.0,'5m_1d')]:
        rs,_=rets(sym,rng,iv)
        if len(rs)<5: continue
        n_eff=len(rs)/ppd  # days represented
        sd=math.sqrt(sum(x*x for x in rs)/len(rs))*math.sqrt(ppd)
        out[lbl]=(sd,len(rs),n_eff)
    return out

V={'ETH':vol_per_day('ETH-USD'),'BTC':vol_per_day('BTC-USD')}
for s in V:
    print(s,'spot=',SPOT0[s])
    for k,(sd,n,ne) in V[s].items(): print('   %-12s sigma_d=%.4f (%.1f%%/d) n=%d days~%.1f'%(k,sd,sd*100,n,ne))

SPOT={'ETH':float(ys['ETH-USD_1d_5m']['chart']['result'][0]['meta']['regularMarketPrice']),
      'BTC':float(ys['BTC-USD_1d_5m']['chart']['result'][0]['meta']['regularMarketPrice'])}
SPOT['ETH']=2393.59; SPOT['BTC']=81539.23
print('SPOT',SPOT)
NOW=datetime.datetime(2026,10,20,0,20,tzinfo=datetime.timezone.utc)

def N(x): return 0.5*math.erfc(-x/math.sqrt(2.0))
def touch(S,K,sig_d,T):
    # P(price crosses K at any time before T), either side; first-passage GBM zero drift
    if K==S: return 1.0
    sigT=sig_d*math.sqrt(T)
    if sigT<=0: return 1.0 if (K<S) else 0.0
    a=math.log(S/K)/sigT
    p=2*N(-abs(a))
    return min(max(p,0.0),1.0)
def touch_dn(S,K,sig_d,T):
    if K>=S: return 1.0
    sigT=sig_d*math.sqrt(T)
    a=math.log(S/K)/sigT
    return 2*N(-a) if a>0 else min(2*N(-a),1.0)
def touch_up(S,K,sig_d,T):
    if K<=S: return 1.0
    return touch_dn(S,S*S/K,sig_d,T)  # mirror
def prob_above_close(S,K,sig_d,T):
    # P(S_T >= K), zero drift
    sigT=sig_d*math.sqrt(T)
    if sigT<=0: return 1.0 if S>=K else 0.0
    return N(math.log(S/K)/sigT)

def conservative(fn,S,K,Ts):
    vals=[fn(S,K,sd,T) for sd in [0.8*v for v in [1]] ] # placeholder

def model_range(fn,sym,S,K,T):
    vs=[]
    for lbl,(sd,_,_) in V[sym].items():
        if lbl=='5m_1d': continue  # too noisy
        vs.append(fn(S,K,sd,T))
    return min(vs),max(vs)

# ---------- polymarket crypto markets ----------
def toks(m):
    try: return json.loads(m.get('clobTokenIds') or '[]')
    except Exception: return []

cands=[]
for tag in ['crypto','eth','btc']:
    for e in res.get(tag,[]):
        t=(e.get('title') or '')
        if not e.get('markets'): continue
        for m in e.get('markets'):
            if m.get('closed'): continue
            q=(m.get('question') or m.get('groupItemTitle') or '')
            liq=m.get('liquidityNum') or 0
            if liq<5000: continue
            thr=m.get('groupItemThreshold')
            cands.append((t,q,m,liq,thr))

# classify
rows=[]
for t,q,m,liq,thr in cands:
    sym=None; kind=None; K=None
    mm=re.match(r'^Will (Bitcoin|Ethereum) reach \$([\d,]+(?:\.\d+)?)\s*k?\b',q.strip())
    if mm: sym,kind='BTC' if mm.group(1)=='Bitcoin' else 'ETH','touch_up'
    else:
        mm=re.match(r'^Will (Bitcoin|Ethereum) dip to \$([\d,]+(?:\.\d+)?)\s*k?\b',q.strip())
        if mm: sym,kind='BTC' if mm.group(1)=='Bitcoin' else 'ETH','touch_dn'
        else:
            mm=re.match(r'^(Bitcoin|Ethereum) above \$([\d,]+(?:\.\d+)?)\s*k? on October (\d+)',q.strip())
            if mm: sym,kind='BTC' if mm.group(1)=='Bitcoin' else 'ETH','daily_above'
    if not sym: continue
    K=float(mm.group(2).replace(',',''))
    if K<1000 and K>50: K*=1000  # 82.5k style written as 82,500 normally; skip
    pr=json.loads(m.get('outcomePrices') or '[]')
    bb=m.get('bestBid'); ba=m.get('bestAsk')
    rows.append(dict(sym=sym,kind=kind,K=K,q=q,pr=pr,bb=bb,ba=ba,liq=liq,
                     end=m.get('endDate') or '',day=None))

# time to expiry
def T_for(r):
    try: ed=datetime.datetime.strptime(r['end'][:19],'%Y-%m-%dT%H:%M:%S').replace(tzinfo=datetime.timezone.utc)
    except Exception: return None
    return (ed-NOW).total_seconds()/86400.0

print()
print('%-4s %-11s %9s %6s %6s %6s %6s %6s %7s  %s'%('sym','kind','K','T(d)','bid','ask','m_lo','m_hi','c_edge','q'))
seen=set()
edges=[]
for r in sorted(rows,key=lambda x:-x['liq']):
    key=(r['sym'],r['kind'],r['K'],r['q'])
    if key in seen: continue
    seen.add(key)
    T=T_for(r)
    if T is None or T<=0 or T>45: continue
    S=SPOT[r['sym']]
    if r['kind']=='daily_above':
        lo,hi=model_range(prob_above_close,r['sym'],S,r['K'],T)
    elif r['kind']=='touch_up':
        lo,hi=model_range(touch_up,r['sym'],S,r['K'],T)
    else:
        lo,hi=model_range(touch_dn,r['sym'],S,r['K'],T)
    yes_ask=r['ba'] if r['ba'] else (r['pr'][0] if r['pr'] else None)
    if yes_ask is None: continue
    ce=lo-yes_ask
    edges.append((ce,r['sym'],r['kind'],r['K'],T,r['bb'],yes_ask,lo,hi,r['q'][:55],r['liq']))

for ce,sym,kind,K,T,bb,ask,lo,hi,q,liq in sorted(edges,key=lambda x:-x[0])[:45]:
    print('%-6s %-12s %9.0f %6.2f %7s %7s %7.3f %7.3f  %+7.3f  %s [$%d]'%(sym,kind,K,T,bb,ask,lo,hi,ce,q,liq))

json.dump([dict(ce=round(e[0],4),sym=e[1],kind=e[2],K=e[3],T=round(e[4],2),bid=e[5],ask=e[6],m_lo=round(e[7],4),m_hi=round(e[8],4),q=e[9],liq=e[10]) for e in edges],open(RAW+'/crypto7_edges.json','w'),indent=1)
