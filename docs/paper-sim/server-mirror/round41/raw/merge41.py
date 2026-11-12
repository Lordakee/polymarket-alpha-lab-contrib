#!/usr/bin/env python3
"""Merge the Nov 1-5 FotMob Big-5 backfill into the round25 Understat snapshot.

For each Big-5 2026 season block:
  * keep every Understat row through Oct 31 verbatim (2025 blocks byte-identical)
  * map FotMob team titles -> Understat team ids (normalized match + explicit
    overrides for the three known divergent titles; unresolved => league skipped)
  * fill the EXISTING future fixture rows (isResult=false, nulls) in place with
    FotMob goals/xG, keeping the Understat row id + datetime (kickoff delta
    recorded); a pairing with no future row gets a new appended row
  * append history entries to the Understat team objects (Understat ids)

Idempotency: a history entry with the same (team, date) is never duplicated;
reruns fill nothing new. Output + meta written atomically.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

OLD_DEFAULT = Path('/home/ubuntu/paper-sim/round25/raw/xg_understat_25.json')
NEW_DEFAULT = Path('/home/ubuntu/paper-sim/round36/raw/xg_fotmob_big5_new.json')
OUT_DEFAULT = Path('/home/ubuntu/paper-sim/round36/raw/xg_fotmob_big5_merged.json')

LEAGUE_KEYS = ('EPL', 'La_liga', 'Serie_A', 'Bundesliga', 'Ligue_1')
SEASON = '2026'

# FotMob title -> Understat title, where normalized matching cannot reach
OVERRIDES = {
    ('Serie_A', 'Parma'): 'Parma Calcio 1913',
    ('Bundesliga', '1. FC Köln'): 'FC Cologne',
    ('La_liga', 'Deportivo A Coruña'): 'Deportivo La Coruna',
    # r41 additions (Saturday Nov-7 slate introduced these FotMob titles)
    ('EPL', 'Coventry City'): 'Coventry',
    ('EPL', 'Hull City'): 'Hull',
    ('EPL', 'Leeds United'): 'Leeds',
    ('EPL', 'Tottenham Hotspur'): 'Tottenham',
    ('La_liga', 'Deportivo Alavés'): 'Alaves',
    ('Bundesliga', 'Bayern München'): 'Bayern Munich',
    ('Bundesliga', 'Borussia Mönchengladbach'): 'Borussia M.Gladbach',
    ('Bundesliga', 'RB Leipzig'): 'RasenBallsport Leipzig',
}


def atomic_write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(text)
    shutil.move(str(tmp), str(path))


def norm(s: str) -> str:
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r'[^a-z0-9 ]', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def result_code(gf: int, ga: int) -> str:
    return 'w' if gf > ga else ('d' if gf == ga else 'l')


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--old', type=Path, default=OLD_DEFAULT)
    parser.add_argument('--new', type=Path, default=NEW_DEFAULT)
    parser.add_argument('--out', type=Path, default=OUT_DEFAULT)
    args = parser.parse_args()

    old = json.loads(args.old.read_text())
    new = json.loads(args.new.read_text())
    merged = json.loads(json.dumps(old))  # deep copy; 2025 blocks stay untouched

    merge_meta = {}
    for lgk in LEAGUE_KEYS:
        key = '{}_{}'.format(lgk, SEASON)
        ob, nb = old[key], new[key]
        stats = {
            'before_isResult': sum(1 for r in ob['dates'] if r.get('isResult')),
            'appended_dates_filled': 0, 'appended_dates_new_rows': 0,
            'history_entries_added': 0, 'anomalies': [], 'mapping': {},
        }

        # 1) title -> understat id resolution
        by_norm_title = {}
        for tid, row in ob['teams'].items():
            by_norm_title[norm(row['title'])] = (row['title'], tid)
        fotmob_titles = {d['h']['title'] for d in nb['dates']} | {d['a']['title'] for d in nb['dates']}
        resolve = {}
        for ft in sorted(fotmob_titles):
            if (lgk, ft) in OVERRIDES:
                target = OVERRIDES[(lgk, ft)]
                hit = by_norm_title.get(norm(target))
                if hit is None:
                    stats['anomalies'].append('override target missing: {!r}'.format(target))
                    continue
            else:
                hit = by_norm_title.get(norm(ft))
            if hit is None:
                stats['anomalies'].append('unresolved fotmob title: {!r}'.format(ft))
                continue
            resolve[ft] = hit
            stats['mapping'][ft] = hit[0]
        if len(resolve) != len(fotmob_titles):
            merge_meta[lgk] = stats
            continue  # league skipped: do not merge partial title coverage

        # index future rows by pairing for in-place fill; index completed rows
        # for rerun idempotency (already-merged pairings are skipped)
        fut_by_pair = {}
        done_by_pair = {}
        for row in merged[key]['dates']:
            pk = (norm(row['h']['title']), norm(row['a']['title']))
            if row.get('isResult'):
                done_by_pair.setdefault(pk, []).append(row)
            else:
                fut_by_pair.setdefault(pk, []).append(row)

        def history_date_exists(team_row, date_s):
            return any(e['date'] == date_s for e in team_row['history'])

        for nd in nb['dates']:
            ht, hid = resolve[nd['h']['title']]
            at, aid = resolve[nd['a']['title']]
            hg, ag = int(nd['goals']['h']), int(nd['goals']['a'])
            hxg, axg = nd['xG']['h'], nd['xG']['a']
            pk = (norm(ht), norm(at))
            ndt = datetime.strptime(nd['datetime'], '%Y-%m-%d %H:%M:%S')

            target = None
            for row in fut_by_pair.get(pk, []):
                odt = datetime.strptime(row['datetime'], '%Y-%m-%d %H:%M:%S')
                delta = abs((odt - ndt).total_seconds())
                if delta <= 7200:
                    if target is not None:
                        stats['anomalies'].append('pairing {} has multiple future rows'.format(pk))
                    target = row
                    stats.setdefault('kickoff_deltas_s', []).append(delta)
            if target is None:
                # rerun guard: already-merged completed row for this pairing?
                already = [r for r in done_by_pair.get(pk, [])
                           if abs((datetime.strptime(r['datetime'], '%Y-%m-%d %H:%M:%S')
                                   - ndt).total_seconds()) <= 7200]
                if already:
                    stats['already_merged_skipped'] = stats.get('already_merged_skipped', 0) + 1
                    continue
            if target is None:
                target = {
                    'id': 'fm_' + nd['id'], 'isResult': True,
                    'h': {'id': hid, 'title': ht, 'short_title': ''},
                    'a': {'id': aid, 'title': at, 'short_title': ''},
                    'goals': {'h': None, 'a': None}, 'xG': {'h': None, 'a': None},
                    'datetime': nd['datetime'],
                }
                merged[key]['dates'].append(target)
                stats['appended_dates_new_rows'] += 1
            else:
                stats['appended_dates_filled'] += 1
            target['isResult'] = True
            target['goals'] = {'h': str(hg), 'a': str(ag)}
            target['xG'] = {'h': hxg, 'a': axg}

            # history entries (Understat ids, Understat datetime)
            for side, tid_, xgf, xga, gf, ga in (
                ('h', hid, float(hxg), float(axg), hg, ag),
                ('a', aid, float(axg), float(hxg), ag, hg),
            ):
                team_row = merged[key]['teams'][tid_]
                if history_date_exists(team_row, target['datetime']):
                    stats['anomalies'].append(
                        'dup history date skipped: {} {}'.format(tid_, target['datetime']))
                    continue
                team_row['history'].append({
                    'h_a': side, 'xG': xgf, 'xGA': xga,
                    'npxG': xgf, 'npxGA': xga,
                    'scored': gf, 'missed': ga,
                    'result': result_code(gf, ga), 'date': target['datetime'],
                })
                stats['history_entries_added'] += 1

        for row in merged[key]['teams'].values():
            row['history'].sort(key=lambda e: e['date'])
        merged[key]['dates'].sort(key=lambda r: r['datetime'])

        stats['after_isResult'] = sum(1 for r in merged[key]['dates'] if r.get('isResult'))
        expected = stats['before_isResult'] + stats['appended_dates_filled'] + stats['appended_dates_new_rows']
        stats['count_check'] = 'OK' if stats['after_isResult'] == expected else \
            'MISMATCH expected={} got={}'.format(expected, stats['after_isResult'])
        merge_meta[lgk] = stats

    atomic_write(args.out, json.dumps(merged, indent=1) + '\n')
    meta = {
        'generated_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'old_snapshot': str(args.old),
        'new_source': str(args.new),
        'out': str(args.out),
        'leagues': merge_meta,
        'overrides_used': ['{}: {} -> {}'.format(k[0], k[1], v) for k, v in OVERRIDES.items()],
        'history_fields_note': ('new entries carry h_a/xG/xGA/npxG/npxGA/scored/missed/'
                               'result/date only (FotMob has no ppda/deep/xpts); '
                               'same shape as the WP-P3 validated Championship block'),
    }
    atomic_write(args.out.with_name(args.out.name + '.meta.json'),
                 json.dumps(meta, indent=1) + '\n')

    for lgk, s in merge_meta.items():
        print('{}: before={} filled={} new_rows={} after={} hist+{} check={} anomalies={}'.format(
            lgk, s['before_isResult'], s['appended_dates_filled'], s['appended_dates_new_rows'],
            s.get('after_isResult'), s['history_entries_added'], s.get('count_check'),
            len(s['anomalies'])))
        for a in s['anomalies']:
            print('   ANOMALY:', a)
        if s['anomalies']:
            return 1
    print('wrote {} ({} bytes)'.format(args.out, args.out.stat().st_size))
    return 0


if __name__ == '__main__':
    sys.exit(main())
