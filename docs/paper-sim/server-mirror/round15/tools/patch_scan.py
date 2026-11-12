import json, math, datetime
RAW='/home/ubuntu/paper-sim/round15/raw'
def N(x): return 0.5*math.erfc(-x/math.sqrt(2.0))
scan=json.load(open(f'{RAW}/crypto_scan.json'))
SPOT=scan['spot']; VOL=scan['realized_vol_daily']
NOW=datetime.datetime.fromisoformat(scan['generated_at'])
def ptd(x,mu,sig,T):
    sigT=sig*math.sqrt(T)
    return N((mu*T-x)/sigT)+math.exp(-2*mu*x/(sig*sig))*N(-(mu*T+x)/sigT)
def ptu(a,mu,sig,T):
    sigT=sig*math.sqrt(T)
    return N((mu*T-a)/sigT)+math.exp(2*mu*a/(sig*sig))*N(-(mu*T+a)/sigT)
fixed=[]
for m in scan['classified_markets']:
    if not m.get('already_touched'): continue
    sym=m['sym']; sig=VOL[sym]['30d']; T=m['T']; K=m['K']
    S=SPOT[sym]
    if m['kind']=='touch_dn':
        x=math.log(S/K); muB=-sig*sig/2
        pA=ptd(x,0.0,sig,T); pB=ptd(x,muB,sig,T); fair=max(pA,pB)
    else:
        a=math.log(K/S); muB=-sig*sig/2
        pA=ptu(a,0.0,sig,T); pB=ptu(a,muB,sig,T); fair=min(pA,pB)
    m['pA']=round(pA,4); m['pB']=round(pB,4); m['fair_yes']=round(fair,4)
    m['edge_yes']=round(fair-m['yes_ask'],4)
    m['edge_no']=round((1.0-fair)-(1.0-m['yes_bid']),4)
    m['already_touched']=False
    m['window_note']='Binance+Coinbase printed an intraweek high above K (Oct 21) but market trades YES<<0.5: touch evidently counts only from market creation (post-spike). Forward-only fair shown; excluded from edge ranking.'
    fixed.append((m['q'],m['fair_yes'],m['edge_yes']))
scan['model']['r15_change']='weekly window markets: touch counted from window start only when consistent with market price; Oct-21-spike touch_up weeklies treated forward-only (creation-effective window)'
json.dump(scan, open(f'{RAW}/crypto_scan.json','w'), indent=1)
print('patched:',fixed)
