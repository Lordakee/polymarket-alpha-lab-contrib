import json, datetime

D = json.load(open('/home/ubuntu/paper-sim/round10/raw/discover10.json'))
print('events in window:', len(D))

def classify(e):
    sl = e['slug']
    t = (e['title'] or '').lower()
    tags = e.get('tags') or []
    if sl.startswith('uel-') or 'europa-league' in tags: return 'UEL'
    if sl.startswith('uecl-') or sl.startswith('col-') or 'europa-conference-league' in tags: return 'UECL'
    if sl.startswith('epl-'): return 'EPL'
    if sl.startswith('ucl-') or 'champions-league' in tags: return 'UCL'
    if sl.startswith('fl1-'): return 'Ligue1'
    if sl.startswith('ser-'): return 'SerieA'
    if sl.startswith('lal-') or sl.startswith('lla-'): return 'LaLiga'
    if sl.startswith('bun-'): return 'Bundesliga'
    if sl.startswith('ned-'): return 'Eredivisie'
    if sl.startswith('por-'): return 'PrimeiraLiga'
    if sl.startswith('sco-'): return 'Scotland'
    if sl.startswith('cha-') or 'championship' in tags: return 'Championship'
    if 'fa-cup' in tags or sl.startswith('fac-'): return 'FaCup'
    if 'carabao' in tags or 'efl-cup' in tags: return 'Carabao'
    if 'copa-del-rey' in tags: return 'CopaDelRey'
    if 'dfb-pokal' in tags or sl.startswith('dfb-') or sl.startswith('gdp-'): return 'DfbPokal'
    if 'k-league' in tags: return 'KLeague'
    if 'mls' in tags: return 'MLS'
    if 'afcon' in tags: return 'AFCON'
    if 'world-cup' in tags: return 'WorldCup'
    if 'women' in t or 'womens' in ' '.join(tags): return 'Womens'
    return 'OTHER:' + sl.split('-')[0]

rows = []
for e in D:
    best = 0
    bestmk = None
    sumliq = 0
    for m in e['markets']:
        l = m.get('liq') or 0
        sumliq += l
        if l > best:
            best = l
            bestmk = m.get('q')
    rows.append({'cls': classify(e), 'title': e['title'], 'slug': e['slug'], 'end': (e['endDate'] or '')[:16],
                 'best': best, 'sum': sumliq, 'n': len(e['markets']), 'bestq': bestmk, 'ev': e})

rows.sort(key=lambda r: -r['best'])
from collections import Counter, defaultdict
cnt = Counter(r['cls'] for r in rows)
hi = Counter(r['cls'] for r in rows if r['best'] >= 30000)
print('\n== events per competition (kept / with any market >=30k):')
for c, n in cnt.most_common():
    print('  %-14s %4d / %d' % (c, n, hi.get(c, 0)))

print('\n== TOP 45 events by best market liquidity:')
for r in rows[:45]:
    print('  %-12s %-44s end=%s bestMktLiq=%-8d sumLiq=%-9d mk=%d' % (r['cls'], (r['title'] or '')[:44], r['end'], r['best'], r['sum'], r['n']))

json.dump([{'cls': r['cls'], 'title': r['title'], 'slug': r['slug'], 'end': r['end'], 'best': r['best'], 'sum': r['sum'], 'n': r['n']} for r in rows],
          open('/home/ubuntu/paper-sim/round10/raw/liquidity_rank.json', 'w'), indent=1)
