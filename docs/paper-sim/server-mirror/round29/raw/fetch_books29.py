import json, urllib.request, time
def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=30) as r: return json.load(r)
out={}
m=get('https://gamma-api.polymarket.com/markets?slug=will-the-democratic-party-control-the-senate-after-the-2026-midterm-elections')
mk=m[0] if m else {}
out['senate_mkt']={'id':mk.get('id'),'q':mk.get('question'),'px':mk.get('outcomePrices'),'bestBid':mk.get('bestBid'),'bestAsk':mk.get('bestAsk'),'vol24':mk.get('volume24hr'),'liq':mk.get('liquidityNum')}
print('senate mkt:',out['senate_mkt'])
toks=json.loads(mk.get('clobTokenIds','[]'))
time.sleep(1.2)
b=get('https://clob.polymarket.com/book?token_id='+toks[0])
bids=sorted(b['bids'],key=lambda x:-float(x['price']))[:6]
asks=sorted(b['asks'],key=lambda x:float(x['price']))[:6]
out['senate_book']={'bids':bids,'asks':asks,'last':b.get('last_trade_price')}
print('SENATE-D YES book: bids',[(x['price'],x['size']) for x in bids])
print('                   asks',[(x['price'],x['size']) for x in asks],'last',b.get('last_trade_price'))
time.sleep(1.2)
# also ceasefire re-check
b2=get('https://clob.polymarket.com/book?token_id=67102598924726349989742049657609063097299442010642912942032681022413402597017')
bids2=sorted(b2['bids'],key=lambda x:-float(x['price']))[:5]
asks2=sorted(b2['asks'],key=lambda x:float(x['price']))[:5]
out['ceasefire_book_now']={'bids':bids2,'asks':asks2,'last':b2.get('last_trade_price')}
print('CEASEFIRE YES now: bids',[(x['price'],x['size']) for x in bids2],'asks',[(x['price'],x['size']) for x in asks2],'last',b2.get('last_trade_price'))
json.dump(out,open('/home/ubuntu/paper-sim/round29/raw/books_now.json','w'),indent=1)
