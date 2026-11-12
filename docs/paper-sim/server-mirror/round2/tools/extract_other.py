import json

RAW = '/home/ubuntu/paper-sim/round2/raw/events_open_other.json'
events = json.load(open(RAW))
by_slug = {}
for ev in events:
    s = ev.get('slug')
    if s and s not in by_slug:
        by_slug[s] = ev

INTEREST = [
  # NFL wk5 finale + wk6 slate
  'nfl-buf-la-2026-10-13','nfl-sea-den-2026-10-16','nfl-dal-gb-2026-10-19','nfl-car-phi-2026-10-18',
  'nfl-pit-tb-2026-10-18','nfl-hou-jax-2026-10-18','nfl-lac-kc-2026-10-18','nfl-was-sf-2026-10-20',
  'nfl-bal-cle-2026-10-18','nfl-buf-lv-2026-10-18','nfl-chi-atl-2026-10-18','nfl-ten-ind-2026-10-18',
  'nfl-nyj-ne-2026-10-18','nfl-no-nyg-2026-10-18','nfl-ari-la-2026-10-18',
  # MLB games + series
  'mlb-lad-mil-2026-10-12','mlb-cle-tb-2026-10-12',
  # NHL
  'nhl-fla-buf-2026-10-12','nhl-las-min-2026-10-12','nhl-ott-nj-2026-10-12','nhl-bos-sj-2026-10-13',
  'nhl-nj-det-2026-10-13','nhl-tb-nyr-2026-10-13','nhl-van-nyi-2026-10-13',
  # UFC
  'ufc-wilren-luifra-2026-10-13','ufc-aliper-smisun-2026-10-13','ufc-eri3-jas3-2026-10-17',
  'ufc-nat2-man17-2026-10-17','ufc-ilibul-erivis-2026-09-29',
]

out = {}
for slug in INTEREST:
    ev = by_slug.get(slug)
    if not ev:
        print('MISSING', slug); continue
    mk = []
    for m in ev.get('markets', []):
        if m.get('closed'): continue
        outcomes = m.get('outcomes'); prices = m.get('outcomePrices')
        try: outcomes = json.loads(outcomes) if isinstance(outcomes, str) else outcomes
        except Exception: pass
        try: prices = json.loads(prices) if isinstance(prices, str) else prices
        except Exception: pass
        mk.append({
            'id': m.get('id'), 'q': m.get('question'), 'group': m.get('groupItemTitle'),
            'outcomes': outcomes, 'prices': prices,
            'bestBid': m.get('bestBid'), 'bestAsk': m.get('bestAsk'),
            'liq': m.get('liquidityNum') or m.get('liquidity'), 'vol24': m.get('volume24hr'),
            'spread': m.get('spread'), 'gameStartTime': m.get('gameStartTime'),
            'tokens': m.get('clobTokenIds'),
        })
    out[slug] = {'id': ev.get('id'), 'title': ev.get('title'), 'endDate': ev.get('endDate'),
                 'markets': mk}
    print('OK', slug, 'open_markets=', len(mk))

json.dump(out, open('/home/ubuntu/paper-sim/round2/raw/other_details.json','w'), indent=1)

# also: find MLB series/pennant/WS futures still open
print()
print('MLB non-game events still open:')
for ev in events:
    s = ev.get('slug') or ''
    tg = [t.get('slug') for t in (ev.get('tags') or [])]
    if ('mlb' in tg or 'baseball' in tg) and not any(x in s for x in ['-2026-10-','-2026-11-']):
        liq = 0.0
        for m in ev.get('markets', []):
            try: liq += float(m.get('liquidityNum') or 0)
            except Exception: pass
        if liq > 50000:
            print('  %-52s liq=%s nmk=%d' % (s[:52], format(liq, ',.0f'), len(ev.get('markets', []))))
