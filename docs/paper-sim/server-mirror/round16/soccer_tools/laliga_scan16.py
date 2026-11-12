"""Round-16 La Liga sub-scan. Window: 2026-10-24 11:20Z .. 2026-10-25 03:00Z.
xG: round15/raw/xg_understat_15.json (through Oct 23).
Eligible: full-match O/U both, BTTS both, team totals both. match_winner suspended.
Spreads computed for flagged-not-recommended only (blowout-tail suspended).
"""
import json, math, re, time
from collections import defaultdict
from datetime import datetime, timezone

RAW15 = "/home/ubuntu/paper-sim/round15/raw"
RAW16 = "/home/ubuntu/paper-sim/round16/raw"
XG = json.load(open(RAW15 + "/xg_understat_15.json"))
RHO_DC = -0.1
LO = datetime(2026, 10, 24, 11, 20, tzinfo=timezone.utc)
HI = datetime(2026, 10, 25, 3, 0, tzinfo=timezone.utc)

NAME_MAP = {
 "Rayo Vallecano de Madrid": "Rayo Vallecano",
 "Elche CF": "Elche",
 "Real Racing Club": "Racing Santander",
 "RCD Espanyol de Barcelona": "Espanyol",
 "Valencia CF": "Valencia",
 "Villarreal CF": "Villarreal",
 "Club Atlético de Madrid": "Atletico Madrid",
 "RC Deportivo A Coruña": "Deportivo La Coruna",
}

HELD_TOTAL = {
 "Rayo Vallecano de Madrid vs. Elche CF",
 "Valencia CF vs. Villarreal CF",
}

SWEEPS = [
    ("blend w=.5 p=8 rho0", 0.5, 8, 0.0, "blend"),
    ("blend w=.5 p=8 DC",   0.5, 8, RHO_DC, "blend"),
    ("blend w=1.0 p=8",     1.0, 8, 0.0, "blend"),
    ("blend w=.25 p=8",     0.25, 8, 0.0, "blend"),
    ("blend w=.5 p=16",     0.5, 16, 0.0, "blend"),
    ("blend w=.5 p=4",      0.5, 4, 0.0, "blend"),
    ("current-only",        None, None, 0.0, "cur"),
    ("last-only",           None, None, 0.0, "last"),
    ("cross-shrink .8",     0.5, 8, 0.0, "blend"),
    ("cross-shrink 1.1",    0.5, 8, 0.0, "blend"),
]

def load(lg, se):
    return XG["%s_%s" % (lg, se)]

_cache = {}
def ratings_for(LASTW, PRIOR, mode):
    key = (LASTW, PRIOR, mode)
    if key in _cache:
        return _cache[key]
    d25 = load("La_liga", "2025")
    d26 = load("La_liga", "2026")
    ms = [m for m in d25["dates"] if m.get("isResult")]
    bh = sum(float(m["xG"]["h"]) for m in ms) / len(ms)
    ba = sum(float(m["xG"]["a"]) for m in ms) / len(ms)
    lgf = (bh + ba) / 2.0
    last = {}
    for t in d25["teams"].values():
        h = t["history"]
        last[t["title"]] = (sum(float(x["xG"]) for x in h) / len(h),
                            sum(float(x["xGA"]) for x in h) / len(h))
    r = {}
    for t in d26["teams"].values():
        h = t["history"]
        name = t["title"]
        if not h:
            continue
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

def pois(l, k):
    return math.exp(-l) * l ** k / math.factorial(k)

def grid(lh, la, N=10, rho=0.0):
    g = [[pois(lh, i) * pois(la, j) for j in range(N + 1)] for i in range(N + 1)]
    if rho:
        g[0][0] *= max(1 - lh * la * rho, .01)
        g[0][1] *= max(1 + lh * rho, .01)
        g[1][0] *= max(1 + la * rho, .01)
        g[1][1] *= max(1 - rho, .01)
    s = sum(sum(row) for row in g)
    return [[v / s for v in row] for row in g]

def variant_outputs(lh, la, rho):
    g = grid(lh, la, 10, rho)
    tot = defaultdict(float)
    btts = 0.0
    hg = defaultdict(float)
    ag = defaultdict(float)
    marg = defaultdict(float)
    for i in range(11):
        for j in range(11):
            p = g[i][j]
            tot[i + j] += p
            if i >= 1 and j >= 1:
                btts += p
            hg[i] += p
            ag[j] += p
            marg[i - j] += p
    return {"btts": btts, "tot": dict(tot), "hg": dict(hg), "ag": dict(ag), "marg": dict(marg)}

def tail(d, n):
    return sum(v for k, v in d.items() if k >= n)

def lambdas(hn, an, LASTW, PRIOR, mode, shrink=1.0):
    bh1, ba1, lgf1, r1 = ratings_for(LASTW, PRIOR, mode)
    ah, dh = r1.get(hn, (1.0, 1.0))
    aa, da = r1.get(an, (1.0, 1.0))
    lh = bh1 * (ah ** shrink) * (da ** shrink)
    la = ba1 * (aa ** shrink) * (dh ** shrink)
    return lh, la

def model_match(hn, an):
    per = []
    for name, LASTW, PRIOR, rho, mode in SWEEPS:
        shrink = 0.8 if name.startswith("cross-shrink .8") else (1.1 if name.startswith("cross-shrink 1.1") else 1.0)
        lh, la = lambdas(hn, an, LASTW, PRIOR, mode, shrink)
        per.append({"name": name, "lh": lh, "la": la, "o": variant_outputs(lh, la, rho)})
    return per

def med(v):
    s = sorted(v)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0

def recent_form(name_us):
    def _hist(se):
        for t in load("La_liga", se)["teams"].values():
            if t.get("title") == name_us:
                return t.get("history") or []
        return []
    h = _hist("2026")
    if len(h) < 3:
        h = _hist("2025")
    if not h:
        return None
    last5 = h[-5:]
    gp = len(last5)
    gf = sum(int(x.get("scored") or 0) for x in last5)
    ga = sum(int(x.get("missed") or 0) for x in last5)
    xgf = sum(float(x.get("xG") or 0) for x in last5)
    xga = sum(float(x.get("xGA") or 0) for x in last5)
    o25 = sum(1 for x in last5 if (int(x.get("scored") or 0) + int(x.get("missed") or 0)) >= 3)
    btts = sum(1 for x in last5 if int(x.get("scored") or 0) >= 1 and int(x.get("missed") or 0) >= 1)
    return {"gp": gp, "gf": gf, "ga": ga, "gpg_team": round((gf + ga) / gp, 2),
            "xg_pg": round((xgf + xga) / gp, 2), "o25_hits": o25, "btts_hits": btts,
            "scores": ["%s-%s" % (x.get("scored"), x.get("missed")) for x in last5]}

def norm(ts):
    s = str(ts or "").strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None

RE_SPREAD = re.compile(r"^Spread: (.+) \((-?\d+(?:\.\d+)?)\)$")
RE_TT = re.compile(r"^(.+): (.+) O/U (\d+(?:\.\d+)?)$")
RE_OU = re.compile(r"^(.+): O/U (\d+(?:\.\d+)?)$")

def classify(q, base, home_pm, away_pm):
    if "Corner" in q or "Card" in q or "Booking" in q:
        return None
    if "Exact Score" in q or "exact score" in q:
        return None
    if "1st Half" in q or "2nd Half" in q or "First Half" in q or "Second Half" in q:
        return None
    if q == base + ": Both Teams to Score":
        return ("btts", None, None)
    if q.startswith("Will ") or " win on " in q:
        return ("ml", None, None)
    mm = RE_SPREAD.match(q)
    if mm:
        return ("spread", mm.group(1), float(mm.group(2)))
    mm = RE_OU.match(q)
    if mm and mm.group(1) == base:
        return ("total", float(mm.group(2)), None)
    mm = RE_TT.match(q)
    if mm and mm.group(1) == base and mm.group(2) in (home_pm, away_pm):
        return ("teamtotal", mm.group(2), float(mm.group(3)))
    return None

def quant(variants, kind, a1, a2, home_pm, away_pm):
    out = []
    for v in variants:
        o = v["o"]
        if kind == "total":
            n = int(math.floor(a1 + 1e-9)) + 1
            out.append(tail(o["tot"], n))
        elif kind == "btts":
            out.append(o["btts"])
        elif kind == "teamtotal":
            n = int(math.floor(a2 + 1e-9)) + 1
            dist = o["hg"] if a1 == home_pm else (o["ag"] if a1 == away_pm else None)
            if dist is None:
                return None
            out.append(tail(dist, n))
        elif kind == "spread":
            line = a2
            if a1 == home_pm:
                m = o["marg"]
            elif a1 == away_pm:
                m = {-(k): val for k, val in o["marg"].items()}
            else:
                return None
            need = -line
            out.append(sum(p for k, p in m.items() if k > need + 1e-9))
        else:
            return None
    return out

evs = json.load(open(RAW16 + "/gamma_la-liga.json"))
groups = {}
for e in evs:
    t = str(e.get("title") or "")
    base = t.split(" - ")[0].strip()
    if " vs. " not in base:
        continue
    home_pm, away_pm = [x.strip() for x in base.split(" vs. ")]
    if home_pm not in NAME_MAP or away_pm not in NAME_MAP:
        continue
    for m in e.get("markets") or []:
        g = norm(m.get("gameStartTime"))
        if g is None or not (LO <= g <= HI):
            continue
        if m.get("closed"):
            continue
        grp = groups.setdefault(base, {"home": home_pm, "away": away_pm, "kickoff": g, "markets": {}, "vol24": 0.0})
        grp["vol24"] += (m.get("volume24hr") or 0)
        q = (m.get("question") or "").strip()
        cls = classify(q, base, home_pm, away_pm)
        if cls is None:
            continue
        prices = m.get("outcomePrices")
        if isinstance(prices, str):
            prices = json.loads(prices)
        toks = m.get("clobTokenIds")
        if isinstance(toks, str):
            toks = json.loads(toks)
        outs = m.get("outcomes")
        if isinstance(outs, str):
            outs = json.loads(outs)
        key = (cls[0], str(cls[1]), str(cls[2]) if cls[2] is not None else "")
        prev = grp["markets"].get(key)
        liq = m.get("liquidityNum") or m.get("liquidity") or 0
        if prev and (prev["liq"] or 0) >= liq:
            continue
        grp["markets"][key] = {
            "id": str(m.get("id")), "q": q, "cls": cls, "outcomes": outs,
            "prices": prices, "tokens": toks, "liq": liq,
            "vol24": m.get("volume24hr"), "bid": m.get("bestBid"), "ask": m.get("bestAsk"),
        }

print("in-window modelable fixtures:", len(groups))
scan_matches = []
shortlist = []
flagged = []
skipped = defaultdict(int)
kind_counts = defaultdict(int)

for base, grp in sorted(groups.items(), key=lambda kv: kv[1]["kickoff"]):
    home_pm, away_pm = grp["home"], grp["away"]
    hn, an = NAME_MAP[home_pm], NAME_MAP[away_pm]
    variants = model_match(hn, an)
    lam_h = med([v["lh"] for v in variants])
    lam_a = med([v["la"] for v in variants])
    fh, fa = recent_form(hn), recent_form(an)
    rec = {
        "match": base, "league": "La_liga",
        "kickoff": grp["kickoff"].strftime("%Y-%m-%dT%H:%M:%SZ"),
        "lambda_home": round(lam_h, 3), "lambda_away": round(lam_a, 3),
        "lambda_total": round(lam_h + lam_a, 2),
        "form_home": fh, "form_away": fa,
        "markets": {},
    }
    print("%-52s %s lh=%.2f la=%.2f lT=%.2f mkts=%d" % (
        base[:52], rec["kickoff"], lam_h, lam_a, lam_h + lam_a, len(grp["markets"])))
    if fh:
        print("   formH", fh["scores"], "o25", fh["o25_hits"], "btts", fh["btts_hits"], "gpg", fh["gpg_team"])
    if fa:
        print("   formA", fa["scores"], "o25", fa["o25_hits"], "btts", fa["btts_hits"], "gpg", fa["gpg_team"])
    for key, mkt in grp["markets"].items():
        kind, a1, a2 = mkt["cls"]
        kind_counts[kind] += 1
        qs = quant(variants, kind, a1, a2, home_pm, away_pm)
        pr = mkt["prices"] or []
        outs = mkt["outcomes"] or []
        liq = mkt["liq"] or 0
        p0 = float(pr[0]) if pr else None
        if qs is None:
            continue
        q_med, q_min, q_max = med(qs), min(qs), max(qs)
        spread = q_max - q_min
        label = mkt["q"]
        row = {
            "kind": kind, "id": mkt["id"], "q": label, "outcomes": outs, "prices": pr,
            "liq": liq, "bid": mkt["bid"], "ask": mkt["ask"], "tokens": mkt["tokens"],
            "p0_med": round(q_med, 4), "p0_min": round(q_min, 4), "p0_max": round(q_max, 4),
            "var_spread": round(spread, 4),
            "edge0_mid": None if p0 is None else round(q_med - p0, 4),
            "edge1_mid": None if p0 is None else round((1 - q_med) - (1 - p0), 4),
        }
        rec["markets"][label] = row
        if kind == "spread":
            if p0 is None or liq < 5000:
                continue
            e0 = q_med - p0
            line = a2
            edge = abs(e0)
            if edge >= 0.04:
                side = outs[0] if e0 >= 0 else (outs[1] if len(outs) > 1 else "?")
                flagged.append({
                    "match": base, "kickoff": rec["kickoff"], "q": label, "kind": "spread",
                    "side": side, "line": line, "listed_team": a1,
                    "gamma_mid_side0": p0, "model_med_side0": round(q_med, 4),
                    "model_min": round(q_min, 4), "model_max": round(q_max, 4),
                    "var_spread": round(spread, 4), "edge_mid_abs": round(edge, 4),
                    "liq": liq, "tokens": mkt["tokens"], "id": mkt["id"],
                    "outcomes": outs,
                    "reason": "spread/blowout-tail SUSPENDED (Depor +2.5 recommended+rejected 3 rounds; persistent unclosed edge = model bias). Not recommended.",
                })
            continue
        if kind not in ("total", "btts", "teamtotal"):
            continue
        held = base in HELD_TOTAL and kind == "total"
        if liq < 5000:
            skipped["illiquid"] += 1
            continue
        if p0 is None:
            skipped["no_price"] += 1
            continue
        e0 = q_med - p0
        gate_fail = None
        if spread > 0.06:
            gate_fail = "var_spread %.4f > 0.06" % spread
            skipped["var_spread>6c"] += 1
        if held:
            gate_fail = (gate_fail + "; " if gate_fail else "") + "held_same_type"
        if abs(e0) >= 0.03 or held or gate_fail:
            if abs(e0) >= 0.03 or held:
                shortlist.append({
                    "match": base, "kickoff": rec["kickoff"], "kind": kind, "q": label,
                    "side0": outs[0] if outs else "?", "side1": outs[1] if len(outs) > 1 else "?",
                    "mid": p0, "q0_med": round(q_med, 4), "q0_min": round(q_min, 4),
                    "q0_max": round(q_max, 4), "var_spread": round(spread, 4),
                    "liq": liq, "id": mkt["id"], "tokens": mkt["tokens"],
                    "lambda_home": round(lam_h, 3), "lambda_away": round(lam_a, 3),
                    "lambda_total": round(lam_h + lam_a, 2),
                    "form_home": fh, "form_away": fa,
                    "edge0_mid": round(e0, 4), "edge1_mid": round(-e0, 4),
                    "gate_fail": gate_fail,
                    "held_same_type": held,
                })
    scan_matches.append(rec)

print("kind counts", dict(kind_counts))
print("skipped", dict(skipped))
print("shortlist", len(shortlist), "flagged spreads", len(flagged))
json.dump({
    "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "window": "2026-10-24T11:20:00Z .. 2026-10-25T03:00:00Z",
    "xg_file": "round15/raw/xg_understat_15.json (La Liga last result 2026-10-23 19:00 Alaves 1-1 Malaga)",
    "variants": [s[0] for s in SWEEPS],
    "matches": scan_matches,
    "shortlist": shortlist,
    "flagged_spreads": flagged,
    "kind_counts": dict(kind_counts),
    "skipped": dict(skipped),
}, open(RAW16 + "/laliga_model.json", "w"), indent=1)
json.dump(shortlist, open(RAW16 + "/shortlist_prelim.json", "w"), indent=1)
print("saved laliga_model.json + shortlist_prelim.json")
