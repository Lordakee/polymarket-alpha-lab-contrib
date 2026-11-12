"""Round-23 gates: exec from books, worst-variant edge, var gate; assemble scan + candidates.
Early-entry gates: var<=6c, worst>=+4c, exec>=+5c, liq>=$5k. match_winner SUSPENDED, spreads flag-only."""
import json, time

M = json.load(open('/home/ubuntu/paper-sim/round23/raw/seriea_model23.json'))
B = json.load(open('/home/ubuntu/paper-sim/round23/raw/clob_books23.json'))

def walk_ask(levels, dollars=250.0):
    lv=sorted(((float(l['price']), float(l['size'])) for l in levels), key=lambda x:x[0])
    if not lv: return None
    best=lv[0][0]
    cash=0.0; sh=0.0
    for p,sz in lv:
        take=min(sz,(dollars-cash)/p)
        if take<=0: break
        cash+=take*p; sh+=take
        if cash>=dollars-1e-9: break
    return {'best':round(best,4),'vwap250':round(cash/sh if sh>0 else best,4),
            'filled':cash>=dollars-1e-6,'n_levels':len(lv)}

def walk_bid(levels, dollars=250.0):
    lv=sorted(((float(l['price']), float(l['size'])) for l in levels), key=lambda x:-x[0])
    if not lv: return None
    best=lv[0][0]
    cash=0.0; sh=0.0
    for p,sz in lv:
        take=min(sz,(dollars-cash)/p)
        if take<=0: break
        cash+=take*p; sh+=take
        if cash>=dollars-1e-9: break
    return {'best':round(best,4),'vwap250':round(cash/sh if sh>0 else best,4)}

rows=[]
for mr in M['matches']:
    for q, rec in mr['markets'].items():
        prices=rec['prices']
        if isinstance(prices,str):
            try: prices=json.loads(prices)
            except Exception: prices=None
        bb,ba=rec['bestBid'],rec['bestAsk']
        if bb is not None and ba is not None: mid0=(float(bb)+float(ba))/2.0
        elif prices: mid0=float(prices[0])
        else: continue
        liq=rec['liq'] or 0
        for sidx in (0,1):
            bk=B.get('%s||%d'%(q,sidx))
            if not bk: continue
            a=walk_ask(bk.get('asks') or [])
            bd=walk_bid(bk.get('bids') or [])
            if not a: continue
            p_med = rec['p0_med'] if sidx==0 else round(1-rec['p0_med'],4)
            p_min = rec['p0_min'] if sidx==0 else round(1-rec['p0_max'],4)
            p_max = rec['p0_max'] if sidx==0 else round(1-rec['p0_min'],4)
            vs = round(p_max-p_min,4)
            exec_ask=a['vwap250']
            edge_exec=round(p_med-exec_ask,4)
            edge_worst=round(p_min-exec_ask,4)
            rows.append({'match':mr['label'],'match_full':mr['match'],'kickoff':mr['kickoff_utc'],
                'q':q,'kind':rec['kind'],'side_idx':sidx,
                'side':'Over/Yes' if sidx==0 else 'Under/No',
                'gamma_mid':round(mid0 if sidx==0 else 1-mid0,4),
                'p_med':p_med,'p_min':p_min,'p_max':p_max,'var_spread':vs,
                'exec_ask_vwap250':exec_ask,'exec_filled':a['filled'],'best_ask':a['best'],'best_bid':bd['best'] if bd else None,
                'edge_exec':edge_exec,'edge_worst':edge_worst,'liq':liq,'vol24':rec['vol24']})

GATES={'variant_spread_max':0.06,'worst_edge_min':0.04,'exec_edge_min':0.05,'liq_min':5000}
cands=[]; flagged=[]; near=[]
for r in rows:
    is_spread = r['kind'].startswith('spread')
    checks={'liq_ge_5k': r['liq']>=GATES['liq_min'],
            'var_le_6c': r['var_spread']<=GATES['variant_spread_max'],
            'worst_ge_4c': r['edge_worst']>=GATES['worst_edge_min'],
            'exec_ge_5c': r['edge_exec']>=GATES['exec_edge_min'],
            'kind_eligible': not is_spread,
            'exec_filled': r['exec_filled']}
    r['checks']=checks
    if is_spread:
        if r['edge_exec']>=0.03 or r['edge_worst']>=0.02: flagged.append(r)
    elif all([checks['liq_ge_5k'],checks['var_le_6c'],checks['worst_ge_4c'],checks['exec_ge_5c'],checks['exec_filled']]):
        cands.append(r)
    elif r['edge_exec']>=0.02 or r['edge_worst']>=0.015:
        near.append(r)

cands.sort(key=lambda x:(-x['edge_exec'],-x['edge_worst']))
near.sort(key=lambda x:-x['edge_exec'])
print('=== ROWS WITH BOOKS ===')
for r in rows:
    print('%-22s %-58s %-9s | exec %.3f edge %+.4f worst %+.4f var %.3f liq %6.0f | %s' % (
        r['match'], r['q'][:58], r['side'], r['exec_ask_vwap250'], r['edge_exec'], r['edge_worst'], r['var_spread'], r['liq'],
        'PASS' if r in cands else ('FLAG' if r in flagged else 'near')))
print()
print('CANDIDATES:', len(cands), '| FLAGGED:', len(flagged), '| NEAR:', len(near))
json.dump({'gates':GATES,'rows':rows,'candidates':cands,'flagged':flagged,'near':near},
    open('/home/ubuntu/paper-sim/round23/raw/gate_rows23.json','w'), indent=1)
