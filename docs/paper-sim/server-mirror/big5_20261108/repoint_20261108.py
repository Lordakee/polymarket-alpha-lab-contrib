#!/usr/bin/env python3
"""Re-point ~/paper-sim/understat_latest.json at the validated
big5_20261108/xg_fotmob_big5_merged.json (Sunday Nov-8 refresh).

Follows the publish_latest convention from tools/understat_refresh.py:
atomic symlink swap (temp + os.replace, never a dangling window) and a
refreshed understat_latest_pointer.json sidecar (target, sha256, per-league
summaries). Sidecar extra fields follow the round41 manual re-point shape
(source / merged_from / note). Pointer-only writes; no snapshot mutation.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

TARGET = Path('/home/ubuntu/paper-sim/big5_20261108/xg_fotmob_big5_merged.json')
LATEST = Path('/home/ubuntu/paper-sim/understat_latest.json')
SIDECAR = Path('/home/ubuntu/paper-sim/understat_latest_pointer.json')
LEAGUES = ('EPL', 'La_liga', 'Serie_A', 'Bundesliga', 'Ligue_1')


def atomic_json(path, value):
    tmp = path.with_name('.' + path.name + '.swap')
    tmp.write_text(json.dumps(value, indent=1) + '\n')
    os.replace(tmp, path)


snap = json.loads(TARGET.read_text())
digest = hashlib.sha256(TARGET.read_bytes()).hexdigest()
leagues = {}
for lgk in LEAGUES:
    b = snap[lgk + '_2026']
    done = [r for r in b['dates'] if r.get('isResult')]
    leagues[lgk] = {
        'completed_matches': len(done),
        'latest_match_date': done[-1]['datetime'] if done else None,
        'teams': len(b['teams']),
    }

target = TARGET.resolve()
temp = LATEST.with_name('.' + LATEST.name + '.swap')
temp.unlink(missing_ok=True)
os.symlink(os.path.relpath(target, start=LATEST.parent), temp)
os.replace(temp, LATEST)

atomic_json(SIDECAR, {
    'target': str(target),
    'sha256': digest,
    'status': 'complete',
    'paper_only': True,
    'fetched_at_utc': None,
    'required_results_date': None,
    'leagues': leagues,
    'pointed_at_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    'source': 'fotmob-big5-recovery (Understat outage since Oct 31)',
    'merged_from': [
        'round41/raw/xg_fotmob_big5_merged.json (r41 FotMob merge, through Sat 2026-11-07)',
        'big5_20261108/xg_fotmob_big5_new.json (FotMob window 2026-11-01..2026-11-10, '
        'incl. the full Sunday 2026-11-08 slate)',
    ],
    'note': ('Sunday Nov-8 refresh: merge_20261108.py fills all 24 Sunday fixtures '
             '(EPL 5 incl ManUtd-Villa, La Liga 5, Serie A 5, Bundesliga 3, Ligue 1 6) '
             'with 4 new title overrides (AFC Bournemouth/Brighton & Hove Albion/'
             'Ipswich Town/Milan); all 38 Block-2 validation checks PASS and the merge '
             'rerun is byte-identical. Championship on break (no Nov-8 fixtures; next '
             'round Nov-21). Eredivisie refreshed separately in '
             'round39/raw/xg_fotmob_eredivisie.json (not pointer-served). Understat '
             'recovery cron keeps priority and will re-point on its next successful '
             'refresh.'),
})
print('pointer ->', os.path.realpath(LATEST))
print('sha256', digest)
print('leagues', json.dumps(leagues))
