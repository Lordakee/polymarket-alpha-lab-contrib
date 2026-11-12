import json

D = json.load(open('/home/ubuntu/paper-sim/round10/raw/discover10.json'))
COVERED_PREFIX = ('epl-', 'ucl-', 'fl1-', 'ser-', 'lal-', 'lla-', 'bun-')

for e in D:
    sl = e['slug']
    if sl.startswith(COVERED_PREFIX):
        continue
    best = 0
    for m in e['markets']:
        best = max(best, m.get('liq') or 0)
    if best < 30000:
        continue
    print('== %s | %s | end=%s | evLiq=%s' % (sl[:60], e['title'], (e['endDate'] or '')[:16], e.get('liq')))
    for m in sorted(e['markets'], key=lambda m: -(m.get('liq') or 0))[:8]:
        print('   liq=%-8d vol24=%-9s %s | px=%s out=%s' % (m.get('liq') or 0, m.get('vol24'), (m.get('q') or '')[:70], m.get('prices'), (m.get('outcomes') or [])[:4]))
    print()
