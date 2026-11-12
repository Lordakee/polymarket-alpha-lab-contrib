import json, math
from collections import defaultdict

XG = json.load(open("/home/ubuntu/paper-sim/round4/raw/xg_understat.json"))
LEAGUES = ["EPL", "La_liga", "Serie_A", "Bundesliga", "Ligue_1"]

def load(lg, se):
    return XG["%s_%s" % (lg, se)]

env = {}
for lg in LEAGUES:
    env[lg] = {}
    for se in ["2025", "2026"]:
        d = load(lg, se)
        ms = [m for m in d["dates"] if m.get("isResult") and m.get("xG") and m["xG"].get("h")]
        xg = sum(float(m["xG"]["h"]) + float(m["xG"]["a"]) for m in ms) / len(ms)
        hxg = sum(float(m["xG"]["h"]) for m in ms) / len(ms)
        axg = sum(float(m["xG"]["a"]) for m in ms) / len(ms)
        gl = sum(int(m["goals"]["h"]) + int(m["goals"]["a"]) for m in ms) / len(ms)
        o25 = sum(1 for m in ms if int(m["goals"]["h"]) + int(m["goals"]["a"]) >= 3) / len(ms)
        env[lg][se] = {"xg": xg, "hxg": hxg, "axg": axg, "goals": gl, "n": len(ms), "o25": o25}
        print("ENV %-10s %s: n=%3d goals=%.2f xG=%.2f O2.5=%.3f" % (lg, se, len(ms), gl, xg, o25))

_cache = {}
def ratings_for(lg, LASTW, PRIOR, mode):
    key = (lg, LASTW, PRIOR, mode)
    if key in _cache: return _cache[key]
    d25 = load(lg, "2025"); d26 = load(lg, "2026")
    ms = [m for m in d25["dates"] if m.get("isResult")]
    bh = sum(float(m["xG"]["h"]) for m in ms) / len(ms)
    ba = sum(float(m["xG"]["a"]) for m in ms) / len(ms)
    lgf = (bh + ba) / 2.0
    last = {}
    for t in d25["teams"].values():
        h = t["history"]
        last[t["title"]] = (sum(float(x["xG"]) for x in h) / len(h), sum(float(x["xGA"]) for x in h) / len(h))
    r = {}
    for t in d26["teams"].values():
        h = t["history"]; name = t["title"]
        if not h: continue
        cf = sum(float(x["xG"]) for x in h) / len(h)
        ca = sum(float(x["xGA"]) for x in h) / len(h)
        nc = len(h)
        if mode == "cur":
            f, a = cf, ca
        elif mode == "last":
            f, a = last.get(name, (lgf, lgf))
        else:
            lf, la_ = last.get(name, (lgf, lgf))
            f = (nc * cf + LASTW * 38 * lf + PRIOR * lgf) / (nc + LASTW * 38 + PRIOR)
            a = (nc * ca + LASTW * 38 * la_ + PRIOR * lgf) / (nc + LASTW * 38 + PRIOR)
        r[name] = (f / lgf, a / lgf)
    _cache[key] = (bh, ba, lgf, r)
    return _cache[key]

SWEEPS = [
    ("blend w=.5 p=8 rho0", 0.5, 8, 0.0, "blend"),
    ("blend w=.5 p=8 DC",   0.5, 8, -0.08, "blend"),
    ("blend w=1.0 p=8",     1.0, 8, 0.0, "blend"),
    ("blend w=.25 p=8",     0.25, 8, 0.0, "blend"),
    ("blend w=.5 p=16",     0.5, 16, 0.0, "blend"),
    ("blend w=.5 p=4",      0.5, 4, 0.0, "blend"),
    ("current-only",        None, None, 0.0, "cur"),
    ("last-only",           None, None, 0.0, "last"),
    ("cross-shrink .8",     0.5, 8, 0.0, "blend"),
    ("cross-shrink 1.1",    0.5, 8, 0.0, "blend"),
]

def pois(l, k):
    return math.exp(-l) * l ** k / math.factorial(k)

def grid(lh, la, N=10, rho=0.0):
    g = [[pois(lh, i) * pois(la, j) for j in range(N + 1)] for i in range(N + 1)]
    if rho:
        g[0][0] *= max(1 - lh * la * rho, .01)
        g[0][1] *= max(1 + lh * rho, .01)
        g[1][0] *= max(1 + la * rho, .01)
        g[1][1] *= max(1 - rho, .01)
    s = sum(sum(r) for r in g)
    return [[v / s for v in row] for row in g]

def outs(g):
    ptot = defaultdict(float)
    for i in range(len(g)):
        for j in range(len(g)):
            ptot[i + j] += g[i][j]
    o25 = sum(v for t, v in ptot.items() if t >= 3)
    o35 = sum(v for t, v in ptot.items() if t >= 4)
    return o25, o35

TEAM_LEAGUE = {}
for lg in LEAGUES:
    for t in load(lg, "2026")["teams"].values():
        TEAM_LEAGUE[t["title"]] = lg

def find_team(sub):
    for name, lg in TEAM_LEAGUE.items():
        if sub.lower() == name.lower():
            return name, lg
    for name, lg in TEAM_LEAGUE.items():
        if sub.lower() in name.lower():
            return name, lg
    return None, None

def model_game(home, away, LASTW, PRIOR, rho, mode, shrink=1.0, boost=0.0):
    hn, lgh = find_team(home); an_, lga = find_team(away)
    if lgh is None or lga is None: return None
    bh1, ba1, lgf1, r1 = ratings_for(lgh, LASTW, PRIOR, mode)
    bh2, ba2, lgf2, r2 = ratings_for(lga, LASTW, PRIOR, mode)
    if hn not in r1 or an_ not in r2: return None
    bh = (bh1 + bh2) / 2.0
    ba = (ba1 + ba2) / 2.0
    ah, dh = r1[hn]; aa, da = r2[an_]
    lh = bh * (ah ** shrink) * (da ** shrink) * (1 + boost)
    la = ba * (aa ** shrink) * (dh ** shrink) * (1 + boost)
    g = grid(lh, la, 10, rho)
    o25, o35 = outs(g)
    return o25, o35, lh, la

# fixture list: (label, home_understat, away_understat, is_ucl, pm_over_ask)
FIX = [
    ("MCI-IPS (EPL 10/17)", "Manchester City", "Ipswich", False, 0.71),
    ("BRE-LIV (EPL 10/17)", "Brentford", "Liverpool", False, 0.61),
    ("EVE-CHE (EPL 10/17)", "Everton", "Chelsea", False, 0.58),
    ("LEE-MUN (EPL 10/18)", "Leeds", "Manchester United", False, 0.58),
    ("FOR-ARS (EPL 10/18)", "Nottingham Forest", "Arsenal", False, 0.50),
    ("NEW-AVL (EPL 10/17)", "Newcastle United", "Aston Villa", False, 0.61),
    ("BET-BAR (Lal 10/17)", "Real Betis", "Barcelona", False, 0.77),
    ("RMA-SEV (Lal 10/18)", "Real Madrid", "Sevilla", False, 0.69),
    ("ESP-ATM (Lal 10/17)", "Espanyol", "Atletico Madrid", False, 0.53),
    ("VAL-ATH (Lal 10/17)", "Valencia", "Athletic Club", False, 0.46),
    ("BOL-INT (Sea 10/17)", "Bologna", "Inter", False, 0.59),
    ("BAY-LEI (Bun 10/17)", "Bayern Munich", "RasenBallsport Leipzig", False, 0.86),
    ("MCI-PSG (UCL 10/14)", "Manchester City", "Paris Saint Germain", True, 0.68),
    ("ROM-RMA (UCL 10/14)", "Roma", "Real Madrid", True, 0.67),
]

results = {}
print()
for label, h, a, is_ucl, pm_ask in FIX:
    hn, l1 = find_team(h); an_, l2 = find_team(a)
    key = label
    results[key] = {"teams": [hn, an_], "leagues": [l1, l2], "pm_over_ask": pm_ask}
    variants = {}
    for name, LASTW, PRIOR, rho, mode in SWEEPS:
        shr = 0.8 if name.startswith("cross-shrink .8") else (1.1 if name.startswith("cross-shrink 1.1") else 1.0)
        for boost, blabel in ([(0.0, ""), (0.10, "+10%UCLg"), (0.20, "+20%UCLg")] if is_ucl else [(0.0, "")]):
            out = model_game(h, a, LASTW, PRIOR, rho, mode, shr, boost)
            if out is None: continue
            o25, o35, lh, la = out
            variants["%s%s" % (name, blabel)] = {"o25": o25, "lh": lh, "la": la}
    if not variants:
        print("%-24s UNMODELABLE (%s / %s)" % (label, hn, an_))
        continue
    base = [v["o25"] for k, v in variants.items() if "UCLg" not in k]
    boosted = [v["o25"] for k, v in variants.items() if "UCLg" in k]
    allv = [v["o25"] for v in variants.values()]
    lam_h = [v["lh"] for v in variants.values()]; lam_a = [v["la"] for v in variants.values()]
    results[key]["variants"] = variants
    print("%-24s %-22s vs %-22s lam %.2f-%.2f/%.2f-%.2f | O2.5 min=%.3f max=%.3f%s | PM ask %.2f | edge(min) %+.1fc" % (
        label, str(hn)[:22], str(an_)[:22], min(lam_h), max(lam_h), min(lam_a), max(lam_a),
        min(allv), max(allv), (" (boost %.3f-%.3f)" % (min(boosted), max(boosted))) if boosted else "",
        pm_ask, 100 * (min(allv) - pm_ask)))

json.dump(results, open("/home/ubuntu/paper-sim/round4/raw/model_round4.json", "w"), indent=1)
print("saved")
