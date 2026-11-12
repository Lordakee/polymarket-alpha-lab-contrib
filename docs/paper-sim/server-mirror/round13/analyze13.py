import json, math, datetime

RAW = '/home/ubuntu/paper-sim/round13/raw'
OUT = '/home/ubuntu/paper-sim/round13'
NOW = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)

def N(x): return 0.5 * math.erfc(-x / math.sqrt(2.0))

scan = json.load(open(f'{RAW}/crypto_scan.json'))
SPOT = scan['spot']
VOL = scan['realized_vol_daily']

# ---------- order-book helpers ----------
pb = json.load(open(f'{RAW}/position_books.json'))
BOOKS = pb['books']

def book_summary(key, size=None):
    b = BOOKS[key]
    bids = sorted(b.get('bids', []), key=lambda x: -float(x['price']))   # best first
    asks = sorted(b.get('asks', []), key=lambda x: float(x['price']))
    bb = float(bids[0]['price']) if bids else None
    ba = float(asks[0]['price']) if asks else None
    mid = (bb + ba) / 2 if (bb is not None and ba is not None) else None
    # depth walk: sell `size` shares into bids
    walk = None
    if size:
        rem = size
        cash = 0.0
        filled = 0.0
        for lvl in bids:
            p = float(lvl['price'])
            q = float(lvl['size'])
            take = min(rem, q)
            cash += take * p
            filled += take
            rem -= take
            if rem <= 0: break
        walk = {'realizable_cash': round(cash, 2), 'filled': round(filled, 2),
                'avg_px': round(cash / filled, 4) if filled > 0 else None,
                'levels_needed': None}
    return {'best_bid': bb, 'best_ask': ba, 'mid': mid, 'bid_depth_walk': walk,
            'bid_top_size': float(bids[0]['size']) if bids else 0,
            'ask_top_size': float(asks[0]['size']) if asks else 0}

# ---------- positions ----------
POSITIONS = [
    dict(name='ETH-dip-2250 YES', mkt='Will Ethereum dip to $2,250 by December 31, 2026?',
         side_key='ETH2250_YES', mirror_key='ETH2250_NO', shares=2555.0, avg=0.489, cost=1250.0,
         gamma_id='3866000', entry_note='entered via rounds 8-12 avg'),
    dict(name='ETH-dip-2000 YES', mkt='Will Ethereum dip to $2,000 by December 31, 2026?',
         side_key='ETH2000_YES', mirror_key='ETH2000_NO', shares=1208.0, avg=0.265, cost=320.0,
         gamma_id='3865999', entry_note='round ~10 entry'),
    dict(name='BTC-dip-65k NO', mkt='Will Bitcoin dip to $65,000 by December 31, 2026?',
         side_key='BTC65K_NO', mirror_key='BTC65K_YES', shares=384.6, avg=0.78, cost=300.0,
         gamma_id='3865962', entry_note='entered ~13h ago (round 12)'),
]

DEC31 = datetime.datetime(2026, 12, 31, 23, 59, tzinfo=datetime.timezone.utc)
T_DEC31 = (DEC31 - NOW).total_seconds() / 86400.0

def p_above(S, K, mu, sig, T):
    sigT = sig * math.sqrt(T)
    if sigT <= 0: return 1.0 if S >= K else 0.0
    return N((math.log(S / K) + mu * T) / sigT)

def p_touch_dn(x, mu, sig, T):
    # P(min_{t<=T} X_t <= -x), X_t = mu t + sig W_t, start 0, x>0
    sigT = sig * math.sqrt(T)
    if sigT <= 0: return 0.0
    return N((-x - mu * T) / sigT) + math.exp(-2.0 * mu * x / (sig * sig)) * N((-x + mu * T) / sigT)

mtm = []
for p in POSITIONS:
    bs = book_summary(p['side_key'], size=p['shares'])
    mid = bs['mid']
    mtm_bid = bs['bid_depth_walk']['avg_px'] if bs['bid_depth_walk'] else bs['best_bid']
    unreal_bid = (mtm_bid - p['avg']) * p['shares']
    unreal_mid = (mid - p['avg']) * p['shares']
    realizable = bs['bid_depth_walk']['realizable_cash'] if bs['bid_depth_walk'] else None
    mtm.append(dict(**p, book=bs, mtm_px=mtm_bid, unrealized_bid=round(unreal_bid, 2),
                    unrealized_mid=round(unreal_mid, 2),
                    unrealized_bid_pct=round(unreal_bid / p['cost'] * 100, 1),
                    unrealized_mid_pct=round(unreal_mid / p['cost'] * 100, 1),
                    realizable_cash=realizable,
                    mark_to_mid=round(mid * p['shares'], 2)))
    print('%-18s bid=%.3f mid=%.4f ask=%.3f  avg=%.3f  unreal_bid=$%.2f (%.1f%%)  sell_all=$%.2f' % (
        p['name'], bs['best_bid'], mid, bs['best_ask'], p['avg'], unreal_bid,
        unreal_bid / p['cost'] * 100, realizable))

# ---------- ETH-2250 exit analysis ----------
S = SPOT['ETH']
K = 2250.0
x = math.log(S / K)
CREATED_2250 = datetime.datetime(2026, 8, 25, tzinfo=datetime.timezone.utc)
elapsed = (NOW - CREATED_2250).total_seconds()
total_window = (DEC31 - CREATED_2250).total_seconds()
frac_elapsed = elapsed / total_window

sigA = VOL['ETH']
fair_grid = {}
for w in ['7d', '30d', '60d', '87d']:
    sig = sigA[w]
    pA = p_touch_dn(x, 0.0, sig, T_DEC31)
    pB = p_touch_dn(x, -sig * sig / 2.0, sig, T_DEC31)
    fair_grid[w] = {'sig_daily': round(sig, 5), 'pA_zero_drift': round(pA, 4), 'pB_median_flat': round(pB, 4)}
# elevated-vol stress: +25% vol (ETF outflow regime)
for w, bump in [('30d+15%', 1.15), ('30d+25%', 1.25), ('7d+25%', 1.25)]:
    base = w.split('+')[0]
    sig = sigA[base] * bump
    pA = p_touch_dn(x, 0.0, sig, T_DEC31)
    pB = p_touch_dn(x, -sig * sig / 2.0, sig, T_DEC31)
    fair_grid[w] = {'sig_daily': round(sig, 5), 'pA_zero_drift': round(pA, 4), 'pB_median_flat': round(pB, 4)}

# breakeven vol: sigma such that zero-drift fair = current YES bid (p increasing in sigma)
bid2250 = book_summary('ETH2250_YES')['best_bid']
lo, hi = 0.005, 0.10
for _ in range(80):
    mid_ = (lo + hi) / 2
    if p_touch_dn(x, 0.0, mid_, T_DEC31) > bid2250: hi = mid_
    else: lo = mid_
be_vol = (lo + hi) / 2
# breakeven upward drift (mu>0 reduces touch prob): mu such that pA = bid, at 30d vol
sig30 = sigA['30d']
lo, hi = -0.10, 0.50
for _ in range(80):
    mid_ = (lo + hi) / 2
    if p_touch_dn(x, mid_, sig30, T_DEC31) > bid2250: lo = mid_
    else: hi = mid_
be_mu = (lo + hi) / 2  # per-day log drift

fair30A = fair_grid['30d']['pA_zero_drift']
fair30B = fair_grid['30d']['pB_median_flat']
edge_hold_A = fair30A - bid2250
edge_hold_B = fair30B - bid2250

# scale-out math
sh = 2555.0
sell25 = round(sh * 0.25)
bs2250 = book_summary('ETH2250_YES', size=sh)
px_all = bs2250['bid_depth_walk']['avg_px']
cash_all = bs2250['bid_depth_walk']['realizable_cash']
bs25 = book_summary('ETH2250_YES', size=sell25)
px25 = bs25['bid_depth_walk']['avg_px']
cash25 = bs25['bid_depth_walk']['realizable_cash']

exit_analysis = {
    'asof': NOW.isoformat(), 'spot_ETH': S, 'barrier': K,
    'log_distance': round(x, 4), 'pct_distance': round((S / K - 1) * 100, 2),
    'T_days_to_dec31': round(T_DEC31, 2),
    'window_created': '2026-08-25', 'frac_window_elapsed': round(frac_elapsed, 4),
    'min_low_since_created': scan['barrier_checks']['eth2250']['min_low_since'],
    'closest_approach_pct_above_barrier': round((scan['barrier_checks']['eth2250']['min_low_since'] / K - 1) * 100, 2),
    'yes_bid': bid2250,
    'fair_grid': fair_grid,
    'breakeven_daily_vol_for_bid': round(be_vol, 5),
    'current_vol_30d': round(sig30, 5),
    'breakeven_upward_log_drift_at_30d_vol': round(be_mu, 5),
    'breakeven_drift_annualized_pct': round(be_mu * 365 * 100, 1),
    'edge_vs_bid_A': round(edge_hold_A, 4), 'edge_vs_bid_B': round(edge_hold_B, 4),
    'hold_ev_premium_vs_sell': {
        'per_share_A': round(edge_hold_A, 4), 'per_share_B': round(edge_hold_B, 4),
        'position_A': round(edge_hold_A * sh, 2), 'position_B': round(edge_hold_B * sh, 2)},
    'scale_out_25pct': {'shares': sell25, 'avg_px': px25, 'cash': cash25,
                        'remaining_shares': sh - sell25},
    'sell_all': {'shares': sh, 'avg_px': px_all, 'cash': cash_all},
}

print('\nETH-2250 exit analysis')
print(json.dumps(exit_analysis, indent=1))

# ---------- weekend touch risk ----------
horizons = {}
for label, days in [('12h', 0.5), ('24h', 1.0), ('to_Sun_2359', 2.96), ('to_Mon_0600', 3.2), ('72h', 3.0), ('7d', 7.0)]:
    row = {}
    for w in ['7d', '30d']:
        sig = sigA[w]
        row[w] = {'A': round(p_touch_dn(x, 0.0, sig, days), 4),
                  'B': round(p_touch_dn(x, -sig * sig / 2.0, sig, days), 4)}
    horizons[label] = {'hours': days * 24, 'probs': row}
# BTC 65k weekend risk too
xb = math.log(SPOT['BTC'] / 65000.0)
horizons_btc = {}
for label, days in [('to_Sun_2359', 2.96), ('72h', 3.0)]:
    sig = VOL['BTC']['30d']
    horizons_btc[label] = {'A': round(p_touch_dn(xb, 0.0, sig, days), 4),
                           'B': round(p_touch_dn(xb, -sig * sig / 2.0, sig, days), 4)}
weekend = {'note': 'Oct 23 2026 is a Friday; weekend = Sat Oct 24 00:00 - Sun Oct 25 23:59 UTC',
           'eth_touch_2250': horizons, 'btc_touch_65000': horizons_btc,
           'eth_sigma_1d_2250': round(x / sigA['30d'], 2),
           'eth_sigma_1d_2250_7dvol': round(x / sigA['7d'], 2)}
print('\nWeekend risk')
print(json.dumps(weekend, indent=1))

json.dump({'generated_at': NOW.isoformat(), 'positions_mtm': mtm, 'exit_analysis_eth2250': exit_analysis,
           'weekend_risk': weekend}, open(f'{OUT}/crypto_recommendations.json', 'w'), indent=1)
print('\nwrote', f'{OUT}/crypto_recommendations.json')
