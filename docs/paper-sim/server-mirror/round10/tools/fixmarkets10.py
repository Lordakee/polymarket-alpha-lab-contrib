import json

D = json.load(open('/home/ubuntu/paper-sim/round10/raw/discover10.json'))
PREFIXES = ['uel-hof-lyo-2026-10-22', 'uel-juv-ren1-2026-10-22', 'uel-bou-mil1-2026-10-22', 'col-asm-scf-2026-10-22', 'col-aja-ata-2026-10-22']
res = {}
for e in D:
    sl = e['slug']
    for p in PREFIXES:
        if sl.startswith(p):
            for m in e['markets']:
                l = m.get('liq') or 0
                if l < 3000:
                    continue
                q = m.get('q') or ''
                res.setdefault(p, []).append({'id': m['id'], 'q': q, 'liq': l, 'outcomes': m.get('outcomes'), 'prices': m.get('prices'), 'evslug': sl})

for p in PREFIXES:
    print('==== ' + p)
    for m in sorted(res.get(p, []), key=lambda x: -x['liq']):
        print('  %-8d %-70s id=%s out=%s px=%s' % (m['liq'], m['q'][:70], m['id'], (m.get('outcomes') or [])[:2], m.get('prices')))
json.dump(res, open('/home/ubuntu/paper-sim/round10/raw/fixt_markets10.json', 'w'), indent=1)
