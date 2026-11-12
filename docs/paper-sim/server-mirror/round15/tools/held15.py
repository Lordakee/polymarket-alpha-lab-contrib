"""Round-15 held-position verification: current CLOB books for 6 weekend soccer positions.

Token lookup: fresh from round15/raw/events_window.json by market question;
hardcoded round-13 token fallback if lookup misses (market still open).
"""
import json, time, urllib.request

RAW = '/home/ubuntu/paper-sim/round15/raw'

def get(url, tries=4):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=20) as r: return json.load(r)
        except Exception as e:
            last = e; time.sleep(1.5 + i)
    return {'err': repr(last)}

HELD = [
 {'match': 'Rayo Vallecano de Madrid vs. Elche CF', 'mkt': 'O/U 2.5', 'side': 'Over', 'side_tok_i': 0,
  'entry': 0.53, 'kickoff': '2026-10-24T12:00:00Z',
  'tok': '9116669476112265462694025495013443117366130063892402444985630293176393540908',
  'other': '92487992206873564286167337477355302070522911085195502140758667451060581755956'},
 {'match': 'Arsenal FC vs. Everton FC', 'mkt': 'O/U 3.5', 'side': 'Over', 'side_tok_i': 0,
  'entry': 0.30, 'kickoff': '2026-10-24T14:00:00Z',
  'tok': '86952922319782459000573239448963872822616788657845800941417935509880762248202',
  'other': '91490842968483514605128943479564633939609605755311016410968800110312490449288'},
 {'match': 'Valencia CF vs. Villarreal CF', 'mkt': 'O/U 2.5', 'side': 'Over', 'side_tok_i': 0,
  'entry': None, 'kickoff': '2026-10-24T16:30:00Z',
  'tok': '113956885313196773326296494013949843712263930132261242498902776458548076379606',
  'other': '66752275775900667478223386766383210406236369483584185753267389385513071781405'},
 {'match': 'Racing Club de Lens vs. Paris FC', 'mkt': 'O/U 1.5', 'side': 'Over', 'side_tok_i': 0,
  'entry': 0.81, 'kickoff': '2026-10-24T18:45:00Z',
  'tok': '113478505921291345757646047144512080105023507666947065227710701857377544814788',
  'other': None},
 {'match': 'Hull City AFC vs. Brentford FC', 'mkt': 'BTTS', 'side': 'Yes', 'side_tok_i': 0,
  'entry': 0.58, 'kickoff': '2026-10-25T14:00:00Z',
  'tok': '69490845002987222093688725350357071854826331880034843497949273436107963998783',
  'other': '38552361894697984046226070812932030619784300884724525278086579798122832577991'},
 {'match': 'Sunderland AFC vs. Leeds United FC', 'mkt': 'O/U 2.5', 'side': 'Over', 'side_tok_i': 0,
  'entry': None, 'kickoff': '2026-10-25T16:30:00Z',
  'tok': '71635534484631441239929894929524036161339080787762925655844551684321199285282',
  'other': '73276420481210434295945528440266302507422225784813152300467731949037810163133'},
]

QMAP = {
 'Rayo Vallecano de Madrid vs. Elche CF': 'Rayo Vallecano de Madrid vs. Elche CF: O/U 2.5',
 'Arsenal FC vs. Everton FC': 'Arsenal FC vs. Everton FC: O/U 3.5',
 'Valencia CF vs. Villarreal CF': 'Valencia CF vs. Villarreal CF: O/U 2.5',
 'Racing Club de Lens vs. Paris FC': 'Racing Club de Lens vs. Paris FC: O/U 1.5',
 'Hull City AFC vs. Brentford FC': 'Hull City AFC vs. Brentford FC: Both Teams to Score',
 'Sunderland AFC vs. Leeds United FC': 'Sunderland AFC vs. Leeds United FC: O/U 2.5',
}

# refresh tokens from fresh gamma window (handles missing LENS other-token, rotation)
try:
    evs = json.load(open(RAW + '/events_window.json'))
    for e in evs:
        for h in HELD:
            if e.get('title', '').split(' - ')[0].strip() != h['match']: continue
            for m in e.get('markets') or []:
                if m.get('q') == QMAP[h['match']]:
                    toks = m.get('tokens')
                    if isinstance(toks, str): toks = json.loads(toks)
                    if toks and len(toks) >= 2:
                        h['tok'] = toks[h['side_tok_i']]
                        h['other'] = toks[1 - h['side_tok_i']]
except Exception as ex:
    print('token refresh skipped:', repr(ex))

def book_side(levels, side):
    if not levels: return None
    lv = sorted(((float(l['price']), float(l['size'])) for l in levels), key=lambda x: x[0] if side == 'ask' else -x[0])
    best = lv[0][0]
    if side == 'ask': near = sum(p * s for p, s in lv if p <= best + 0.02)
    else: near = sum(p * s for p, s in lv if p >= best - 0.02)
    return {'best': round(best, 4), 'levels': len(lv), 'depth_near2c': round(near, 0)}

out = []
for h in HELD:
    rec = dict(h)
    if h.get('other'):
        o = get('https://clob.polymarket.com/book?token_id=' + h['other'])
        rec['other_book'] = ({'bid': book_side(o.get('bids', []), 'bid'),
                              'ask': book_side(o.get('asks', []), 'ask'), 'ts': o.get('timestamp')}
                             if 'err' not in o else {'err': o['err']})
        time.sleep(0.25)
    else:
        rec['other_book'] = {'err': 'no other token'}
    b = get('https://clob.polymarket.com/book?token_id=' + h['tok'])
    if 'err' in b:
        rec['side_book'] = {'err': b['err']}
    else:
        rec['side_book'] = {'bid': book_side(b.get('bids', []), 'bid'),
                            'ask': book_side(b.get('asks', []), 'ask'), 'ts': b.get('timestamp')}
    bid = rec.get('side_book', {}).get('bid', {}) or {}
    ask = rec.get('side_book', {}).get('ask', {}) or {}
    mid = None
    if bid.get('best') is not None and ask.get('best') is not None:
        mid = round((bid['best'] + ask['best']) / 2, 4)
    rec['current_mid'] = mid
    rec['pnl_vs_entry_c'] = None if (h['entry'] is None or bid.get('best') is None) else round(bid['best'] - h['entry'], 4)
    out.append(rec)
    print('%-46s %-6s bid=%-7s ask=%-7s mid=%-7s entry=%-6s pnl_bid_c=%s' % (
        h['match'][:46], h['side'], bid.get('best'), ask.get('best'), mid, h['entry'], rec['pnl_vs_entry_c']), flush=True)
    time.sleep(0.3)

json.dump({'generated_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'held': out},
          open(RAW + '/held_books.json', 'w'), indent=1)
print('saved held_books.json')
