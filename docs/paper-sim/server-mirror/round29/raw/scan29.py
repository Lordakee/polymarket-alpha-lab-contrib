import json, urllib.request, urllib.parse, time

BASE='https://gamma-api.polymarket.com'
def get(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=40) as r: return json.load(r)

all_mkts=[]
for tag in ['politics','us-politics','geopolitics','economy','middle-east']:
    for off in [0,100]:
        try:
            d=get(BASE+'/markets?tag_slug='+tag+'&closed=false&active=true&limit=100&offset='+str(off)+'&order=volume24hr&ascending=false')
            for m in d: m['_tag']=tag
            all_mkts.extend(d)
            print(tag,off,'->',len(d))
        except Exception as e:
            print(tag,off,'ERR',str(e)[:60])
        time.sleep(1.2)

seen=set(); rows=[]
for m in all_mkts:
    mid=m.get('id')
    if mid in seen: continue
    seen.add(mid)
    try: px=json.loads(m.get('outcomePrices','[]'))
    except: px=[]
    if not px: continue
    try: yes=float(px[0])
    except: continue
    vol24=m.get('volume24hr') or 0
    liq=m.get('liquidityNum') or 0
    end=m.get('endDate','')
    q=m.get('question','')
    if vol24<20000: continue
    if not (0.06<=yes<=0.94): continue
    rows.append({'id':mid,'q':q[:90],'tag':m['_tag'],'yes':round(yes,3),'bid':m.get('bestBid'),'ask':m.get('bestAsk'),'vol24':round(vol24),'liq':round(liq),'end':end,'slug':m.get('slug','')})

rows.sort(key=lambda r:-r['vol24'])
print()
for r in rows[:60]:
    print(f"{r['yes']:.3f} v24={r['vol24']:>9,} liq={r['liq']:>9,} end={r['end'][:10]} [{r['tag'][:6]}] {r['q'][:80]}")
json.dump(rows,open('/home/ubuntu/paper-sim/round29/raw/scan_rows.json','w'),indent=1)
print('total rows:',len(rows))
