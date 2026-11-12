"""Round-15: merge Gamma 'sea'-tag (Serie A) events into events_window.json.

Serie A match events on Polymarket are tagged 'sea' (+sports/games/soccer), NOT
'serie-a', so the per-league sweeps missed them. This sweeps tag_slug=sea, keeps
markets kicking off Oct 24-27, slims to the same format, tags them 'serie-a'
(only when both team names are Understat Serie_A sides), and merges by event id.
"""
import json, urllib.request, urllib.parse, time
from datetime import datetime, timezone

BASE = 'https://gamma-api.polymarket.com'
RAW = '/home/ubuntu/paper-sim/round15/raw'
LO = '2026-10-24T00:00:00Z'
HI = '2026-10-27T23:59:59Z'

def norm(ts):
    s = str(ts or '').strip()
    if not s: return ''
    try:
        if s.endswith('Z'): s = s[:-1] + '+00:00'
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception:
        return s

def get(url, tries=5):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=25) as r: return json.load(r)
        except Exception as e:
            last = e; time.sleep(1.5 + i)
    raise last

out = []; offset = 0
while True:
    u = BASE + '/events/pagination?' + urllib.parse.urlencode({
        'limit': 100, 'tag_slug': 'sea', 'active': 'true', 'closed': 'false',
        'order': 'volume24hr', 'ascending': 'false', 'offset': offset})
    d = get(u); batch = d.get('data') if isinstance(d, dict) else d
    out.extend(batch)
    if len(batch) < 100: break
    offset += 100
    if offset >= 1000: break
    time.sleep(0.5)
print('sea events fetched:', len(out))

XG = json.load(open(RAW + '/xg_understat_15.json'))
seriea_teams = set(XG['Serie_A_2026']['teams'].keys())
alias = {'FC Internazionale Milano':'Inter', 'Atalanta BC':'Atalanta', 'Juventus FC':'Juventus',
         'AC Milan':'Milan', 'SSC Napoli':'Napoli', 'AS Roma':'Roma'}
def to_us(name):
    n = str(name or '').strip()
    if n in seriea_teams: return n
    if n in alias and alias[n] in seriea_teams: return alias[n]
    return None

evs = json.load(open(RAW + '/events_window.json'))
seen = {str(e.get('id')) for e in evs}
added = 0
for e in out:
    eid = str(e.get('id'))
    if eid in seen: continue
    mkwin = []
    for m in (e.get('markets') or []):
        g = norm(m.get('gameStartTime'))
        if LO <= g <= HI: mkwin.append(m)
    if not mkwin: continue
    title = str(e.get('title') or '')
    base = title.split(' - ')[0].strip()
    is_seriea = False
    if ' vs. ' in base:
        h, a = [x.strip() for x in base.split(' vs. ')]
        uh, ua = to_us(h), to_us(a)
        is_seriea = uh is not None and ua is not None
    slim = {
      'id': eid, 'title': title, 'slug': e.get('slug'),
      'startDate': e.get('startDate'), 'endDate': e.get('endDate'),
      'liq': e.get('liquidityNum'), 'vol24': e.get('volume24hr'), 'vol': e.get('volume'),
      'tags': [t.get('slug') for t in (e.get('tags') or [])] + (['serie-a'] if is_seriea else []),
      'markets': []}
    for m in mkwin:
        slim['markets'].append({
          'id': str(m.get('id')), 'q': m.get('question'), 'slug': m.get('slug'),
          'group': m.get('groupItemTitle'), 'type': m.get('marketType'),
          'outcomes': m.get('outcomes'), 'prices': m.get('outcomePrices'),
          'tokens': m.get('clobTokenIds'), 'line': m.get('line') or m.get('handicap'),
          'gameStartTime': m.get('gameStartTime'),
          'liq': m.get('liquidityNum'), 'vol24': m.get('volume24hr'),
          'bestBid': m.get('bestBid'), 'bestAsk': m.get('bestAsk'),
          'spread': m.get('spread'), 'closed': m.get('closed'), 'active': m.get('active')})
    evs.append(slim); seen.add(eid); added += 1
    print('  + %-58s liq=%9s nmk=%d seriea=%s' % (title[:58], slim['liq'], len(slim['markets']), is_seriea))

evs.sort(key=lambda e: -(e.get('liq') or 0))
json.dump(evs, open(RAW + '/events_window.json', 'w'), indent=1)
print('merged +%d sea events; total window events: %d' % (added, len(evs)))
