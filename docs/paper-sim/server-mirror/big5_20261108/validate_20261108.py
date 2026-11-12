#!/usr/bin/env python3
"""Validate big5_20261108/xg_fotmob_big5_merged.json (Block-2 contract).

Checks: per-league team counts (20/20/20/18/18), zero duplicate history
dates for every team in every block (both seasons), completed-count delta
== window Sunday rows, last completed date per 2026 league block covers
2026-11-08, goal-vs-xG sanity on every row dated 2026-11-08+, and
verifies the 2025 blocks are byte-identical to the old snapshot's.
Read-only; prints PASS/FAIL lines and exits nonzero on any FAIL.
"""
import hashlib
import json
import sys
from pathlib import Path

OLD = Path('/home/ubuntu/paper-sim/round41/raw/xg_fotmob_big5_merged.json')
NEW = Path('/home/ubuntu/paper-sim/big5_20261108/xg_fotmob_big5_merged.json')
EXPECT_TEAMS = {'EPL': 20, 'La_liga': 20, 'Serie_A': 20, 'Bundesliga': 18, 'Ligue_1': 18}
SUNDAY_NEW = {'EPL': 5, 'La_liga': 5, 'Serie_A': 5, 'Bundesliga': 3, 'Ligue_1': 6}

fails = []


def check(name, ok, detail=''):
    print('{} {} {}'.format('PASS' if ok else 'FAIL', name, detail))
    if not ok:
        fails.append(name)


old = json.loads(OLD.read_text())
new = json.loads(NEW.read_text())
check('block_keys_preserved', sorted(old) == sorted(new),
      '{} blocks'.format(len(new)))

# 2025 blocks byte-identical (canonical dump comparison)
same25 = all(json.dumps(old[k], indent=1) == json.dumps(new[k], indent=1)
             for k in old if k.endswith('_2025'))
check('season_2025_blocks_identical', same25)

for lgk, want_teams in EXPECT_TEAMS.items():
    key = lgk + '_2026'
    ob, nb = old[key], new[key]
    odone = sum(1 for r in ob['dates'] if r.get('isResult'))
    ndone = sum(1 for r in nb['dates'] if r.get('isResult'))
    check(lgk + '.team_count', len(nb['teams']) == want_teams,
          'teams={} expected={}'.format(len(nb['teams']), want_teams))
    check(lgk + '.completed_delta', ndone - odone == SUNDAY_NEW[lgk],
          '{} -> {} (delta {}, expected {})'.format(odone, ndone, ndone - odone, SUNDAY_NEW[lgk]))
    done = [r for r in nb['dates'] if r.get('isResult')]
    last = done[-1]['datetime'] if done else None
    check(lgk + '.last_date_covers_nov8', last is not None and last >= '2026-11-08', last)
    # duplicate history dates across every team (2026 + 2025 blocks)
    for blk in (lgk + '_2026', lgk + '_2025'):
        dups = []
        for tid, t in new[blk]['teams'].items():
            dates = [e['date'] for e in t['history']]
            if len(dates) != len(set(dates)):
                dups.append(tid)
        check(blk + '.zero_dup_history_dates', not dups, str(dups)[:80])
    # goal-fit sanity on new rows (dated >= 2026-11-08)
    rows = [r for r in done if r['datetime'] >= '2026-11-08']
    bad = []
    for r in rows:
        try:
            gh, ga = int(r['goals']['h']), int(r['goals']['a'])
            xh, xa = float(r['xG']['h']), float(r['xG']['a'])
        except (TypeError, ValueError):
            bad.append(('nonnumeric', r['id']))
            continue
        if min(xh, xa) < 0 or max(xh, xa) > 6 or abs(gh - xh) > 3.5 or abs(ga - xa) > 3.5:
            bad.append(('outlier', r['id'], gh, ga, xh, xa))
    check(lgk + '.goal_fit_new_rows', len(rows) == SUNDAY_NEW[lgk] and not bad,
          '{} rows, bad={}'.format(len(rows), bad))

# history entries dated Nov 8 == 2 * matches per league, mapped teams exist
for lgk, n in SUNDAY_NEW.items():
    blk = new[lgk + '_2026']
    h8 = sum(1 for t in blk['teams'].values() for e in t['history']
             if e['date'] >= '2026-11-08')
    check(lgk + '.history_entries_nov8', h8 == 2 * n, '{} entries (expected {})'.format(h8, 2 * n))

print('sha256', hashlib.sha256(NEW.read_bytes()).hexdigest())
print('VERDICT:', 'PASS' if not fails else 'FAIL ' + str(fails))
sys.exit(0 if not fails else 1)
