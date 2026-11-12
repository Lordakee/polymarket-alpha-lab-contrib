import json
D = json.load(open('/home/ubuntu/paper-sim/round2/raw/other_details.json'))

# UFC open-position status check (read-only)
ev = D['ufc-ilibul-erivis-2026-09-29']
print('=== OPEN POSITION CHECK: ufc-ilibul-erivis-2026-09-29 ===')
for m in ev['markets']:
    print('  id=%-9s %-64s bid=%-6s ask=%-6s v24=%s' % (m['id'], str(m['q'])[:64], m['bestBid'], m['bestAsk'], m['vol24']))
print()

# Game start times for MLB + method markets for other UFC fights
for s in ['ufc-aliper-smisun-2026-10-13','ufc-eri3-jas3-2026-10-17','ufc-nat2-man17-2026-10-17']:
    ev = D[s]
    print('=== %s | %s ===' % (s, ev['title'][:80]))
    for m in ev['markets'][:20]:
        print('  id=%-9s %-64s bid=%-6s ask=%-6s v24=%s' % (m['id'], str(m['q'])[:64], m['bestBid'], m['bestAsk'], m['vol24']))
    print()

# MLB game start times
for s in ['mlb-lad-mil-2026-10-12','mlb-cle-tb-2026-10-12']:
    ev = D[s]
    gs = set(m.get('gameStartTime') for m in ev['markets'][:3])
    print(s, 'gameStartTime=', gs)

# Full NFL ladders for the liquid wk6 games + MNF
for s in ['nfl-buf-la-2026-10-13','nfl-sea-den-2026-10-16','nfl-dal-gb-2026-10-19','nfl-car-phi-2026-10-18','nfl-pit-tb-2026-10-18','nfl-hou-jax-2026-10-18','nfl-lac-kc-2026-10-18']:
    ev = D[s]
    print()
    print('=== %s ===' % s)
    for m in ev['markets']:
        q = str(m['q'])
        if q.startswith('Spread:') or ': O/U' in q or m['outcomes'] in ([ 'Bills','Rams' ],['Seahawks','Broncos'],['Cowboys','Packers'],['Panthers','Eagles'],['Steelers','Buccaneers'],['Texans','Jaguars'],['Chargers','Chiefs']):
            print('  id=%-9s %-52s bid=%-6s ask=%-6s v24=%s' % (m['id'], q[:52], m['bestBid'], m['bestAsk'], m['vol24']))
