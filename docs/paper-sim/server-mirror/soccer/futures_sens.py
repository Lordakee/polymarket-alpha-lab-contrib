import json, math, random
from collections import defaultdict

RAW = "/home/ubuntu/paper-sim/soccer/raw/"
def load(lg, se): return json.load(open(RAW + "xg/%s_%s.json" % (lg, se)))
def pois(l, k): return math.exp(-l) * l**k / math.factorial(k)
def grid(lh, la, N=10):
    g = [[pois(lh, i) * pois(la, j) for j in range(N + 1)] for i in range(N + 1)]
    return g

def ratings_for(lg, LASTW, PRIOR, mode):
    if LASTW is None: LASTW = 0.5
    if PRIOR is None: PRIOR = 8
    d25 = load(lg, "2025"); d26 = load(lg, "2026")
    ms = [m for m in d25["dates"] if m.get("isResult")]
    bh = sum(float(m["xG"]["h"]) for m in ms) / len(ms)
    ba = sum(float(m["xG"]["a"]) for m in ms) / len(ms)
    lgf = (bh + ba) / 2
    last = {}
    for t in d25["teams"].values():
        h = t["history"]
        last[t["title"]] = (sum(float(x["xG"]) for x in h) / len(h), sum(float(x["xGA"]) for x in h) / len(h))
    r = {}
    for t in d26["teams"].values():
        h = t["history"]
        name = t["title"]
        if not h: continue
        cf = sum(float(x["xG"]) for x in h) / len(h); ca = sum(float(x["xGA"]) for x in h) / len(h)
        nc = len(h)
        if mode == "cur":
            f = cf; a = ca
        elif mode == "last" and name in last:
            f = last[name][0]; a = last[name][1]
        else:
            lf, la_ = last.get(name, (lgf, lgf))
            f = (nc * cf + LASTW * 38 * lf + PRIOR * lgf) / (nc + LASTW * 38 + PRIOR)
            a = (nc * ca + LASTW * 38 * la_ + PRIOR * lgf) / (nc + LASTW * 38 + PRIOR)
        r[name] = (f / lgf, a / lgf)
    return bh, ba, lgf, r

def sim_league(lg, N_SIM, LASTW, PRIOR, mode, seed):
    random.seed(seed)
    bh, ba, lgf, r = ratings_for(lg, LASTW, PRIOR, mode)
    d26 = load(lg, "2026")
    current_pts = defaultdict(int)
    for m in d26["dates"]:
        if not m.get("isResult"): continue
        gh, ga = int(m["goals"]["h"]), int(m["goals"]["a"])
        current_pts[m["h"]["title"]] += 3 if gh > ga else (1 if gh == ga else 0)
        current_pts[m["a"]["title"]] += 3 if ga > gh else (1 if gh == ga else 0)
    fixtures = []
    for m in d26["dates"]:
        if m.get("isResult"): continue
        h_, a_ = m["h"]["title"], m["a"]["title"]
        if h_ not in r or a_ not in r: continue
        lh = bh * r[h_][0] * r[a_][1]; la = ba * r[a_][0] * r[h_][1]
        g = grid(lh, la)
        acc = []; tot = 0.0
        for i in range(11):
            for j in range(11):
                if g[i][j] > 0:
                    tot += g[i][j]; acc.append((tot, i, j))
        fixtures.append((h_, a_, acc, tot))
    teams = sorted(r.keys())
    wins = defaultdict(float)
    for s in range(N_SIM):
        pts = dict(current_pts)
        for h_, a_, acc, tot in fixtures:
            u = random.random() * tot
            lo, hi = 0, len(acc) - 1
            while lo < hi:
                mid = (lo + hi) // 2
                if acc[mid][0] < u: lo = mid + 1
                else: hi = mid
            _, i, j = acc[lo]
            if i > j: pts[h_] += 3
            elif i == j: pts[h_] += 1; pts[a_] += 1
            else: pts[a_] += 3
        best = max(pts.values())
        champs = [t for t in teams if pts[t] == best]
        for t in champs: wins[t] += 1.0 / len(champs)
    return {t: wins[t] / N_SIM for t in teams}

VARIANTS = [("w.5p8", 0.5, 8, "blend"), ("w1p8", 1.0, 8, "blend"), ("w.25p8", 0.25, 8, "blend"),
            ("w.5p16", 0.5, 16, "blend"), ("w.5p4", 0.5, 4, "blend"),
            ("cur", None, None, "cur"), ("last", None, None, "last")]

print("=== Futures title-prob sensitivity (10k sims each) ===")
targets = {"EPL": ["Arsenal", "Manchester City", "Liverpool", "Chelsea", "Brighton", "Manchester United"],
           "La_liga": ["Barcelona", "Real Madrid", "Atletico Madrid", "Villarreal"]}
out = {}
for lg in ["EPL", "La_liga"]:
    print("--- " + lg)
    hdr = "%-22s" % "variant"
    for t in targets[lg]: hdr += "%16s" % t[:15]
    print(hdr)
    res = {}
    for vname, LASTW, PRIOR, mode in VARIANTS:
        p = sim_league(lg, 10000, LASTW, PRIOR, mode, seed=hash((lg, vname)) % 10**6)
        res[vname] = p
        line = "%-22s" % vname
        for t in targets[lg]: line += "%16.3f" % p.get(t, 0.0)
        print(line)
    out[lg] = res

json.dump(out, open("/home/ubuntu/paper-sim/soccer/futures_sensitivity.json", "w"), indent=1)

# current + last-season tables
print()
print("=== Current 2026/27 tables (played rounds) ===")
for lg in ["EPL", "La_liga"]:
    d26 = load(lg, "2026")
    pts = defaultdict(int); gf = defaultdict(int); ga = defaultdict(int); pl = defaultdict(int)
    for m in d26["dates"]:
        if not m.get("isResult"): continue
        gh, gaa = int(m["goals"]["h"]), int(m["goals"]["a"])
        pl[m["h"]["title"]] += 1; pl[m["a"]["title"]] += 1
        gf[m["h"]["title"]] += gh; ga[m["h"]["title"]] += gaa
        gf[m["a"]["title"]] += gaa; ga[m["a"]["title"]] += gh
        pts[m["h"]["title"]] += 3 if gh > gaa else (1 if gh == gaa else 0)
        pts[m["a"]["title"]] += 3 if gaa > gh else (1 if gh == gaa else 0)
    print(" --- " + lg)
    for t, p in sorted(pts.items(), key=lambda kv: -kv[1]):
        print("   %-24s P=%2d pl=%2d GD=%+d" % (t, p, pl[t], gf[t] - ga[t]))
print()
print("=== 2025/26 final tables (last season) ===")
for lg in ["EPL", "La_liga"]:
    d25 = load(lg, "2025")
    pts = defaultdict(int)
    for m in d25["dates"]:
        if not m.get("isResult"): continue
        gh, ga = int(m["goals"]["h"]), int(m["goals"]["a"])
        pts[m["h"]["title"]] += 3 if gh > ga else (1 if gh == ga else 0)
        pts[m["a"]["title"]] += 3 if ga > gh else (1 if gh == ga else 0)
    print(" --- " + lg + " top6/bottom3")
    srt = sorted(pts.items(), key=lambda kv: -kv[1])
    for t, p in srt[:6]: print("   %-24s %d" % (t, p))
    print("   ...")
    for t, p in srt[-3:]: print("   %-24s %d" % (t, p))
