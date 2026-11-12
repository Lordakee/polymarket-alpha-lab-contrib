"""ROUND-44B fetch part 3: CLOB books for barrier-table + candidate markets.

PAPER ONLY, no DB writes. Pulls both tokens' books for each selected market
from the Gamma event snapshots already saved by fetch44.py.
"""
import json, urllib.request, time, datetime

RAW = '/home/ubuntu/paper-sim/round44/raw'

def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as ex:
            if i == tries - 1:
                raise
            time.sleep(2.0)

NOW = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
print('now', NOW.isoformat(), flush=True)

events = json.load(open(f'{RAW}/events_touch.json'))

# market id -> (event key) selection for the barrier tables + candidate pool
WANT = {
    # ETH primary + daily (Nov 9, ends Nov 10 05:00Z)
    6891297: 'ETH_daily_touch_nov9',    # dip 2000 daily
    6891287: 'ETH_daily_touch_nov9',    # dip 2050 daily
    6891318: 'ETH_daily_touch_nov9',    # dip 1900 daily
    6891263: 'ETH_daily_touch_nov9',    # reach 2200 daily
    6891259: 'ETH_daily_touch_nov9',    # reach 2250 daily
    6891256: 'ETH_daily_touch_nov9',    # reach 2300 daily
    # ETH weekly (Nov 9-15, ends Nov 16 05:00Z)
    6891265: 'ETH_weekly_touch_nov9_15',  # dip 2000 weekly
    6891272: 'ETH_weekly_touch_nov9_15',  # dip 1900 weekly
    6891261: 'ETH_weekly_touch_nov9_15',  # reach 2200 weekly
    6891258: 'ETH_weekly_touch_nov9_15',  # reach 2300 weekly
    # ETH in November (ends Dec 1 05:00Z)
    6507421: 'ETH_in_november',         # dip 2000 nov
    6507422: 'ETH_in_november',         # dip 1900 nov
    6721888: 'ETH_in_november',         # reach 2300 nov
    6721890: 'ETH_in_november',         # reach 2400 nov
    # ETH in 2026 / Dec-31 (ends Jan 1 05:00Z)
    3865999: 'ETH_in_2026',             # dip 2000 dec31 (PRIMARY held)
    3387867: 'ETH_in_2026',             # dip 1750 dec31
    701552: 'ETH_in_2026',              # dip 1500 dec31
    # BTC in 2026 / Dec-31
    3013350: 'BTC_in_2026',             # dip 60k dec31
    3865962: 'BTC_in_2026',             # dip 65k dec31 (held NO)
    3865960: 'BTC_in_2026',             # dip 70k dec31
    1345531: 'BTC_in_2026',             # reach 90k dec31
    # BTC in November
    6507388: 'BTC_in_november',         # dip 60k nov
    6507384: 'BTC_in_november',         # dip 65k nov
    6507382: 'BTC_in_november',         # dip 70k nov
    6721566: 'BTC_in_november',         # reach 80k nov
    # BTC weekly
    6891218: 'BTC_weekly_touch_nov9_15',  # dip 60k weekly
    6891205: 'BTC_weekly_touch_nov9_15',  # dip 70k weekly
    6891187: 'BTC_weekly_touch_nov9_15',  # reach 80k weekly
    6891211: 'BTC_weekly_touch_nov9_15',  # dip 66k weekly
    # BTC daily
    6891208: 'BTC_daily_touch_nov9',    # dip 73k daily
    6891210: 'BTC_daily_touch_nov9',    # dip 72k daily
    6891214: 'BTC_daily_touch_nov9',    # dip 70k daily
    6891201: 'BTC_daily_touch_nov9',    # reach 75k daily
    6891196: 'BTC_daily_touch_nov9',    # reach 76k daily
    # SOL in November / in 2026
    6507439: 'SOL_in_november',         # dip 80 nov
    6507440: 'SOL_in_november',         # dip 70 nov
    6507437: 'SOL_in_november',         # reach 100 nov
    3866002: 'SOL_in_2026',             # dip 80 dec31
    2818594: 'SOL_in_2026',             # dip 70 dec31
    701578: 'SOL_in_2026',              # dip 60 dec31
    # XRP in November / in 2026
    6507457: 'XRP_in_november',         # dip 1.00 nov
    6753574: 'XRP_in_november',         # reach 1.20 nov
    6507455: 'XRP_in_november',         # reach 1.40 nov
    6507458: 'XRP_in_november',         # dip 0.80 nov
    3866621: 'XRP_in_2026',             # dip 1.00 dec31
    701604: 'XRP_in_2026',              # dip 0.80 dec31
}

by_id = {}
for ek, e in events.items():
    for m in e.get('markets', []):
        try:
            by_id[int(m.get('id'))] = (ek, m)
        except (TypeError, ValueError):
            pass

books, snaps = {}, {}
for mid, ek in WANT.items():
    if mid not in by_id:
        print('MISSING market', mid, 'in', ek, flush=True)
        continue
    _, m = by_id[mid]
    toks = json.loads(m.get('clobTokenIds') or '[]')
    snaps[str(mid)] = {'event': ek, 'question': m.get('question'), 'tokens': toks}
    for ti, t in enumerate(toks):
        key = f'{mid}_{"YES" if ti == 0 else "NO"}'
        for attempt in range(3):
            try:
                b = get(f'https://clob.polymarket.com/book?token_id={t}')
                books[key] = b
                break
            except Exception as ex:
                print('book', key, 'ERR', ex, flush=True)
                time.sleep(1.5)
        time.sleep(0.3)
    print('done', mid, m.get('question', '')[:50], flush=True)

json.dump({'fetched_at': NOW.isoformat(), 'books': books, 'market_index': snaps},
          open(f'{RAW}/books44.json', 'w'))
print('books fetched:', len(books), flush=True)
print('DONE fetch44c', flush=True)
