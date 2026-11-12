"""Round-16 discovery: fixtures kicking off 2026-10-24T11:20Z .. 2026-10-25T03:00Z.

Leagues: Bundesliga, Ligue 1, and other non-English non-LaLiga non-SerieA soccer
leagues that have Polymarket tags. English leagues + La Liga + Serie A skipped
(other agents). Window filter is market gameStartTime, NOT event startDate.
"""
import json, urllib.request, urllib.parse, time

BASE = 'https://gamma-api.polymarket.com'
LO = '2026-10-24T11:20:00Z'
HI = '2026-10-25T03:00:00Z'
OUT = '/home/ubuntu/paper-sim/round16/raw/bund_events_window.json'

# slug, label, modelable
LEAGUES = [
    ('bundesliga', 'Bundesliga', True),
    ('ligue-1', 'Ligue 1', True),
    ('ere', 'Eredivisie', False),
    ('primeira-liga', 'Primeira Liga', False),
    ('scottish-premiership', 'Scottish Premiership', False),
    ('bel1', 'Belgian Pro League', False),
    ('saudi-professional-league', 'Saudi Pro League', False),
    ('australian-a-league', 'A-League', False),
    ('mls', 'MLS', False),
    ('bundesliga-2', '2. Bundesliga', False),
    ('ligue-2', 'Ligue 2', False),
    ('mex', 'Liga MX', False),
    ('denmark-superliga', 'Danish Superliga', False),
    ('norway-eliteserien', 'Eliteserien', False),
    ('sweden-allsvenskan', 'Allsvenskan', False),
    ('austria-bundesliga', 'Austrian Bundesliga', False),
    ('switzerland-super-league', 'Swiss Super League', False),
    ('gre1', 'Greek Super League', False),
    ('egypt-premier-league', 'Egyptian Premier', False),
    ('czechia-fortuna-liga', 'Czech Chance Liga', False),
    ('champions-league', 'UCL', False),
    ('europa-league', 'UEL', False),
    ('conference-league', 'UECL', False),
    ('ucl', 'UCL-ucl', False),
    ('uel', 'UEL-uel', False),
    ('brazil-serie-a', 'Brasileirao', False),
    ('bra', 'Brasileirao-bra', False),
    ('argentina-primera', 'Argentina', False),
    ('arg', 'Argentina-arg', False),
    ('super-lig', 'Turkish Super Lig', False),
    ('tur', 'Turkish-tur', False),
    ('turkey-super-lig', 'Turkish Super Lig 2', False),
    ('j1-league', 'J1', False),
    ('k-league', 'K League', False),
    ('col', 'UECL-col', False),
]

def get(url, tries=6):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except Exception as e:
            last = e
            time.sleep(1.2 + i)
    raise last

def norm(ts):
    s = str(ts or '').strip()
    if not s:
        return ''
    try:
        from datetime import datetime, timezone
        if s.endswith('Z'):
            s = s[:-1] + '+00:00'
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception:
        return s

def sweep(slug):
    """Page by volume24hr AND by liquidity; stop early once a full page is
    older than the window on BOTH event startDate and every market kickoff.
    Also page ascending startDate is useless (startDate != kickoff)."""
    seen = {}
    for order in ('volume24hr', 'liquidity'):
        offset = 0
        stale_pages = 0
        while offset < 2500:
            url = BASE + '/events/pagination?' + urllib.parse.urlencode({
                'limit': 100, 'tag_slug': slug, 'active': 'true', 'closed': 'false',
                'order': order, 'ascending': 'false', 'offset': offset})
            resp = get(url)
            batch = resp.get('data') if isinstance(resp, dict) else resp
            if not batch:
                break
            page_has_future_or_window = False
            for e in batch:
                sd = norm(e.get('startDate') or e.get('endDate'))
                kicks = [norm(m.get('gameStartTime')) for m in (e.get('markets') or [])]
                kicks = [k for k in kicks if k]
                newest = max(kicks) if kicks else sd
                if newest and newest >= LO[:10]:
                    page_has_future_or_window = True
                eid = str(e.get('id'))
                if eid not in seen:
                    seen[eid] = e
            if len(batch) < 100:
                break
            if not page_has_future_or_window:
                stale_pages += 1
                if stale_pages >= 2:
                    break
            else:
                stale_pages = 0
            offset += 100
            time.sleep(0.35)
    return list(seen.values())

def in_window_markets(ev):
    out = []
    for m in (ev.get('markets') or []):
        g = norm(m.get('gameStartTime'))
        if LO <= g <= HI:
            out.append(m)
    return out

all_events = {}
counts = {}
for slug, label, modelable in LEAGUES:
    try:
        evs = sweep(slug)
    except Exception as e:
        print('SWEEP FAIL', slug, repr(e), flush=True)
        counts[slug] = {'error': repr(e)}
        continue
    n_fix = 0
    bases = set()
    for e in evs:
        mk = in_window_markets(e)
        if not mk:
            continue
        eid = str(e.get('id'))
        title = e.get('title') or ''
        base = title.split(' - ')[0].strip()
        if ' vs. ' in base or ' vs ' in base:
            bases.add(base)
        n_fix += 1
        slim = all_events.get(eid) or {
            'id': eid, 'title': title, 'slug': e.get('slug'),
            'startDate': e.get('startDate'), 'endDate': e.get('endDate'),
            'liq': e.get('liquidityNum'), 'vol24': e.get('volume24hr'),
            'vol': e.get('volume'),
            'tags': [t.get('slug') for t in (e.get('tags') or [])],
            'league_slugs': [],
            'markets': [],
        }
        if slug not in slim['league_slugs']:
            slim['league_slugs'].append(slug)
        have = {m['id'] for m in slim['markets']}
        for m in mk:
            mid = str(m.get('id'))
            if mid in have:
                continue
            slim['markets'].append({
                'id': mid, 'q': m.get('question'), 'slug': m.get('slug'),
                'group': m.get('groupItemTitle'), 'type': m.get('marketType'),
                'outcomes': m.get('outcomes'), 'prices': m.get('outcomePrices'),
                'tokens': m.get('clobTokenIds'),
                'line': m.get('line') or m.get('handicap'),
                'gameStartTime': m.get('gameStartTime'),
                'liq': m.get('liquidityNum'), 'vol24': m.get('volume24hr'),
                'bestBid': m.get('bestBid'), 'bestAsk': m.get('bestAsk'),
                'spread': m.get('spread'), 'closed': m.get('closed'), 'active': m.get('active'),
            })
        all_events[eid] = slim
    counts[slug] = {'events_scanned': len(evs), 'window_events': n_fix, 'bases': len(bases)}
    print('%-28s scanned=%4d window_events=%3d bases=%2d' % (slug, len(evs), n_fix, len(bases)), flush=True)
    time.sleep(0.3)

evs = list(all_events.values())
evs.sort(key=lambda e: -(e.get('liq') or 0))
json.dump({'generated_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
           'window': [LO, HI], 'counts': counts, 'events': evs},
          open(OUT, 'w'), indent=1)
print('saved', OUT, 'events', len(evs))
# fixture rollup
from collections import defaultdict
fix = defaultdict(lambda: {'leagues': set(), 'kick': '', 'liq': 0, 'nmk': 0, 'vol24': 0})
for e in evs:
    base = (e.get('title') or '').split(' - ')[0].strip()
    kicks = [norm(m.get('gameStartTime')) for m in e['markets']]
    kick = min([k for k in kicks if k] or [''])
    rec = fix[base]
    rec['leagues'] |= set(e.get('league_slugs') or [])
    rec['kick'] = kick or rec['kick']
    rec['liq'] += e.get('liq') or 0
    rec['vol24'] += e.get('vol24') or 0
    rec['nmk'] += len(e['markets'])
print('--- FIXTURES ---')
for base, rec in sorted(fix.items(), key=lambda kv: (min(kv[1]['leagues'] or ['~']), kv[1]['kick'])):
    print('%-22s %-56s kick=%s nmk=%3d liq=%10.0f vol24=%8.0f' % (
        ','.join(sorted(rec['leagues']))[:22], base[:56], rec['kick'][:16], rec['nmk'], rec['liq'], rec['vol24']))
