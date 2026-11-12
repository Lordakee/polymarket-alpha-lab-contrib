"""Round-15 econ scan: Gamma current prices for oil/gold/Fed/index complexes."""
import json, urllib.request, urllib.parse, time

BASE='https://gamma-api.polymarket.com'
RAW='/home/ubuntu/paper-sim/round15/raw'

def get(url, tries=6):
    last=None
    for i in range(tries):
        try:
            req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as r: return json.load(r)
        except Exception as e:
            last=e; time.sleep(2.5+2*i)
    raise last

# Public-markets search sweep on keywords
KEYWORDS=['WTI','Crude Oil','Brent','Gold (XAUUSD','Silver','Fed ','interest rates after','S&P 500','SPY','Nasdaq','Bitcoin above','Eggs','Natural gas','Recession','US government shutdown']
out={}
for kw in KEYWORDS:
    res=[]
    offset=0
    while True:
        url=BASE+'/markets?'+urllib.parse.urlencode({
            'limit':100,'active':'true','closed':'false','archived':'false',
            'order':'volume24hr','ascending':'false','offset':offset,
            'keyword':kw})
        try: batch=get(url)
        except Exception as e:
            print('ERR',kw,repr(e)); break
        if not batch: break
        res.extend(batch)
        if len(batch)<100: break
        offset+=100
        if offset>=500: break
        time.sleep(0.6)
    slim=[]
    for m in res:
        q=str(m.get('question') or '')
        slim.append({
          'id':str(m.get('id')),'q':q,'slug':m.get('slug'),
          'outcomes':m.get('outcomes'),'prices':m.get('outcomePrices'),
          'tokens':m.get('clobTokenIds'),
          'bestBid':m.get('bestBid'),'bestAsk':m.get('bestAsk'),
          'spread':m.get('spread'),
          'liq':m.get('liquidityNum'),'vol24':m.get('volume24hr'),'vol':m.get('volume'),
          'endDate':m.get('endDate'),'closed':m.get('closedTime'),
          'umaResolutionStatus':m.get('umaResolutionStatus')})
    out[kw]=slim
    print(kw, len(slim))
    time.sleep(0.5)

json.dump(out, open(RAW+'/gamma_kw_sweep.json','w'), indent=1)
print('saved')
