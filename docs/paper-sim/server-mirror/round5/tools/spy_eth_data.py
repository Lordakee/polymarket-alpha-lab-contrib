import json, urllib.request, urllib.parse, time, math

BASE = 'https://gamma-api.polymarket.com'

def get(url, tries=3, hdrs=None):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=hdrs or {'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            if i == tries - 1: raise
            time.sleep(2)

# 1. NBA opener event detail
out = {}
for slug in ['nba-bos-det-2026-10-20', 'nba-okc-sas-2026-10-20']:
    try:
        ev = get(BASE + '/events?slug=' + urllib.parse.quote(slug))
        if ev:
            out[slug] = ev[0]
            print('== NBA', ev[0].get('title'), 'markets:', len(ev[0].get('markets', [])))
            for m in ev[0].get('markets', []):
                if m.get('closed'): continue
                print('   -', (m.get('question') or m.get('groupItemTitle') or '')[:90])
    except Exception as e:
        print('ERR', slug, e)
    time.sleep(0.5)
json.dump(out, open('/home/ubuntu/paper-sim/round5/raw/nba_detail.json', 'w'))

# 2. Yahoo: SPY, VIX daily 3mo + recent
def yahoo(sym, rng='3mo', interval='1d'):
    u = 'https://query1.finance.yahoo.com/v8/finance/chart/%s?range=%s&interval=%s' % (sym, rng, interval)
    return get(u, hdrs={'User-Agent': 'Mozilla/5.0'})

ys = {}
for sym in ['SPY', '^VIX', 'ETH-USD']:
    try:
        ys[sym] = yahoo(sym)
        r = ys[sym]['chart']['result'][0]
        meta = r['meta']
        print(sym, 'regularMarketPrice=', meta.get('regularMarketPrice'))
    except Exception as e:
        print('YERR', sym, repr(e))
    time.sleep(0.6)
json.dump(ys, open('/home/ubuntu/paper-sim/round5/raw/yahoo_round5.json', 'w'))

# 3. SPY model inputs
r = ys['SPY']['chart']['result'][0]
ts = r['timestamp']; q = r['indicators']['quote'][0]
closes = [(t, c) for t, c in zip(ts, q['close']) if c is not None]
spot = r['meta'].get('regularMarketPrice')
print('SPY spot=', spot, 'n closes=', len(closes), 'last close=', closes[-1])
# October daily lows/highs for the month window (ET dates)
import datetime
octdata = []
for t, c in closes:
    dt = datetime.datetime.utcfromtimestamp(t)
    if dt.month == 10:
        octdata.append((dt.date(), c))
print('Oct closes (last 10):', octdata[-10:])
# realized vol (log returns, annualized)
import statistics
for win, label in [(10, '10d'), (21, '21d'), (63, '63d')]:
    cs = [c for _, c in closes[-(win + 1):]]
    rets = [math.log(cs[i + 1] / cs[i]) for i in range(len(cs) - 1)]
    sd = statistics.stdev(rets)
    print('SPY realized %s: %.4f daily -> %.1f%% ann' % (label, sd, sd * math.sqrt(252) * 100))
vix = ys['^VIX']['chart']['result'][0]['meta'].get('regularMarketPrice')
print('VIX=', vix)
eth = ys['ETH-USD']['chart']['result'][0]['meta'].get('regularMarketPrice')
print('ETH spot (Yahoo)=', eth)
# ETH realized vol
r2 = ys['ETH-USD']['chart']['result'][0]
ts2 = r2['timestamp']; q2 = r2['indicators']['quote'][0]
c2 = [c for c in q2['close'] if c is not None]
for win, label in [(10, '10d'), (21, '21d'), (63, '63d')]:
    cs = c2[-(win + 1):]
    rets = [math.log(cs[i + 1] / cs[i]) for i in range(len(cs) - 1)]
    sd = statistics.stdev(rets)
    print('ETH realized %s: %.4f daily -> %.1f%% ann' % (label, sd, sd * math.sqrt(365) * 100))
print('ETH last 5 closes:', [round(x, 1) for x in c2[-5:]])
