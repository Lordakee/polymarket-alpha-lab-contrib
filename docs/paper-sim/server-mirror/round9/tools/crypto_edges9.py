import json, math, datetime, re

ys=json.load(open('/home/ubuntu/paper-sim/round9/raw/yahoo_crypto9.json'))
res=json.load(open('/home/ubuntu/paper-sim/round9/raw/discover9.json'))
NOW=datetime.datetime(2026,10,21,3,55,tzinfo=datetime.timezone.utc)

def rets(sym,rng,iv):
    r=ys['%s-USD_%s_%s'%(sym,rng,iv)]['chart']['result'][0]
    ts=r['timestamp']; q=r['indicators']['quote'][0]
    cs=[(t,c) for t,c in zip(ts,q['close']) if c is not None]
    out=[]
    for i in range(1,len(cs)):
        if cs[i][0]>cs[i-1][0]:
            out.append(math.log(cs[i][1]/cs[i-1][1]))
    return out, cs[-1]

def vol_per_day(sym):
    out={}
    for rng,iv,ppd,lbl in [('3mo','1d',1.0,'daily_63d'),('1mo','1h',24.0,'hourly_30d'),('5d','15m',96.0,'15m_5d')]:
        rs,_=rets(sym,rng,iv)
        if len(rs)<5: continue
        sd=math.sqrt(sum(x*x for x in rs)/len(rs))*math.sqrt(ppd)
        out[lbl]=(sd,len(rs))
    return out

SPOT={'ETH':2445.59,'BTC':82725.69}
V={'ETH':vol_per_day('ETH'),'BTC':vol_per_day('BTC')}
for s in V:
    print(s,'spot=',SPOT[s])
    for k,(sd,n) in V[s].items(): print('   %-12s sigma_d=%.4f (%.1f%%/d) n=%d'%(k,sd,sd*100,n))

def N(x): return 0.5*math.erfc(-x/math.sqrt(2.0))
def touch_dn(S,K,sig_d,T):
    if K>=S: return 1.0
    sigT=sig_d*math.sqrt(T)
    if sigT<=0: return 0.0
    a=math.log(S/K)/sigT
    return min(2*N(-a),1.0)
def touch_up(S,K,sig_d,T):
    if K<=S: return 1.0
    sigT=sig_d*math.sqrt(T)
    if sigT<=0: return 0.0
    a=math.log(K/S)/sigT
    return min(2*N(-a),1.0)
def prob_above_close(S,K,sig_d,T):
    sigT=sig_d*math.sqrt(T)
    if sigT<=0: return 1.0 if S>=K else 0.0
    return N(math.log(S/K)/sigT)

# conservative: use min vol estimate across windows (minus 15% haircut)
def cons_vol(sym):
    return 0.85*min(sd for sd,_ in V[sym].values())

def model_range(fn,sym,S,K,T):
    vs=[fn(S,K,sd,T) for sd,_ in V[sym].values()]
    return min(vs),max(vs)

cands=[]
for e in res.get('crypto',[]):
    t=(e.get('title') or '')
    if not e.get('markets'): continue
    em=mliq=0
    for m in e.get('markets'):
        if m.get('closed'): continue
        q=(m.get('question') or '')
        ml=m.get('liquidityNum') or 0
        if ml<3000: continue
        cands.append((t,q,m,ml))
print()
print('cand markets:',len(cands))

rows=[]
for t,q,m,liq in cands:

    sym=None; kind=None; K=None
    q2=q.strip()
    D='[$]'
    mm=re.match('^Will (Bitcoin|Ethereum) reach '+D+'([\d,]+(?:\.\d+)?)',q2)
    if mm: sym,kind=('BTC' if mm.group(1)=='Bitcoin' else 'ETH'),'touch_up'; K=mm.group(2)
    else:
        mm=re.match('^Will (Bitcoin|Ethereum) dip to '+D+'([\d,]+(?:\.\d+)?)',q2)
        if mm: sym,kind=('BTC' if mm.group(1)=='Bitcoin' else 'ETH'),'touch_dn'; K=mm.group(2)
        else:
            mm=re.match('^Will the price of (Bitcoin|Ethereum) be above '+D+'([\d,]+(?:\.\d+)?) on ([A-Za-z]+ \d+)',q2)
            if mm: sym,kind=('BTC' if mm.group(1)=='Bitcoin' else 'ETH'),'daily_above'; K=mm.group(2)
    if not sym: continue
    K=float(K.replace(',',''))
    if sym=='BTC' and 50<K<1000: K*=1000
    pr=json.loads(m.get('outcomePrices') or '[]')
    bb=m.get('bestBid'); ba=m.get('bestAsk')
    end=m.get('endDate') or ''
    try: T=(datetime.datetime.strptime(end[:19],'%Y-%m-%dT%H:%M:%S').replace(tzinfo=datetime.timezone.utc)-NOW).total_seconds()/86400.0
    except Exception: T=None
    rows.append(dict(sym=sym,kind=kind,K=K,q=q2[:75],pr=pr,bb=bb,ba=ba,liq=int(liq),T=T,end=end[:16]))

json.dump(rows,open('/home/ubuntu/paper-sim/round9/raw/crypto_rows9.json','w'),indent=1)
FN={'touch_up':touch_up,'touch_dn':touch_dn,'daily_above':prob_above_close}
print('%-4s %-11s %9s %6s %6s %6s %6s %6s %6s  %s'%('sym','kind','K','T(d)','mkt','m_lo','m_hi','edge','cons','q'))
for r in sorted(rows,key=lambda x:(x['sym'],x['kind'],-x['K'])):
    if r['T'] is None or r['T']<=0: continue
    fn=FN[r['kind']]
    lo,hi=model_range(fn,r['sym'],SPOT[r['sym']],r['K'],r['T'])
    mk=float(r["pr"][0]) if r["pr"] else None
    cv=cons_vol(r['sym'])
    c=fn(SPOT[r['sym']],r['K'],cv,r['T'])
    edge=(mk-lo) if mk is not None else None
    print('%-4s %-11s %9.0f %6.2f %6s %6.1f%% %6.1f%% %6s %6.1f%%  %s'%(r['sym'],r['kind'],r['K'],r['T'],
        ('%.3f'%mk) if mk is not None else '-',lo*100,hi*100,('%+.1f%%'%(edge*100)) if edge is not None else '-',c*100,r['q'][:60]))
