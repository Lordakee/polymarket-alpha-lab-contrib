import json, urllib.request, time, re

d=json.load(open('/home/ubuntu/paper-sim/round4/raw/events_detail.json'))
def toks(m):
    ids=m.get('clobTokenIds'); outs=m.get('outcomes')
    if not ids or not outs: return None
    try:
        ids=json.loads(ids) if isinstance(ids,str) else ids
        outs=json.loads(outs) if isinstance(outs,str) else outs
    except: return None
    return dict(zip(outs,ids))

# shortlist: (event_key, market question substring)
short=[
 # BTC
 ('What price will Bitcoin hit in October?',None),
 ('What price will Bitcoin hit October 12-18?',None),
 ('What price will Bitcoin hit on October 14?',None),
 ('Bitcoin above ___ on October 15?',None),
 # ETH report-only
 ('What price will Ethereum hit in October?',None),
 ('What price will Ethereum hit in 2026?',None),
 # GOLD
 ('What will Gold (XAUUSD) hit in October 2026?',None),
 ('What will Gold (XAUUSD) hit Week of October 12 2026?',None),
 ('What will Gold (GC) hit__ by end of December?',None),
 # OIL
 ('What will WTI Crude Oil (WTI) hit in October 2026?',None),
 ('What will WTI Crude Oil (WTI) hit Week of October 12 2026?',None),
 # SPY / SPX
 ('What will S&P 500 (SPY) hit in October 2026?',None),
 ('What will S&P 500 (SPY) hit Week of October 12 2026?',None),
 ('What will S&P 500 (SPX) hit by end of December?',None),
 # FED fresh
 ('fed_oct',None),('fed_dec',None),('fed_jan',None),('fed_path_sepdec',None),
 # politics
 ('brazil_runoff_amapa',None),('french_advance',None),
 # soccer weekend EPL + big others (O/U 2.5)
 ('Manchester City FC vs. Ipswich Town FC - More Markets',['O/U 2.5','Over/Under']),
 ('Brentford FC vs. Liverpool FC - More Markets',['O/U 2.5']),
 ('Everton FC vs. Chelsea FC - More Markets',['O/U 2.5']),
 ('Leeds United FC vs. Manchester United FC - More Markets',['O/U 2.5']),
 ('Real Betis Balompié vs. FC Barcelona - More Markets',['O/U 2.5']),
 ('Real Madrid CF vs. Sevilla FC - More Markets',['O/U 2.5']),
 ('Bologna FC 1909 vs. FC Internazionale Milano - More Markets',['O/U 2.5']),
 ('FC Bayern München vs. RB Leipzig - More Markets',['O/U 2.5']),
 ('RCD Espanyol de Barcelona vs. Club Atlético de Madrid - More Markets',['O/U 2.5']),
 ('Newcastle United FC vs. Aston Villa FC - More Markets',['O/U 2.5']),
 ('Nottingham Forest FC vs. Arsenal FC - More Markets',['O/U 2.5']),
 # UCL today big game
 ('Manchester City FC vs. Paris Saint-Germain FC - More Markets',['O/U 2.5']),
 ('AS Roma vs. Real Madrid CF - More Markets',['O/U 2.5']),
 # NFL totals
 ('Seahawks vs. Broncos',['O/U 40.5','O/U 42.5','O/U 38.5']),
 ('Bills vs. Raiders',['O/U 52.5','O/U 50.5']),
 ('Chargers vs. Chiefs',['O/U 42.5','O/U 40.5']),
 ('Cardinals vs. Rams',['O/U 52.5']),
 ('Steelers vs. Buccaneers',['O/U 40.5']),
 ('Panthers vs. Eagles',['O/U 41.5']),
 ('Bears vs. Falcons',['O/U 47.5']),
 ('Cowboys vs. Packers',['O/U 52.5']),
 # MLB
 ('MLB World Series Champion 2026',None),
 ('Milwaukee Brewers vs. Los Angeles Dodgers',['Milwaukee Brewers vs. Los Angeles Dodgers']),
 # NHL
 ('Stars vs. Avalanche',['O/U 5.5','O/U 6.5']),
 # UFC
 ('ufc_fn_malott',None),
 ('ufc333_merab',['Merab Dvalishvili vs. Petr Yan']),
 # NBA playoffs (POR)
 ('NBA: Team to Make Playoffs',['Portland','Orlando','Atlanta','Brooklyn','Utah','Phoenix','Dallas','Washington']),
]
sel=[]
for key,filters in short:
    if key not in d or not d[key].get('event'): continue
    e=d[key]['event']
    for m in e.get('markets',[]):
        if m.get('closed'): continue
        q=(m.get('question') or '')+' '+(m.get('groupItemTitle') or '')
        if filters and not any(f.lower() in q.lower() for f in filters): continue
        t=toks(m)
        if not t: continue
        for side,tid in t.items():
            sel.append({'event':key,'slug':d[key]['slug'],'q':(m.get('question') or m.get('groupItemTitle'))[:80],'id':m.get('id'),'side':side,'token':tid,
                        'desc':(m.get('description') or '')[:900]})
print('markets selected:',len(sel))
json.dump(sel, open('/home/ubuntu/paper-sim/round4/raw/shortlist.json','w'), indent=1)

def book(tid):
    url='https://clob.polymarket.com/book?token_id='+tid
    req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36','Accept':'application/json'})
    for i in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20) as r: return json.load(r)
        except Exception as ex:
            if i==2: return {'err':str(ex)}
            time.sleep(1.5)
books={}
for s in sel:
    b=book(s['token'])
    books[s['token']]={'meta':{k:s[k] for k in ('event','q','side','id','slug')},'book':b}
    time.sleep(0.25)
json.dump(books, open('/home/ubuntu/paper-sim/round4/raw/books.json','w'))
ok=sum(1 for b in books.values() if 'err' not in b['book'])
print('books fetched',ok,'/',len(books))
# quick summary of top of book
for tid,b in books.items():
    bb=b['book']
    if 'err' in bb: print('ERR',b['meta']['event'],b['meta']['q'][:40]); continue
    bids=sorted([float(l['price']) for l in bb.get('bids',[])],reverse=True)[:1]
    asks=sorted([float(l['price']) for l in bb.get('asks',[])])[:1]
    bsz=sum(float(l['size']) for l in bb.get('bids',[]) if float(l['price'])==bids[0]) if bids else 0
    asz=sum(float(l['size']) for l in bb.get('asks',[]) if float(l['price'])==asks[0]) if asks else 0
    print('%-46s %-3s bid %s x%d | ask %s x%d' % (b['meta']['q'][:46], b['meta']['side'][:3], bids[0] if bids else '-', int(bsz), asks[0] if asks else '-', int(asz)))
