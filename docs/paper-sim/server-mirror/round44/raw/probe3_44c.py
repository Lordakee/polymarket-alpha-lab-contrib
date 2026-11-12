"""ROUND-44C probe 3: sanity-check FotMob schedule extraction and find the
next scheduled league matchday after Mon Nov-9 for all 7 in-scope leagues.
Also peek at raw snapshot structure. PAPER ONLY."""
import json
from collections import Counter

HOME = '/home/ubuntu/paper-sim'
CHAMP = f'{HOME}/championship_20261108/xg_fotmob_championship.json'
ERED = f'{HOME}/round39/raw/xg_fotmob_eredivisie.json'
BIG5 = f'{HOME}/round41/raw/xg_fotmob_big5_merged.json'


def load_raw(path):
    with open(path) as fh:
        return json.load(fh)


def walk_matches(obj):
    if isinstance(obj, dict):
        if 'matches' in obj and isinstance(obj['matches'], list):
            for m in obj['matches']:
                yield m
        for v in obj.values():
            yield from walk_matches(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk_matches(v)


def summarize(path, label):
    raw = load_raw(path)
    print('== %s  top-level type=%s' % (label, type(raw).__name__))
    if isinstance(raw, dict):
        print('   top keys:', list(raw.keys())[:12])
        for k, v in list(raw.items())[:6]:
            if isinstance(v, dict):
                print('     %s keys: %s' % (k, list(v.keys())[:10]))
    total, finished, sched = 0, 0, []
    for m in walk_matches(raw):
        if not isinstance(m, dict):
            continue
        total += 1
        status = m.get('status') or {}
        if not isinstance(status, dict):
            continue
        utc = (m.get('utcTime') or '')[:16].replace('T', ' ')
        if status.get('finished'):
            finished += 1
        elif utc:
            sched.append((utc, (m.get('home') or {}).get('name'),
                          (m.get('away') or {}).get('name')))
    sched.sort()
    print('   matches walked=%d finished=%d scheduled-with-time=%d'
          % (total, finished, len(sched)))
    byday = Counter(s[0][:10] for s in sched)
    for d in sorted(byday):
        print('     scheduled %s  n=%d' % (d, byday[d]))
    nxt = [s for s in sched if s[0] >= '2026-11-10']
    print('   next scheduled matches >= Nov-10: %d' % len(nxt))
    for s in nxt[:12]:
        print('     %s  %s vs %s' % s)
    return sched


def main():
    summarize(CHAMP, 'Championship (championship_20261108)')
    summarize(ERED, 'Eredivisie (round39)')
    summarize(BIG5, 'Big5 merged (round41)')


if __name__ == '__main__':
    main()
