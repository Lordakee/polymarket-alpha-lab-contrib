import json, math, random
from collections import defaultdict

random.seed(20261010)
RAW = "/home/ubuntu/paper-sim/soccer/raw/"

# ---------- load xG ----------
def load(lg, se):
    return json.load(open(RAW + "xg/%s_%s.json" % (lg, se)))

LEAGUES = {"EPL": "epl", "La_liga": "lal"}

def league_profile(lg):
    d25 = load(lg, "2025"); d26 = load(lg, "2026")
    # base home/away xG from completed 2025/26
    hs, as_ = [], []
    for m in d25["dates"]:
        if m.get("isResult") and m.get("xG") and m["xG"]["h"]:
            hs.append(float(m["xG"]["h"])); as_.append(float(m["xG"]["a"]))
    base_home = sum(hs)/len(hs); base_away = sum(as_)/len(as_)
    lg_for = (base_home+base_away)/2.0
    # last-season per-team rates
    last = {}
    for t in d25["teams"].values():
        h = t["history"]
        last[t["title"]] = (sum(float(x["xG"]) for x in h)/len(h),
                            sum(float(x["xGA"]) for x in h)/len(h))
    # current-season per-team rates
    cur = {}
    for t in d26["teams"].values():
        h = t["history"]
        if h:
            cur[t["title"]] = (sum(float(x["xG"]) for x in h)/len(h),
                               sum(float(x["xGA"]) for x in h)/len(h), len(h))
    # blended ratings
    PRIOR = 8.0; LASTW = 0.5
    ratings = {}
    for name, (c_f, c_a, n_c) in cur.items():
        if name in last:
            l_f, l_a = last[name]
            f = (n_c*c_f + LASTW*38*l_f + PRIOR*lg_for) / (n_c + LASTW*38 + PRIOR)
            a = (n_c*c_a + LASTW*38*l_a + PRIOR*lg_for) / (n_c + LASTW*38 + PRIOR)
            src = "S"
        else:
            f = (n_c*c_f + PRIOR*lg_for) / (n_c + PRIOR)
            a = (n_c*c_a + PRIOR*lg_for) / (n_c + PRIOR)
            src = "P"  # promoted/new: no prior EPL season
        ratings[name] = {"att": f/lg_for, "def": a/lg_for, "src": src,
                         "cur_n": n_c, "cur_for": c_f, "cur_ag": c_a,
                         "last_for": last.get(name, (None, None))[0],
                         "last_ag": last.get(name, (None, None))[1]}
    return {"base_home": base_home, "base_away": base_away, "lg_for": lg_for,
            "ratings": ratings, "d26": d26, "d25": d25}

PROF = {lg: league_profile(lg) for lg in LEAGUES}

# ---------- Poisson machinery ----------
def pois(l, k):
    return math.exp(-l) * l**k / math.factorial(k)

def grid(lh, la, N=10, rho=0.0):
    g = [[pois(lh, i)*pois(la, j) for j in range(N+1)] for i in range(N+1)]
    if rho:
        # Dixon-Coles low-score adjustment
        t00 = 1 - lh*la*rho; t01 = 1 + lh*rho; t10 = 1 + la*rho; t11 = 1 - rho
        g[0][0] *= max(t00, 0.01); g[0][1] *= max(t01, 0.01)
        g[1][0] *= max(t10, 0.01); g[1][1] *= max(t11, 0.01)
    s = sum(sum(r) for r in g)
    return [[v/s for v in row] for row in g]

def outcomes(g):
    ph = sum(g[i][j] for i in range(len(g)) for j in range(len(g)) if i > j)
    pd = sum(g[i][i] for i in range(len(g)))
    pa = sum(g[i][j] for i in range(len(g)) for j in range(len(g)) if i < j)
    return ph, pd, pa

def match_lambdas(prof, home, away):
    r = prof["ratings"]
    lh = prof["base_home"] * r[home]["att"] * r[away]["def"]
    la = prof["base_away"] * r[away]["att"] * r[home]["def"]
    return lh, la

# ---------- sanity: walk-forward on played 2026/27 matches ----------
print("=== Model sanity: predict played 2026/27 matches using LAST-SEASON-only ratings ===")
for lg in LEAGUES:
    d25 = load(lg, "2025"); d26 = load(lg, "2026")
    hs = [float(m["xG"]["h"]) for m in d25["dates"] if m.get("isResult") and m.get("xG") and m["xG"]["h"]]
    as_ = [float(m["xG"]["a"]) for m in d25["dates"] if m.get("isResult") and m.get("xG") and m["xG"]["h"]]
    bh = sum(hs)/len(hs); ba = sum(as_)/len(as_); lgf = (bh+ba)/2
    last = {t["title"]: (sum(float(x["xG"]) for x in t["history"])/38,
                         sum(float(x["xGA"]) for x in t["history"])/38) for t in d25["teams"].values()}
    n_ok = 0; logloss = 0.0; hits = 0; n_act = 0
    for m in d26["dates"]:
        if not m.get("isResult"): continue
        h_, a_ = m["h"]["title"], m["a"]["title"]
        if h_ not in last or a_ not in last: continue
        lh = bh * (last[h_][0]/lgf) * (last[a_][1]/lgf)
        la = ba * (last[a_][0]/lgf) * (last[h_][1]/lgf)
        ph, pd_, pa = outcomes(grid(lh, la))
        gh, ga = int(m["goals"]["h"]), int(m["goals"]["a"])
        actual = 0 if gh > ga else (1 if gh == ga else 2)
        p = [ph, pd_, pa][actual]
        logloss += -math.log(max(p, 1e-9)); n_ok += 1
        pick = [ph, pd_, pa].index(max(ph, pd_, pa))
        if pick == actual: hits += 1
        n_act += 1
    base_ll = 0.0
    cnts = [0, 0, 0]
    for m in d26["dates"]:
        if m.get("isResult"):
            gh, ga = int(m["goals"]["h"]), int(m["goals"]["a"])
            cnts[0 if gh > ga else (1 if gh == ga else 2)] += 1
    tot = sum(cnts)
    freq = [c/tot for c in cnts]
    for m in d26["dates"]:
        if not m.get("isResult"): continue
        gh, ga = int(m["goals"]["h"]), int(m["goals"]["a"])
        base_ll += -math.log(max(freq[0 if gh > ga else (1 if gh == ga else 2)], 1e-9))
    print("  %s: n=%d model_logloss=%.4f freq_logloss=%.4f top-pick_acc=%.1f%% (freq H/D/A=%.2f/%.2f/%.2f)" %
          (lg, n_ok, logloss/n_ok, base_ll/n_ok, 100.0*hits/n_act, *freq))

# ---------- match valuation ----------
FIX = [
    # slug_base, league, home, away
    ("epl-mun-tot-2026-10-10", "EPL", "Manchester United", "Tottenham"),
    ("epl-cry-not-2026-10-11", "EPL", "Crystal Palace", "Nottingham Forest"),
    ("lal-bar-get-2026-10-10", "La_liga", "Barcelona", "Getafe"),
    ("lal-rea-vil-2026-10-10", "La_liga", "Real Madrid", "Villarreal"),
]

books = json.load(open(RAW + "match_books.json"))
fam = json.load(open(RAW + "family_events.json"))

def fnum(x):
    try: return float(x)
    except Exception: return None

print()
print("=== Match valuations (model vs CLOB executable) ===")
results = {}
for base, lg, home, away in FIX:
    prof = PROF[lg]
    r = prof["ratings"]
    lh, la = match_lambdas(prof, home, away)
    g0 = grid(lh, la, 10, 0.0)
    gdc = grid(lh, la, 10, -0.08)
    ph, pd_, pa = outcomes(g0)
    ph2, pd2, pa2 = outcomes(gdc)
    print()
    print("--- %s vs %s (%s)  lambda_home=%.2f lambda_away=%.2f" % (home, away, lg, lh, la))
    print("    ratings: %s att=%.2f def=%.2f (n=%d cur %0.2f/%0.2f, last %s/%s %s) | %s att=%.2f def=%.2f (n=%d cur %0.2f/%0.2f, last %s/%s %s)" % (
        home, r[home]["att"], r[home]["def"], r[home]["cur_n"], r[home]["cur_for"], r[home]["cur_ag"],
        ("%.2f" % r[home]["last_for"]) if r[home]["last_for"] else "-", ("%.2f" % r[home]["last_ag"]) if r[home]["last_ag"] else "-", r[home]["src"],
        away, r[away]["att"], r[away]["def"], r[away]["cur_n"], r[away]["cur_for"], r[away]["cur_ag"],
        ("%.2f" % r[away]["last_for"]) if r[away]["last_for"] else "-", ("%.2f" % r[away]["last_ag"]) if r[away]["last_ag"] else "-", r[away]["src"]))
    # 1X2 from books
    ev = books[base]
    rows = []
    for mk in ev["markets"]:
        q = mk["q"] or ""
        if "win on" in q and home in q: side = "H"
        elif "win on" in q and away in q: side = "A"
        elif "draw" in q: side = "D"
        else: continue
        b0 = mk["book"][0] if mk.get("book") else {}
        bid = float(b0["bids"][0]["price"]) if b0.get("bids") else None
        ask = float(b0["asks"][0]["price"]) if b0.get("asks") else None
        bsz = float(b0["bids"][0]["size"]) if b0.get("bids") else 0
        asz = float(b0["asks"][0]["size"]) if b0.get("asks") else 0
        rows.append((side, bid, ask, bsz, asz))
    for side, bid, ask, bsz, asz in rows:
        p = {"H": ph, "D": pd_, "A": pa}[side]
        pdc = {"H": ph2, "D": pd2, "A": pa2}[side]
        lbl = {"H": "1 " + home, "D": "X draw", "A": "2 " + away}[side]
        if bid is None: continue
        edge_yes = p - ask          # buy YES at ask
        edge_no = bid - p           # buy NO at (1-bid)
        print("    %-28s model=%.3f (DC %.3f) bid=%.3f ask=%.3f  edge_buy_yes=%+.3f edge_buy_no=%+.3f  depth(bid/ask sz)=%d/%d" %
              (lbl[:28], p, pdc, bid, ask, edge_yes, edge_no, bsz, asz))
    results[base] = {"lh": lh, "la": la, "g0": g0, "gdc": gdc}

# family markets for mun-tot and cry-not, bar-get, rea-vil: O/U + BTTS + exact scores vs model
print()
print("=== O/U, BTTS, exact-score vs model ===")
for base, lg, home, away in FIX:
    g = results[base]["g0"]
    N = 10
    p_tot = defaultdict(float)
    for i in range(N+1):
        for j in range(N+1):
            p_tot[i+j] += g[i][j]
    p_btts = sum(g[i][j] for i in range(1, N+1) for j in range(1, N+1))
    p_over = {k: sum(v for t, v in p_tot.items() if t >= k) for k in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]}
    print()
    print("--- %s vs %s: model P(BTTS)=%.3f  P(o2.5)=%.3f" % (home, away, p_btts, p_over[2.5]))
    fe = fam.get(base + "-more-markets")
    if fe:
        for m in fe["markets"]:
            q = str(m["q"] or "")
            bid, ask = fnum(m["bestBid"]), fnum(m["bestAsk"])
            if bid is None or ask is None: continue
            mid = None
            pr = m["prices"]
            if pr:
                try: mid = float(pr[0])
                except Exception: pass
            val = None; kind = ""
            if ": O/U 2.5" in q and "1st Half" not in q and "2nd Half" not in q: val = p_over[2.5]; kind = "O2.5"
            elif ": O/U 1.5" in q and "1st Half" not in q and "2nd Half" not in q: val = p_over[1.5]; kind = "O1.5"
            elif ": O/U 3.5" in q and "1st Half" not in q and "2nd Half" not in q: val = p_over[3.5]; kind = "O3.5"
            elif "Both Teams to Score" == q.split(": ")[-1] + (":" if False else "") or q.endswith("Both Teams to Score"): val = p_btts; kind = "BTTS"
            if val is not None:
                print("    %-6s model=%.3f bid=%.3f ask=%.3f  edge_yes=%+.3f edge_no=%+.3f" %
                      (kind, val, bid, ask, val - ask, bid - val))
    fe = fam.get(base + "-exact-score")
    if fe:
        grid_disp = []
        for m in fe["markets"]:
            q = str(m["q"] or "")
            bid, ask = fnum(m["bestBid"]), fnum(m["bestAsk"])
            mid = None
            pr = m["prices"]
            if pr:
                try: mid = float(pr[0])
                except Exception: pass
            import re
            mt = re.search(r"(\d+) - (\d+)", q)
            if mt and mid is not None:
                hs_, as_ = int(mt.group(1)), int(mt.group(2))
                if hs_ <= 5 and as_ <= 5:
                    grid_disp.append((hs_, as_, mid, bid, ask, g[hs_][as_]))
        print("    exact scores (<=5 goals each): market_mid vs model")
        for hs_, as_, mid, bid, ask, mp in sorted(grid_disp, key=lambda x: -x[2])[:12]:
            eb = mp - ask if ask else None
            en = bid - mp if bid else None
            print("      %d-%d  mkt=%.3f bid=%s ask=%s model=%.3f  edge_yes=%s edge_no=%s" %
                  (hs_, as_, mid, ("%.3f" % bid) if bid else "-", ("%.3f" % ask) if ask else "-", mp,
                   ("%+.3f" % eb) if eb is not None else "-", ("%+.3f" % en) if en is not None else "-"))
        mkt_ph = sum(x[2] for x in grid_disp if x[0] > x[1])
        mkt_pd = sum(x[2] for x in grid_disp if x[0] == x[1])
        mkt_pa = sum(x[2] for x in grid_disp if x[0] < x[1])
        print("    exact-grid implied 1X2 (mids, scores<=5): %.3f / %.3f / %.3f" % (mkt_ph, mkt_pd, mkt_pa))

json.dump({k: {"lh": v["lh"], "la": v["la"]} for k, v in results.items()},
          open("/home/ubuntu/paper-sim/soccer/model_lambdas.json", "w"), indent=1)
print()
print("saved model_lambdas.json")
