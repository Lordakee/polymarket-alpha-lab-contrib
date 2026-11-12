import json, math, random
from collections import defaultdict

random.seed(7)
RAW = "/home/ubuntu/paper-sim/soccer/raw/"

def load(lg, se):
    return json.load(open(RAW + "xg/%s_%s.json" % (lg, se)))

LEAGUES = ["EPL", "La_liga"]

# ---------- A) current-season league environment ----------
print("=== A) League scoring environment (played 2026/27) vs 2025/26 ===")
for lg in LEAGUES:
    for se in ["2025", "2026"]:
        d = load(lg, se)
        ms = [m for m in d["dates"] if m.get("isResult") and m.get("xG") and m["xG"]["h"]]
        gl = sum(int(m["goals"]["h"]) + int(m["goals"]["a"]) for m in ms) / len(ms)
        xg = sum(float(m["xG"]["h"]) + float(m["xG"]["a"]) for m in ms) / len(ms)
        hxg = sum(float(m["xG"]["h"]) for m in ms) / len(ms)
        axg = sum(float(m["xG"]["a"]) for m in ms) / len(ms)
        print("  %s %s/%s: n=%d goals/match=%.2f xG/match=%.2f (home %.2f / away %.2f)" %
              (lg, se[:4], int(se[:4]) + 1, len(ms), gl, xg, hxg, axg))

# ---------- B) calibration: walk-forward with last-season ratings ----------
def pois(l, k): return math.exp(-l) * l**k / math.factorial(k)

def grid(lh, la, N=10, rho=0.0):
    g = [[pois(lh, i) * pois(la, j) for j in range(N + 1)] for i in range(N + 1)]
    if rho:
        g[0][0] *= max(1 - lh * la * rho, .01); g[0][1] *= max(1 + lh * rho, .01)
        g[1][0] *= max(1 + la * rho, .01); g[1][1] *= max(1 - rho, .01)
    s = sum(sum(r) for r in g)
    return [[v / s for v in row] for row in g]

def outs(g):
    ph = sum(g[i][j] for i in range(len(g)) for j in range(len(g)) if i > j)
    pd = sum(g[i][i] for i in range(len(g)))
    pa = sum(g[i][j] for i in range(len(g)) for j in range(len(g)) if i < j)
    return ph, pd, pa

print()
print("=== B) Calibration on played 2026/27 (ratings: last season only, no lookahead) ===")
for lg in LEAGUES:
    d25 = load(lg, "2025"); d26 = load(lg, "2026")
    lgf = sum(float(m["xG"]["h"]) + float(m["xG"]["a"]) for m in d25["dates"] if m.get("isResult")) / (2 * 380)
    bh = sum(float(m["xG"]["h"]) for m in d25["dates"] if m.get("isResult")) / 380
    ba = sum(float(m["xG"]["a"]) for m in d25["dates"] if m.get("isResult")) / 380
    last = {t["title"]: (sum(float(x["xG"]) for x in t["history"]) / 38,
                         sum(float(x["xGA"]) for x in t["history"]) / 38) for t in d25["teams"].values()}
    bins_fav = defaultdict(lambda: [0.0, 0])   # model P(fav) -> realized fav wins
    draws = [0.0, 0]
    dogs = [0.0, 0]
    for m in d26["dates"]:
        if not m.get("isResult"): continue
        h_, a_ = m["h"]["title"], m["a"]["title"]
        if h_ not in last or a_ not in last: continue
        lh = bh * (last[h_][0] / lgf) * (last[a_][1] / lgf)
        la = ba * (last[a_][0] / lgf) * (last[h_][1] / lgf)
        ph, pd_, pa = outs(grid(lh, la))
        gh, ga = int(m["goals"]["h"]), int(m["goals"]["a"])
        fav_p = max(ph, pa); fav_is_home = ph >= pa
        fav_won = (gh > ga) if fav_is_home else (gh < ga)
        b = min(int(fav_p * 10), 9)
        bins_fav[b][0] += fav_p; bins_fav[b][1] += 1
        # realized accumulate
        bins_fav[b].append(1 if fav_won else 0)
        draws[0] += pd_; draws[1] += 1
        draws.append(1 if gh == ga else 0)
        dog_p = min(ph, pa); dog_won = (gh < ga) if fav_is_home else (gh > ga)
        dogs[0] += dog_p; dogs[1] += 1
        dogs.append(1 if dog_won else 0)
    n = draws[1]
    print("  %s n=%d" % (lg, n))
    print("    DRAWS : model avg=%.3f  realized=%.3f" % (draws[0] / n, sum(draws[2:]) / n))
    print("    DOGWIN: model avg=%.3f  realized=%.3f" % (dogs[0] / n, sum(dogs[2:]) / n))
    for b in sorted(bins_fav):
        v = bins_fav[b]
        cnt = v[1]; mp = v[0] / cnt; real = sum(v[2:]) / cnt
        print("    fav bin %d.%d-%d.0: model=%.3f realized=%.3f (n=%d)" % (b // 10, b % 10, b // 10 + 1, mp, real, cnt))

# ---------- C) sensitivity sweep for candidate trades ----------
print()
print("=== C) Weighting sensitivity of candidate edges (net of spread, buy at ask) ===")

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

FIX = [
    ("epl-mun-tot-2026-10-10", "EPL", "Manchester United", "Tottenham", 0.57, 0.604),
    ("epl-cry-not-2026-10-11", "EPL", "Crystal Palace", "Nottingham Forest", 0.35, 0.480),
    ("lal-bar-get-2026-10-10", "La_liga", "Barcelona", "Getafe", None, None),
    ("lal-rea-vil-2026-10-10", "La_liga", "Real Madrid", "Villarreal", None, None),
]

# candidate trades: (label, fixture idx, side/market, executable cost (buy YES ask) or NO-cost)
# will compute model prob under each parameter set
def model_probs(lg, home, away, LASTW, PRIOR, rho, mode):
    bh, ba, lgf, r = ratings_for(lg, LASTW, PRIOR, mode)
    lh = bh * r[home][0] * r[away][1]
    la = ba * r[away][0] * r[home][1]
    g = grid(lh, la, 10, rho)
    ph, pd_, pa = outs(g)
    ptot = defaultdict(float)
    for i in range(11):
        for j in range(11):
            ptot[i + j] += g[i][j]
    o25 = sum(v for t, v in ptot.items() if t >= 3)
    return ph, pd_, pa, o25, lh, la

SWEEPS = [("blend w=.5 p=8 rho0", 0.5, 8, 0.0, "blend"),
          ("blend w=.5 p=8 DC", 0.5, 8, -0.08, "blend"),
          ("blend w=1.0 p=8", 1.0, 8, 0.0, "blend"),
          ("blend w=.25 p=8", 0.25, 8, 0.0, "blend"),
          ("blend w=.5 p=16", 0.5, 16, 0.0, "blend"),
          ("blend w=.5 p=4", 0.5, 4, 0.0, "blend"),
          ("current-only", None, None, 0.0, "cur"),
          ("last-only", None, None, 0.0, "last")]

CANDS = [
    ("MUN win YES @0.57", "EPL", "Manchester United", "Tottenham", lambda ph, pd, pa, o: ph, 0.57),
    ("CP win YES @0.35", "EPL", "Crystal Palace", "Nottingham Forest", lambda ph, pd, pa, o: ph, 0.35),
    ("CP-FOR O2.5 YES @0.51", "EPL", "Crystal Palace", "Nottingham Forest", lambda ph, pd, pa, o: o, 0.51),
    ("BAR win NO @0.11", "La_liga", "Barcelona", "Getafe", lambda ph, pd, pa, o: 1 - ph, 0.11),
    ("BAR-GET draw YES @0.073", "La_liga", "Barcelona", "Getafe", lambda ph, pd, pa, o: pd, 0.073),
    ("BAR-GET BTTS YES @0.44", "La_liga", "Barcelona", "Getafe", None, 0.44),
    ("VIL win YES @0.13", "La_liga", "Real Madrid", "Villarreal", lambda ph, pd, pa, o: pa, 0.13),
    ("REA-VIL draw YES @0.16", "La_liga", "Real Madrid", "Villarreal", lambda ph, pd, pa, o: pd, 0.16),
]

def btts_prob(lg, home, away, LASTW, PRIOR, rho, mode):
    bh, ba, lgf, r = ratings_for(lg, LASTW, PRIOR, mode)
    lh = bh * r[home][0] * r[away][1]; la = ba * r[away][0] * r[home][1]
    return (1 - math.exp(-lh)) * (1 - math.exp(-la))

print("%-26s" % "trade", "".join("%22s" % s[0][:21] for s in SWEEPS))
for label, lg, home, away, fn, cost in CANDS:
    vals = []
    for name, LASTW, PRIOR, rho, mode in SWEEPS:
        if fn is not None:
            ph, pd_, pa, o25, lh, la = model_probs(lg, home, away, LASTW, PRIOR, rho, mode)
            p = fn(ph, pd_, pa, o25)
        else:
            p = btts_prob(lg, home, away, LASTW, PRIOR, rho, mode)
        vals.append(p - cost)
    print("%-26s" % label, "".join("%+22.3f" % v for v in vals))

# ---------- D) season futures Monte Carlo ----------
print()
print("=== D) Season futures Monte Carlo (EPL + LaLiga 2026/27 champion) ===")
def sim_league(lg, N_SIM=20000):
    bh, ba, lgf, r = ratings_for(lg, 0.5, 8, "blend")
    d26 = load(lg, "2026")
    current_pts = defaultdict(int)
    played_pairs = defaultdict(int)
    for m in d26["dates"]:
        if not m.get("isResult"): continue
        gh, ga = int(m["goals"]["h"]), int(m["goals"]["a"])
        current_pts[m["h"]["title"]] += 3 if gh > ga else (1 if gh == ga else 0)
        current_pts[m["a"]["title"]] += 3 if ga > gh else (1 if gh == ga else 0)
        played_pairs[(m["h"]["title"], m["a"]["title"])] += 1
    fixtures = []
    for m in d26["dates"]:
        if m.get("isResult"): continue
        h_, a_ = m["h"]["title"], m["a"]["title"]
        if h_ not in r or a_ not in r: continue
        lh = bh * r[h_][0] * r[a_][1]; la = ba * r[a_][0] * r[h_][1]
        g = grid(lh, la, 10)
        # precompute cumulative outcome per score-line
        cum = []
        for i in range(11):
            for j in range(11):
                if g[i][j] > 0: cum.append((g[i][j], i, j))
        tot = 0.0; acc = []
        for p, i, j in cum:
            tot += p; acc.append((tot, i, j))
        fixtures.append((h_, a_, acc, tot))
    teams = sorted(r.keys())
    wins = defaultdict(int)
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

sims = {}
for lg in LEAGUES:
    sims[lg] = sim_league(lg)
    print("  %s simulated (top8):" % lg)
    for t, p in sorted(sims[lg].items(), key=lambda kv: -kv[1])[:8]:
        print("     %-26s %.3f" % (t, p))
json.dump(sims, open("/home/ubuntu/paper-sim/soccer/sim_champions.json", "w"), indent=1)

# market futures comparison
cand = json.load(open(RAW + "candidate_events.json"))
FUT = {"epl-2027-champion-20260701200428749": "EPL", "laliga-2027-champion-20260701200737375": "La_liga",
       "uefa-champions-league-2027-champion-20260701202025549": "UCL",
       "serie-a-2027-champion-20260701200118390": "SA", "ligue-1-2027-champion-20260701201053335": "L1"}

def fnum(x):
    try: return float(x)
    except Exception: return None

print()
print("=== E) Futures: model vs market ===")
for slug, key in FUT.items():
    ev = cand.get(slug)
    if not ev: print("missing", slug); continue
    rows = []
    s_sum = a_sum = 0.0
    for m in ev["markets"]:
        pr = m["prices"]
        mid = None
        if pr:
            try: mid = float(pr[0])
            except Exception: pass
        bid, ask = fnum(m["bestBid"]), fnum(m["bestAsk"])
        if mid: s_sum += mid
        if ask: a_sum += ask
        rows.append((m["q"], mid, bid, ask, m["tokens"]))
    print()
    print("--- %s (open=%d) sum_mids=%.3f sum_asks=%.3f" % (ev["title"], len(rows), s_sum, a_sum))
    lgkey = None
    if key == "EPL": lgkey = "EPL"
    if key == "La_liga": lgkey = "La_liga"
    rows.sort(key=lambda x: -(x[1] or 0))
    for q, mid, bid, ask, toks in rows[:12]:
        model = ""
        if lgkey:
            # fuzzy match team in sim
            for t, p in sims[lgkey].items():
                if t.split()[0].lower() in str(q).lower() or str(q).lower().find(t.lower()[:8]) >= 0:
                    model = " model=%.3f" % p
                    break
        print("   %-58s mid=%s bid=%s ask=%s%s" % (str(q)[:58], mid, bid, ask, model))
