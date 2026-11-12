import json, urllib.request, time, datetime

RAW='/home/ubuntu/paper-sim/round19/raw'
def get(url, tries=3):
    for i in range(tries):
        try:
            req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as ex:
            if i==tries-1: raise
            time.sleep(2.5)

NOW=datetime.datetime.now(datetime.timezone.utc)
print('now',NOW.isoformat())

# ---- 1) Spot: Coinbase first, Binance fallback ----
spot={}; spot_src={}
for sym, cb, bn in [('ETH','ETH-USD','ETHUSDT'),('BTC','BTC-USD','BTCUSDT')]:
    try:
        d=get(f'https://api.exchange.coinbase.com/products/{cb}/ticker')
        spot[sym]=float(d['price']); spot_src[sym]='coinbase'
    except Exception as ex:
        print(sym,'coinbase ERR',ex)
        d=get(f'https://api.binance.com/api/v3/ticker/price?symbol={bn}')
        spot[sym]=float(d['price']); spot_src[sym]='binance'
    time.sleep(0.5)
print('SPOT',spot,spot_src)

# ---- 2) Binance 6h klines back to Jun 1 2026 (vol + barrier history) ----
for sym, bn in [('ETH','ETHUSDT'),('BTC','BTCUSDT')]:
    rows_all=[]
    start=int(datetime.datetime(2026,6,1,tzinfo=datetime.timezone.utc).timestamp()*1000)
    while True:
        u=(f'https://api.binance.com/api/v3/klines?symbol={bn}&interval=6h'
           f'&startTime={start}&limit=1000')
        d=get(u)
        if not d: break
        for r in d:
            rows_all.append([r[0]//1000, float(r[3]), float(r[2]), float(r[1]), float(r[4]), float(r[5])])
        if len(d)<1000: break
        start=d[-1][0]+6*3600*1000
        time.sleep(0.5)
    json.dump(rows_all, open(f'{RAW}/{sym.lower()}_candles.json','w'))
    print(sym,'bars',len(rows_all),
          'first',datetime.datetime.fromtimestamp(rows_all[0][0],datetime.timezone.utc),
          'last_bar_t0',datetime.datetime.fromtimestamp(rows_all[-1][0],datetime.timezone.utc),
          'last_close',rows_all[-1][4],'last_low',rows_all[-1][1])
    time.sleep(0.5)

# ---- 3) ETH 1m klines Oct 24 00:00 UTC -> now (weekend low verification) ----
m1_start=int(datetime.datetime(2026,10,24,tzinfo=datetime.timezone.utc).timestamp()*1000)
m1=[]
while True:
    u=f'https://api.binance.com/api/v3/klines?symbol=ETHUSDT&interval=1m&startTime={m1_start}&limit=1000'
    d=get(u)
    if not d: break
    for r in d:
        m1.append([r[0]//1000, float(r[3]), float(r[2]), float(r[1]), float(r[4])])
    if len(d)<1000: break
    m1_start=d[-1][0]+60*1000
    time.sleep(0.5)
json.dump(m1, open(f'{RAW}/eth_1m_weekend.json','w'))
wk=[r for r in m1 if r[0] < int(datetime.datetime(2026,10,26,tzinfo=datetime.timezone.utc).timestamp())]
lo=min(wk,key=lambda r:r[1])
today=[r for r in m1 if r[0] >= int(datetime.datetime(2026,10,26,tzinfo=datetime.timezone.utc).timestamp())]
lo_t=min(today,key=lambda r:r[1]) if today else None
print('ETH weekend(Oct24-25) 1m low', lo[1], 'at', datetime.datetime.fromtimestamp(lo[0],datetime.timezone.utc))
print('ETH Monday-so-far 1m low', (lo_t[1], str(datetime.datetime.fromtimestamp(lo_t[0],datetime.timezone.utc))) if lo_t else None)
# lows per day
for day in (24,25,26):
    dd=[r for r in m1 if datetime.datetime.fromtimestamp(r[0],datetime.timezone.utc).day==day]
    if dd:
        l=min(dd,key=lambda r:r[1]); h=max(dd,key=lambda r:r[2])
        print(f'Oct{day}: low {l[1]} at {datetime.datetime.fromtimestamp(l[0],datetime.timezone.utc).strftime("%H:%M")} | high {h[2]}')
# sub-2280 minutes count (proximity clock)
sub2280=[r for r in m1 if r[1]<=2280]
sub2275=[r for r in m1 if r[1]<=2275]
print('minutes <=2280:',len(sub2280),' <=2275:',len(sub2275))

# ---- 4) Gamma market snapshots for the 3 position markets ----
pos={}
for mid in [3866000,3865999,3865962]:
    try:
        m=get(f'https://gamma-api.polymarket.com/markets/{mid}')
        pos[str(mid)]=m
        print('market',mid,'->',m.get('question'),'| active',m.get('active'),'closed',m.get('closed'),
              '| lastTrade',m.get('lastTradePrice'),'| bb',m.get('bestBid'),'ba',m.get('bestAsk'))
    except Exception as ex:
        print('market',mid,'ERR',ex)
    time.sleep(0.6)
json.dump(pos, open(f'{RAW}/position_markets.json','w'))

# ---- 5) CLOB books for position tokens (YES+NO sides) ----
TOKS={
 'ETH2250_YES':'66335306745821529065179061745515953781644081595464464996921948603911228936814',
 'ETH2250_NO' :'63382519856399132244485492020084100091374236550290181904952415637486462703240',
 'ETH2000_YES':'84768145019786095547717415732823502270141145470320952547313245070010555237775',
 'ETH2000_NO' :'41139993928652620342595776605433147455405569646745899886663605344607611434891',
 'BTC65K_YES' :'53780045235418715931128205720209124033878539466833083429441668150974549326823',
 'BTC65K_NO'  :'104072675121616169708481552608019889218004323979484070212305769583143217407441',
}
books={}
for k,t in TOKS.items():
    for attempt in range(3):
        try:
            b=get(f'https://clob.polymarket.com/book?token_id={t}')
            books[k]=b
            bids=sorted(b.get('bids',[]), key=lambda x:-float(x['price']))[:3]
            asks=sorted(b.get('asks',[]), key=lambda x: float(x['price']))[:3]
            print(k,'top bids',bids,'top asks',asks)
            break
        except Exception as ex:
            print(k,'ERR',ex)
            time.sleep(2.0)
    time.sleep(0.8)
json.dump({'fetched_at':NOW.isoformat(),'books':books}, open(f'{RAW}/position_books.json','w'))

# ---- 6) Batch-refresh classified markets from round15 scan ----
prev=json.load(open('/home/ubuntu/paper-sim/round15/raw/crypto_scan.json'))['classified_markets']
conds=[m['condId'] for m in prev if m.get('condId')]
print('condIds to refresh:',len(conds))
fresh={}
for i in range(0,len(conds),20):
    batch=conds[i:i+20]
    try:
        ms=get('https://gamma-api.polymarket.com/markets?condition_ids='+','.join(batch))
        for m in ms:
            if m.get('conditionId'): fresh[m['conditionId']]=m
    except Exception as ex:
        print('batch',i,'ERR',ex)
    time.sleep(1.0)
json.dump({'fetched_at':NOW.isoformat(),'markets':fresh}, open(f'{RAW}/market_refresh.json','w'))
print('fresh markets:',len(fresh))
print('DONE fetch19')
