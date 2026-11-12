"""ROUND-41 enumeration (paper-only): Gamma soccer events in the 12h window
2026-11-07T13:50Z .. 2026-11-08T01:50Z + ESPN scoreboard cross-check.

Sweeps: 2 date-window sweeps (vol/liq order) + exact-tag sweeps for each
in-scope league (epl, championship, bundesliga, la-liga, sea, ligue-1, ere,
bel1, tur, primeira-liga, scottish-premiership) + generic soccer tag.
Board format follows round39/raw/enum39.py (slim events, closed dropped).
"""
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

BASE = 'https://gamma-api.polymarket.com'
ESPN = 'https://site.api.espn.com/apis/site/v2/sports/soccer'
HOME = '/home/ubuntu/paper-sim'
OUTDIR = f'{HOME}/round41/raw'
LO = '2026-11-08T01:15:00Z'
HI = '2026-11-09T01:15:00Z'


def get(url, tries=6):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (research)'})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            last = e
            time.sleep(2.0 + 2 * i)
    raise last


def norm_ts(ts):
    s = str(ts or '').strip()
    if not s:
        return ''
    try:
        if s.endswith('Z'):
            s = s[:-1] + '+00:00'
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    except Exception:
        return s


def parse_listy(raw):
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return []
    return raw or []


def sweep(order, extra_params, max_offset=1500):
    out, offset = [], 0
    while True:
        params = {'limit': 100, 'active': 'true', 'closed': 'false',
                  'order': order, 'ascending': 'false', 'offset': offset}
        params.update(extra_params)
        resp = get(BASE + '/events/pagination?' + urllib.parse.urlencode(params))
        batch = resp.get('data') if isinstance(resp, dict) else resp
        out.extend(batch)
        if len(batch) < 100:
            return out
        offset += 100
        if offset >= max_offset:
            return out
        time.sleep(1.0)


def slim_event(e):
    eid = str(e.get('id'))
    tags = [t.get('slug') for t in (e.get('tags') or []) if t.get('slug')]
    slim = {'id': eid, 'title': e.get('title'), 'slug': e.get('slug'),
            'tags': tags, 'liq': e.get('liquidityNum'),
            'vol24': e.get('volume24hr'), 'markets': []}
    for m in e.get('markets') or []:
        if m.get('closed'):
            continue
        slim['markets'].append({
            'id': str(m.get('id')), 'q': m.get('question'), 'slug': m.get('slug'),
            'group': m.get('groupItemTitle'), 'type': m.get('marketType'),
            'outcomes': parse_listy(m.get('outcomes')),
            'prices': parse_listy(m.get('outcomePrices')),
            'tokens': parse_listy(m.get('clobTokenIds')),
            'line': m.get('line') or m.get('handicap'),
            'gameStartTime': norm_ts(m.get('gameStartTime')),
            'liq': m.get('liquidityNum'), 'vol24': m.get('volume24hr'),
            'bestBid': m.get('bestBid'), 'bestAsk': m.get('bestAsk'),
            'spread': m.get('spread'), 'active': m.get('active')})
    kos = [m['gameStartTime'] for m in slim['markets'] if m['gameStartTime']]
    slim['kick'] = min(kos) if kos else ''
    return slim


def in_range(ev, lo, hi):
    kos = [m['gameStartTime'] for m in ev['markets'] if m['gameStartTime']]
    return any(lo <= k <= hi for k in kos)


def main():
    import os
    os.makedirs(OUTDIR, exist_ok=True)
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    print('UTC now:', now, flush=True)

    sweeps = [
        ('date-volume', 'volume24hr', {'start_date_min': LO, 'start_date_max': HI}),
        ('date-liquidity', 'liquidity', {'start_date_min': LO, 'start_date_max': HI}),
        ('tag-soccer', 'volume24hr', {'tag_slug': 'soccer'}),
        ('tag-epl', 'volume24hr', {'tag_slug': 'epl'}),
        ('tag-champ', 'volume24hr', {'tag_slug': 'efl-championship'}),
        ('tag-bundesliga', 'volume24hr', {'tag_slug': 'bundesliga'}),
        ('tag-laliga', 'volume24hr', {'tag_slug': 'la-liga'}),
        ('tag-seriea', 'volume24hr', {'tag_slug': 'sea'}),
        ('tag-ligue1', 'volume24hr', {'tag_slug': 'ligue-1'}),
        ('tag-ere', 'volume24hr', {'tag_slug': 'ere'}),
        ('tag-bel1', 'volume24hr', {'tag_slug': 'bel1'}),
        ('tag-tur', 'volume24hr', {'tag_slug': 'tur'}),
        ('tag-primeira', 'volume24hr', {'tag_slug': 'primeira-liga'}),
        ('tag-scottish', 'volume24hr', {'tag_slug': 'scottish-premiership'}),
    ]
    seen = {}
    for label, order, extra in sweeps:
        try:
            evs = sweep(order, extra)
        except Exception as e:
            print('sweep', label, 'FAILED', repr(e), flush=True)
            continue
        n = 0
        for e in evs:
            try:
                slim = slim_event(e)
            except Exception:
                continue
            if not in_range(slim, LO, HI):
                sd = norm_ts(e.get('startDate'))
                if not (sd and LO <= sd <= HI and slim['markets']):
                    continue
            n += 1
            if slim['id'] not in seen:
                seen[slim['id']] = slim
        print('sweep %-16s total=%4d in_window=%d unique=%d' % (
            label, len(evs), n, len(seen)), flush=True)
        time.sleep(1.0)

    events = [e for e in seen.values()
              if 'soccer' in (e.get('tags') or []) and e.get('kick')
              and LO <= e['kick'] <= HI]
    events.sort(key=lambda e: (e['kick'], e.get('title') or ''))
    json.dump(events, open(f'{OUTDIR}/events_window_41.json', 'w'), indent=1)
    print('unique soccer events in window:', len(events), flush=True)

    # ---- ESPN scoreboards for cross-check ----
    espn_leagues = {
        'eng.1': 'EPL', 'eng.2': 'Championship', 'ger.1': 'Bundesliga',
        'esp.1': 'La_liga', 'ita.1': 'Serie_A', 'fra.1': 'Ligue_1',
        'ned.1': 'Eredivisie', 'bel.1': 'Belgian Pro League',
        'tur.1': 'Turkish Super Lig', 'por.1': 'Primeira Liga',
        'sco.1': 'Scottish Premiership'}
    espn = {}
    for date in ('20261108', '20261109'):
        day = {}
        for code, label in espn_leagues.items():
            try:
                d = get(f'{ESPN}/{code}/scoreboard?dates={date}')
                evs = []
                for ev in d.get('events') or []:
                    comp = (ev.get('competitions') or [{}])[0]
                    teams = {}
                    for c in comp.get('competitors') or []:
                        t = c.get('team') or {}
                        teams['home' if c.get('homeAway') == 'home' else 'away'] = {
                            'name': t.get('displayName'), 'abbr': t.get('abbreviation')}
                    evs.append({'date': ev.get('date'), 'name': ev.get('name'),
                                'venue': (comp.get('venue') or {}).get('fullName'),
                                'teams': teams,
                                'status': (ev.get('status') or {}).get('type', {}).get('description')})
                day[label] = evs
            except Exception as e:
                day[label] = {'error': repr(e)}
            time.sleep(0.4)
        espn[date] = day
    json.dump(espn, open(f'{OUTDIR}/espn_fixtures_41.json', 'w'), indent=1)
    n_fx = sum(len(v) for day in espn.values() for v in day.values() if isinstance(v, list))
    print('ESPN fixtures fetched:', n_fx, flush=True)
    print('saved events_window_41.json + espn_fixtures_41.json', flush=True)


if __name__ == '__main__':
    main()
