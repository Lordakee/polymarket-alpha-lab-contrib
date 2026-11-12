#!/usr/bin/env python3
"""G1 overlap validation: FotMob 2025/26 Big-5 xG vs Understat 2025/26.

FotMob Big-5 xG is enet/Opta-sourced; Understat runs its own model. This
check quantifies the mixed-source hazard on the only overlapping complete
season on disk (2025/26 = season key 2025; Understat down since Oct 31,
2026, last complete snapshot round25).

Per league: pairing by (normalized home title, normalized away title,
kickoff date), then xG scale ratio (mean FotMob xG / mean Understat xG
per team-match), Pearson correlation on common matches (match-total xG
and home-side xG), mean abs diff, and score agreement. Writes
overlap_check.json. Read-only for everything else.
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from pathlib import Path

BASE = Path('/home/ubuntu/paper-sim/fotmob_backfill')
UNDERSTAT = Path('/home/ubuntu/paper-sim/round25/raw/xg_understat_25.json')
LEAGUES = ('EPL', 'La_liga', 'Serie_A', 'Bundesliga', 'Ligue_1')
SEASON = '2025'

# FotMob title -> Understat title where normalized matching cannot reach
# (unresolved titles surfaced by the first pass, 2026-11-10)
OVERRIDES = {
    ('EPL', 'Man Utd'): 'Manchester United',
    ('EPL', 'Man City'): 'Manchester City',
    ('EPL', 'AFC Bournemouth'): 'Bournemouth',
    ('EPL', 'Brighton & Hove Albion'): 'Brighton',
    ('EPL', 'Leeds United'): 'Leeds',
    ('EPL', 'Tottenham Hotspur'): 'Tottenham',
    ('EPL', 'West Ham United'): 'West Ham',
    ('EPL', 'Wolves'): 'Wolverhampton Wanderers',
    ('Serie_A', 'Parma'): 'Parma Calcio 1913',
    ('Serie_A', 'Hellas Verona'): 'Verona',
    ('Serie_A', 'Milan'): 'AC Milan',
    ('Bundesliga', '1. FC Köln'): 'FC Cologne',
    ('Bundesliga', 'Bayern München'): 'Bayern Munich',
    ('Bundesliga', 'Borussia Mönchengladbach'): 'Borussia M.Gladbach',
    ('Bundesliga', 'RB Leipzig'): 'RasenBallsport Leipzig',
    ('La_liga', 'Deportivo Alavés'): 'Alaves',
    ('La_liga', 'Deportivo A Coruña'): 'Deportivo La Coruna',
    ('La_liga', 'Atlético Madrid'): 'Atletico Madrid',
    ('Ligue_1', 'Paris Saint-Germain'): 'Paris Saint Germain',
}


def norm(s: str) -> str:
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r'[^a-z0-9 ]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    # drop purely-numeric tokens (e.g. 'bayer 04 leverkusen' -> 'bayer leverkusen')
    s = ' '.join(t for t in s.split() if not t.isdigit())
    return s


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
    fm_snap = json.loads((BASE / 'big5_2025.json').read_text())
    us_snap = json.loads(UNDERSTAT.read_text())
    out = {'leagues': {}, 'unresolved': {}, 'overrides_used': {}}
    pooled_fx, pooled_ux, pooled_fh, pooled_uh = [], [], [], []

    for lgk in LEAGUES:
        key = '{}_{}'.format(lgk, SEASON)
        fblock, ublock = fm_snap[key], us_snap[key]
        # title resolution fotmob -> understat (norm space)
        us_by_norm = {norm(t['title']): (t['title'], str(tid))
                      for tid, t in ublock['teams'].items()}
        fm_titles = sorted({d['h']['title'] for d in fblock['dates']}
                           | {d['a']['title'] for d in fblock['dates']})
        resolve = {}
        unresolved = []
        used = {}
        for ft in fm_titles:
            if (lgk, ft) in OVERRIDES:
                target = OVERRIDES[(lgk, ft)]
                hit = us_by_norm.get(norm(target))
                if hit is None:
                    unresolved.append(ft + ' (override target missing: ' + target + ')')
                    continue
                used[ft] = hit[0]
            else:
                hit = us_by_norm.get(norm(ft))
                if hit is None:
                    unresolved.append(ft)
                    continue
            resolve[ft] = norm(hit[0])  # normalized UNDERSTAT title for pairing keys
        out['unresolved'][lgk] = unresolved
        out['overrides_used'][lgk] = used
        if unresolved:
            out['leagues'][lgk] = {'error': 'unresolved fotmob titles: ' + ', '.join(unresolved)}
            continue

        # index understat completed matches by (norm home title, norm away, date)
        us_norm_title = {str(tid): t['title'] for tid, t in ublock['teams'].items()}
        us_idx = {}
        for d in ublock['dates']:
            if not d.get('isResult'):
                continue
            pk = (norm(us_norm_title.get(str(d['h']['id']), d['h'].get('title', ''))),
                  norm(us_norm_title.get(str(d['a']['id']), d['a'].get('title', ''))),
                  str(d['datetime'])[:10])
            us_idx.setdefault(pk, []).append(d)

        fx_tot, ux_tot, fh_x, uh_x, absdiffs = [], [], [], [], []
        score_mm = 0
        paired = 0
        for d in fblock['dates']:
            pk = (resolve[d['h']['title']],
                  resolve[d['a']['title']],
                  str(d['datetime'])[:10])
            cands = us_idx.get(pk) or []
            if not cands:
                # kickoff-date drift: try neighbouring days
                from datetime import date, timedelta
                base = date.fromisoformat(pk[2])
                for delta in (-1, 1):
                    alt = (pk[0], pk[1], (base + timedelta(days=delta)).isoformat())
                    cands = us_idx.get(alt) or []
                    if cands:
                        break
            if not cands:
                continue
            u = cands.pop(0)
            paired += 1
            fxh, fxa = float(d['xG']['h']), float(d['xG']['a'])
            uxh, uxa = float(u['xG']['h']), float(u['xG']['a'])
            fx_tot.append(fxh + fxa)
            ux_tot.append(uxh + uxa)
            fh_x.append(fxh)
            uh_x.append(uxh)
            absdiffs.append(abs(fxh - uxh) + abs(fxa - uxa))
            if (str(d['goals']['h']), str(d['goals']['a'])) != (str(u['goals']['h']), str(u['goals']['a'])):
                score_mm += 1
        fx_all = fx_tot  # totals list length = matches
        n = paired
        row = {
            'fotmob_matches': len(fblock['dates']),
            'understat_matches': sum(1 for d in ublock['dates'] if d.get('isResult')),
            'paired': paired,
            'score_mismatches': score_mm,
            'mean_fotmob_teamxg': round((sum(fx_tot) * 2) / (2 * n), 4) if n else None,
            'mean_understat_teamxg': round((sum(ux_tot) * 2) / (2 * n), 4) if n else None,
            'scale_ratio_fotmob_over_understat': (round(sum(fx_tot) / sum(ux_tot), 4)
                                                  if n and sum(ux_tot) else None),
            'pearson_r_total_xg': round(pearson(fx_tot, ux_tot), 4) if n else None,
            'pearson_r_home_xg': round(pearson(fh_x, uh_x), 4) if n else None,
            'mean_abs_xg_diff_per_teammatch': round(sum(absdiffs) / (2 * n), 4) if n else None,
        }
        out['leagues'][lgk] = row
        pooled_fx += fx_tot
        pooled_ux += ux_tot
        pooled_fh += fh_x
        pooled_uh += uh_x

    if pooled_fx:
        n = len(pooled_fx)
        out['pooled_big5'] = {
            'paired': n,
            'mean_fotmob_teamxg': round(sum(pooled_fx) / n, 4),
            'mean_understat_teamxg': round(sum(pooled_ux) / n, 4),
            'scale_ratio_fotmob_over_understat': round(sum(pooled_fx) / sum(pooled_ux), 4),
            'pearson_r_total_xg': round(pearson(pooled_fx, pooled_ux), 4),
            'pearson_r_home_xg': round(pearson(pooled_fh, pooled_uh), 4),
        }
    dest = BASE / 'overlap_check.json'
    dest.write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out, indent=1))
    print('WROTE', dest)


if __name__ == '__main__':
    main()
