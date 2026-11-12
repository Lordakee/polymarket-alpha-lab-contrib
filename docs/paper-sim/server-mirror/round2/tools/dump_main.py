import json
D = json.load(open('/home/ubuntu/paper-sim/round2/raw/other_details.json'))

def show(slug, maxn=30, filt=None):
    ev = D.get(slug)
    if not ev: print('MISSING', slug); return
    print()
    print('=== %s | %s | end=%s' % (slug, ev['title'], str(ev.get('endDate'))[:19]))
    for m in ev['markets'][:maxn]:
        q = str(m['q'])[:72]
        if filt and filt.lower() not in q.lower(): continue
        print('  id=%-9s %-72s bid=%-6s ask=%-6s out=%s px=%s' % (
            m['id'], q, m['bestBid'], m['bestAsk'], m['outcomes'], m['prices']))

# NFL main game markets (the first few markets are ML/spread/total)
for s in ['nfl-buf-la-2026-10-13','nfl-sea-den-2026-10-16','nfl-dal-gb-2026-10-19','nfl-pit-tb-2026-10-18']:
    show(s, 12)
# MLB game markets
for s in ['mlb-lad-mil-2026-10-12','mlb-cle-tb-2026-10-12']:
    show(s, 27)
# NHL
for s in ['nhl-fla-buf-2026-10-12','nhl-las-min-2026-10-12','nhl-ott-nj-2026-10-12']:
    show(s, 7)
# UFC method families
for s in ['ufc-wilren-luifra-2026-10-13','ufc-aliper-smisun-2026-10-13','ufc-eri3-jas3-2026-10-17','ufc-nat2-man17-2026-10-17','ufc-ilibul-erivis-2026-09-29']:
    show(s, 19)
