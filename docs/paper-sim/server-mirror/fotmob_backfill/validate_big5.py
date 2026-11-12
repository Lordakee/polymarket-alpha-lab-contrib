#!/usr/bin/env python3
"""Validate the Big-5 FotMob season backfill blocks (task 3 of the dispatch).

Per season-league: match counts vs official season sizes, team counts,
xG coverage (skips), team-history lengths, goal-fit (xG sum vs goals sum),
plus sha256/size of each snapshot file. Reads only; writes
validation_big5.json next to the snapshots.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

BASE = Path('/home/ubuntu/paper-sim/fotmob_backfill')
SEASONS = ('2023', '2024', '2025')
EXPECTED = {  # league -> (teams, matches)
    'EPL': (20, 380), 'La_liga': (20, 380), 'Serie_A': (20, 380),
    'Bundesliga': (18, 306), 'Ligue_1': (18, 306),
}
HISTORY_LEN = {20: 38, 18: 34}


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def pearson(xs, ys):
    n = len(xs)
    if n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    sxx = math.sqrt(sum(v * v for v in dx))
    syy = math.sqrt(sum(v * v for v in dy))
    if sxx == 0 or syy == 0:
        return None
    return sum(a * b for a, b in zip(dx, dy)) / (sxx * syy)


def main() -> None:
    out = {'files': {}, 'seasons': {}}
    for season in SEASONS:
        snap_path = BASE / ('big5_{}.json'.format(season))
        meta_path = BASE / ('big5_{}.json.meta.json'.format(season))
        if not snap_path.exists():
            out['seasons'][season] = {'missing': True}
            continue
        snap = json.loads(snap_path.read_text())
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        out['files']['big5_{}.json'.format(season)] = {
            'bytes': snap_path.stat().st_size, 'sha256': sha256_of(snap_path)}
        season_rows = {}
        for lgk, (exp_teams, exp_matches) in EXPECTED.items():
            key = '{}_{}'.format(lgk, season)
            block = snap.get(key)
            if block is None:
                season_rows[lgk] = {'missing_block': True}
                continue
            dates = block['dates']
            teams = block['teams']
            goals_h = sum(int(d['goals']['h']) for d in dates)
            goals_a = sum(int(d['goals']['a']) for d in dates)
            xg_h = sum(float(d['xG']['h']) for d in dates)
            xg_a = sum(float(d['xG']['a']) for d in dates)
            hist_lens = sorted(len(t['history']) for t in teams.values())
            lm = meta.get('leagues', {}).get(lgk, {})
            row = {
                'matches': len(dates),
                'expected_matches': exp_matches,
                'matches_ok': len(dates) == exp_matches,
                'teams': len(teams),
                'expected_teams': exp_teams,
                'teams_ok': len(teams) == exp_teams,
                'history_len_minmax': [hist_lens[0], hist_lens[-1]] if hist_lens else None,
                'expected_history_len': HISTORY_LEN[exp_teams],
                'skipped_no_xg': len(lm.get('skipped_no_xg_ids', [])),
                'md_fetch_failures': len(lm.get('md_fetch_failures', {})),
                'kept': lm.get('kept_finished_numeric'),
                'excluded_cancelled': lm.get('excluded_cancelled'),
                'excluded_playoff': lm.get('excluded_playoff'),
                'excluded_unfinished': lm.get('excluded_unfinished'),
                'goals_h': goals_h, 'goals_a': goals_a, 'goals_total': goals_h + goals_a,
                'xg_h': round(xg_h, 2), 'xg_a': round(xg_a, 2),
                'xg_total': round(xg_h + xg_a, 2),
                'goalfit_h_pct': round(100.0 * (xg_h - goals_h) / goals_h, 2) if goals_h else None,
                'goalfit_a_pct': round(100.0 * (xg_a - goals_a) / goals_a, 2) if goals_a else None,
                'goalfit_total_pct': (round(100.0 * (xg_h + xg_a - goals_h - goals_a)
                                            / (goals_h + goals_a), 2)
                                      if (goals_h + goals_a) else None),
                'mean_home_xg': round(xg_h / len(dates), 3) if dates else None,
                'mean_away_xg': round(xg_a / len(dates), 3) if dates else None,
                'dates_range': ([dates[0]['datetime'], dates[-1]['datetime']]
                                if dates else None),
            }
            # per-team season xG-for vs goals-for correlation (gate-C style)
            xs, ys = [], []
            for t in teams.values():
                xgf = sum(e['xG'] for e in t['history'])
                gf = sum(e['scored'] for e in t['history'])
                xs.append(xgf)
                ys.append(gf)
            row['pearson_team_xgf_gf'] = (round(pearson(xs, ys), 4)
                                          if len(xs) == exp_teams else None)
            season_rows[lgk] = row
        out['seasons'][season] = {
            'leagues': season_rows,
            'total_matches': sum(r.get('matches', 0) for r in season_rows.values()),
            'total_goalfit_pct': None,
        }
        tot_m = sum(r.get('matches', 0) for r in season_rows.values())
        tot_xg = sum(r.get('xg_total', 0) for r in season_rows.values())
        tot_g = sum(r.get('goals_total', 0) for r in season_rows.values())
        if tot_g:
            out['seasons'][season]['total_goalfit_pct'] = round(
                100.0 * (tot_xg - tot_g) / tot_g, 2)
        out['seasons'][season]['total_matches'] = tot_m

    dest = BASE / 'validation_big5.json'
    dest.write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out, indent=1))
    print('WROTE', dest)


if __name__ == '__main__':
    main()
