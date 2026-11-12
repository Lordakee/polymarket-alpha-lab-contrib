"""Round-15: CLOB books for held econ positions + Yahoo Friday closes."""
import json, time, urllib.request
RAW='/home/ubuntu/paper-sim/round15/raw'

def get(url, tries=5):
    last=None
    for i in range(tries):
        try:
            req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=25) as r: return json.load(r)
        except Exception as e:
            last=e; time.sleep(1.5+i)
    return {'err':repr(last)}

held=json.load(open(RAW+'/held_tokens15.json'))
books={}
for name,m in held.items():
    if not m: continue
    toks=json.loads(m['tokens'])
    b={}
    for i,side in enumerate(['YES','NO']):
        r=get('https://clob.polymarket.com/book?token_id='+toks[i])
        bids=sorted([{'p':float(l['price']),'s':float(l['size'])} for l in (r.get('bids') or [])], key=lambda x:-x['p'])
        asks=sorted([{'p':float(l['price']),'s':float(l['size'])} for l in (r.get('asks') or [])], key=lambda x:x['p'])
        b[side]={'bids':bids[:8],'asks':asks[:8]}
    books[name]={'q':m['q'],'gamma_prices':m['prices'],'book':b}
    # executable size for YES at various depths
    ys=b['YES']
    cum=0; cumv=0; lvls=[]
    for a in ys['asks']:
        cum+=a['s']; cumv+=a['s']*a['p']; lvls.append((a['p'],int(a['s']),round(cumv/max(cum,1),4)))
    print('===',name,m['q'])
    print('  YES bids:',[(x['p'],int(x['s'])) for x in ys['bids'][:5]])
    print('  YES asks (cum-avg):',lvls[:6])
json.dump(books, open(RAW+'/clob_books15.json','w'), indent=1)
print('saved clob_books15.json')
