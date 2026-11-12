import json, math, datetime, re

RAW = '/home/ubuntu/paper-sim/round15/raw'
NOW = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
def N(x): return 0.5 * math.erfc(-x / math.sqrt(2.0))

# ---------- candles: [t0_sec, low, high, open, close, vol] (binance 6h, coinbase layout) ----------
cd = {}
for s in ['ETH','BTC']:
    rows = sorted(json.load(open(f'{RAW}/{s.lower()}_candles.json')), key=lambda r: r[0])
    complete = [r for r in rows if (NOW.timestamp() - r[0]) >= 6*3600]
    cd[s] = {'rows': rows, 'closes': [r[4] for r in complete], 'last_complete': complete[-1], 'last_bar': rows[-1]}
SPOT = {s: cd[s]['last_bar'][4] for s in cd}
print('SPOT (live partial-bar close)', SPOT, 'last bar t0', datetime.datetime.fromtimestamp(cd['ETH']['last_bar'][0], datetime.timezone.utc))
print('last complete bar close:', {s: cd[s]['last_complete'][4] for s in cd})

def vol_from(closes, n):
    cs = closes[-n:]
    rs = [math.log(cs[i]/cs[i-1]) for i in range(1,len(cs))]
    sd6 = math.sqrt(sum(x*x for x in rs)/len(rs))
    return sd6*math.sqrt(4.0)
VOL = {}
for s in ['ETH','BTC']:
    cl = cd[s]['closes']
    VOL[s] = {w: vol_from(cl,n) for w,n in [('7d',28),('30d',120),('60d',240),('87d',348)]}
    print(s,'spot=%.2f'%SPOT[s],{k:'%.3f%%'%(v*100) for k,v in VOL[s].items()})

# ---------- barriers (creation->now, incl partial bar) ----------
CREATED = {'btc65': datetime.datetime(2026,8,25,tzinfo=datetime.timezone.utc),
           'btc95': datetime.datetime(2026,6,8,tzinfo=datetime.timezone.utc),
           'eth3000': datetime.datetime(2026,6,8,tzinfo=datetime.timezone.utc),
           'eth2250': datetime.datetime(2026,8,25,tzinfo=datetime.timezone.utc),
           'eth2000': datetime.datetime(2026,8,25,tzinfo=datetime.timezone.utc)}
SYMS = {'btc65':'BTC','btc95':'BTC','eth3000':'ETH','eth2250':'ETH','eth2000':'ETH'}
BARRIER = {'btc65':65000,'btc95':95000,'eth3000':3000,'eth2250':2250,'eth2000':2000}
barrier_checks={}
for k,dt0 in CREATED.items():
    rows=[r for r in cd[SYMS[k]]['rows'] if r[0]>=dt0.timestamp()]
    lo=min(r[1] for r in rows); hi=max(r[2] for r in rows)
    dn=BARRIER[k]
    touched=(lo<=dn) if dn<SPOT[SYMS[k]] else (hi>=dn)
    barrier_checks[k]={'created':dt0.date().isoformat(),
        'min_low_since': lo if dn<SPOT[SYMS[k]] else None,
        'max_high_since': hi if dn>SPOT[SYMS[k]] else None,'touched':touched}
    print(k,'min_low',lo,'max_high',hi,'touched',touched)

# lows since round-13 scan & since Oct19 window start
for label,t0dt in [('since_round13_scan', datetime.datetime(2026,10,23,1,7,tzinfo=datetime.timezone.utc)),
                   ('since_oct19', datetime.datetime(2026,10,19,tzinfo=datetime.timezone.utc))]:
    for s in ['ETH','BTC']:
        rows=[r for r in cd[s]['rows'] if r[0]>=t0dt.timestamp()]
        print(label,s,'low=%.2f high=%.2f'%(min(r[1] for r in rows),max(r[2] for r in rows)))

def p_above(S,K,mu,sig,T):
    sigT=sig*math.sqrt(T)
    if sigT<=0: return 1.0 if S>=K else 0.0
    return N((math.log(S/K)+mu*T)/sigT)
def p_touch_up(a,mu,sig,T):
    sigT=sig*math.sqrt(T)
    if sigT<=0: return 1.0 if a<=0 else 0.0
    return N((mu*T-a)/sigT)+math.exp(2*mu*a/(sig*sig))*N(-(mu*T+a)/sigT)
def p_touch_dn(x,mu,sig,T): return p_touch_up(x,-mu,sig,T)
def probs(sym,kind,K,T,sig):
    S=SPOT[sym]; muB=-sig*sig/2.0
    if kind=='touch_up':
        if K<=S: return (1.0,1.0)
        a=math.log(K/S); return (p_touch_up(a,0,sig,T),p_touch_up(a,muB,sig,T))
    if kind=='touch_dn':
        if K>=S: return (1.0,1.0)
        x=math.log(S/K); return (p_touch_dn(x,0,sig,T),p_touch_dn(x,muB,sig,T))
    if kind=='above': return (p_above(S,K,0,sig,T),p_above(S,K,muB,sig,T))
    if kind=='below':
        pa=(p_above(S,K,0,sig,T),p_above(S,K,muB,sig,T)); return (1-pa[0],1-pa[1])
    return (None,None)

DEC31=datetime.datetime(2026,12,31,23,59,tzinfo=datetime.timezone.utc)
T_DEC31=(DEC31-NOW).total_seconds()/86400.0
print('T to Dec31 = %.2f d'%T_DEC31)

# ---------- refresh classified markets ----------
prev=json.load(open('/home/ubuntu/paper-sim/round13/raw/crypto_scan.json'))['classified_markets']
fr=json.load(open(f'{RAW}/market_refresh.json'))['markets']
MONTHS={m:i+1 for i,m in enumerate(['January','February','March','April','May','June','July','August','September','October','November','December'])}
SIGTAB='30d'
WSTART=datetime.datetime(2026,10,19,tzinfo=datetime.timezone.utc)
table=[]
win_low={s:min(r[1] for r in cd[s]['rows'] if r[0]>=WSTART.timestamp()) for s in ['ETH','BTC']}
win_hi={s:max(r[2] for r in cd[s]['rows'] if r[0]>=WSTART.timestamp()) for s in ['ETH','BTC']}
print('Oct19-25 window so far: low',win_low,'high',win_hi)
dropped=[]
for m in prev:
    c=m.get('condId')
    g=fr.get(c)
    if not g:
        dropped.append('(gone) '+m['q'][:60]); continue
    if g.get('closed'):
        dropped.append('(closed) '+m['q'][:60]); continue
    q=m['q']; sym=m['sym']; kind=m['kind']; K=m['K']
    mr=re.search(r'October (\d{1,2})-(\d{1,2})', q)
    mMon=re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December) (\d{1,2})(?:, ?(\d{4}))?', q)
    if mr:
        rdt=datetime.datetime(2026,10,int(mr.group(2)),23,59,tzinfo=datetime.timezone.utc)
        win_start=WSTART
    else:
        rdt=None; win_start=None
        if mMon:
            yr=int(mMon.group(3)) if mMon.group(3) else 2026
            # monthly/dated resolution: end of that day 23:59
            rdt=datetime.datetime(yr,MONTHS[mMon.group(1)],int(mMon.group(2)),23,59,tzinfo=datetime.timezone.utc)
    if rdt is None: rdt=DEC31
    T=(rdt-NOW).total_seconds()/86400.0
    prs=g.get('outcomePrices')
    if isinstance(prs,str):
        try: prs=json.loads(prs)
        except Exception: prs=None
    try: p_yes=float(prs[0])
    except Exception: continue
    bb=g.get('bestBid'); ba=g.get('bestAsk')
    yes_ask=ba if ba is not None else min(1.0,p_yes+0.02)
    yes_bid=bb if bb is not None else max(0.0,p_yes-0.02)
    no_ask=1.0-yes_bid
    liq=g.get('liquidityNum') or m.get('liq') or 0
    already=False
    if win_start is not None:
        if kind=='touch_dn' and win_low[sym]<=K: already=True
        if kind=='touch_up' and win_hi[sym]>=K: already=True
    if already:
        fair_yes=1.0; pA=pB=1.0
        edge_yes=1.0-yes_ask; edge_no=-no_ask
    else:
        if T<=0 or T>75 or liq<10000: continue
        pA,pB=probs(sym,kind,K,T,VOL[sym][SIGTAB])
        if pA is None: continue
        fair_yes=min(pA,pB) if kind in ('touch_up','above') else max(pA,pB)
        edge_yes=fair_yes-yes_ask
        edge_no=(1.0-fair_yes)-no_ask
    table.append(dict(q=q[:95],sym=sym,kind=kind,K=K,T=round(T,2),pA=round(pA,4),pB=round(pB,4),
        fair_yes=round(fair_yes,4),yes_bid=yes_bid,yes_ask=yes_ask,edge_yes=round(edge_yes,4),
        edge_no=round(edge_no,4),liq=round(liq),already_touched=already,
        condId=c,toks=m.get('toks')))
print('kept',len(table),'dropped',len(dropped),dropped[:6])
json.dump({'generated_at':NOW.isoformat(),'spot':SPOT,'realized_vol_daily':VOL,
 'model':{'vol_source':'Binance 6h klines (complete bars), RMS log-ret x sqrt(4); spot via Coinbase (fallback Binance ticker)',
   'sig_table':SIGTAB,'conventions':['A: zero-log-drift GBM','B: median-flat (mu_log=-sigma^2/2)'],
   'touch':'drifted first-passage (reflection principle form)','fair_buy_convention':'least-favorable to the side being bought',
   'r15_change':'weekly window markets now marked fair=1 if barrier already touched since window start (Oct 19)'},
 'barrier_checks':barrier_checks,'weekly_window_so_far':{'low':win_low,'high':win_hi},
 'classified_markets':table}, open(f'{RAW}/crypto_scan.json','w'), indent=1)
print('wrote crypto_scan.json', len(table))
print('%-50s %5s %8s %6s %6s %6s %6s %+7s %+7s'%('market','T','K','pA','pB','fair','bidY','edgeY','edgeN'))
for x in sorted(table,key=lambda z:-max(z['edge_yes'],z['edge_no']))[:25]:
    print('%-50s %5.1f %8.0f %6.3f %6.3f %6.3f %6s %+7.3f %+7.3f'%(x['q'][:50],x['T'],x['K'],x['pA'],x['pB'],x['fair_yes'],
        ('%.3f'%x['yes_bid'])[:5] if x['yes_bid'] is not None else '-',x['edge_yes'],x['edge_no']))
