"""Round-21 EFL Cup Wed sub-scan model: 10-variant xG-Poisson (same methodology as r15/r19/r20/seriea21).
Rotation-blind season xG ratings from understat EPL 2025+2026 (through 2026-10-24, seeded from r20 file).
All 5 ties are EPL-vs-EPL so model coverage exists for every tie."""
import json, math, time
from collections import defaultdict

RAW = "/home/ubuntu/paper-sim/round21/raw"
XG = json.load(open(RAW + "/xg_understat_21.json"))
RHO_DC = -0.1

TIES = [("Manchester City", "Brighton and Hove Albion", "mnc-bha", "19:30Z"),
        ("AFC Bournemouth", "Aston Villa", "bor-ast", "19:45Z"),
        ("Fulham", "Crystal Palace", "ful-cry", "19:45Z"),
        ("Sunderland", "Brentford", "sun-bre", "19:45Z"),
        ("Liverpool", "Chelsea", "liv-cfc", "20:00Z")]

def load(lg, se): return XG["%s_%s" % (lg, se)]

_c = {}
def ratings_for(lg, LASTW, PRIOR, mode):
    key = (lg, LASTW, PRIOR, mode)
    if key in _c: return _c[key]
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
        if mode == "cur": f, a = cf, ca
        elif mode == "last": f, a = last.get(name, (lgf, lgf))
        else:
            lf, la_ = last.get(name, (lgf, lgf))
            f = (nc * cf + LASTW * 38 * lf + PRIOR * lgf) / (nc + LASTW * 38 + PRIOR)
            a = (nc * ca + LASTW * 38 * la_ + PRIOR * lgf) / (nc + LASTW * 38 + PRIOR)
        r[name] = (f / lgf, a / lgf)
    _c[key] = (bh, ba, lgf, r)
    return _c[key]

SWEEPS = [("blend w=.5 p=8 rho0", 0.5, 8, 0.0, "blend"), ("blend w=.5 p=8 DC", 0.5, 8, RHO_DC, "blend"),
 ("blend w=1.0 p=8", 1.0, 8, 0.0, "blend"), ("blend w=.25 p=8", 0.25, 8, 0.0, "blend"),
 ("blend w=.5 p=16", 0.5, 16, 0.0, "blend"), ("blend w=.5 p=4", 0.5, 4, 0.0, "blend"),
 ("current-only", None, None, 0.0, "cur"), ("last-only", None, None, 0.0, "last"),
 ("cross-shrink .8", 0.5, 8, 0.0, "blend"), ("cross-shrink 1.1", 0.5, 8, 0.0, "blend")]

def pois(l, k): return math.exp(-l) * l ** k / math.factorial(k)

def gridf(lh, la, N=10, rho=0.0):
    g = [[pois(lh, i) * pois(la, j) for j in range(N + 1)] for i in range(N + 1)]
    if rho:
        g[0][0] *= max(1 - lh * la * rho, .01); g[0][1] *= max(1 + lh * rho, .01)
        g[1][0] *= max(1 + la * rho, .01); g[1][1] *= max(1 - rho, .01)
    s = sum(sum(r_) for r_ in g)
    return [[v / s for v in row] for row in g]

def variant_outputs(lh, la, rho):
    g = gridf(lh, la, 10, rho)
    ph = sum(g[i][j] for i in range(11) for j in range(11) if i > j)
    pd = sum(g[i][i] for i in range(11)); pa = 1.0 - ph - pd
    tot = defaultdict(float); btts = 0.0
    for i in range(11):
        for j in range(11):
            p = g[i][j]; tot[i + j] += p
            if i >= 1 and j >= 1: btts += p
    return {"H": ph, "D": pd, "A": pa, "btts": btts,
            "o25": sum(v for k, v in tot.items() if k >= 3), "o35": sum(v for k, v in tot.items() if k >= 4)}

def lambdas(home, away, LASTW, PRIOR, mode, shrink=1.0):
    bh, ba, lgf, r = ratings_for("EPL", LASTW, PRIOR, mode)
    ah, dh = r.get(home, (1.0, 1.0)); aa, da = r.get(away, (1.0, 1.0))
    return bh * (ah ** shrink) * (da ** shrink), ba * (aa ** shrink) * (dh ** shrink)

def med(v):
    s = sorted(v); n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0

out = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
       "scan": "efl-cup", "round": 21, "paper_only": True,
       "note": "rotation-blind season xG; news-concurrence required per r20/r21 rules",
       "xg_base": "round21/raw/xg_understat_21.json EPL through 2026-10-24 (75 games)",
       "matches": {}}

for home, away, code, ko in TIES:
    per = []
    for name, LASTW, PRIOR, rho, mode in SWEEPS:
        shrink = 0.8 if name.startswith("cross-shrink .8") else (1.1 if name.startswith("cross-shrink 1.1") else 1.0)
        lh, la = lambdas(home, away, LASTW, PRIOR, mode, shrink)
        per.append({"name": name, "lh": round(lh,3), "la": round(la,3),
                    "o": {k: round(v,4) for k, v in variant_outputs(lh, la, rho).items()}})
    def vs(k): return [v["o"][k] for v in per]
    rec = {"kickoff": "2026-10-28T" + ko, "code": code,
           "lambda_home": round(med([v["lh"] for v in per]),3), "lambda_away": round(med([v["la"] for v in per]),3),
           "model_1x2_med": {"H": round(med(vs("H")),4), "D": round(med(vs("D")),4), "A": round(med(vs("A")),4)},
           "fair": {"o25": {"med": round(med(vs("o25")),4), "min": round(min(vs("o25")),4), "max": round(max(vs("o25")),4)},
                    "o35": {"med": round(med(vs("o35")),4), "min": round(min(vs("o35")),4), "max": round(max(vs("o35")),4)},
                    "btts": {"med": round(med(vs("btts")),4), "min": round(min(vs("btts")),4), "max": round(max(vs("btts")),4)}}}
    out["matches"]["%s vs %s" % (home, away)] = rec
    print("%s vs %s | lam %.2f-%.2f | H/D/A %.3f/%.3f/%.3f | O2.5 %.3f [%.3f-%.3f] | O3.5 %.3f | BTTS %.3f" % (
        home, away, rec["lambda_home"], rec["lambda_away"],
        rec["model_1x2_med"]["H"], rec["model_1x2_med"]["D"], rec["model_1x2_med"]["A"],
        rec["fair"]["o25"]["med"], rec["fair"]["o25"]["min"], rec["fair"]["o25"]["max"],
        rec["fair"]["o35"]["med"], rec["fair"]["btts"]["med"]))

json.dump(out, open(RAW + "/eflcup_model21.json", "w"), indent=1)
print("saved", RAW + "/eflcup_model21.json")
