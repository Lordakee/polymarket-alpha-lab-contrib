import json, urllib.request, time, datetime, os

RAW='/home/ubuntu/paper-sim/round13/raw'
def get(url, tries=3):
    for i in range(tries):
        try:
            req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as ex:
            if i==tries-1: raise
            time.sleep(2)

NOW=datetime.datetime.now(datetime.timezone.utc)
print('now',NOW.isoformat())

# ---- 1) Coinbase 6h candles, ~92d lookback, paginated ----
LOOKBACK_DAYS=92
start0=NOW-datetime.timedelta(days=LOOKBACK_DAYS)
for sym,prod in [('ETH','ETH-USD'),('BTC','BTC-USD')]:
    allrows={}
    cur=start0
    while cur < NOW:
        end=min(cur+datetime.timedelta(days=70), NOW)
        u=(f'https://api.exchange.coinbase.com/products/{prod}/candles?granularity=21600'
           f'&start={cur.strftime("%Y-%m-%dT%H:%M:%SZ")}&end={end.strftime("%Y-%m-%dT%H:%M:%SZ")}')
        d=get(u)
        for r in d: allrows[r[0]]=r
        print(sym,cur.date(),'->',end.date(),'got',len(d),'cum',len(allrows),flush=True)
        cur=end
        time.sleep(0.5)
    rows=sorted(allrows.values(), key=lambda r:r[0])
    json.dump(rows, open(f'{RAW}/{sym.lower()}_candles.json','w'))
    print(sym,'total bars',len(rows),
          'first',datetime.datetime.fromtimestamp(rows[0][0],datetime.timezone.utc),
          'last',datetime.datetime.fromtimestamp(rows[-1][0],datetime.timezone.utc),
          'last_close',rows[-1][4])

# ---- 2) Gamma events discovery (crypto/ethereum/bitcoin tags) ----
out={}
for slug in ['crypto','ethereum','bitcoin']:
    out[slug]=[]
    for off in range(0,1000,100):
        try:
            d=get(f'https://gamma-api.polymarket.com/events/pagination?limit=100&offset={off}&active=true&order=volume24hr&ascending=false&tag_slug={slug}')
        except Exception as ex:
            print(slug,off,'ERR',ex); break
        evs=d.get('data') or []
        if not evs: break
        out[slug].extend(evs)
        time.sleep(0.4)
    print(slug,'events cum',len(out[slug]))
json.dump(out, open(f'{RAW}/discover13.json','w'))

# ---- 3) Gamma market snapshots for the 3 position markets ----
pos={}
for mid in [3866000,3865999,3865962]:
    try:
        m=get(f'https://gamma-api.polymarket.com/markets/{mid}')
        pos[str(mid)]=m
        print('market',mid,'->',m.get('question'))
    except Exception as ex:
        print('market',mid,'ERR',ex)
json.dump(pos, open(f'{RAW}/position_markets.json','w'))

# ---- 4) CLOB books for position tokens (YES+NO sides) ----
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
    try:
        b=get(f'https://clob.polymarket.com/book?token_id={t}')
        books[k]=b
        print(k,'book ok, bids',len(b.get('bids',[])),'asks',len(b.get('asks',[])))
    except Exception as ex:
        print(k,'ERR',ex)
    time.sleep(0.4)
json.dump({'fetched_at':NOW.isoformat(),'books':books}, open(f'{RAW}/position_books.json','w'))
print('DONE')
