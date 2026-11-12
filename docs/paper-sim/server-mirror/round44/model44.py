"""ROUND-44B crypto model: barrier tables, ETH-2000 add-on, gates, coherence.

PAPER ONLY / REPORT ONLY / READONLY. No orders, no DB writes.
Model: polymarket_alpha_lab.papersim.crypto_model (r19 lineage, production
signature = 30d 6h-bar realized vol). Conservative YES = min(pA,pB),
conservative NO = 1 - max(pA,pB). Gates: net>=5c after crypto fee 0.07
(fee = 0.07*p*(1-p) per share), worst-variant >=4c (gross vs walked VWAP),
liq >= $5k, fill at stated size. 7d/60d windows are CONTEXT (WP-P4 shadow),
never gating.
"""
import json, math, datetime, os
from types import SimpleNamespace

from polymarket_alpha_lab.papersim import crypto_model as cm
from polymarket_alpha_lab.papersim import gates as G

RAW = '/home/ubuntu/paper-sim/round44/raw'
OUT = '/home/ubuntu/paper-sim/round44'
NOW = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)

# ---------------- data ----------------
spot_doc = json.load(open(f'{RAW}/spot.json'))
candles = {}
for s in ['ETH', 'BTC', 'SOL', 'XRP']:
    rows = sorted(json.load(open(f'{RAW}/{s.lower()}_candles.json')), key=lambda r: r[0])
    complete = [r for r in rows if (NOW.timestamp() - r[0]) >= 6 * 3600]
    candles[s] = {'rows': rows, 'closes': [r[4] for r in complete]}
m5 = {s: json.load(open(f'{RAW}/{s.lower()}_5m_nov9.json')) for s in ['ETH', 'BTC', 'SOL', 'XRP']}
h1 = {s: json.load(open(f'{RAW}/{s.lower()}_1h_oct24.json')) for s in ['ETH', 'BTC']}

SPOT = {}
for s in ['ETH', 'BTC', 'SOL', 'XRP']:
    last5 = m5[s][-1] if m5[s] else None
    SPOT[s] = last5[4] if last5 else candles[s]['rows'][-1][4]
print('SPOT (freshest 5m close):', {s: round(p, 4) for s, p in SPOT.items()}, flush=True)

VOL = {s: cm.realized_vol_windows(candles[s]['closes']) for s in ['ETH', 'BTC', 'SOL', 'XRP']}
for s in VOL:
    print(s, 'vol', {k: f'{v*100:.3f}%' for k, v in VOL[s].items()}, flush=True)
SIG = {s: VOL[s]['30d'] for s in VOL}  # production signature

# ---------------- horizons ----------------
HZ = {
    'daily_nov9': datetime.datetime(2026, 11, 10, 5, 0, tzinfo=datetime.timezone.utc),
    'weekly_nov9_15': datetime.datetime(2026, 11, 16, 5, 0, tzinfo=datetime.timezone.utc),
    'november': datetime.datetime(2026, 12, 1, 5, 0, tzinfo=datetime.timezone.utc),
    'dec31': datetime.datetime(2027, 1, 1, 5, 0, tzinfo=datetime.timezone.utc),
}
def hours_to(dt):
    return round((dt - NOW).total_seconds() / 3600.0, 2)
print('horizon hours:', {k: hours_to(v) for k, v in HZ.items()}, flush=True)

# ---------------- window touch checks (barrier already breached?) ----------------
WSTART = {
    'daily_nov9': datetime.datetime(2026, 11, 9, 5, 0, tzinfo=datetime.timezone.utc),
    'weekly_nov9_15': datetime.datetime(2026, 11, 9, 5, 0, tzinfo=datetime.timezone.utc),
    'november': datetime.datetime(2026, 11, 1, 5, 0, tzinfo=datetime.timezone.utc),
    # dec31 family creation >= 2026-08-25 (r19 book-of-record lineage; the
    # early-July ETH ~1552 / BTC ~57.8k lows PREDATE every un-resolved dec31
    # market -- all dec31 dip markets quote YES << 1, proving no touch since
    # their creation; a Jul-1 window start would false-positive them).
    'dec31': datetime.datetime(2026, 8, 25, 0, 0, tzinfo=datetime.timezone.utc),
}
# transparency: min low between data start (Jul 1) and the Aug 25 window start,
# so readers can see the pre-creation regime that the dec31 windows exclude.
PRE_WINDOW_LOWS = {}
for s in ['ETH', 'BTC', 'SOL', 'XRP']:
    pre = [r for r in candles[s]['rows'] if r[0] < WSTART['dec31'].timestamp()]
    PRE_WINDOW_LOWS[s] = round(min((r[1] for r in pre), default=None), 4)
def window_extremes(sym, hz):
    t0 = WSTART[hz].timestamp()
    if hz in ('daily_nov9', 'weekly_nov9_15'):
        rows = [r for r in m5[sym] if r[0] >= t0]
    elif hz == 'november':
        rows = [r for r in candles[sym]['rows'] if r[0] >= t0]
    else:
        rows = [r for r in candles[sym]['rows'] if r[0] >= t0]
    if not rows:
        return None, None
    return min(r[1] for r in rows), max(r[2] for r in rows)

def already_touched(sym, hz, barrier):
    lo, hi = window_extremes(sym, hz)
    if lo is None:
        return None
    below = lo <= barrier
    above = hi >= barrier
    if barrier < SPOT[sym]:
        return below   # down-barrier market: touched if window low <= barrier
    return above       # up-barrier market: touched if window high >= barrier

# ---------------- books ----------------
books_doc = json.load(open(f'{RAW}/books44.json'))
BOOKS, MIDX = books_doc['books'], books_doc['market_index']
events = json.load(open(f'{RAW}/events_touch.json'))
EVBY = {}
for ek, e in events.items():
    for m in e.get('markets', []):
        try:
            EVBY[int(m['id'])] = (ek, m)
        except (TypeError, ValueError):
            pass

def levels(mid, side):
    b = BOOKS.get(f'{mid}_{side}')
    if not b:
        return []
    out = [(float(x['price']), float(x['size'])) for x in (b.get('asks') or [])]
    return [lv for lv in out if lv[0] > 0 and lv[1] > 0]

def bids(mid, side):
    b = BOOKS.get(f'{mid}_{side}')
    if not b:
        return []
    out = [(float(x['price']), float(x['size'])) for x in (b.get('bids') or [])]
    return sorted([lv for lv in out if lv[0] > 0 and lv[1] > 0], key=lambda x: -x[0])

def gamma_fields(mid):
    ek, m = EVBY[mid]
    liq = m.get('liquidityNum') or m.get('liquidity') or 0
    px = json.loads(m.get('outcomePrices') or '[]')
    return {'question': m.get('question'), 'event': ek, 'liq': float(liq),
            'gamma_yes': float(px[0]) if px else None,
            'bb': m.get('bestBid'), 'ba': m.get('bestAsk'),
            'end': m.get('endDate'), 'tokens': json.loads(m.get('clobTokenIds') or '[]')}

# ---------------- candidate evaluation (production gates) ----------------
FEE = G.FEE_RATE_CRYPTO

def eval_side(mid, side, pA, pB, *, news_delta, notional=250.0):
    """Evaluate one (market, side) with the production gate stack."""
    gamma = gamma_fields(mid)
    book = levels(mid, 'YES' if side == 'YES' else 'NO')
    if side == 'YES':
        median = min(pA, pB); variants = (pA, pB)
    else:
        median = 1 - max(pA, pB); variants = (1 - pA, 1 - pB)
    news = G.check_news(f'crypto m{mid}', 'scan-time', news_delta=news_delta,
                        sources=('web search: ETH crash trajectory 2026-11-08/09',))
    quote = SimpleNamespace(model_median=median, qs_variants=variants, liq=gamma['liq'])
    try:
        rep = G.evaluate_candidate(quote, book, side='ask', gamma_liquidity=gamma['liq'],
                                   news=news, fee_rate=FEE, notional=notional)
    except Exception as ex:
        return {'error': str(ex)}
    walk300 = G.walk_book(book, side='ask', notional=300.0)
    bidwalk = G.walk_book(bids(mid, 'YES' if side == 'YES' else 'NO'), side='bid', notional=250.0)
    return {
        'market_id': mid, 'side': side, 'question': gamma['question'], 'event': gamma['event'],
        'gamma_yes': gamma['gamma_yes'], 'best_bid': gamma['bb'], 'best_ask': gamma['ba'],
        'liq': gamma['liq'], 'end': gamma['end'],
        'pA': round(pA, 4), 'pB': round(pB, 4),
        'fair_conservative': round(median, 4),
        'walk250': {'vwap': rep.walk.vwap, 'filled': rep.walk.filled,
                    'shares': rep.walk.shares, 'depth_near2c': rep.walk.depth_near2c},
        'walk300': {'vwap': walk300.vwap, 'filled': walk300.filled, 'shares': walk300.shares},
        'bid_walk250_vwap': bidwalk.vwap,
        'exec_edge_gross': rep.exec_edge_gross, 'exec_edge_net': rep.exec_edge,
        'fee_per_share': round(G.fee_cost(rep.entry_price or 0.0, FEE), 4) if rep.entry_price else None,
        'worst_variant_edge': rep.worst_variant_edge, 'variant_spread': rep.variant_spread,
        'haircut': rep.haircut, 'exec_edge_net_haircut': rep.exec_edge_haircut,
        'checks': {k: bool(v) for k, v in rep.checks.items()},
        'failed': list(rep.decision.failed),
        'passed': bool(rep.decision.passed),
        'entry_window_ok': bool(rep.checks.get('entry_window')),
    }

def model_probs(sym, barrier, hz, sigma=None):
    sig = sigma if sigma is not None else SIG[sym]
    tp = cm.touch_probability(SPOT[sym], sig, barrier, hours_to(HZ[hz]), asset=sym)
    return tp.convention_a, tp.convention_b

# ---------------- barrier tables (Task 2) ----------------
ETH_BARRIERS = [1900, 2000, 2100, 2200, 2250, 2300]
BTC_BARRIERS = [60000, 65000, 70000, 75000, 80000]
# market ids per (asset, barrier, horizon): None = model-only row
MKT = {
    ('ETH', 1900, 'daily_nov9'): 6891318, ('ETH', 1900, 'weekly_nov9_15'): 6891272,
    ('ETH', 1900, 'november'): 6507422, ('ETH', 1900, 'dec31'): None,
    ('ETH', 2000, 'daily_nov9'): 6891297, ('ETH', 2000, 'weekly_nov9_15'): 6891265,
    ('ETH', 2000, 'november'): 6507421, ('ETH', 2000, 'dec31'): 3865999,
    ('ETH', 2100, 'daily_nov9'): 6891277, ('ETH', 2100, 'weekly_nov9_15'): None,
    ('ETH', 2100, 'november'): None, ('ETH', 2100, 'dec31'): None,
    ('ETH', 2200, 'daily_nov9'): 6891263, ('ETH', 2200, 'weekly_nov9_15'): 6891261,
    ('ETH', 2200, 'november'): None, ('ETH', 2200, 'dec31'): None,
    ('ETH', 2250, 'daily_nov9'): 6891259, ('ETH', 2250, 'weekly_nov9_15'): None,
    ('ETH', 2250, 'november'): None, ('ETH', 2250, 'dec31'): None,
    ('ETH', 2300, 'daily_nov9'): 6891256, ('ETH', 2300, 'weekly_nov9_15'): 6891258,
    ('ETH', 2300, 'november'): 6721888, ('ETH', 2300, 'dec31'): None,
    ('BTC', 60000, 'daily_nov9'): None, ('BTC', 60000, 'weekly_nov9_15'): 6891218,
    ('BTC', 60000, 'november'): 6507388, ('BTC', 60000, 'dec31'): 3013350,
    ('BTC', 65000, 'daily_nov9'): None, ('BTC', 65000, 'weekly_nov9_15'): None,
    ('BTC', 65000, 'november'): 6507384, ('BTC', 65000, 'dec31'): 3865962,
    ('BTC', 70000, 'daily_nov9'): 6891214, ('BTC', 70000, 'weekly_nov9_15'): 6891205,
    ('BTC', 70000, 'november'): 6507382, ('BTC', 70000, 'dec31'): 3865960,
    ('BTC', 75000, 'daily_nov9'): 6891201, ('BTC', 75000, 'weekly_nov9_15'): None,
    ('BTC', 75000, 'november'): None, ('BTC', 75000, 'dec31'): None,
    ('BTC', 80000, 'daily_nov9'): None, ('BTC', 80000, 'weekly_nov9_15'): 6891187,
    ('BTC', 80000, 'november'): 6721566, ('BTC', 80000, 'dec31'): None,
}
# note: BTC weekly 66k (6891211) and 76k (6891196), BTC dec31 90k (1345531),
# ETH dec31 1750 (3387867) / 1500 (701552), ETH nov 2400 (6721890),
# BTC daily 73k (6891208) / 72k (6891210) / 76k (6891196) fetched as context brackets.

def barrier_rows(sym, barriers):
    rows = []
    for K in barriers:
        for hz in ['daily_nov9', 'weekly_nov9_15', 'november', 'dec31']:
            pA, pB = model_probs(sym, K, hz)
            c7 = model_probs(sym, K, hz, sigma=VOL[sym]['7d'])
            c60 = model_probs(sym, K, hz, sigma=VOL[sym]['60d'])
            mid = MKT.get((sym, K, hz))
            g = gamma_fields(mid) if mid in EVBY else None
            touched = already_touched(sym, hz, K)
            side = 'dip' if K < SPOT[sym] else 'reach'
            row = {
                'asset': sym, 'barrier': K, 'side': side, 'horizon': hz,
                'hours_left': hours_to(HZ[hz]),
                'spot': SPOT[sym],
                'pct_distance': round((SPOT[sym] / K - 1) * 100, 2),
                'sigma_30d': round(SIG[sym], 5),
                'pA': round(pA, 4), 'pB': round(pB, 4),
                'conservative_yes': round(min(pA, pB), 4),
                'conservative_no': round(1 - max(pA, pB), 4),
                'context_7d': {'pA': round(c7[0], 4), 'pB': round(c7[1], 4)},
                'context_60d': {'pA': round(c60[0], 4), 'pB': round(c60[1], 4)},
                'already_touched_in_window': touched,
                'market_id': mid,
                'market_question': g['question'] if g else None,
                'gamma_yes': g['gamma_yes'] if g else None,
                'best_bid': g['bb'] if g else None, 'best_ask': g['ba'] if g else None,
                'liq': g['liq'] if g else None,
            }
            if g and f'{mid}_YES' in BOOKS:
                w = G.walk_book(levels(mid, 'YES'), side='ask', notional=250.0)
                row['yes_ask_walk250_vwap'] = w.vwap
                row['yes_fill_250'] = w.filled
            rows.append(row)
    return rows

eth_rows = barrier_rows('ETH', ETH_BARRIERS)
btc_rows = barrier_rows('BTC', BTC_BARRIERS)
print('barrier rows built:', len(eth_rows), len(btc_rows), flush=True)

# ---------------- Task 1: ETH-2000 add-on (market 3865999) ----------------
pA_d, pB_d = model_probs('ETH', 2000, 'dec31')
fairY = min(pA_d, pB_d)
book_yes = levels(3865999, 'YES')
w250 = G.walk_book(book_yes, side='ask', notional=250.0)
w300 = G.walk_book(book_yes, side='ask', notional=300.0)
w275 = G.walk_book(book_yes, side='ask', notional=275.0)
fee250 = G.fee_cost(w250.vwap, FEE) if w250.vwap else None
net250 = round(fairY - w250.vwap - fee250, 4) if w250.vwap else None
worst250 = round(fairY - w250.vwap, 4) if w250.vwap else None
# NO side of the same market (context)
book_no = levels(3865999, 'NO')
w_no = G.walk_book(book_no, side='ask', notional=250.0)
fairN = 1 - max(pA_d, pB_d)

# breakeven: price p where conservative fair - p - fee(p) = 0
# fair = p + fee*p*(1-p)  =>  fee*p^2 - (1+fee)*p + fair = 0
def breakeven(fair, fee_rate=FEE):
    a, b, c = fee_rate, -(1.0 + fee_rate), fair
    return (-b - math.sqrt(b * b - 4 * a * c)) / (2 * a)

be = breakeven(fairY)
# model prob needed at the walked ask for +5c NET edge:
need5 = round(w250.vwap + G.fee_cost(w250.vwap, FEE) + 0.05, 4) if w250.vwap else None
# at best (cheapest) ask too
top_ask = min((p for p, _ in book_yes), default=None)
need5_top = round(top_ask + G.fee_cost(top_ask, FEE) + 0.05, 4) if top_ask else None

g = gamma_fields(3865999)
yes_eval = eval_side(3865999, 'YES', pA_d, pB_d, news_delta='better')  # crash-continuation news concordant with dip-YES
no_eval = eval_side(3865999, 'NO', pA_d, pB_d, news_delta='worse')     # same news contradicts dip-NO

bid_levels = bids(3865999, 'YES')
def bid_walk_shares(lv, shares):
    cash, rem = 0.0, shares
    for p, s in lv:
        take = min(s, rem)
        cash += take * p; rem -= take
        if rem <= 1e-9:
            break
    return round(cash, 2), rem <= 1e-6
realizable_1207, full_fill = bid_walk_shares(bid_levels, 1207)

held_shares, held_avg, held_cost = 1207, 0.265, 1207 * 0.265
BANKROLL = 13768.0
add_cash = 275.0
add_shares_275 = round(add_cash / (w275.vwap or 0.71), 1)
cur_px = g['gamma_yes'] or 0.705
exposure_now = round(held_shares * cur_px, 2)
exposure_after = round((held_shares + add_shares_275) * cur_px, 2)
btc65_no_shares = round(300.0 / 0.78, 1)
btc65_no_px = 1 - (EVBY[3865962][1].get('bestAsk') or 0.37)  # NO approx = 1 - yes ask
add_on = {
    'market_id': 3865999, 'question': g['question'],
    'market_state': {'gamma_yes': g['gamma_yes'], 'bb': g['bb'], 'ba': g['ba'],
                     'liq': g['liq'], 'end': g['end']},
    'spot_eth': SPOT['ETH'], 'sigma_30d': round(SIG['ETH'], 5),
    'sigma_context': {k: round(v, 5) for k, v in VOL['ETH'].items() if k != '30d'},
    'horizon_hours': hours_to(HZ['dec31']),
    'model': {'pA': round(pA_d, 4), 'pB': round(pB_d, 4),
              'conservative_yes_fair': round(fairY, 4),
              'conservative_no_fair': round(fairN, 4)},
    'walks': {'250': {'vwap': w250.vwap, 'filled': w250.filled, 'shares': w250.shares,
                      'depth_near2c': w250.depth_near2c},
              '275': {'vwap': w275.vwap, 'filled': w275.filled, 'shares': w275.shares},
              '300': {'vwap': w300.vwap, 'filled': w300.filled, 'shares': w300.shares}},
    'edges_at_250': {'gross': worst250, 'fee_per_share': round(fee250, 4) if fee250 else None,
                     'net': net250},
    'breakeven_price_net0': round(be, 4),
    'model_prob_needed_at_walk250_for_plus5c_net': need5,
    'model_prob_needed_at_top_ask_for_plus5c_net': need5_top,
    'top_ask': top_ask,
    'gate_table': {k: bool(v) for k, v in yes_eval['checks'].items()},
    'gate_failed': yes_eval['failed'],
    'no_side_context': {'fair': round(fairN, 4), 'walk250_vwap': w_no.vwap,
                        'edge_net': round(fairN - w_no.vwap - G.fee_cost(w_no.vwap, FEE), 4) if w_no.vwap else None},
    'position_mtm': {'shares': held_shares, 'avg': held_avg, 'cost': round(held_cost, 2),
                     'gamma_yes_now': cur_px,
                     'mark_to_mid': round(held_shares * cur_px, 2),
                     'realizable_bid_walk_1207': realizable_1207,
                     'bid_walk_fully_filled': full_fill,
                     'top_bid': bid_levels[0][0] if bid_levels else None},
    'concentration': {
        'bankroll': BANKROLL,
        'eth2000_exposure_now': exposure_now,
        'eth2000_exposure_after_275_addon': exposure_after,
        'pct_bankroll_now': round(exposure_now / BANKROLL * 100, 2),
        'pct_bankroll_after': round(exposure_after / BANKROLL * 100, 2),
        'cost_at_risk_after': round(held_cost + add_cash, 2),
        'pct_bankroll_cost_at_risk_after': round((held_cost + add_cash) / BANKROLL * 100, 2),
        'btc65_no_shares': btc65_no_shares,
        'btc65_no_exposure_approx': round(btc65_no_shares * btc65_no_px, 2),
        'largest_position_before': 'ETH-2000 YES already largest by exposure',
        'largest_after': 'ETH-2000 YES extends lead',
    },
}
print('ADD-ON fair_yes', round(fairY, 4), 'walk250', w250.vwap, 'net', net250,
      'breakeven', round(be, 4), 'need5', need5, flush=True)

# ---------------- candidate pool (all barrier markets with books) ----------------
NEWS_DELTA = {  # one focused search (ETH crash trajectory) applied by direction
    ('dip', 'YES'): 'better',   # liquidations/ETF outflows support further downside
    ('dip', 'NO'): 'worse',
    ('reach', 'YES'): 'worse',
    ('reach', 'NO'): 'better',
}
CAND_IDS = sorted({mid for mid in (set(MKT.values()) | {6891211, 6891196, 1345531, 3387867, 701552,
                                                      6721890, 6891208, 6891210,
                                                      6507439, 6507440, 6507437, 3866002, 2818594, 701578,
                                                      6507457, 6753574, 6507455, 6507458, 3866621, 701604})
                   if mid})
cands = []
for mid in CAND_IDS:
    if mid not in EVBY or f'{mid}_YES' not in BOOKS:
        continue
    q = (EVBY[mid][1].get('question') or '')
    ek = EVBY[mid][0]
    import re
    mnum = re.search(r'\$([\d,\.]+)', q)
    if not mnum:
        continue
    K = float(mnum.group(1).replace(',', ''))
    sym = 'ETH' if 'Ethereum' in q else 'BTC' if 'Bitcoin' in q else 'SOL' if 'Solana' in q else 'XRP' if 'XRP' in q else None
    if sym is None:
        continue
    EK2HZ = {
        'ETH_daily_touch_nov9': 'daily_nov9', 'BTC_daily_touch_nov9': 'daily_nov9',
        'XRP_daily_touch_nov9': 'daily_nov9',
        'ETH_weekly_touch_nov9_15': 'weekly_nov9_15', 'BTC_weekly_touch_nov9_15': 'weekly_nov9_15',
        'SOL_weekly_touch_nov9_15': 'weekly_nov9_15', 'XRP_weekly_touch_nov9_15': 'weekly_nov9_15',
        'ETH_in_november': 'november', 'BTC_in_november': 'november',
        'SOL_in_november': 'november', 'XRP_in_november': 'november',
        'ETH_in_2026': 'dec31', 'BTC_in_2026': 'dec31', 'SOL_in_2026': 'dec31', 'XRP_in_2026': 'dec31',
    }
    hz = EK2HZ.get(ek)
    if hz is None:
        continue
    side_kind = 'dip' if 'dip to' in q else 'reach' if ('reach' in q or 'hit' in q) else None
    if side_kind is None:
        continue
    touched = already_touched(sym, hz, K)
    pA, pB = model_probs(sym, K, hz)
    for side in ('YES', 'NO'):
        ev = eval_side(mid, side, pA, pB, news_delta=NEWS_DELTA[(side_kind, side)])
        ev.update({'asset': sym, 'barrier': K, 'kind': side_kind, 'horizon': hz,
                   'already_touched_in_window': touched,
                   'unvalidated_asset': sym in ('SOL', 'XRP')})
        cands.append(ev)

passing = [c for c in cands if c.get('passed')]
near = [c for c in cands if not c.get('passed') and c.get('exec_edge_net') is not None
        and c['exec_edge_net'] >= 0.02]
print('candidates evaluated:', len(cands), 'passing:', len(passing), flush=True)

# context sensitivity for passing candidates: same walk, 7d/60d vol fair (NOT gating)
for c in passing:
    pA7, pB7 = model_probs(c['asset'], c['barrier'], c['horizon'], sigma=VOL[c['asset']]['7d'])
    pA60, pB60 = model_probs(c['asset'], c['barrier'], c['horizon'], sigma=VOL[c['asset']]['60d'])
    v = c['walk250']['vwap']
    if c['side'] == 'YES':
        f7, f60 = min(pA7, pB7), min(pA60, pB60)
    else:
        f7, f60 = 1 - max(pA7, pB7), 1 - max(pA60, pB60)
    c['context_7d_vol_edge_net'] = round(f7 - v - G.fee_cost(v, FEE), 4)
    c['context_60d_vol_edge_net'] = round(f60 - v - G.fee_cost(v, FEE), 4)
    c['context_7d_vol_fair'] = round(f7, 4)
    c['context_60d_vol_fair'] = round(f60, 4)

# ---------------- Task 3 output: SOL/XRP flagged ----------------
solxrp = [c for c in cands if c.get('asset') in ('SOL', 'XRP')]

# ---------------- Task 4: coherence ----------------
def mid_px(row):
    if row.get('best_bid') is not None and row.get('best_ask') is not None:
        return (row['best_bid'] + row['best_ask']) / 2
    return row.get('gamma_yes')

coherence = {'model_monotonicity': [], 'market_yes_plus_no': [], 'cross_horizon': []}
# 1) touch monotonicity in barrier distance (model, 30d sigma)
for sym, barriers in [('ETH', ETH_BARRIERS), ('BTC', BTC_BARRIERS)]:
    for hz in ['daily_nov9', 'weekly_nov9_15', 'november', 'dec31']:
        below = [K for K in barriers if K < SPOT[sym]]
        above = [K for K in barriers if K > SPOT[sym]]
        for lst, direction in [(sorted(below, reverse=True), 'dip'), (sorted(above), 'reach')]:
            probs = [model_probs(sym, K, hz)[0] for K in lst]
            ok = all(probs[i] >= probs[i + 1] - 1e-9 for i in range(len(probs) - 1))
            coherence['model_monotonicity'].append(
                {'asset': sym, 'horizon': hz, 'direction': direction,
                 'barriers': lst, 'pA_seq': [round(p, 4) for p in probs], 'monotone_decreasing': ok})
# 2) YES+NO ~ 1 - spread from books
for mid in CAND_IDS:
    if f'{mid}_YES' not in BOOKS or f'{mid}_NO' not in BOOKS:
        continue
    ya = levels(mid, 'YES'); na = levels(mid, 'NO')
    yb = bids(mid, 'YES'); nb = bids(mid, 'NO')
    if not ya or not na:
        continue
    yes_ask, no_ask = ya[0][0], na[0][0]
    yes_bid, no_bid = (yb[0][0] if yb else None), (nb[0][0] if nb else None)
    row = {'market_id': mid, 'question': EVBY[mid][1].get('question'),
           'yes_best_ask': yes_ask, 'no_best_ask': no_ask,
           'yes_ask_plus_no_ask': round(yes_ask + no_ask, 4),
           'overround_vs_1': round(yes_ask + no_ask - 1, 4)}
    if yes_bid is not None and no_bid is not None:
        row['yes_bid_plus_no_bid'] = round(yes_bid + no_bid, 4)
        row['mid_sum'] = round((yes_ask + yes_bid + no_ask + no_bid) / 2 / 2, 4)
    coherence['market_yes_plus_no'].append(row)
# 3) cross-horizon monotonicity (same barrier, longer horizon => higher touch prob)
for sym, barriers in [('ETH', ETH_BARRIERS), ('BTC', BTC_BARRIERS)]:
    for K in barriers:
        seq = [min(model_probs(sym, K, hz)) for hz in ['daily_nov9', 'weekly_nov9_15', 'november', 'dec31']]
        ok = all(seq[i] <= seq[i + 1] + 1e-9 for i in range(len(seq) - 1))
        coherence['cross_horizon'].append(
            {'asset': sym, 'barrier': K, 'conservative_yes_seq':
             {'daily': round(seq[0], 4), 'weekly': round(seq[1], 4),
              'november': round(seq[2], 4), 'dec31': round(seq[3], 4)},
             'monotone_increasing': ok})
# market-side cross-horizon (ETH 2000 ladder)
mkt_ladder = []
for hz in ['daily_nov9', 'weekly_nov9_15', 'november', 'dec31']:
    mid = MKT.get(('ETH', 2000, hz))
    if mid and mid in EVBY:
        mkt_ladder.append({'horizon': hz, 'gamma_yes': gamma_fields(mid)['gamma_yes']})
coherence['market_eth2000_ladder'] = mkt_ladder
mkt_ladder_btc = []
for hz in ['daily_nov9', 'weekly_nov9_15', 'november', 'dec31']:
    mid = MKT.get(('BTC', 70000, hz))
    if mid and mid in EVBY:
        mkt_ladder_btc.append({'horizon': hz, 'gamma_yes': gamma_fields(mid)['gamma_yes']})
coherence['market_btc70k_ladder'] = mkt_ladder_btc

# ---------------- scan doc ----------------
scan = {
    'generated_at': NOW.isoformat(),
    'mode': 'PAPER ONLY - scan/report; no orders, no DB writes',
    'round': '44B',
    'model': 'polymarket_alpha_lab.papersim.crypto_model (r19 lineage; conservative YES=min(pA,pB), NO=1-max(pA,pB))',
    'vol_signature': '30d 6h-bar realized RMS (production); 7d/60d shown as CONTEXT ONLY (WP-P4 shadow, not gating)',
    'spot': {s: round(p, 4) for s, p in SPOT.items()},
    'realized_vol_daily': {s: {k: round(v, 5) for k, v in VOL[s].items()} for s in VOL},
    'horizons_utc': {k: v.isoformat() for k, v in HZ.items()},
    'horizon_hours': {k: hours_to(v) for k, v in HZ.items()},
    'news_falsifier': {
        'search': 'ETH crash trajectory Nov 6-9 2026 (liquidations / ETF flows)',
        'findings': [
            'Nov 8: long-liquidation cascade pushed ETH to ~$2,120; $343M ETH liquidated in 24h (largest single $48M)',
            '6th consecutive week of spot ETH ETF outflows; $571M out over six sessions through Nov 6 ($99.9M on Nov 6 alone)',
            'Analyst downside targets after $2,200 break: $2,180 then $2,000; whale longs forced near $2,180 (cleared Nov 8)',
        ],
        'falsifier_direction': 'cascade/flow dynamics put fat left tails NEAR TERM: lognormal touch probs likely UNDERSTATE near-barrier dip-YES and OVERSTATE dip-NO fair values; dip-NO edges are the dangerous family, dip-YES edges are if anything conservative',
        'sources': ['cryptoticker.io/en/ethereum-price-long-liquidations-november-8-2026',
                    '247wallst.com/investing/cryptocurrency/2026/10/16/ethereum-led-nearly-1-billion-in-crypto-liquidations-its-traders-never-cut-back-before-the-drop'],
    },
    'barrier_tables': {'ETH': eth_rows, 'BTC': btc_rows},
    'add_on_eth2000': add_on,
    'coherence': coherence,
    'sol_xrp_candidates': [
        {k: v for k, v in c.items() if k != 'checks'} | {'checks': c.get('checks', {})}
        for c in solxrp if not c.get('error')
    ],
    'caveats': [
        'SOL/XRP modeled model-generically from Binance 6h realized vol; outside the validated ETH/BTC signature (unvalidated-asset); any passing entry capped at $150',
        'Gamma ids=/condition_ids= list params broken (0 rows); single condition_id and /markets/{id} used instead',
        'dec31 touch windows start at market creation (>= 2026-08-25, r19 lineage); the early-July 2026 lows (ETH ~1552, BTC ~57.8k, pre-window lows: '
        + json.dumps(PRE_WINDOW_LOWS)
        + ') predate every un-resolved dec31 market (all quote YES << 1, proving no touch since creation)',
        'in-November markets added as a third horizon where liquid (ends Dec 1 05:00 UTC)',
        'ETH daily dip-2100 (6891277) and BTC daily dip-74k (6891204): barrier already touched inside the daily window; excluded from model candidacy',
    ],
}
json.dump(scan, open(f'{OUT}/crypto_scan.json', 'w'), indent=1)

cands_doc = {
    'generated_at': NOW.isoformat(),
    'mode': 'PAPER ONLY - candidates for paper-sim ledger; no orders placed',
    'gates_frozen': {'net_edge_after_crypto_fee_0.07': '>= +5c', 'worst_variant_gross': '>= +4c',
                     'liquidity': '>= $5k', 'fill': '$250 walk completes',
                     'extras_reported': ['variant_spread<=6c', 'entry_window 0.10-0.92',
                                          '50-50 haircut on net edge', 'news_concordance']},
    'news_basis': 'single focused search (ETH crash trajectory): dip-YES concordant, dip-NO discordant, reach-YES discordant, reach-NO concordant',
    'passing': [c for c in passing if not c.get('error')],
    'near_misses': sorted(near, key=lambda c: -c['exec_edge_net'])[:12],
    'all_evaluated': cands,
    'held_positions': {
        'ETH-2000-dip YES': {'market_id': 3865999, 'shares': 1207, 'avg': 0.265,
                             'cost': 320.0, 'gamma_yes_now': cur_px,
                             'realizable_bid_walk': realizable_1207},
        'BTC-65k-dip NO': {'market_id': 3865962, 'shares': 384.6, 'avg': 0.78,
                           'cost': 300.0, 'gamma_yes_now': gamma_fields(3865962)['gamma_yes'],
                           'no_mark_approx': round(btc65_no_px, 3)},
    },
}
json.dump(cands_doc, open(f'{OUT}/crypto_candidates.json', 'w'), indent=1)
print('WROTE', f'{OUT}/crypto_scan.json', f'{OUT}/crypto_candidates.json', flush=True)

# ---------------- console summary ----------------
print('\n=== ADD-ON SUMMARY ===')
print('fairY', round(fairY, 4), '| walk250 vwap', w250.vwap, '| net', net250,
      '| breakeven', round(be, 4), '| need@top', need5_top)
print('\n=== PASSING CANDIDATES ===')
for c in passing:
    print(f"m{c['market_id']} {c['side']:3s} {c['question'][:55]:55s} net {c['exec_edge_net']:+.4f} "
          f"worst {c['worst_variant_edge']:+.4f} liq {c['liq']:.0f} walk {c['walk250']['vwap']}")
print('\n=== NEAR MISSES (net>=+2c, not passing) ===')
for c in sorted(near, key=lambda x: -x['exec_edge_net'])[:12]:
    print(f"m{c['market_id']} {c['side']:3s} {c['question'][:55]:55s} net {c['exec_edge_net']:+.4f} "
          f"failed {c['failed']}")
print('DONE model44', flush=True)
