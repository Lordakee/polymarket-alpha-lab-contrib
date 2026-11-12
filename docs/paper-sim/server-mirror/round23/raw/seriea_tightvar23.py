"""Round-23 sanity sweep: ALL eligible markets, both sides, Gamma-mid edges.
Find any liq>=5k + var<=6c market and its best mid edge (would need >=~5.5c for exec gate)."""
import json

M = json.load(open('/home/ubuntu/paper-sim/round23/raw/seriea_model23.json'))
tight=[]
for mr in M['matches']:
    for q, rec in mr['markets'].items():
        if rec['kind'].startswith('spread'): continue
        prices=rec['prices']
        if isinstance(prices,str):
            try: prices=json.loads(prices)
            except Exception: prices=None
        bb,ba=rec['bestBid'],rec['bestAsk']
        if bb is not None and ba is not None: mid0=(float(bb)+float(ba))/2.0
        elif prices: mid0=float(prices[0])
        else: continue
        liq=rec['liq'] or 0
        if liq<5000: continue
        vs=rec['var_spread']
        if vs>0.06: continue
        # both sides mid edge
        e0=rec['p0_med']-mid0
        e1=(1-rec['p0_med'])-(1-mid0)
        best_side='Over/Yes' if e0>=e1 else 'Under/No'
        best_e=max(e0,e1)
        tight.append({'match':mr['label'],'q':q,'kind':rec['kind'],'var':vs,'liq':liq,
                      'best_side':best_side,'best_mid_edge':round(best_e,4),
                      'p0_med':rec['p0_med'],'mid0':round(mid0,4)})
tight.sort(key=lambda x:-x['best_mid_edge'])
print('tight-var (<=6c) + liq>=5k eligible markets:', len(tight))
for t in tight:
    print('  %-22s %-60s %-9s var %.3f edge %+.4f p0 %.3f mid %.3f liq %6.0f' % (
        t['match'], t['q'][:60], t['best_side'], t['var'], t['best_mid_edge'], t['p0_med'], t['mid0'], t['liq']))
