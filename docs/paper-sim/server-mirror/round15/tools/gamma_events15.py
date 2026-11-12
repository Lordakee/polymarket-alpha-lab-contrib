"""Round-15: fetch full Gamma events for econ complexes."""
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
            last=e; time.sleep(2+2*i)
    raise last

EVENTS=[
 'what-price-will-spy-hit-in-october-2026',
 'what-price-will-xauusd-hit-in-october-2026',
 'what-price-will-wti-hit-in-october-2026',
 'will-spy-hit-week-of-october-26-2026',
 'will-spy-hit-week-of-october-19-2026',
 'will-xauusd-hit-week-of-october-26-2026',
 'will-wti-hit-week-of-october-26-2026',
 'fed-decision-in-december-20260729232808632',
 'spx-close-dec-2026',
 'ndx-close-dec-2026',
 'crude-oil-all-time-high-by',
 'military-action-against-saudi-oil-pipeline-east-west-byptptpt',
 'will-gold-gc-hit-high-5000-by-end-of-december-2026',
 'will-gold-gc-hit-high-6000-by-end-of-december',
 'will-gold-gc-hit-low-3500-by-end-of-december',
 'will-gold-gc-hit-low-3000-by-end-of-december',
 'will-gold-gc-hit-high-4500-by-end-of-december',
 'bab-el-mandeb-strait-effectively-closed-by',
]
out={}
for slug in EVENTS:
    try:
        e=get(BASE+'/events?'+urllib.parse.urlencode({'slug':slug}))
        if isinstance(e,list) and e: e=e[0]
        out[slug]={
          'title':e.get('title'),'endDate':e.get('endDate'),
          'liq':e.get('liquidityNum'),'vol24':e.get('volume24hr'),'vol':e.get('volume'),
          'markets':[{
            'q':m.get('question'),'slug':m.get('slug'),'id':str(m.get('id')),
            'outcomes':m.get('outcomes'),'prices':m.get('outcomePrices'),
            'tokens':m.get('clobTokenIds'),
            'bestBid':m.get('bestBid'),'bestAsk':m.get('bestAsk'),
            'liq':m.get('liquidityNum'),'vol24':m.get('volume24hr'),
            'endDate':m.get('endDate'),
            'closed':m.get('closed'),'active':m.get('active'),
          } for m in (e.get('markets') or [])]}
        print(slug,'->',len(out[slug]['markets']),'markets')
    except Exception as ex:
        print(slug,'ERR',repr(ex))
    time.sleep(0.6)
json.dump(out, open(RAW+'/gamma_events15.json','w'), indent=1)
print('saved', len(out))
