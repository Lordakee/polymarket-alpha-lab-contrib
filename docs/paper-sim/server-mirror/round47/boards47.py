"""ROUND-47 boards: soccer+basketball board tables, CLOB books, anomaly flags.
PAPER ONLY - no orders, no DB writes, no entries, GET-only HTTP.
Window: 2026-11-12T01:15:00Z .. 2026-11-13T01:15:00Z (kickoff/tip based).
Soccer: ALL report-only / board-only (no soccer model coverage for UNL/Copa/
friendlies/intl). Basketball: NBA board + books; KBL/B.League/CBA/NBL/
EuroLeague boards only. No model-eligible entry content in this window.
"""
import json, re, time, unicodedata, urllib.request, urllib.parse, datetime

R47 = "/home/ubuntu/paper-sim/round47"
RAW = f"{R47}/raw"
NOW = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
LO, HI = "2026-11-12T01:15:00Z", "2026-11-13T01:15:00Z"
LOn, HIn = "2026-11-12 01:15", "2026-11-13 01:15"
G = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"

def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except Exception as ex:
            print("ERR", url[:120], ex, flush=True)
            if i == tries - 1:
                return None
            time.sleep(2.0)

def load(name):
    return json.load(open(f"{RAW}/{name}.json"))["data"]

def dump(name, obj):
    json.dump({"fetched_at": NOW.isoformat(), "data": obj}, open(f"{RAW}/{name}.json", "w"))

print("boards47 now", NOW.isoformat(), flush=True)

def n16(s):
    return str(s)[:16].replace("T", " ")

def parse_px(m):
    try:
        return [float(x) for x in json.loads(m.get("outcomePrices") or "[]")]
    except Exception:
        return None

def parse_outs(m):
    try:
        return json.loads(m.get("outcomes") or "[]")
    except Exception:
        return []

def tokens(m):
    try:
        return json.loads(m.get("clobTokenIds") or "[]")
    except Exception:
        return []

def book_for(m, label, cap=4):
    toks = tokens(m)
    if not toks:
        return None
    b = get(f"{CLOB}/book?token_id={toks[0]}")
    if not b:
        return None
    def best(side, rev):
        lv = [(l.get("price"), l.get("size")) for l in (b.get(side) or [])]
        try:
            lv.sort(key=lambda x: float(x[0]), reverse=rev)
        except Exception:
            pass
        return lv[:cap]
    return {"label": label, "token": str(toks[0])[:12] + "...",
            "bids": best("bids", True), "asks": best("asks", False)}

def flags_for(m, px):
    f = []
    bid, ask = m.get("bestBid"), m.get("bestAsk")
    try:
        bid, ask = float(bid), float(ask)
    except Exception:
        bid = ask = None
    if px and len(px) == 2 and abs(px[0] - px[1] - 0.0) < 0.01 and abs(px[0] - 0.5) < 0.02:
        f.append("TEMPLATE_50_50")
    if px and all(abs(p - 0.495) < 0.011 for p in px):
        f.append("TEMPLATE_495")
    if bid is not None and ask is not None and ask - bid > 0.15:
        f.append(f"WIDE_SPREAD({bid:.3f}/{ask:.3f})")
    if bid is None and ask is None:
        f.append("NO_BA_QUOTE")
    liq = m.get("liquidityNum") or 0
    try:
        liqf = float(liq)
    except Exception:
        liqf = 0.0
    if liqf < 100:
        f.append(f"THIN_LIQ({liqf:.0f})")
    qd = re.search(r"on (20\d\d-\d\d-\d\d)", str(m.get("question") or ""))
    gst = n16(m.get("gameStartTime") or "")[:10]
    if qd and gst and qd.group(1) != gst:
        f.append(f"STALE_QDATE(q={qd.group(1)},game={gst})")
    if m.get("closed"):
        f.append("CLOSED")
    return f

def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()

# ---------------- event family index across soccer sweeps ----------------
FAMS = {}   # (kick16, root) -> {eid: event}
TAGS = {}
for src in ["tag_soccer", "tag_uefa_nations_league", "tag_nations_league", "tag_clf",
            "tag_copa_del_rey", "tag_friendlies", "datewin_soccer_start", "datewin_soccer_vol"]:
    try:
        evs = load(src)
    except Exception:
        continue
    for e in evs:
        ms = e.get("markets") or []
        gs = [n16(m.get("gameStartTime")) for m in ms if m.get("gameStartTime")]
        g = min(gs) if gs else ""
        if not g:
            continue
        root = re.sub(r" - (More Markets|Exact Score|Halftime Result|First Team to Score|Second Half Result|Total Corners|Player Props)$", "", str(e.get("title")))
        key = (g[:16], root)
        FAMS.setdefault(key, {})
        FAMS[key][str(e.get("id"))] = e
        for t in (e.get("tags") or []):
            sl = t.get("slug")
            if sl and sl not in ("games", "sports"):
                TAGS.setdefault(key, set()).add(sl)

def fresh_family(key):
    """Fresh detail fetches for every event of a fixture family; returns {eid: ev}."""
    out = {}
    for eid in FAMS.get(key, {}):
        fe = get(f"{G}/events/{eid}?include_markets=true")
        if fe:
            out[eid] = fe
        time.sleep(0.3)
    return out

def soccer_board_row(key, category, fresh=None):
    kick, root = key
    home, away = (root.split(" vs. ") + ["?"])[:2]
    home, away = home.strip(), away.strip()
    evs = fresh if fresh is not None else FAMS.get(key, {})
    ml = {"home": None, "draw": None, "away": None}
    ou25 = None
    spreads, tot_ladder = {}, {}
    tot_liq, tot_vol = 0.0, 0.0
    fl, books = [], []
    for eid, ev in evs.items():
        for m in ev.get("markets") or []:
            px = parse_px(m)
            q = norm(m.get("question"))
            try:
                tot_liq += float(m.get("liquidityNum") or 0)
            except Exception:
                pass
            try:
                tot_vol += float(m.get("volume24hr") or 0) or 0.0
            except Exception:
                pass
            fl += flags_for(m, px)
            if px is None:
                continue
            yes = px[0]
            if "end in a draw" in q:
                ml["draw"] = (yes, m)
            elif f"will {norm(home)} win" in q:
                ml["home"] = (yes, m)
            elif f"will {norm(away)} win" in q:
                ml["away"] = (yes, m)
            mq = re.match(r"spread (\w.*) \(([-+]?\d+\.\d)\)", str(m.get("question") or "").lower())
            if mq:
                spreads[mq.group(2)] = (mq.group(1), yes)
            mo = re.search(r"o/u (\d+\.\d)$", str(m.get("question") or "").lower())
            if mo:
                tot_ladder[mo.group(1)] = yes
                if mo.group(1) == "2.5":
                    ou25 = (yes, m)
    for side in ("home", "draw", "away"):
        if ml[side] and len(books) < 3:
            b = book_for(ml[side][1], f"ML-{side}")
            if b:
                books.append(b)
            time.sleep(0.25)
    if ou25 and len(books) < 4:
        b = book_for(ou25[1], "O2.5")
        if b:
            books.append(b)
        time.sleep(0.25)
    row = {
        "kickoff_utc": kick.replace(" ", "T") + ":00Z",
        "fixture": root,
        "category": category,
        "in_window": LOn <= kick <= HIn,
        "ml_yes_prices": {k: (v[0] if v else None) for k, v in ml.items()},
        "ou25_yes_price": ou25[0] if ou25 else None,
        "total_ladder_prices": dict(sorted(tot_ladder.items())),
        "spread_prices": {k: v for k, v in sorted(spreads.items())},
        "liquidity_sum": round(tot_liq, 2),
        "vol24_sum": round(tot_vol, 2),
        "flags": sorted(set(fl))[:12],
        "clob_books": books,
        "gamma_event_ids": [str(x) for x in evs.keys()],
        "note": "REPORT-ONLY (no soccer model coverage)",
    }
    return row

# ================= SOCCER: UEFA Nations League =================
print("\n== SOCCER: Nations League ==", flush=True)
UNL_IN = [("2026-11-12 17:00", "Armenia vs. Cyprus"), ("2026-11-12 17:00", "Türkiye vs. Belgium"),
          ("2026-11-12 19:45", "Albania vs. Finland"), ("2026-11-12 19:45", "Czechia vs. Spain"),
          ("2026-11-12 19:45", "England vs. Croatia"), ("2026-11-12 19:45", "Italy vs. France"),
          ("2026-11-12 19:45", "Montenegro vs. Latvia"), ("2026-11-12 19:45", "San Marino vs. Belarus")]
unl_rows = []
for key in UNL_IN:
    if key not in FAMS:
        print("MISSING UNL family", key, flush=True)
        continue
    fr = fresh_family(key)
    row = soccer_board_row(key, "UEFA Nations League (NATIONAL TEAMS - report-only)", fresh=fr)
    unl_rows.append(row)
    print("UNL", row["kickoff_utc"], row["fixture"][:34], row["ml_yes_prices"],
          "ou2.5", row["ou25_yes_price"], "liq", row["liquidity_sum"], row["flags"][:4], flush=True)
unl_later = []
for (g, root) in sorted(FAMS):
    if " vs. " not in root:
        continue
    if not ("2026-11-13" <= g[:10] <= "2026-11-14"):
        continue
    if not (TAGS.get((g, root), set()) & {"uefa-nations-league"}):
        continue
    if (g, root) in UNL_IN:
        continue
    row = soccer_board_row((g, root), "UEFA Nations League (NATIONAL TEAMS - report-only)")
    row["in_window"] = False
    unl_later.append({k: row[k] for k in ("kickoff_utc", "fixture", "ml_yes_prices", "ou25_yes_price",
                                          "liquidity_sum", "vol24_sum", "flags")})

# ================= SOCCER: Copa del Rey Nov 12 =================
print("\n== SOCCER: Copa del Rey ==", flush=True)
COPA_IN = [("2026-11-12 17:30", "Calvo Sotelo Puertollano CF vs. Albacete Balompié"),
           ("2026-11-12 18:00", "CD Tarancón vs. Levante UD"),
           ("2026-11-12 18:00", "CDA Navalcarnero vs. Real Betis Balompié")]
copa_rows = []
for key in COPA_IN:
    if key not in FAMS:
        print("MISSING Copa family", key, flush=True)
        continue
    fr = fresh_family(key)
    row = soccer_board_row(key, "Copa del Rey (cross-tier cup - MODEL-VOID, board-only)", fresh=fr)
    stale = [f for f in row["flags"] if f.startswith("STALE_QDATE")]
    row["stale_question_date_cloned_from_oct28"] = bool(stale)
    copa_rows.append(row)
    print("COPA", row["kickoff_utc"], row["fixture"][:44], row["ml_yes_prices"],
          "ou2.5", row["ou25_yes_price"], "liq", row["liquidity_sum"], stale[:1], flush=True)
copa_later = []
for (g, root) in sorted(FAMS):
    if g[:10] == "2026-11-13" and TAGS.get((g, root), set()) & {"copa-del-rey"}:
        row = soccer_board_row((g, root), "Copa del Rey (outside window - enumerate only)")
        copa_later.append({k: row[k] for k in ("kickoff_utc", "fixture", "ml_yes_prices", "liquidity_sum", "flags")})

# ================= SOCCER: everything else in window =================
print("\n== SOCCER: other in-window ==", flush=True)
skip_roots = {r[1] for r in UNL_IN + COPA_IN}
CAT_MAP = [
    ("fifa-friendly", "FIFA friendly (intl - board-only)"),
    ("afcq", "AFCON qualifier (intl - board-only)"),
    ("concacaf-nations-league", "CONCACAF NL (intl - board-only)"),
    ("clf", "Club friendly (clf - board-only)"),
    ("copa-del-rey", "Copa del Rey"),
    ("uefa-nations-league", "UEFA Nations League"),
]
other_rows = []
for (g, root) in sorted(FAMS):
    if not (LOn <= g <= HIn) or " vs. " not in root:
        continue
    if root in skip_roots:
        continue
    tg = TAGS.get((g, root), set())
    cat = next((lab for sl, lab in CAT_MAP if sl in tg), None)
    if cat is None:
        # league-tag or untagged: name by tag
        lg = ",".join(sorted(tg))[:30] or "uncategorized"
        cat = f"League/other ({lg}) - board-only"
    row = soccer_board_row((g, root), cat)
    other_rows.append(row)
# CLOB spot-checks for two notable others
for row in other_rows:
    if row["fixture"] in ("Uzbekistan vs. Russia", "Curaçao vs. Panama"):
        key = (row["kickoff_utc"][:16].replace("T", " "), row["fixture"])
        fr = fresh_family(key)
        if fr:
            row2 = soccer_board_row(key, row["category"], fresh=fr)
            row2["note"] = "REPORT-ONLY (fresh detail + CLOB spot-check)"
            other_rows[other_rows.index(row)] = row2
            print("SPOT", row2["fixture"], row2["ml_yes_prices"], "liq", row2["liquidity_sum"], flush=True)
print("other in-window rows:", len(other_rows), flush=True)

# ================= BASKETBALL =================
print("\n== BASKETBALL ==", flush=True)
bkb = {}

# --- NBA US-Wed slate (ESPN 20261111; tips 2026-11-12 00:00-04:00Z) ---
wed = []
sb = load("espn_nba_sb_20261111")
for e in sb.get("events") or []:
    comp = (e.get("competitions") or [{}])[0]
    sc = {}
    for c in comp.get("competitors") or []:
        ab = (c.get("team") or {}).get("abbreviation", "?")
        s = c.get("score")
        s = s.get("displayValue", "") if isinstance(s, dict) else str(s)
        sc["home" if c.get("homeAway") == "home" else "away"] = f"{ab} {s}"
    st = (e.get("status") or {}).get("type", {})
    tip = n16(e.get("date"))
    wed.append({"tip_utc": tip.replace(" ", "T") + ":00Z", "game": e.get("shortName") or e.get("name"),
                "score": f"{sc.get('home','?')} vs {sc.get('away','?')}",
                "state": st.get("state"), "detail": st.get("detail"),
                "in_window": LOn <= tip <= HIn})
bkb["nba_us_wed_nov11_slate"] = wed

# --- NBA Gamma events this stretch ---
NBA_EV = {"1284273": ("2026-11-12 01:00", "Spurs vs. Bulls"),
          "1284277": ("2026-11-12 02:00", "Magic vs. Jazz"),
          "1284278": ("2026-11-12 02:30", "Warriors vs. Rockets"),
          "1284280": ("2026-11-12 03:00", "Thunder vs. Trail Blazers"),
          "1284283": ("2026-11-13 00:00", "Pistons vs. Wizards"),
          "1284281": ("2026-11-13 00:00", "Raptors vs. 76ers"),
          "1284284": ("2026-11-13 01:00", "Mavericks vs. Timberwolves"),
          "1284286": ("2026-11-13 02:00", "Hornets vs. Suns")}
nba_rows = []
det_nba = {}
for eid, (g, title) in NBA_EV.items():
    fe = get(f"{G}/events/{eid}?include_markets=true")
    time.sleep(0.3)
    if not fe:
        print("NBA detail FAIL", eid, flush=True)
        continue
    det_nba[eid] = fe
    ml = None
    spreads, totals = {}, {}
    liq_sum, vol_ml = 0.0, None
    fl = []
    for m in fe.get("markets") or []:
        q = str(m.get("question") or "")
        px = parse_px(m)
        outs = parse_outs(m)
        try:
            liq_sum += float(m.get("liquidityNum") or 0)
        except Exception:
            pass
        if q == title and " vs. " in q:
            ml = {"question": q, "outcomes": outs, "prices": px,
                  "bid/ask": [m.get("bestBid"), m.get("bestAsk")],
                  "vol24": m.get("volume24hr"), "liq": m.get("liquidityNum"),
                  "closed": m.get("closed"), "uma": m.get("umaResolutionStatus"),
                  "tokens": tokens(m)}
            vol_ml = m.get("volume24hr")
        mq = re.match(r"Spread: (.+) \(([-+]?\d+\.\d)\)$", q)
        if mq and px:
            spreads[mq.group(2)] = {"team": mq.group(1), "yes": px[0], "vol24": m.get("volume24hr")}
        mo = re.search(r"O/U (\d+(?:\.\d)?)$", q)
        if mo and px:
            totals[mo.group(1)] = {"yes": px[0], "vol24": m.get("volume24hr")}
    fl = flags_for({"bestBid": (ml or {}).get("bid/ask", [None, None])[0],
                    "bestAsk": (ml or {}).get("bid/ask", [None, None])[1],
                    "liquidityNum": (ml or {}).get("liq"), "closed": (ml or {}).get("closed"),
                    "question": "", "gameStartTime": "", "outcomePrices": None}, None)
    row = {"tip_utc": g.replace(" ", "T") + ":00Z", "game": title, "gamma_id": eid,
           "in_window": LOn <= g <= HIn, "ml": ml, "spread_rungs": dict(sorted(spreads.items())),
           "total_rungs": dict(sorted(totals.items(), key=lambda kv: float(kv[0]))),
           "liq_sum": round(liq_sum, 2), "flags": fl, "label": "BOARD-ONLY (no entry)"}
    # CLOB book on the ML token for in-window & near-window games
    if ml and ml.get("tokens") and len(nba_rows) < 8:
        b = get(f"{CLOB}/book?token_id={ml['tokens'][0]}")
        if b:
            row["clob_book_ml"] = {"bids": (b.get("bids") or [])[:3], "asks": (b.get("asks") or [])[:3]}
        time.sleep(0.25)
    nba_rows.append(row)
    print("NBA", g, title[:30], (ml or {}).get("prices"), "vol24", vol_ml,
          "spread_rungs", len(spreads), "total_rungs", len(totals), (ml or {}).get("closed"), flush=True)
bkb["nba_games"] = nba_rows
dump("nba_event_details", det_nba)

thu = load("espn_nba_sb_20261112")
bkb["nba_us_thu_nov12_slate_espn"] = [
    {"tip_utc": n16(e.get("date")).replace(" ", "T") + ":00Z", "game": e.get("shortName") or e.get("name"),
     "state": ((e.get("status") or {}).get("type") or {}).get("state")} for e in thu.get("events") or []]

# --- POR@OKC line history via CLOB prices-history (cheap, resolved game) ---
por_hist = {}
try:
    ev = det_nba.get("1284280") or {}
    for m in ev.get("markets") or []:
        if str(m.get("question")) == "Thunder vs. Trail Blazers":
            toks = tokens(m)
            h = get(f"{CLOB}/prices-history?market={toks[0]}&startTs=1762867200&endTs=1762930800&fidelity=10")
            if h and h.get("history"):
                hs = h["history"]
                por_hist = {"token0_outcome": (parse_outs(m) or ["?", "?"])[0],
                            "n_points": len(hs), "first": hs[0], "last": hs[-1],
                            "min": min(hs, key=lambda x: x["p"]), "max": max(hs, key=lambda x: x["p"])}
            break
except Exception as ex:
    por_hist = {"error": str(ex)}
bkb["por_okc_ml_price_history"] = por_hist

# --- KBL / B.League / NBL / EuroLeague / NCAA boards ---
bb_other = []
for src, label in [("tag_kbl", "KBL (Korea)"), ("tag_basketball", "mixed")]:
    try:
        evs = load(src)
    except Exception:
        continue
    seen = set()
    for e in evs:
        ms = e.get("markets") or []
        gs = [n16(m.get("gameStartTime")) for m in ms if m.get("gameStartTime")]
        g = min(gs) if gs else ""
        if not g or not (LOn <= g <= HIn):
            continue
        tg = {t.get("slug") for t in (e.get("tags") or [])}
        if "nba" in tg or "college-basketball" in tg or "nba" in str(e.get("title", "")).lower():
            continue
        if "college" in str(e.get("title", "")).lower():
            continue
        if (g, str(e.get("title"))) in seen:
            continue
        seen.add((g, str(e.get("title"))))
        mm = ms[0] if ms else {}
        px = parse_px(mm)
        row = {"tip_utc": g.replace(" ", "T") + ":00Z", "game": str(e.get("title"))[:60],
               "league_guess": label, "gamma_id": str(e.get("id")),
               "main_prices": px, "outcomes": parse_outs(mm),
               "liq": mm.get("liquidityNum"), "vol24": mm.get("volume24hr"),
               "n_markets": len(ms), "in_window": True,
               "label": "BOARD-ONLY (no model)"}
        bb_other.append(row)
bb_other.sort(key=lambda r: r["tip_utc"])
for r in bb_other:
    print("BB", r["tip_utc"], r["game"][:44], r["main_prices"], "liq", r["liq"], flush=True)
bkb["other_basketball_boards"] = bb_other

# --- NCAA count (context only) ---
ncaa = []
for e in (load("tag_college_basketball") or []):
    ms = e.get("markets") or []
    gs = [n16(m.get("gameStartTime")) for m in ms if m.get("gameStartTime")]
    g = min(gs) if gs else ""
    if g and LOn <= g <= HIn:
        ncaa.append({"tip_utc": g.replace(" ", "T") + ":00Z", "game": str(e.get("title"))[:50]})
bkb["ncaa_in_window_count"] = len(ncaa)
bkb["ncaa_in_window_sample"] = ncaa[:8]

# ================= depth stats =================
def stats(rows, key="liquidity_sum"):
    vals = [r.get(key) or 0 for r in rows]
    return {"n": len(rows), "liq_sum": round(sum(r.get("liquidity_sum") or 0 for r in rows), 2),
            "liq_median": round(sorted(vals)[len(vals)//2], 2) if vals else 0,
            "vol24_sum": round(sum(r.get("vol24_sum") or 0 for r in rows), 2)}
depth = {
    "unl_nov12_in_window": stats(unl_rows),
    "unl_ml_home_liq": [r["liquidity_sum"] for r in unl_rows],
    "copa_nov12_in_window": stats(copa_rows),
    "fifa_friendly_in_window": stats([r for r in other_rows if "FIFA friendly" in r["category"]]),
    "afcq_in_window": stats([r for r in other_rows if "AFCON" in r["category"]]),
    "concacaf_in_window": stats([r for r in other_rows if "CONCACAF" in r["category"]]),
    "clf_in_window": stats([r for r in other_rows if "Club friendly" in r["category"]]),
    "kbl_bleague_nbl_in_window": stats(bb_other),
}

board = {
    "round": 47,
    "scan": "24h soccer+basketball board scan (Nations League window)",
    "paper_only": True, "no_db_writes": True, "no_entries": True,
    "generated_utc": NOW.isoformat(),
    "window_utc": {"lo": LO, "hi": HI},
    "soccer": {
        "nations_league_nov12": unl_rows,
        "nations_league_later": unl_later,
        "copa_del_rey_nov12": copa_rows,
        "copa_del_rey_later": copa_later,
        "other_in_window": other_rows,
    },
    "basketball": bkb,
    "depth_stats": depth,
    "model_coverage": {
        "uefa_nations_league": "NO model (national teams, no xG snapshot coverage) - REPORT-ONLY",
        "copa_del_rey": "NO model (cross-tier cup; minnows unrated) - MODEL-VOID, board-only",
        "friendlies_clf_and_fifa": "NO model (friendlies frozen rule) - board-only",
        "afcq_concacaf_league_games": "NO model - board-only",
        "nba": "shadow model exists (papersim nba_model) - SHADOW-MONITORING-ONLY rows in nba_shadow_rows.json; NO entry",
        "kbl_bleague_cba_nbl_euroleague": "NO model - board-only",
    },
    "decision": "ENTER NOTHING: window contains no entry-eligible model content (paper-only scan, no entries)",
    "entries": [],
}
json.dump(board, open(f"{R47}/board.json", "w"), indent=1)
print("\nBOARD47 DONE ->", f"{R47}/board.json", flush=True)
print("depth:", json.dumps(depth, indent=1)[:1200], flush=True)
