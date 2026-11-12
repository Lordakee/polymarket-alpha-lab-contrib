import json, math, datetime, re

RAW="/home/ubuntu/paper-sim/round12/raw"
NOW=datetime.datetime(2026,10,22,12,0,tzinfo=datetime.timezone.utc)

# ---------- spot & realized vol from Coinbase 6h candles ----------
cd={}
for s,f in [("ETH","eth_candles"),("BTC","btc_candles")]:
    d=json.load(open(f"{RAW}/{f}.json"))
    # coinbase: [[time, low, high, open, close, volume],...] newest first
    rows=sorted(d,key=lambda r:r[0])
    closes=[r[4] for r in rows]
    cd[s]={"closes":closes,"last_close":closes[-1],"last_time":rows[-1][0]}
SPOT={s:cd[s]["last_close"] for s in cd}
print("SPOT",SPOT,"last candle t0=",datetime.datetime.fromtimestamp(cd["ETH"]["last_time"],datetime.timezone.utc))

def logrets(closes):
    return [math.log(closes[i]/closes[i-1]) for i in range(1,len(closes))]

def vol_from(closes, n, bars_per_day=4.0, label=""):
    # use last n 6h bars
    cs=closes[-n:]
    rs=logrets(cs)
    sd6=math.sqrt(sum(x*x for x in rs)/len(rs))
    return sd6*math.sqrt(bars_per_day)  # per-day sigma

V={}
for s in ["ETH","BTC"]:
    cl=cd[s]["closes"]
    V[s]={
      "vol_30d": vol_from(cl,120),   # 120 bars = 30d
      "vol_14d": vol_from(cl,56),
      "vol_7d":  vol_from(cl,28),
      "vol_3d":  vol_from(cl,12),
    }
    print(s,"spot=%.2f"%SPOT[s], {k:("%.2f%%"%(v*100)) for k,v in V[s].items()})

def N(x): return 0.5*math.erfc(-x/math.sqrt(2.0))

# Convention A: zero log-drift GBM. Convention B: median-flat drift (mu = -sigma^2/2 so median constant).
# For P(above K at T): A: N(ln(S/K)/(sig*sqrt(T))) ; B: N(ln(S/K)/(sig*sqrt(T)) - ... ) 
# median-flat: S_median(T)=S0 => P(S_T>=K)=N(ln(S/K)/(sigT)) as well? No:
# GBM: ln S_T ~ N(ln S0 + (mu - s2/2)T, s2 T). median-flat => ln S0 + (mu-s2/2)T = ln S0 => mu=s2/2.
# P(S_T>=K)=N( ln(S0/K)/(sigT) ) under BOTH A(mu=0) and B(mu=s2/2)?? Under A: lnS_T ~ N(lnS0 - s2T/2, s2T) => P=N((ln(S0/K)+? )...
# A: z=(ln(S0/K) - s2T/2)/ (sigT)? No: P(lnS_T >= lnK)=N( (lnS0 - s2T/2 - lnK)/(sigT) + sigT )? Let X~N(m,v2), P(X>=k)=N((m-k)/v2... careful:
# P(X>=k)=N((m-k)/sd). A: m=lnS0-s2T/2, sd=sigT => N((ln(S0/K)-sigT^2/2)/sigT)
# B: m=lnS0 => N(ln(S0/K)/sigT)
def p_above(S,K,sig_d,T,conv):
    sigT=sig_d*math.sqrt(T)
    if sigT<=0: return 1.0 if S>=K else 0.0
    if conv=="A": return N((math.log(S/K)-sigT*sigT/2.0)/sigT)
    else:        return N(math.log(S/K)/sigT)

# touch via reflection principle, one-sided barrier, drift-adjusted:
# For zero drift (A in log space w/o drift): P(touch K below) = 2*N(-d) where d=ln(S/K)/sigT (K<S)
# For drifted BM: P(max_{t<=T} (x+mu t+sig W_t) >= a) = N((x-a+muT)/sigT) + exp(2 mu a /sig^2)*N(-(x+a+muT)/sigT) (x=0 start, barrier a)
# For DOWN-touch: P(min <= b) with x=0, b<0: = N((b-x-muT)/sigT) + exp(2 mu b/sig^2) N((x+b-muT)/sigT) ... use standard formula.
def p_touch_dn(S,K,sig_d,T,conv):
    if K>=S: return 1.0
    sigT=sig_d*math.sqrt(T)
    if sigT<=0: return 0.0
    x=math.log(S/K)  # distance down to barrier in log space, >0
    if conv=="A":
        mu=0.0
    else:
        mu=-sig_d*sig_d/2.0  # median-flat in log space
    # P( min_{t<=T} X_t <= -x ), X_t = mu t + sig W_t, start 0
    lam=mu/sig_d  # per sqrt-time
    # standard: = N((-x-mu T)/sigT) + exp(-2*lam*x/sig_d)*N((-x+mu T)/sigT)
    # careful: exp(2 mu (-x)/sig^2)
    p=N((-x-mu*T)/sigT)+math.exp(-2.0*mu*x/(sig_d*sig_d))*N((-x+mu*T)/sigT)
    return min(max(p,0.0),1.0)

def p_touch_up(S,K,sig_d,T,conv):
    if K<=S: return 1.0
    return p_touch_dn(S,S*S/K,sig_d,T,conv)  # log-space mirror

