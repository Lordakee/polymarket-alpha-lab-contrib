import json, time, urllib.request, sys

IDS = {
 '62_alaves_tt_o05': 6111575,
 '63_villa_win_no': 6237007,
 '64_mainz_bayern_btts_yes': 6176123,
 '65_osasuna_tt_o05': 6180838,
 '66_valencia_rm_u35': 6180689,
 '67_monaco_win_no': 6236736,
 '68_brest_lyon_o25': 6239548,
}
def get(url):
    req = urllib.request.Request(url, headers={'User-Agent':'papersim-r39-recheck'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

out = {}
for key, mid in IDS.items():
    try:
        m = get('https://gamma-api.polymarket.com/markets/%d' % mid)
    except Exception as e:
        out[key] = {'error': str(e)}
        continue
    rec = {
      'id': mid,
      'question': m.get('question'),
      'outcomes': m.get('outcomes'),
      'outcomePrices': m.get('outcomePrices'),
      'closed': m.get('closed'),
      'active': m.get('active'),
      'archived': m.get('archived'),
      'endDate': m.get('endDate'),
      'clobTokenIds': m.get('clobTokenIds'),
      'liquidityNum': m.get('liquidityNum'),
      'volumeNum': m.get('volumeNum'),
      'umaResolutionStatus': m.get('umaResolutionStatus'),
      'fetched_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    }
    # CLOB book for both tokens
    toks = json.loads(m.get('clobTokenIds') or '[]')
    books = []
    for t in toks:
        try:
            b = get('https://clob.polymarket.com/book?token_id=%s' % t)
            bids = b.get('bids') or []
            asks = b.get('asks') or []
            bid_depth = sum(float(x.get('size',0)) for x in bids)
            ask_depth = sum(float(x.get('size',0)) for x in asks)
            best_bid = max((float(x['price']) for x in bids), default=None)
            best_ask = min((float(x['price']) for x in asks), default=None)
            books.append({'token': t[:16]+'...', 'best_bid': best_bid, 'best_ask': best_ask,
                          'bid_depth_shares': round(bid_depth,1), 'ask_depth_shares': round(ask_depth,1),
                          'top_bids': sorted([{'p':float(x['price']),'s':float(x['size'])} for x in bids], key=lambda z:-z['p'])[:5],
                          'top_asks': sorted([{'p':float(x['price']),'s':float(x['size'])} for x in asks], key=lambda z:z['p'])[:5]})
            time.sleep(0.4)
        except Exception as e:
            books.append({'token': t[:16]+'...', 'error': str(e)})
    rec['books'] = books
    out[key] = rec
    print(key, 'closed=', rec['closed'], 'prices=', rec['outcomePrices'], flush=True)
    time.sleep(0.4)

json.dump(out, open('/home/ubuntu/paper-sim/round39/raw/held_fresh.json','w'), indent=1)
print('SAVED')
