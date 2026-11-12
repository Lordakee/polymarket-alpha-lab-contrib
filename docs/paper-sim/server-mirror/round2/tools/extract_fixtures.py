import json, re

RAW = '/home/ubuntu/paper-sim/round2/raw/events_open_dated.json'
events = json.load(open(RAW))
by_slug = {}
for ev in events:
    s = ev.get('slug')
    if s and s not in by_slug:
        by_slug[s] = ev

# (main slug, league_key, understat_home, understat_away, cross_league?)
CANDS = [
    # today Oct 12
    ('epl-cov-new-2026-10-12', 'EPL', 'Coventry', 'Newcastle United', False),
    ('lal-lev-sev-2026-10-12', 'La_liga', 'Levante', 'Sevilla', False),
    ('sea-ata-ven-2026-10-12', 'Serie_A', 'Atalanta', 'Venezia', False),
    ('sea-tor-udi-2026-10-12', 'Serie_A', 'Torino', 'Udinese', False),
    # UCL Oct 13
    ('ucl-atm-mnu-2026-10-13', 'X', 'Atletico Madrid', 'Manchester United', True),
    ('ucl-int-bru-2026-10-13', 'X', 'Inter', 'Club Brugge', True),
    ('ucl-gal-fcb-2026-10-13', 'X', 'Galatasaray', 'Barcelona', True),
    ('ucl-ars-lil-2026-10-13', 'X', 'Arsenal', 'Lille', True),
    ('ucl-vf-bay-2026-10-13', 'X', 'Viking', 'Bayern Munich', True),
    ('ucl-rcl-spo-2026-10-13', 'X', 'Lens', 'Sporting CP', True),
    ('ucl-rbl-psv-2026-10-13', 'X', 'RasenBallsport Leipzig', 'PSV Eindhoven', True),
    ('ucl-vil-nap-2026-10-13', 'X', 'Villarreal', 'Napoli', True),
    ('ucl-sf-slp-2026-10-13', 'X', 'Sabah', 'Slavia Praha', True),
    # UCL Oct 14
    ('ucl-rom-rma-2026-10-14', 'X', 'Roma', 'Real Madrid', True),
    ('ucl-mnc-psg-2026-10-14', 'X', 'Manchester City', 'Paris Saint Germain', True),
    ('ucl-lin2-liv-2026-10-14', 'X', 'LASK', 'Liverpool', True),
    ('ucl-bet-por-2026-10-14', 'X', 'Real Betis', 'Porto', True),
    ('ucl-fey-com-2026-10-14', 'X', 'Feyenoord', 'Como', True),
    ('ucl-ast-fen-2026-10-14', 'X', 'Aston Villa', 'Fenerbahce', True),
    ('ucl-sba-stu-2026-10-14', 'X', 'Slovan Bratislava', 'Stuttgart', True),
    ('ucl-shd-aek1-2026-10-14', 'X', 'Shakhtar Donetsk', 'AEK Athens', True),
    ('ucl-bog-bvb-2026-10-14', 'X', 'Bodoe/Glimt', 'Dortmund', True),
    # UEL Oct 15
    ('uel-cel1-juv-2026-10-15', 'X', 'Celta Vigo', 'Juventus', True),
    ('uel-lyo-cry-2026-10-15', 'X', 'Lyon', 'Crystal Palace', True),
    # weekend Oct 16-19 domestic
    ('epl-eve-che-2026-10-17', 'EPL', 'Everton', 'Chelsea', False),
    ('epl-bou-sun-2026-10-18', 'EPL', 'Bournemouth', 'Sunderland', False),
    ('epl-bri-cry-2026-10-18', 'EPL', 'Brighton', 'Crystal Palace', False),
    ('epl-ful-hul-2026-10-17', 'EPL', 'Fulham', 'Hull', False),
    ('epl-mac-ips-2026-10-17', 'EPL', 'Manchester City', 'Ipswich', False),
    ('epl-not-ars-2026-10-18', 'EPL', 'Nottingham Forest', 'Arsenal', False),
    ('epl-bre-liv-2026-10-17', 'EPL', 'Brentford', 'Liverpool', False),
    ('epl-new-ast-2026-10-17', 'EPL', 'Newcastle United', 'Aston Villa', False),
    ('epl-lee-mun-2026-10-18', 'EPL', 'Leeds', 'Manchester United', False),
    ('epl-tot-cov-2026-10-19', 'EPL', 'Tottenham', 'Coventry', False),
    ('sea-bol-int-2026-10-17', 'Serie_A', 'Bologna', 'Inter', False),
    ('sea-ven-nap-2026-10-17', 'Serie_A', 'Venezia', 'Napoli', False),
    ('sea-rom-gen-2026-10-17', 'Serie_A', 'Roma', 'Genoa', False),
    ('sea-fio-com-2026-10-18', 'Serie_A', 'Fiorentina', 'Como', False),
    ('sea-udi-lec-2026-10-18', 'Serie_A', 'Udinese', 'Lecce', False),
    ('sea-fro-sas-2026-10-16', 'Serie_A', 'Frosinone', 'Sassuolo', False),
    ('sea-juv-laz-2026-10-18', 'Serie_A', 'Juventus', 'Lazio', False),
    ('lal-osa-rrc-2026-10-18', 'La_liga', 'Osasuna', 'Racing Santander', False),
    ('lal-bet-bar-2026-10-17', 'La_liga', 'Real Betis', 'Barcelona', False),
    ('lal-esp-mad-2026-10-17', 'La_liga', 'Espanyol', 'Atletico Madrid', False),
    ('lal-rea-sev-2026-10-18', 'La_liga', 'Real Madrid', 'Sevilla', False),
    ('lal-val-bil-2026-10-17', 'La_liga', 'Valencia', 'Athletic Club', False),
    ('lal-cel-ala-2026-10-18', 'La_liga', 'Celta Vigo', 'Alaves', False),
    ('bun-bay-lei-2026-10-17', 'Bundesliga', 'Bayern Munich', 'RasenBallsport Leipzig', False),
    ('bun-ein-koe-2026-10-16', 'Bundesliga', 'Eintracht Frankfurt', 'FC Cologne', False),
    ('bun-s04-mai-2026-10-17', 'Bundesliga', 'Schalke 04', 'Mainz 05', False),
    ('bun-wer-scp-2026-10-17', 'Bundesliga', 'Werder Bremen', 'Paderborn', False),
    ('bun-hsv-stu-2026-10-17', 'Bundesliga', 'Hamburger SV', 'VfB Stuttgart', False),
    ('bun-elv-aug-2026-10-17', 'Bundesliga', 'Elversberg', 'Augsburg', False),
    ('fl1-lil-sbr-2026-10-17', 'Ligue_1', 'Lille', 'Brest', False),
    ('fl1-str-psg-2026-10-17', 'Ligue_1', 'Strasbourg', 'Paris Saint Germain', False),
    ('fl1-lyo-ogc-2026-10-18', 'Ligue_1', 'Lyon', 'Nice', False),
    ('fl1-ang-olm-2026-10-18', 'Ligue_1', 'Angers', 'Marseille', False),
    ('fl1-hac-aja-2026-10-18', 'Ligue_1', 'Le Havre', 'Auxerre', False),
]

def mkt_row(m):
    outcomes = m.get('outcomes'); prices = m.get('outcomePrices')
    try: outcomes = json.loads(outcomes) if isinstance(outcomes, str) else outcomes
    except Exception: pass
    try: prices = json.loads(prices) if isinstance(prices, str) else prices
    except Exception: pass
    toks = m.get('clobTokenIds')
    try: toks = json.loads(toks) if isinstance(toks, str) else toks
    except Exception: pass
    return {
        'id': m.get('id'), 'q': m.get('question'), 'group': m.get('groupItemTitle'),
        'outcomes': outcomes, 'prices': prices, 'bestBid': m.get('bestBid'),
        'bestAsk': m.get('bestAsk'), 'liq': m.get('liquidityNum') or m.get('liquidity'),
        'vol24': m.get('volume24hr'), 'tokens': toks, 'gameStartTime': m.get('gameStartTime'),
    }

out = {}
for slug, lg, home, away, cross in CANDS:
    fam_slugs = [slug, slug + '-more-markets', slug + '-exact-score']
    fam = {}
    for fs in fam_slugs:
        ev = by_slug.get(fs)
        if not ev:
            continue
        mk = [mkt_row(m) for m in ev.get('markets', []) if not m.get('closed')]
        fam[fs] = {'title': ev.get('title'), 'endDate': ev.get('endDate'), 'markets': mk}
    if not fam:
        print('MISSING', slug)
        continue
    main = fam.get(slug, {}).get('markets', [])
    gs = None
    for m in main:
        if m['gameStartTime']:
            gs = m['gameStartTime']; break
    out[slug] = {'league': lg, 'home': home, 'away': away, 'cross': cross,
                 'game_start': gs, 'family': fam}
    n_main = len(main)
    n_more = len(fam.get(slug + '-more-markets', {}).get('markets', []))
    print('OK %-32s main=%d more=%d xs=%d' % (slug, n_main, n_more,
          len(fam.get(slug + '-exact-score', {}).get('markets', []))))

json.dump(out, open('/home/ubuntu/paper-sim/round2/raw/fixtures.json', 'w'), indent=1)
print('saved fixtures.json')

# Show the 1X2 + O/U quotes for the top fixtures
def show_12_ou(slug):
    fx = out.get(slug)
    if not fx: return
    print()
    print('=== %s | %s vs %s | %s' % (slug, fx['home'], fx['away'], fx['game_start']))
    for m in fx['family'].get(slug, {}).get('markets', []):
        print('  MAIN  id=%-9s %-44s bid=%-6s ask=%-6s out=%s' % (m['id'], str(m['group'] or m['q'])[:44], m['bestBid'], m['bestAsk'], m['outcomes']))
    for m in fx['family'].get(slug + '-more-markets', {}).get('markets', [])[:26]:
        q = str(m['group'] or m['q'])
        if re.search(r'(Over|Under) 2\.5|Both Teams|Draw|Double|Yes|No', q):
            print('  MORE  id=%-9s %-44s bid=%-6s ask=%-6s out=%s' % (m['id'], q[:44], m['bestBid'], m['bestAsk'], m['outcomes']))

for s in ['epl-cov-new-2026-10-12', 'lal-lev-sev-2026-10-12', 'sea-ata-ven-2026-10-12', 'sea-tor-udi-2026-10-12', 'ucl-gal-fcb-2026-10-13']:
    show_12_ou(s)
