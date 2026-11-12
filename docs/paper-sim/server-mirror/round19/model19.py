import json, math, datetime, re

RAW='/home/ubuntu/paper-sim/round19/raw'
NOW=datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
def N(x): return 0.5*math.erfc(-x/math.sqrt(2.0))

# ---------- candles ----------
cd={}
for s in ['ETH','BTC']:
    rows=sorted(json.load(open(f'{RAW}/{s.lower()}_candles.json')), key=lambda r:r[0])
    complete=[r for r in rows if (NOW.timestamp()-r[0])>=6*3600]
    cd[s]={'rows':rows,'closes':[r[4] for r in complete],'last_complete':complete[-1],'last_bar':rows[-1]}
SPOT={s:cd[s]['last_bar'][4] for s in cd}
print('SPOT (live partial-bar close)',SPOT)

def vol_from(closes,n):
    cs=closes[-n:]
    rs=[math.log(cs[i]/cs[i-1]) for i in range(1,len(cs))]
    sd6=math.sqrt(sum(x*x for x in rs)/len(rs))
    return sd6*math.sqrt(4.0)
VOL={}
for s in ['ETH','BTC']:
    cl=cd[s]['closes']
    VOL[s]={w:vol_from(cl,n) for w,n in [('7d',28),('30d',120),('60d',240),('87d',348)]}
    print(s,'spot=%.2f'%SPOT[s],{k:'%.3f%%'%(v*100) for k,v in VOL[s].items()})

# ---------- 1m weekend verification ----------
m1=json.load(open(f'{RAW}/eth_1m_weekend.json'))
oct24=datetime.datetime(2026,10,24,tzinfo=datetime.timezone.utc).timestamp()
oct26=datetime.datetime(2026,10,26,tzinfo=datetime.timezone.utc).timestamp()
wk=[r for r in m1 if oct24<=r[0]<oct26]
today=[r for r in m1 if r[0]>=oct26]
lo_wk=min(wk,key=lambda r:r[1]); hi_wk=max(wk,key=lambda r:r[2])
lo_to=min(today,key=lambda r:r[1]) if today else None
d24=[r for r in wk if r[0]<datetime.datetime(2026,10,25,tzinfo=datetime.timezone.utc).timestamp()]
d25=[r for r in wk if r[0]>=datetime.datetime(2026,10,25,tzinfo=datetime.timezone.utc).timestamp()]
lo24=min(d24,key=lambda r:r[1]); lo25=min(d25,key=lambda r:r[1])
def ts(t): return datetime.datetime.fromtimestamp(t,datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
weekend_1m={
 'window':'2026-10-24T00:00Z to 2026-10-26T00:00Z',
 'weekend_low':lo_wk[1],'weekend_low_at':ts(lo_wk[0]),'weekend_high':hi_wk[2],'weekend_high_at':ts(hi_wk[0]),
 'sat_low':lo24[1],'sat_low_at':ts(lo24[0]),'sun_low':lo25[1],'sun_low_at':ts(lo25[0]),
 'monday_low_so_far':lo_to[1] if lo_to else None,'monday_low_at':ts(lo_to[0]) if lo_to else None,
 'pct_above_2250':round((lo_wk[1]/2250.0-1)*100,2),
 'within_1pct_flag': lo_wk[1] <= 2250*1.01,
 'minutes_le_2280':len([r for r in m1 if r[1]<=2280]),
 'minutes_le_2275':len([r for r in m1 if r[1]<=2275]),
 'minutes_le_2300':len([r for r in m1 if r[1]<=2300]),
}
print('WEEKEND',weekend_1m)

# ---------- barrier checks (creation->now, 6h bars incl partial) ----------
CREATED={'btc65':datetime.datetime(2026,8,25,tzinfo=datetime.timezone.utc),
         'btc95':datetime.datetime(2026,6,8,tzinfo=datetime.timezone.utc),
         'eth3000':datetime.datetime(2026,6,8,tzinfo=datetime.timezone.utc),
         'eth2250':datetime.datetime(2026,8,25,tzinfo=datetime.timezone.utc),
         'eth2000':datetime.datetime(2026,8,25,tzinfo=datetime.timezone.utc)}
SYMS={'btc65':'BTC','btc95':'BTC','eth3000':'ETH','eth2250':'ETH','eth2000':'ETH'}
BARRIER={'btc65':65000,'btc95':95000,'eth3000':3000,'eth2250':2250,'eth2000':2000}
barrier_checks={}
for k,dt0 in CREATED.items():
    rows=[r for r in cd[SYMS[k]]['rows'] if r[0]>=dt0.timestamp()]
    lo=min(r[1] for r in rows); hi=max(r[2] for r in rows); dn=BARRIER[k]
    touched=(lo<=dn) if dn<SPOT[SYMS[k]] else (hi>=dn)
    barrier_checks[k]={'created':dt0.date().isoformat(),
        'min_low_since':lo if dn<SPOT[SYMS[k]] else None,
        'max_high_since':hi if dn>SPOT[SYMS[k]] else None,'touched':touched}
    print(k,barrier_checks[k])

def p_touch_up(a,mu,sig,T):
    sigT=sig*math.sqrt(T)
    if sigT<=0: return 1.0 if a<=0 else 0.0
    return N((mu*T-a)/sigT)+math.exp(2*mu*a/(sig*sig))*N(-(mu*T+a)/sigT)
def p_touch_dn(x,mu,sig,T): return p_touch_up(x,-mu,sig,T)
def probs_dn(S,K,sig,T):
    if K>=S: return (1.0,1.0)
    x=math.log(S/K); muB=-sig*sig/2.0
    return (p_touch_dn(x,0,sig,T),p_touch_dn(x,muB,sig,T))
def probs_up(S,K,sig,T):
    if K<=S: return (1.0,1.0)
    a=math.log(K/S); muB=-sig*sig/2.0
    return (p_touch_up(a,0,sig,T),p_touch_up(a,muB,sig,T))
def bisect(f,lo,hi,target,tol=1e-7):
    for _ in range(80):
        mid=(lo+hi)/2
        if f(mid)<target: lo=mid
        else: hi=mid
        if hi-lo<tol: break
    return (lo+hi)/2

# ---------- horizons ----------
H={'Tue_close_Oct27_2359':datetime.datetime(2026,10,27,23,59,tzinfo=datetime.timezone.utc),
   'FOMC_decision_Wed_1800':datetime.datetime(2026,10,28,18,0,tzinfo=datetime.timezone.utc),
   'Fri_close_Oct30_2359':datetime.datetime(2026,10,30,23,59,tzinfo=datetime.timezone.utc),
   'Nov1_0000':datetime.datetime(2026,11,1,tzinfo=datetime.timezone.utc),
   'Dec31_2359':datetime.datetime(2026,12,31,23,59,tzinfo=datetime.timezone.utc)}

def horizon_block(S,K,sym,kind):
    out={}
    for lbl,dt in H.items():
        T=(dt-NOW).total_seconds()/86400.0
        if T<=0: continue
        pr={}
        for vw in ['7d','30d','60d','87d']:
            sig=VOL[sym][vw]
            pA,pB=(probs_dn(S,K,sig,T) if kind=='touch_dn' else probs_up(S,K,sig,T))
            pr[vw]={'A':round(pA,4),'B':round(pB,4)}
        out[lbl]={'hours':round(T*24,2),'days':round(T,2),'probs':pr}
    return out

touch_upd={
 'ETH_2250':horizon_block(SPOT['ETH'],2250.0,'ETH','touch_dn'),
 'ETH_2000':horizon_block(SPOT['ETH'],2000.0,'ETH','touch_dn'),
 'BTC_65000':horizon_block(SPOT['BTC'],65000.0,'BTC','touch_dn'),
}
sig30=VOL['ETH']['30d']; sig7=VOL['ETH']['7d']
x2250=math.log(SPOT['ETH']/2250.0)
eth_risk={
 'spot':SPOT['ETH'],'barrier':2250.0,'pct_distance':round((SPOT['ETH']/2250.0-1)*100,2),
 'log_distance':round(x2250,4),
 'sigma_1d_30d':round(SPOT['ETH']*sig30,2),'dist_in_1d_sigma_30d':round(x2250/sig30,2),
 'sigma_1d_7d':round(SPOT['ETH']*sig7,2),'dist_in_1d_sigma_7d':round(x2250/sig7,2),
 'weekend_low':lo_wk[1],'weekend_low_pct_above_barrier':weekend_1m['pct_above_2250'],
}
print('ETH_RISK',eth_risk)

# ---------- books / MTM ----------
bk=json.load(open(f'{RAW}/position_books.json'))
gm=json.load(open(f'{RAW}/position_markets.json'))
def walk(book,side,qty):
    lvls=book.get('bids',[]) if side=='bid' else book.get('asks',[])
    if side=='bid': lvls=sorted(lvls,key=lambda z:-float(z['price']))
    else: lvls=sorted(lvls,key=lambda z:float(z['price']))
    rem=qty; cash=0.0; fills=[]
    for l in lvls:
        px=float(l['price']); sz=float(l['size'])
        take=min(rem,sz); cash+=take*px; rem-=take; fills.append([px,take])
        if rem<=1e-9: break
    return {'realizable_cash':round(cash,2),'filled':round(qty-rem,2),'avg_px':round(cash/(qty-rem),4) if qty-rem>0 else None,
            'fully_filled':rem<=1e-9,'fills_top':fills[:6]}
POS=[
 ('ETH-dip-2250 YES','Will Ethereum dip to $2,250 by December 31, 2026?',2555.0,0.489,1250.0,'3866000','ETH2250_YES',gm['3866000']),
 ('ETH-dip-2000 YES','Will Ethereum dip to $2,000 by December 31, 2026?',1208.0,0.265,320.0,'3865999','ETH2000_YES',gm['3865999']),
 ('BTC-dip-65k NO','Will Bitcoin dip to $65,000 by December 31, 2026?',384.6,0.78,300.0,'3865962','BTC65K_NO',gm['3865962']),
]
mtm=[]
for name,q,sh,avg,cost,gid,tokk,g in POS:
    b=bk['books'][tokk]
    bids=sorted(b.get('bids',[]),key=lambda z:-float(z['price']))
    asks=sorted(b.get('asks',[]),key=lambda z:float(z['price']))
    bb=float(bids[0]['price']) if bids else None; ba=float(asks[0]['price']) if asks else None
    mid=(bb+ba)/2 if bb and ba else None
    dw=walk(b,'bid',sh)
    mtm_px=dw['avg_px'] if dw['fully_filled'] else None
    mtm.append(dict(name=name,mkt=q,shares=sh,avg=avg,cost=cost,gamma_id=gid,
      book={'best_bid':bb,'best_ask':ba,'mid':mid,
            'bid_depth_walk':dw,
            'bid_top_size':float(bids[0]['size']) if bids else None,
            'ask_top_size':float(asks[0]['size']) if asks else None,
            'n_bid_levels':len(bids),'n_ask_levels':len(asks)},
      last_trade=float(g.get('lastTradePrice')) if g.get('lastTradePrice') else None,
      mtm_px=mtm_px,
      unrealized_bid=round(dw['realizable_cash']-cost,2),
      unrealized_mid=round(sh*mid-cost,2) if mid else None,
      unrealized_bid_pct=round((dw['realizable_cash']-cost)/cost*100,1),
      mark_to_mid=round(sh*mid,2) if mid else None,
      realizable_cash=dw['realizable_cash']))
    print(name,'bb',bb,'ba',ba,'mid',mid,'walk',dw['realizable_cash'],'avgpx',mtm_px,'uPnL_bid',round(dw['realizable_cash']-cost,2))

# fair values of held markets (Dec31) for EV
DEC31_T=(H['Dec31_2359']-NOW).total_seconds()/86400.0
fair2250={vw:probs_dn(SPOT['ETH'],2250.0,VOL['ETH'][vw],DEC31_T) for vw in ['7d','30d','60d','87d']}
fair2000={vw:probs_dn(SPOT['ETH'],2000.0,VOL['ETH'][vw],DEC31_T) for vw in ['7d','30d','60d','87d']}
fairbtc65={vw:probs_dn(SPOT['BTC'],65000.0,VOL['BTC'][vw],DEC31_T) for vw in ['7d','30d','60d','87d']}

# ---------- ETH-2250 exit analysis ----------
b0=bk['books']['ETH2250_YES']
bids2250=sorted(b0.get('bids',[]),key=lambda z:-float(z['price']))
bb2250=float(bids2250[0]['price'])
full_walk=walk(b0,'bid',2555.0)
half_walk=walk(b0,'bid',1278.0)
qtr_walk=walk(b0,'bid',639.0)
sig30e=VOL['ETH']['30d']
def fairA(sig,T=DEC31_T): return probs_dn(SPOT['ETH'],2250.0,sig,T)[0]
def fairB(sig,T=DEC31_T): return probs_dn(SPOT['ETH'],2250.0,sig,T)[1]
grid={}
for lbl,sig in [('7d',VOL['ETH']['7d']),('30d',sig30e),('60d',VOL['ETH']['60d']),('87d',VOL['ETH']['87d']),
                ('30d+15%',sig30e*1.15),('30d+25%',sig30e*1.25),('30d-15%',sig30e*0.85)]:
    a,bn=fairA(sig),fairB(sig)
    grid[lbl]={'sig_daily':round(sig,5),'pA_zero_drift':round(a,4),'pB_median_flat':round(bn,4)}
be_vol=bisect(lambda s: fairA(s), 0.005, 0.10, bb2250)
# breakeven upward drift at 30d vol such that P_A(mu)=bid  (solve p_touch_dn with drift)
def pdn_mu(mu,sig,T=DEC31_T):
    x=math.log(SPOT['ETH']/2250.0); sigT=sig*math.sqrt(T)
    return N(-(mu*T+x)/sigT)+math.exp(-2*mu*x/(sig*sig))*N((mu*T-x)/sigT)
mu_be=bisect(lambda m: -pdn_mu(m,sig30e), -0.05, 0.05, -bb2250)
fair_mid_est=(fairA(sig30e)+fairB(sig30e))/2
edge_vs_bid={'fair_A_30d':round(fairA(sig30e),4),'fair_B_30d':round(fairB(sig30e),4),
  'yes_bid':bb2250,'edge_A':round(fairA(sig30e)-bb2250,4),'edge_B':round(fairB(sig30e)-bb2250,4),
  'position_edge_A':round((fairA(sig30e)-bb2250)*2555,2),'position_edge_B':round((fairB(sig30e)-bb2250)*2555,2),
  'breakeven_daily_vol_for_bid':round(be_vol,5),
  'implied_vol cushion': None}
edge_vs_bid.pop('implied_vol cushion',None)
edge_vs_bid['current_vol_30d']=round(sig30e,5)
edge_vs_bid['breakeven_upward_log_drift_at_30d_vol']=round(mu_be,6)
edge_vs_bid['breakeven_drift_annualized_pct']=round((math.exp(mu_be)-1)*100,1) if mu_be else None
exit_an={
 'asof':NOW.isoformat(),'spot_ETH':SPOT['ETH'],'barrier':2250.0,
 'pct_distance':round((SPOT['ETH']/2250.0-1)*100,2),'log_distance':round(x2250,4),
 'T_days_to_dec31':round(DEC31_T,2),
 'min_low_since_created':barrier_checks['eth2250']['min_low_since'],
 'closest_approach_pct_above_barrier':round((barrier_checks['eth2250']['min_low_since']/2250.0-1)*100,2),
 'yes_bid':bb2250,
 'fair_grid':grid,
 'breakeven_daily_vol_for_bid':round(be_vol,5),
 'current_vol_30d':round(sig30e,5),
 'breakeven_upward_log_drift_at_30d_vol':round(mu_be,6),
 'breakeven_drift_annualized_pct':round((math.exp(mu_be)-1)*100,1) if mu_be else None,
 'edge_vs_bid':edge_vs_bid,
 'hold_ev_premium_vs_sell':{
   'per_share_fairA':round(fairA(sig30e)-bb2250,4),
   'per_share_fairB':round(fairB(sig30e)-bb2250,4),
   'position_fairA':round((fairA(sig30e)-bb2250)*2555,2),
   'position_fairB':round((fairB(sig30e)-bb2250)*2555,2)},
 'exit_walks':{'sell_all_2555':full_walk,'sell_half_1278':half_walk,'sell_quarter_639':qtr_walk},
 'trigger_review':{'prior_triggers':'exit review if ETH>2650; hold to resolution if ETH<2310',
   'current_spot':SPOT['ETH'],'zone':'between 2310 and 2650 (no trigger fired; spot 13 usd above the 2310 hold-to-resolution line)'},
}
print('EXIT',json.dumps(exit_an['fair_grid'],indent=None)[:400])
print('breakeven vol for bid',round(be_vol,5),'current30d',round(sig30e,5))
print('walks: full',full_walk['realizable_cash'],'half',half_walk['realizable_cash'],'qtr',qtr_walk['realizable_cash'])

# ---------- report-only table ----------
prev=json.load(open('/home/ubuntu/paper-sim/round15/raw/crypto_scan.json'))['classified_markets']
fr=json.load(open(f'{RAW}/market_refresh.json'))['markets']
MONTHS={m:i+1 for i,m in enumerate(['January','February','March','April','May','June','July','August','September','October','November','December'])}
SIGTAB='30d'
table=[]
for m in prev:
    c=m.get('condId'); g=fr.get(c)
    if not g or g.get('closed'): continue
    q=m['q']; sym=m['sym']; kind=m['kind']; K=m['K']
    mMon=re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December) (\d{1,2})(?:, ?(\d{4}))?',q)
    mr=re.search(r'October (\d{1,2})-(\d{1,2})',q)
    if mr: rdt=datetime.datetime(2026,10,int(mr.group(2)),23,59,tzinfo=datetime.timezone.utc)
    elif mMon:
        yr=int(mMon.group(3)) if mMon.group(3) else 2026
        rdt=datetime.datetime(yr,MONTHS[mMon.group(1)],int(mMon.group(2)),23,59,tzinfo=datetime.timezone.utc)
    else: rdt=H['Dec31_2359']
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
    if T<=0 or T>75 or liq<10000: continue
    S=SPOT[sym]; sig=VOL[sym][SIGTAB]
    if kind=='touch_dn':
        pA,pB=probs_dn(S,K,sig,T); fair_yes=min(pA,pB)
    elif kind=='touch_up':
        pA,pB=probs_up(S,K,sig,T); fair_yes=min(pA,pB)
    else: continue
    # per-side conservative (2026-10-30 audit fix): conservative YES = min(pA,pB); conservative NO = 1-max(pA,pB)
    edge_yes=min(pA,pB)-yes_ask; edge_no=(1.0-max(pA,pB))-no_ask
    table.append(dict(q=q[:95],sym=sym,kind=kind,K=K,T=round(T,2),pA=round(pA,4),pB=round(pB,4),
        fair_yes=round(fair_yes,4),yes_bid=yes_bid,yes_ask=yes_ask,edge_yes=round(edge_yes,4),
        edge_no=round(edge_no,4),liq=round(liq),condId=c))
table.sort(key=lambda z:-max(z['edge_yes'],z['edge_no']))
print('report-only kept',len(table))
for x in table[:12]:
    print('%-55s T=%5.1f K=%7.0f fair=%.3f bidY=%s askY=%s eY=%+.3f eN=%+.3f'%(x['q'][:55],x['T'],x['K'],x['fair_yes'],x['yes_bid'],x['yes_ask'],x['edge_yes'],x['edge_no']))

out={'generated_at':NOW.isoformat(),'spot':SPOT,'realized_vol_daily':VOL,
 'model':{'vol_source':'Binance 6h klines (complete bars), RMS log-ret x sqrt(4); spot Coinbase (live partial 6h bar close)',
   'sig_table':'30d','conventions':['A: zero-log-drift GBM','B: mean-flat / zero-arithmetic-drift (mu_log=-sigma^2/2, E[S_T]=S_0); A is BOTH zero-log-drift AND median-flat'],
   'touch':'drifted first-passage (reflection principle form)'},
 'weekend_1m_check':weekend_1m,
 'barrier_checks':barrier_checks,
 'touch_horizons':touch_upd,
 'eth_barrier_risk':eth_risk,
 'positions_mtm':mtm,
 'held_fair_dec31':{'ETH2250':{k:{'A':round(v[0],4),'B':round(v[1],4)} for k,v in fair2250.items()},
                    'ETH2000':{k:{'A':round(v[0],4),'B':round(v[1],4)} for k,v in fair2000.items()},
                    'BTC65K_yes':{k:{'A':round(v[0],4),'B':round(v[1],4)} for k,v in fairbtc65.items()}},
 'exit_analysis_eth2250':exit_an,
 'report_only_table':table[:12],
}
json.dump(out,open(f'{RAW}/crypto_scan.json','w'),indent=1)
print('wrote crypto_scan.json')
