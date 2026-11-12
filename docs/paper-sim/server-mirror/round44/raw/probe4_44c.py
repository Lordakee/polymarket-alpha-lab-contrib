"""ROUND-44C probe 4: authoritative league calendar from cached FotMob
leagues payloads (fixtures.allMatches includes future scheduled games).
If a league has no cache, fetch it fresh via the same endpoint. Bucket
scheduled matches Nov 10..Nov 24 per league; find next league matchday.
PAPER ONLY - read-only API GETs."""
import json
import os
import time
import urllib.request
from collections import Counter

FX_DIR = '/home/ubuntu/paper-sim/tools/fotmob_cache/fixtures'
OUT = '/home/ubuntu/paper-sim/round44/raw/fotmob_calendar_44c.json'
LEAGUES = {  # FotMob league id -> our key
    47: 'EPL', 87: 'La_liga', 55: 'Serie_A', 54: 'Bundesliga',
    53: 'Ligue_1', 48: 'Championship', 57: 'Eredivisie',
}


def get(url, tries=5):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(
                url, headers={'User-Agent': 'Mozilla/5.0 (research)'})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            last = e
            time.sleep(2.0 + 2 * i)
    if last:
        raise last


def load_league(lid):
    cache = os.path.join(FX_DIR, 'leagues_%d_2026.json' % lid)
    if os.path.exists(cache):
        with open(cache) as fh:
            return json.load(fh), 'cache', os.path.getmtime(cache)
    payload = get('https://www.fotmob.com/api/data/leagues?id=%d&season=2026/2027' % lid)
    return payload, 'fresh-fetch', None


def main():
    result = {}
    for lid, key in sorted(LEAGUES.items()):
        try:
            payload, src, mtime = load_league(lid)
        except Exception as e:
            print('%s (id %d): FAILED %r' % (key, lid, e))
            result[key] = {'error': repr(e)}
            continue
        matches = ((payload.get('fixtures') or {}).get('allMatches')) or []
        sched = []
        fin = 0
        for m in matches:
            status = m.get('status') or {}
            utc = (m.get('utcTime') or '')[:16].replace('T', ' ')
            if status.get('finished'):
                fin += 1
                continue
            if utc:
                sched.append((utc, (m.get('home') or {}).get('name'),
                              (m.get('away') or {}).get('name'),
                              status.get('cancelled') or False))
        sched.sort()
        byday = Counter(s[0][:10] for s in sched)
        nxt = [s for s in sched if s[0] >= '2026-11-10']
        print('== %-13s id=%-2d %s  finished=%d scheduled=%d' % (
            key, lid, src, fin, len(sched)))
        for d in sorted(byday):
            if d >= '2026-11-01':
                print('     %s  n=%d' % (d, byday[d]))
        print('     next >=Nov-10: %d matches; first 10:' % len(nxt))
        for s in nxt[:10]:
            print('       %s  %s vs %s%s' % (s[0], s[1], s[2],
                                             '  CANCELLED' if s[3] else ''))
        result[key] = {
            'fotmob_league_id': lid, 'source': src,
            'cache_mtime': mtime, 'finished': fin,
            'scheduled_by_day': dict(sorted(byday.items())),
            'next_after_nov10': [
                {'utc': s[0], 'home': s[1], 'away': s[2],
                 'cancelled': bool(s[3])} for s in nxt],
        }
        time.sleep(1.2)
    json.dump(result, open(OUT, 'w'), indent=1)
    print('saved', OUT)


if __name__ == '__main__':
    main()
