import json, math
from collections import defaultdict

XG = json.load(open("/home/ubuntu/paper-sim/round5/raw/xg_understat.json"))
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
    o15 = sum(v for t, v in ptot.items() if t >= 2)
    o35 = sum(v for t, v in ptot.items() if t >= 4)
    return o25, o35, o15

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

def model_game(home, away, LASTW, PRIOR, rho, mode, shrink=1.0):
    hn, lgh = find_team(home); an_, lga = find_team(away)
    if lgh is None or lga is None: return None
    bh1, ba1, lgf1, r1 = ratings_for(lgh, LASTW, PRIOR, mode)
    bh2, ba2, lgf2, r2 = ratings_for(lga, LASTW, PRIOR, mode)
    if hn not in r1 or an_ not in r2: return None
    bh = (bh1 + bh2) / 2.0
    ba = (ba1 + ba2) / 2.0
    ah, dh = r1[hn]; aa, da = r2[an_]
    lh = bh * (ah ** shrink) * (da ** shrink)
    la = ba * (aa ** shrink) * (dh ** shrink)
    g = grid(lh, la, 10, rho)
    o25, o35, o15 = outs(g)
    return o25, o35, o15, lh, la

# fixture list with PM executable Over ask / Under bid (CLOB 2026-10-17 ~13:10Z)
FIX = [
    ("EVE-CHE 10/17 11:30Z INPLAY", "Everton", "Chelsea", 0.20, None),
    ("MAC-IPS 10/17 14:00Z",  "Manchester City", "Ipswich", 0.73, None),
    ("BRE-LIV 10/17 14:00Z",  "Brentford", "Liverpool", 0.62, None),
    ("FUL-HUL 10/17 14:00Z",  "Fulham", "Hull", 0.55, None),
    ("NEW-AST 10/17 16:30Z",  "Newcastle United", "Aston Villa", 0.63, None),
    ("BRI-CRY 10/18 13:00Z",  "Brighton", "Crystal Palace", 0.63, None),
    ("BOU-SUN 10/18 13:00Z",  "Bournemouth", "Sunderland", 0.51, None),
    ("LEE-MUN 10/18 13:00Z",  "Leeds", "Manchester United", 0.58, None),
    ("NOT-ARS 10/18 15:30Z",  "Nottingham Forest", "Arsenal", 0.50, None),
    ("TOT-COV 10/19 19:00Z",  "Tottenham", "Coventry", 0.62, None),
]

results = {}
print()
for label, h, a, pm_ask, _ in FIX:
    hn, l1 = find_team(h); an_, l2 = find_team(a)
    results[label] = {"teams": [hn, an_], "leagues": [l1, l2], "pm_over_ask": pm_ask}
    variants = {}
    for name, LASTW, PRIOR, rho, mode in SWEEPS:
        shr = 0.8 if name.startswith("cross-shrink .8") else (1.1 if name.startswith("cross-shrink 1.1") else 1.0)
        out = model_game(h, a, LASTW, PRIOR, rho, mode, shr)
        if out is None: continue
        o25, o35, o15, lh, la = out
        variants[name] = {"o25": round(o25, 4), "o35": round(o35, 4), "o15": round(o15, 4),
                          "lh": round(lh, 3), "la": round(la, 3)}
    if variants:
        vals = [v["o25"] for v in variants.values()]
        results[label]["variants"] = variants
        results[label]["o25_min"] = round(min(vals), 4)
        results[label]["o25_max"] = round(max(vals), 4)
        results[label]["o25_med"] = round(sorted(vals)[len(vals)//2], 4)
        results[label]["edge_min_at_ask"] = round(min(vals) - pm_ask, 4)
        base = list(variants.values())[0]
        results[label]["lambda_base"] = (base["lh"], base["la"])
        print("%-28s lam=%.2f/%.2f O2.5 %s [%s-%s] ask=%.2f -> min-edge %+.3f" % (
            label, base["lh"], base["la"], results[label]["o25_med"],
            results[label]["o25_min"], results[label]["o25_max"], pm_ask,
            results[label]["edge_min_at_ask"]))

json.dump(results, open("/home/ubuntu/paper-sim/round5/raw/model_round5.json", "w"), indent=1)
print("saved model_round5.json")
