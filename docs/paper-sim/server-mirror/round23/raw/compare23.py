"""Round-23: PM vs DK (ESPN-sourced DraftKings) comparison.
- O/U: full 2-way devig (DK over/under close odds) vs PM O/U mid. Flag |gap|>=15c (non-Big-5).
- ML: same-side compare PM price vs DK vigged implied (favorite via details, draw via drawOdds).
  One-sided conservative flag: PM - DK_vigged >= +15c.
- Ligue 1 O/U devig recorded as big5_dk_context."""
import json, re, time
from collections import defaultdict

RAW = '/home/ubuntu/paper-sim/round23/raw'

def am2prob(s):
    if s is None: return None
    s = str(s).strip()
    if s.startswith('-'):
        v = float(s[1:]); return v / (100 + v)
    if s.startswith('+'):
        v = float(s[1:]); return 100.0 / (100 + v)
    return None

evs = json.load(open(RAW + '/events_window23.json'))
odds = json.load(open(RAW + '/espn_odds_full23.json'))

# group PM events by base
groups = {}
for e in evs:
    t = str(e.get('title') or '')
    base = t.split(' - ')[0].strip()
    if ' vs. ' not in base: continue
    tags = e.get('tags') or []
    lg = None
    for tt in ['ligue-1', 'ere', 'primeira-liga', 'brazil-serie-a', 'brazil-serie-b',
               'efl-championship', 'mls', 'scottish-premiership']:
        if tt in tags: lg = tt; break
    if lg is None and (e.get('league_hint') == 'liga-mx' or 'Tijuana' in base or 'Pumas' in base
                       or 'Querétaro' in base or 'Atlas' in base or 'América' in base or 'Toluca' in base
                       or 'León' in base or 'Necaxa' in base):
        lg = 'liga-mx'
    if lg is None: lg = 'other'
    g = groups.setdefault(base, {'league': lg, 'markets': {}, 'vol24': 0, 'liq': e.get('liq')})
    if e.get('vol24'): g['vol24'] += e['vol24']
    for m in (e.get('markets') or []):
        if m.get('closed'): continue
        g['markets'][str(m.get('q'))] = m

def pm_mid(m):
    b, a = m.get('bestBid'), m.get('bestAsk')
    if b is not None and a is not None: return round((float(b) + float(a)) / 2, 4)
    pr = m.get('prices') or (json.loads(m['prices']) if isinstance(m.get('prices'), str) else [])
    return float(pr[0]) if pr else None

def match_espn(base):
    h, a = [x.strip() for x in base.split(' vs. ')]
    for r in odds:
        if not r.get('home') or not r.get('away'): continue
        hh, aa = str(r['home']), str(r['away'])
        if (h[:10].lower() in hh.lower() or hh[:10].lower() in h.lower()) and \
           (a[:10].lower() in aa.lower() or aa[:10].lower() in a.lower()):
            return r
        if (a[:10].lower() in hh.lower() or hh[:10].lower() in a.lower()) and \
           (h[:10].lower() in aa.lower() or aa[:10].lower() in h.lower()):
            return r
    return None

out_ou = []; out_ml = []
for base, g in sorted(groups.items()):
    r = match_espn(base)
    if r is None: continue
    lg = g['league']
    # O/U compare
    po, pu = am2prob(r.get('over_odds')), am2prob(r.get('under_odds'))
    if po and pu and r.get('ou_line'):
        line = '%.1f' % float(r['ou_line'])
        q = base + ': O/U ' + line
        m = g['markets'].get(q)
        if m:
            pm = pm_mid(m)
            dk_over = po / (po + pu)
            gap = round(pm - dk_over, 4) if pm is not None else None
            row = {'league': lg, 'match': base, 'line': line, 'dk_over_devig': round(dk_over, 4),
                   'dk_raw': [r.get('over_odds'), r.get('under_odds')], 'pm_over_mid': pm,
                   'gap_pm_minus_dk': gap, 'liq': m.get('liq'), 'vol24': g['vol24']}
            (out_ou if lg != 'ligue-1' else out_ou).append(row)
            flag = 'FLAG>=15c' if (gap is not None and abs(gap) >= 0.15) else ''
            print('%-14s %-44s O/U %-3s dk_dev=%.3f pm=%.3f gap=%+.3f liq=%8s %s' % (
                lg, base[:44], line, dk_over, pm, gap, m.get('liq') or 0, flag))
    # ML same-side compare
    det = str(r.get('details') or '')
    ml = re.match(r'^([A-Za-zÀ-ÿ\'\. ]+?) (-?\d+)$', det)
    if ml and r.get('draw_ml'):
        fteam = ml.group(1).strip(); fprob = am2prob('-' + ml.group(2)) if ml.group(2).startswith('-') is False else am2prob(ml.group(2))
        # details gives e.g. 'PSG -425' (moneyline of favorite) or 'REN +135'
        fodd = ml.group(2)
        fprob = am2prob(fodd if fodd.startswith('+') else fodd)
        drawprob = am2prob('+' + str(r['draw_ml']))
        h, a = [x.strip() for x in base.split(' vs. ')]
        fav_pm_name = h if fteam[:6].lower() in h.lower() or h[:6].lower() in fteam.lower() else (a if fteam[:6].lower() in a.lower() or a[:6].lower() in fteam.lower() else None)
        rec = {'league': lg, 'match': base, 'dk_fav': det, 'dk_fav_implied': round(fprob, 4) if fprob else None,
               'dk_draw_implied': round(drawprob, 4) if drawprob else None}
        if fav_pm_name:
            mq = 'Will %s win on' % fav_pm_name
            for qq, mm in g['markets'].items():
                if qq.startswith(mq):
                    rec['pm_fav'] = pm_mid(mm); rec['pm_fav_q'] = qq
                    rec['pm_fav_liq'] = mm.get('liq'); break
        for qq, mm in g['markets'].items():
            if 'end in a draw' in qq:
                rec['pm_draw'] = pm_mid(mm); rec['pm_draw_q'] = qq; rec['pm_draw_liq'] = mm.get('liq'); break
        if rec.get('pm_fav') is not None and rec.get('dk_fav_implied') is not None:
            rec['gap_fav'] = round(rec['pm_fav'] - rec['dk_fav_implied'], 4)
        if rec.get('pm_draw') is not None and rec.get('dk_draw_implied') is not None:
            rec['gap_draw'] = round(rec['pm_draw'] - rec['dk_draw_implied'], 4)
        out_ml.append(rec)
        f1 = 'FLAG>=15c' if rec.get('gap_fav') is not None and rec['gap_fav'] >= 0.15 else ''
        d1 = 'FLAG>=15c' if rec.get('gap_draw') is not None and rec['gap_draw'] >= 0.15 else ''
        if f1 or d1:
            print('%-14s %-44s ML fav pm=%s dk=%.3f gap=%+s %s | draw pm=%s dk=%.3f gap=%+s %s' % (
                lg, base[:44], rec.get('pm_fav'), rec.get('dk_fav_implied') or -1, rec.get('gap_fav'), f1,
                rec.get('pm_draw'), rec.get('dk_draw_implied') or -1, rec.get('gap_draw'), d1))

json.dump({'ou': out_ou, 'ml': out_ml}, open(RAW + '/dk_compare23.json', 'w'), indent=1)
print()
print('ou rows:', len(out_ou), ' ml rows:', len(out_ml))
print('OU flags >=15c:', [(o['league'], o['match'][:40], o['gap_pm_minus_dk']) for o in out_ou if o['gap_pm_minus_dk'] is not None and abs(o['gap_pm_minus_dk']) >= 0.15])
print('ML flags >=15c (PM rich vs DK vigged):', [(o['league'], o['match'][:40], o.get('gap_fav'), o.get('gap_draw')) for o in out_ml if (o.get('gap_fav') is not None and o['gap_fav'] >= 0.15) or (o.get('gap_draw') is not None and o['gap_draw'] >= 0.15)])
print('saved dk_compare23.json')
