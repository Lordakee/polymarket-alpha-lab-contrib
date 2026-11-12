"""Round-13 held-position verification: current CLOB books for 7 weekend soccer positions."""
import json, time, urllib.request

def get(url, tries=4):
    last=None
    for i in range(tries):
        try:
            req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=20) as r: return json.load(r)
        except Exception as e:
            last=e; time.sleep(1.5+i)
    return {'err': repr(last)}

HELD=[
 {'match':'Ipswich Town FC vs. Nottingham Forest FC','mkt':'O/U 2.5','side':'Over','side_tok_i':0,
  'entry':None,'ref_mid_r12':0.555,'kickoff':'2026-10-23T19:00:00Z',
  'tok':'74194026966128789094954083082151276953405335486412760753989232997409511594086',
  'other':'66266950901029663824384539525739886089425572772570667965130063993257653545192'},
 {'match':'Deportivo Alavés vs. Málaga CF','mkt':'O/U 2.5','side':'Over','side_tok_i':0,
  'entry':0.46,'ref_mid_r12':0.455,'kickoff':'2026-10-23T19:00:00Z',
  'tok':'33671301362641900183660534159323237505678075123861517372763137070000327599463',
  'other':'3525398375110874527862941323591823462220813368139751114392218475823733939001'},
 {'match':'Rayo Vallecano de Madrid vs. Elche CF','mkt':'O/U 2.5','side':'Over','side_tok_i':0,
  'entry':0.53,'ref_mid_r12':0.525,'kickoff':'2026-10-24T12:00:00Z',
  'tok':'9116669476112265462694025495013443117366130063892402444985630293176393540908',
  'other':'92487992206873564286167337477355302070522911085195502140758667451060581755956'},
 {'match':'Arsenal FC vs. Everton FC','mkt':'O/U 3.5','side':'Over','side_tok_i':0,
  'entry':0.30,'ref_mid_r12':0.295,'kickoff':'2026-10-24T14:00:00Z',
  'tok':'86952922319782459000573239448963872822616788657845800941417935509880762248202',
  'other':'91490842968483514605128943479564633939609605755311016410968800110312490449288'},
 {'match':'Valencia CF vs. Villarreal CF','mkt':'O/U 2.5','side':'Over','side_tok_i':0,
  'entry':None,'ref_mid_r12':0.555,'kickoff':'2026-10-24T16:30:00Z',
  'tok':'113956885313196773326296494013949843712263930132261242498902776458548076379606',
  'other':'66752275775900667478223386766383210406236369483584185753267389385513071781405'},
 {'match':'Hull City AFC vs. Brentford FC','mkt':'BTTS','side':'Yes','side_tok_i':0,
  'entry':0.58,'ref_mid_r12':0.575,'kickoff':'2026-10-25T14:00:00Z',
  'tok':'69490845002987222093688725350357071854826331880034843497949273436107963998783',
  'other':'38552361894697984046226070812932030619784300884724525278086579798122832577991'},
 {'match':'Sunderland AFC vs. Leeds United FC','mkt':'O/U 2.5','side':'Over','side_tok_i':0,
  'entry':None,'ref_mid_r12':0.445,'kickoff':'2026-10-25T16:30:00Z',
  'tok':'71635534484631441239929894929524036161339080787762925655844551684321199285282',
  'other':'73276420481210434295945528440266302507422225784813152300467731949037810163133'},
]

def book_side(levels, side):
    if not levels: return None
    lv=sorted(((float(l['price']),float(l['size'])) for l in levels), key=lambda x: x[0] if side=='ask' else -x[0])
    best=lv[0][0]
    near=sum(p*s for p,s in lv if (p<=best+0.02) if side=='ask') if side=='ask' else sum(p*s for p,s in lv if p>=best-0.02)
    return {'best':round(best,4),'levels':len(lv),'depth_near2c':round(near,0)}

out=[]
for h in HELD:
    b=get('https://clob.polymarket.com/book?token_id='+h['tok'])
    o=get('https://clob.polymarket.com/book?token_id='+h['other'])
    rec=dict(h)
    if 'err' in b:
        rec['side_book']={'err':b['err']}
    else:
        rec['side_book']={'bid':book_side(b.get('bids',[]),'bid'),'ask':book_side(b.get('asks',[]),'ask'),'ts':b.get('timestamp')}
    if 'err' in o:
        rec['other_book']={'err':o['err']}
    else:
        rec['other_book']={'bid':book_side(o.get('bids',[]),'bid'),'ask':book_side(o.get('asks',[]),'ask'),'ts':o.get('timestamp')}
    bid=rec.get('side_book',{}).get('bid',{}) or {}
    ask=rec.get('side_book',{}).get('ask',{}) or {}
    obid=(rec.get('other_book',{}).get('bid',{}) or {})
    oask=(rec.get('other_book',{}).get('ask',{}) or {})
    mid=None
    if bid.get('best') is not None and ask.get('best') is not None:
        mid=round((bid['best']+ask['best'])/2,4)
    rec['current_mid']=mid
    rec['pnl_vs_entry_c']=None if (h['entry'] is None or bid.get('best') is None) else round(bid['best']-h['entry'],4)
    out.append(rec)
    print('%-46s %-8s bid=%-7s ask=%-7s mid=%-7s entry=%-6s ref_r12=%-6s pnl_bid_c=%s' % (
        h['match'][:46], h['side'], bid.get('best'), ask.get('best'), mid, h['entry'], h['ref_mid_r12'], rec['pnl_vs_entry_c']), flush=True)
    time.sleep(0.3)

json.dump({'generated_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'held':out},
          open('/home/ubuntu/paper-sim/round13/raw/held_books.json','w'),indent=1)
print('saved held_books.json')
