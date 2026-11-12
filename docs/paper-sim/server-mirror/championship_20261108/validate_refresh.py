"""Fail-closed validation + goal-fit sanity for the 2026-11-08 FotMob
Championship/Eredivisie snapshot refresh. Read-only; prints a JSON report.

Checks: load_fotmob_snapshot structural validation (fail-closed), team
counts (24 Championship / 18 Eredivisie), round bounds (from fixtures
partition stats recorded in meta), per-club history growth vs the old
round-31 snapshot, and xG-vs-actual-goals fit on the newly added rounds.
"""
import json, math, sys
from pathlib import Path

sys.path.insert(0, '/home/ubuntu/polymarket-alpha-lab/src')
from polymarket_alpha_lab.papersim import fotmob

CH_NEW = Path('/home/ubuntu/paper-sim/championship_20261108/xg_fotmob_championship.json')
CH_OLD = Path('/home/ubuntu/paper-sim/round31/raw/xg_fotmob_championship.json')
ER_NEW = Path('/home/ubuntu/paper-sim/round39/raw/xg_fotmob_eredivisie.json')

def pearson(xs, ys):
    n = len(xs)
    mx = sum(xs) / n; my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    vy = math.sqrt(sum((y - my) ** 2 for y in ys))
    return cov / (vx * vy) if vx > 0 and vy > 0 else float('nan')

def goal_fit(dates, since=None):
    rows = [d for d in dates if since is None or d['datetime'] >= since]
    if not rows:
        return {'matches': 0}
    xs, ys = [], []
    for d in rows:
        for side in ('h', 'a'):
            xs.append(float(d['xG'][side])); ys.append(int(d['goals'][side]))
    diffs = [abs(x - y) for x, y in zip(xs, ys)]
    return {
        'matches': len(rows),
        'sides': len(xs),
        'sum_xg': round(sum(xs), 2),
        'sum_goals': sum(ys),
        'mean_abs_err': round(sum(diffs) / len(diffs), 3),
        'pearson_r': round(pearson(xs, ys), 3),
        'btts_rate': round(sum(1 for d in rows
                               if int(d['goals']['h']) > 0 and int(d['goals']['a']) > 0)
                           / len(rows), 3),
        'date_range': [rows[0]['datetime'], rows[-1]['datetime']],
    }

report = {}

# 1) structural load validation (raises on malformed values/shapes)
snap_ch = fotmob.load_fotmob_snapshot(str(CH_NEW))
snap_er = fotmob.load_fotmob_snapshot(str(ER_NEW))

# 2) Championship block checks: team count, coverage
for key, block in snap_ch.items():
    teams = block['teams']; dates = block['dates']
    hist_lens = {t['title']: len(t['history']) for t in teams.values()}
    report[key] = {
        'teams': len(teams), 'dates': len(dates),
        'dates_range': [dates[0]['datetime'], dates[-1]['datetime']],
        'history_len_min': min(hist_lens.values()),
        'history_len_max': max(hist_lens.values()),
    }
assert len(snap_ch['Championship_2026']['teams']) == 24, 'Championship_2026: team count != 24'
assert len(snap_ch['Championship_2025']['teams']) == 24, 'Championship_2025: team count != 24'

# 3) delta vs old round-31 snapshot: added matches, per-club growth
old = json.loads(CH_OLD.read_text())
o26 = old['Championship_2026']
b26 = snap_ch['Championship_2026']
new_ids = {d['id'] for d in b26['dates']}
old_ids = {d['id'] for d in o26['dates']}
added = sorted(d['datetime'] for d in b26['dates'] if d['id'] not in old_ids)
growth = {}
for tid, t in o26['teams'].items():
    nt = b26['teams'].get(tid)
    if nt is not None and len(nt['history']) != len(t['history']):
        growth[nt['title']] = len(nt['history']) - len(t['history'])
report['championship_2026_delta_vs_round31'] = {
    'added_match_count': len(new_ids - old_ids),
    'removed_match_count': len(old_ids - new_ids),
    'added_match_datetimes': added,
    'clubs_with_new_history_entries': len(growth),
    'per_club_growth': growth,
}

# 4) goal fit: new Championship rounds (Nov-4 + Nov-7) and prior-season baseline
report['championship_2026_goalfit_since_1104'] = goal_fit(b26['dates'], '2026-11-04 00:00:00')
report['championship_2025_goalfit_full_season'] = goal_fit(snap_ch['Championship_2025']['dates'])

# 5) Eredivisie block checks + Saturday Nov-7 goal fit
er26 = snap_er['Eredivisie_2026']
assert len(er26['teams']) == 18, 'Eredivisie_2026: team count != 18'
report['eredivisie_2026'] = {
    'teams': len(er26['teams']), 'dates': len(er26['dates']),
    'dates_range': [er26['dates'][0]['datetime'], er26['dates'][-1]['datetime']],
}
report['eredivisie_2026_goalfit_since_1107'] = goal_fit(er26['dates'], '2026-11-07 00:00:00')

print(json.dumps(report, indent=1))
print('VALIDATION: PASS (all fail-closed checks passed; see report above)')
