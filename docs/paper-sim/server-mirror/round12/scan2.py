import json, math, datetime, re

RAW="/home/ubuntu/paper-sim/round12/raw"
NOW=datetime.datetime(2026,10,22,12,0,tzinfo=datetime.timezone.utc)

def N(x): return 0.5*math.erfc(-x/math.sqrt(2.0))
def p_touch_up(a,mu,sig,T):
    sigT=sig*math.sqrt(T)
    if sigT<=0: return 1.0 if a<=0 else 0.0
    return N((mu*T-a)/sigT)+math.exp(2*mu*a/(sig*sig))*N(-(mu*T+a)/sigT)
def p_touch_dn(x,mu,sig,T): return p_touch_up(x,-mu,sig,T)

cd={}
for s,f in [("ETH","eth_candles"),("BTC","btc_candles")]:
    rows=sorted(json.load(open(f"{RAW}/{f}.json")),key=lambda r:r[0])
    cd[s]={"closes":[r[4] for r in rows],"lows":[r[1] for r in rows],"highs":[r[2] for r in rows],"ts":[r[0] for r in rows]}
SPOT={s:cd[s]["closes"][-1] for s in cd}
VOL={}
for s in cd:
    cl=cd[s]["closes"]
    def vol(n):
        cs=cl[-n:]; rs=[math.log(cs[i]/cs[i-1]) for i in range(1,len(cs))]
        return math.sqrt(sum(x*x for x in rs)/len(rs))*math.sqrt(4.0)
    VOL[s]={"7d":vol(28),"30d":vol(120),"60d":vol(240),"87d":vol(349)}
    print(s,"spot=%.2f"%SPOT[s],{k:"%.2f%%"%(v*100) for k,v in VOL[s].items()})

# barrier-touch verification since Oct 19 (weekly windows) using 6h lows/highs
t0=datetime.datetime(2026,10,19,0,0,tzinfo=datetime.timezone.utc).timestamp()
for s in ["BTC","ETH"]:
    seg=[(datetime.datetime.fromtimestamp(t,datetime.timezone.utc),lo,hi) for t,lo,hi in zip(cd[s]["ts"],cd[s]["lows"],cd[s]["highs"]) if t>=t0]
    if seg:
        print(s,"since Oct19: min low=%.2f max high=%.2f bars=%d"%(min(x[1] for x in seg),max(x[2] for x in seg),len(seg)))
# today since 00:00
t0d=datetime.datetime(2026,10,22,0,0,tzinfo=datetime.timezone.utc).timestamp()
for s in ["BTC","ETH"]:
    seg=[(lo,hi) for t,lo,hi in zip(cd[s]["ts"],cd[s]["lows"],cd[s]["highs"]) if t>=t0d]
    if seg: print(s,"today: min low=%.2f max high=%.2f"%(min(x[0] for x in seg),max(x[1] for x in seg)))
