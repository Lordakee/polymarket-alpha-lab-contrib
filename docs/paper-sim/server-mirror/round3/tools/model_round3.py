import json, math
from collections import defaultdict

RAW = "/home/ubuntu/paper-sim/round3/raw/xg/"
LEAGUES = ["EPL", "La_liga", "Serie_A", "Bundesliga", "Ligue_1"]

def load(lg, se):
    return json.load(open(RAW + "%s_%s.json" % (lg, se)))

# league env
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
    ph = sum(g[i][j] for i in range(len(g)) for j in range(len(g)) if i > j)
    pd = sum(g[i][i] for i in range(len(g)))
    pa = sum(g[i][j] for i in range(len(g)) for j in range(len(g)) if i < j)
    ptot = defaultdict(float)
    for i in range(len(g)):
        for j in range(len(g)):
            ptot[i + j] += g[i][j]
    o25 = sum(v for t, v in ptot.items() if t >= 3)
    o35 = sum(v for t, v in ptot.items() if t >= 4)
    btts = sum(g[i][j] for i in range(1, len(g)) for j in range(1, len(g)))
    return ph, pd, pa, o25, o35, btts

TEAM_LEAGUE = {}
for lg in LEAGUES:
    for t in load(lg, "2026")["teams"].values():
        TEAM_LEAGUE[t["title"]] = lg

# understat names
NAME_FIX = {"Atletico Madrid": "Atletico Madrid", "Manchester United": "Manchester United"}

def model_game(home, away, LASTW, PRIOR, rho, mode, shrink=1.0, ucl_boost=0.0):
    lgh = TEAM_LEAGUE.get(home); lga = TEAM_LEAGUE.get(away)
    if lgh is None or lga is None: return None
    bh1, ba1, lgf1, r1 = ratings_for(lgh, LASTW, PRIOR, mode)
    bh2, ba2, lgf2, r2 = ratings_for(lga, LASTW, PRIOR, mode)
    if home not in r1 or away not in r2: return None
    bh = (bh1 + bh2) / 2.0
    ba = (ba1 + ba2) / 2.0
    ah, dh = r1[home]; aa, da = r2[away]
    lh = bh * (ah ** shrink) * (da ** shrink) * (1 + ucl_boost)
    la = ba * (aa ** shrink) * (dh ** shrink) * (1 + ucl_boost)
    g = grid(lh, la, 10, rho)
    ph, pd, pa, o25, o35, btts = outs(g)
    return ph, pd, pa, o25, o35, btts, lh, la

GAMES = [
    ("Atletico Madrid", "Manchester United"),
    ("Arsenal", "Lille"),
    ("Inter", "Internazionale-check"),
]
# understat titles check
for lg in LEAGUES:
    for t in load(lg, "2026")["teams"].values():
        for probe in ["Atletico", "Manchester", "Arsenal", "Lille", "Inter", "Barcelona"]:
            if probe.lower() in t["title"].lower():
                print("NAME %-10s -> %s" % (lg, t["title"]))

results = {}
for home, away in [("Atletico Madrid", "Manchester United"), ("Arsenal", "Lille")]:
    key = "%s vs %s" % (home, away)
    results[key] = {}
    print()
    print("==== %s" % key)
    for name, LASTW, PRIOR, rho, mode in SWEEPS:
        shr = 0.8 if name.startswith("cross-shrink .8") else (1.1 if name.startswith("cross-shrink 1.1") else 1.0)
        for boost, blabel in [(0.0, ""), (0.10, "+10%UCLg"), (0.20, "+20%UCLg")]:
            out = model_game(home, away, LASTW, PRIOR, rho, mode, shr, boost)
            if out is None:
                print("  UNRATABLE", name); continue
            ph, pd, pa, o25, o35, btts, lh, la = out
            results[key]["%s%s" % (name, blabel)] = {"o25": o25, "o35": o35, "btts": btts, "ph": ph, "pd": pd, "pa": pa, "lh": lh, "la": la}
        r0 = results[key].get("%s" % name)
        if r0:
            print("  %-24s lam=%.2f/%.2f tot=%.2f O2.5=%.3f O3.5=%.3f BTTS=%.3f" % (
                name, r0["lh"], r0["la"], r0["lh"] + r0["la"], r0["o25"], r0["o35"], r0["btts"]))

json.dump(results, open("/home/ubuntu/paper-sim/round3/raw/model_cross.json", "w"), indent=1)
print()
print("saved model_cross.json")
# summary ranges
for key, variants in results.items():
    o25s = [v["o25"] for k, v in variants.items() if not k.split("+")[0].startswith(("current", "last"))]
    o25s_boost = [v["o25"] for k, v in variants.items() if "UCLg" in k]
    base = [v["o25"] for k, v in variants.items() if "UCLg" not in k]
    print("%s: O2.5 base min=%.3f max=%.3f | with UCL boost min=%.3f max=%.3f" % (
        key, min(base), max(base), min(o25s_boost), max(o25s_boost)))
