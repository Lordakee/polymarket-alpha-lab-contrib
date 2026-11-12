import json, math
from collections import defaultdict

d = json.load(open('/home/ubuntu/paper-sim/round5/raw/espn_summary.json'))

def am_to_p(am):
    if am is None: return None
    am = float(am)
    # negative -X: stake X to profit 100 -> implied X/(X+100)
    # positive +X: stake 100 to profit X -> implied 100/(X+100)
    return abs(am) / (abs(am) + 100.0) if am < 0 else 100.0 / (am + 100.0)

def pois(l, k):
    return math.exp(-l) * l ** k / math.factorial(k)

def ptot_probs(lam):
    # total-goals distribution for Poisson total lam
    return [pois(lam, k) for k in range(15)]

def ou_prob(lam, line):
    # P(total > line) for half-integer line
    return sum(ptot_probs(lam)[int(line) + 1:])

def solve_lam_for_prob(target, line):
    # binary search lam such that P(total>line)=target
    lo, hi = 0.2, 7.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if ou_prob(mid, line) > target: hi = mid
        else: lo = mid
    return (lo + hi) / 2

rows = []
for nm, s in d.items():
    for p in (s.get('pickcenter') or []):
        prov = (p.get('provider') or {}).get('name')
        if not prov or 'DraftKings' not in prov: continue
        line = p.get('overUnder'); ov = p.get('overOdds'); un = p.get('underOdds')
        if line is None or ov is None or un is None: continue
        po, pu = am_to_p(ov), am_to_p(un)
        if po is None or pu is None: continue
        s_sum = po + pu
        devig_over = po / s_sum
        # implied total-goals lambda from devigged over prob at DK's line
        lam = solve_lam_for_prob(devig_over, line)
        # map to 2.5 line
        over25 = ou_prob(lam, 2.5)
        over35 = ou_prob(lam, 3.5)
        over15 = ou_prob(lam, 1.5)
        rows.append({'game': nm, 'dk_line': line, 'over_am': ov, 'under_am': un,
                     'devig_over': round(devig_over, 4), 'lam_implied': round(lam, 3),
                     'over25': round(over25, 4), 'over35': round(over35, 4),
                     'over15': round(over15, 4)})
        break

for r in rows:
    print('%-9s DK line=%.1f O%.0f/U%.0f devig=%.3f lam=%.2f -> O1.5=%.3f O2.5=%.3f O3.5=%.3f' % (
        r['game'], r['dk_line'], r['over_am'], r['under_am'], r['devig_over'],
        r['lam_implied'], r['over15'], r['over25'], r['over35']))
json.dump(rows, open('/home/ubuntu/paper-sim/round5/raw/dk_parsed.json', 'w'), indent=1)
print('saved dk_parsed.json')
