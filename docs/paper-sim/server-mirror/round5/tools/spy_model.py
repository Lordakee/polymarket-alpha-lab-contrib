import json, math

ys = json.load(open('/home/ubuntu/paper-sim/round5/raw/yahoo_round5.json'))
r = ys['SPY']['chart']['result'][0]
ts = r['timestamp']; q = r['indicators']['quote'][0]
import datetime
rows = []
for t, c, l, h in zip(ts, q['close'], q.get('low', []), q.get('high', [])):
    if c is None: continue
    dt = datetime.datetime.fromtimestamp(t, datetime.timezone.utc)
    rows.append((dt.date(), c, l, h))
oct_rows = [x for x in rows if x[0].month == 10 and x[0].year == 2026]
print('SPY October daily (close, low, high):')
for d, c, l, h in oct_rows:
    ls = ('%.2f' % l) if l else '-'
    hs = ('%.2f' % h) if h else '-'
    print('  %s close=%.2f low=%s high=%s' % (d, c, ls, hs))
oct_low = min(l for _, _, l, _ in oct_rows if l)
print('SPY October intraday LOW so far: %.2f' % oct_low)

spot = 763.25
K = 740.0
# trading days remaining: Oct 19-30 inclusive = 10 sessions (Oct 31 = Saturday, end 11-01T03:59Z)
T = 10.0
def N(x):
    return 0.5 * math.erfc(-x / math.sqrt(2.0))

def touch_down(S, K, sigma_d, T, drift_d=0.0):
    # first-passage GBM, continuous monitoring
    sigT = sigma_d * math.sqrt(T)
    if sigT <= 0: return 0.0
    nu = drift_d
    a = (math.log(S / K)) / sigT
    b = a - sigT  # = ln(S/K)/sigT - sigT ; P = N(-a + nu... ) standard: with drift mu (log), P = N((-ln(S/K)+mu*T)/sigT) + exp(2*mu*ln(S/K)/sig^2_d)*N((-ln(S/K)-mu*T)/sigT)
    mu = drift_d
    x1 = (-math.log(S / K) + mu * T) / sigT
    x2 = (-math.log(S / K) - mu * T) / sigT
    p = N(x1) + math.exp(2 * mu * math.log(S / K) / sigma_d ** 2) * N(x2)
    return min(max(p, 0.0), 1.0)

sigmas = {
    'realized 10d (0.65%/d)': 0.0065,
    'realized 21d (0.64%/d)': 0.0064,
    'realized 63d (0.70%/d)': 0.0070,
    'VIX-implied (19.99/252^.5=1.26%/d)': 0.0126,
}
print()
print('P(touch SPY<=740 by Oct 31) from spot 763.25, 10 sessions:')
for lbl, sd in sigmas.items():
    for drift, dl in [(0.0, 'nu=0'), (-sd * sd, 'martingale')]:
        p = touch_down(spot, K, sd, T, drift)
        print('  %-38s %-11s P=%.3f' % (lbl, dl, p))

# also 750 and 730 rungs for context
print()
for K2, ask in [(760, 0.91), (750, 0.60), (730, 0.17), (720, 0.109)]:
    ps = []
    for lbl, sd in sigmas.items():
        for drift in (0.0, -sd * sd):
            ps.append(touch_down(spot, K2, sd, T, drift))
    print('LOW %d: model range [%.3f - %.3f], PM YES ask %s' % (K2, min(ps), max(ps), ask))

# ETH check: weekly Oct 19-25 not listed; sanity check Oct 12-18 weekly + spot
print()
eth_r = ys['ETH-USD']['chart']['result'][0]
print('ETH spot 2420.43; weekly Oct19-25 family: NOT LISTED (checked gamma eth_tag sweep)')
