"""ROUND-46 boards: soccer+basketball board tables, CLOB books, anomaly flags,
rated-club STOP check. PAPER ONLY - no orders, no DB writes, GET-only HTTP.

Window: 2026-11-10T01:10:00Z .. 2026-11-10T13:10:00Z (kickoff-based).
Modelable = BOTH clubs in a rated snapshot AND a modelable competition (Big-5
domestic / Championship / Eredivisie). Copa del Rey cross-tier = MODEL-VOID.
Club friendlies ('clf') = MODEL-VOID by frozen rule. Basketball = NO MODEL.
Exception path (dispatch): Copa del Rey tie with TWO rated clubs -> report
modelable + run domestic path, NO entry without coordinator arbitration.
"""
import json, re, time, unicodedata, urllib.request, urllib.parse, datetime

R46 = "/home/ubuntu/paper-sim/round46"
RAW = f"{R46}/raw"
NOW = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
LO, HI = "2026-11-10T01:10:00Z", "2026-11-10T13:10:00Z"
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

print("boards46 now", NOW.isoformat(), flush=True)

# ---------------- rated club sets ----------------
def norm(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()

SNAPS = {
    "big5": "/home/ubuntu/paper-sim/round41/raw/xg_fotmob_big5_merged.json",
    "championship": "/home/ubuntu/paper-sim/championship_20261108/xg_fotmob_championship.json",
    "eredivisie": "/home/ubuntu/paper-sim/round41/raw/xg_fotmob_eredivisie.json",
}
rated = {}          # norm-title -> league label
for src, path in SNAPS.items():
    try:
        d = json.load(open(path))
    except Exception as ex:
        print("snapshot load ERR", src, ex, flush=True)
        continue
    if src == "big5":
        for lk in [k for k in d if k.endswith("_2026")]:
            for t in d[lk].get("teams", {}).values():
                rated[norm(t.get("title"))] = f"Big5:{lk[:-5]}"
    else:
        teams = d.get("teams", d) if isinstance(d, dict) else {}
        for t in (teams.values() if isinstance(teams, dict) else []):
            if isinstance(t, dict) and t.get("title"):
                rated[norm(t.get("title"))] = src.capitalize()
print("rated clubs loaded:", len(rated), flush=True)

PREFIX = {"cd", "sd", "cf", "fc", "rc", "rcd", "ud", "ue", "cp", "ac", "as", "sc", "ca", "cb", "real", "club", "de", "del", "deportivo", "atletico", "athletic", "club"}
def side_variants(side):
    s = norm(side)
    toks = [t for t in s.split() if t]
    cores = set()
    if toks:
        cores.add(" ".join(toks))
        last = toks[-1]
        if len(last) >= 4:
            cores.add(last)
        nonpref = [t for t in toks if t not in PREFIX]
        if nonpref:
            cores.add(" ".join(nonpref))
            if len(nonpref[-1]) >= 4:
                cores.add(nonpref[-1])
    return {c for c in cores if len(c) >= 4}

def rate_sides(side_a, side_b):
    out = []
    for side in (side_a, side_b):
        full = norm(side)
        hit = None
        for v in side_variants(side):
            if v in rated:
                hit = rated[v]
                break
        if hit is None and len(full) >= 5:
            padded = " " + full + " "
            for k, lg in rated.items():
                if len(k) < 5:
                    continue
                if padded.startswith(" " + k + " ") or (" " + k + " ") in padded \
                   or (" " + k) == padded[: 1 + len(k)] and padded[len(k) + 1 : len(k) + 2] == " ":
                    hit = lg
                    break
                if len(k) >= 7 and k in full:
                    hit = lg
                    break
        out.append(hit)
    return out  # [league_or_None, league_or_None]

# ---------------- fresh detail + CLOB helpers ----------------
def fresh_event(eid):
    return get(f"{G}/events/{eid}?include_markets=true")

def parse_px(m):
    try:
        return [float(x) for x in json.loads(m.get("outcomePrices") or "[]")]
    except Exception:
        return None

def book_for(m, label, cap=4):
    try:
        toks = json.loads(m.get("clobTokenIds") or "[]")
    except Exception:
        toks = []
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
    return {"label": label, "token": toks[0][:10] + "...",
            "bids": best("bids", True), "asks": best("asks", False)}

def flags_for(m, px):
    f = []
    bid, ask = m.get("bestBid"), m.get("bestAsk")
    try:
        bid, ask = float(bid), float(ask)
    except Exception:
        bid = ask = None
    if px and all(abs(p - 0.5) < 0.02 for p in px):
        f.append("TEMPLATE_50_50")
    if px and all(abs(p - 0.495) < 0.011 for p in px):
        f.append("TEMPLATE_495")
    if bid is not None and ask is not None and ask - bid > 0.15:
        f.append(f"WIDE_SPREAD({bid:.3f}/{ask:.3f})")
    if bid is None and ask is None:
        f.append("NO_BA_QUOTE")
    liq = m.get("liquidityNum") or 0
    if not liq or float(liq) < 100:
        f.append(f"THIN_LIQ({liq})")
    qd = re.search(r"on (20\d\d-\d\d-\d\d)", str(m.get("question") or ""))
    gst = str(m.get("gameStartTime") or "")[:10]
    if qd and gst and qd.group(1) != gst:
        f.append(f"STALE_QDATE(q={qd.group(1)},game={gst})")
    g = str(m.get("gameStartTime") or "")
    if g and g < "2026-11-10 13:10" and not m.get("closed"):
        pass  # window-relative handled by caller
    return f

# ---------------- top-up: full clf sweep (friendlies census) ----------------
clf_all = []
for off in [0, 100, 200]:
    d = get(f"{G}/events?tag_slug=clf&closed=false&limit=100&offset={off}&order=volume24hr")
    if not d:
        break
    clf_all.extend(d)
    if len(d) < 100:
        break
    time.sleep(0.3)
dump("clf_sweep_full", clf_all)
print("clf sweep total:", len(clf_all), flush=True)
clf_fix = {}
for e in clf_all:
    root = re.sub(r" - (More Markets|Exact Score|Halftime Result|First Team to Score|Second Half Result|Total Corners|Player Props)$", "", str(e.get("title")))
    for m in e.get("markets") or []:
        g = str(m.get("gameStartTime") or "")[:16]
        if g >= "2026-11-09":
            clf_fix.setdefault((g, root), []).append((e.get("id"), m))
print("clf fixtures >= Nov 9:", len(clf_fix), flush=True)
for k in sorted(clf_fix):
    print("   CLF", k[0], k[1][:48], flush=True)

# ---------------- soccer board ----------------
def fixture_row(kick, home, away, league, events_by_id, need_ou=True):
    """events_by_id: {eid: fresh_event} covering root + More Markets families."""
    mls = {"home": None, "draw": None, "away": None}
    ou25 = None
    tot_liq, tot_vol24, fl = 0.0, 0.0, []
    books = []
    for eid, ev in events_by_id.items():
        for m in ev.get("markets") or []:
            q = norm(m.get("question"))
            gOK = str(m.get("gameStartTime") or "")[:10] == kick[:10]
            px = parse_px(m)
            try:
                tot_liq += float(m.get("liquidityNum") or 0)
                tot_vol24 += float(m.get("volume24hr") or 0)
            except Exception:
                pass
            fl += [f"ev{eid}:{x}" for x in flags_for(m, px)]
            if not gOK or px is None:
                continue
            yes = px[0]
            if "end in a draw" in q:
                mls["draw"] = (yes, m)
            elif f"will {norm(home)} win" in q:
                mls["home"] = (yes, m)
            elif f"will {norm(away)} win" in q:
                mls["away"] = (yes, m)
            elif q == f"{norm(home)} vs {norm(away)} ou 25":
                ou25 = (yes, m)
    for side in ("home", "draw", "away"):
        if mls[side]:
            b = book_for(mls[side][1], f"ML-{side}")
            if b:
                books.append(b)
            time.sleep(0.25)
    if ou25:
        b = book_for(ou25[1], "O2.5")
        if b:
            books.append(b)
        time.sleep(0.25)
    r_a, r_b = rate_sides(home, away)
    return {
        "kickoff_utc": kick.replace(" ", "T") + ":00Z",
        "fixture": f"{home} vs {away}",
        "league": league,
        "ml_yes_prices": {k: (v[0] if v else None) for k, v in mls.items()},
        "ou25_yes_price": ou25[0] if ou25 else None,
        "liquidity_sum": round(tot_liq, 2),
        "vol24_sum": round(tot_vol24, 2),
        "rated": [r_a, r_b],
        "modelable": bool(r_a and r_b),
        "flags": sorted(set(x.split(":")[-1] for x in fl))[:10],
        "clob_books": books,
        "gamma_event_ids": list(events_by_id.keys()),
    }

soccer = {"in_window": [], "copa_del_rey_tue_nov10": [], "copa_del_rey_later": [],
          "club_friendships_week": [], "league_resumption": [], "nations_league": {}}

# --- in-window: from window_soccer_details + clf fresh check ---
wd = load("window_soccer_details")
inwin_ids = {}
for eid, ev in wd.items():
    root = re.sub(r" - (More Markets|Exact Score|Halftime Result|First Team to Score|Total Corners)$", "", str(ev.get("title")))
    inwin_ids.setdefault(root, {})[eid] = ev
for root, evs in inwin_ids.items():
    home, away = [x.strip() for x in root.split(" vs. ")] if " vs. " in root else (root, "?")
    kick = min(str(m.get("gameStartTime") or "9999") for e in evs.values() for m in (e.get("markets") or []) if m.get("gameStartTime"))
    fresh = {}
    for eid in evs:
        fe = fresh_event(eid)
        if fe:
            fresh[eid] = fe
        time.sleep(0.3)
    row = fixture_row(kick[:16], home, away, "Club friendlies (clf)", fresh)
    row["in_window"] = True
    if str(row["kickoff_utc"]) < "2026-11-10T07:00:00Z":
        row["flags"] = row["flags"] + ["KICKED_OFF_BEFORE_SCAN_MIDPOINT"]
    soccer["in_window"].append(row)
    print("INWIN", row["kickoff_utc"], row["fixture"], row["ml_yes_prices"], "liq", row["liquidity_sum"], row["flags"], flush=True)

# --- Copa del Rey: Tue Nov 10 ties (next cycle) + later rounds ---
cd = load("copa_details")
fam = {}
for eid, ev in cd.items():
    root = re.sub(r" - (More Markets|Exact Score|Halftime Result|First Team to Score|Second Half Result|Total Corners|Player Props)$", "", str(ev.get("title")))
    g = min((str(m.get("gameStartTime") or "9999") for m in (ev.get("markets") or []) if m.get("gameStartTime")), default="9999")
    if g[:10] >= "2026-11-10":
        fam.setdefault((g[:16], root), {})[eid] = ev
for (kick, root), evs in sorted(fam.items()):
    home, away = [x.strip() for x in root.split(" vs. ")] if " vs. " in root else (root, "?")
    fresh = {}
    for eid in evs:
        fe = fresh_event(eid)
        if fe:
            fresh[eid] = fe
        time.sleep(0.3)
    row = fixture_row(kick, home, away, "Copa del Rey", fresh)
    row["in_window"] = "2026-11-10T01:10:00Z" <= row["kickoff_utc"] <= "2026-11-10T13:10:00Z"
    if kick[:10] == "2026-11-10":
        soccer["copa_del_rey_tue_nov10"].append(row)
    else:
        soccer["copa_del_rey_later"].append(row)
    print("COPA", row["kickoff_utc"], row["fixture"], row["ml_yes_prices"], "ou", row["ou25_yes_price"], "liq", row["liquidity_sum"], "rated", row["rated"], row["flags"], flush=True)

# --- other clf friendlies this week (kick >= Nov 10, not already in board) ---
done_roots = {r["fixture"] for r in soccer["in_window"]}
for (g, root), lst in sorted(clf_fix.items()):
    if g < "2026-11-10" or root in done_roots:
        continue
    ids = sorted({eid for eid, _ in lst})
    fresh = {}
    for eid in ids:
        fe = fresh_event(eid)
        if fe:
            fresh[eid] = fe
        time.sleep(0.3)
    home, away = [x.strip() for x in root.split(" vs. ")] if " vs. " in root else (root, "?")
    row = fixture_row(g, home, away, "Club friendlies (clf)", fresh)
    row["in_window"] = "2026-11-10T01:10:00Z" <= row["kickoff_utc"] <= "2026-11-10T13:10:00Z"
    soccer["club_friendships_week"].append(row)
    print("CLFW", row["kickoff_utc"], row["fixture"], row["ml_yes_prices"], "rated", row["rated"], flush=True)

# --- league resumption (modelable calendar, next cycles) ---
resum = []
for tag, label in [("la_liga", "La Liga"), ("epl", "EPL"), ("sea", "Serie A"),
                   ("bundesliga", "Bundesliga"), ("ligue_1", "Ligue 1"),
                   ("efl_championship", "Championship"), ("ere", "Eredivisie")]:
    try:
        evs = load(f"tag_{tag}")
    except Exception:
        continue
    ks = set()
    for e in evs:
        for m in e.get("markets") or []:
            g = str(m.get("gameStartTime") or "")[:16]
            if g >= "2026-11-19":
                ks.add((g, re.sub(r" - .*$", "", str(e.get("title")))))
    for g, t in sorted(ks)[:3]:
        resum.append({"league": label, "kickoff_utc": g.replace(" ", "T") + ":00Z", "fixture": t})
resum.sort(key=lambda r: r["kickoff_utc"])
soccer["league_resumption"] = resum[:14]

# --- post-break Monday Nov 23 rated-vs-rated fixtures (newly listed today) ---
pbm = []
for fn, label in [("detail_monza_fiorentina", "Serie A"), ("detail_brentford_everton", "EPL")]:
    try:
        ev = load(fn)
    except Exception:
        continue
    mkts = ev.get("markets") or []
    g = min((str(m.get("gameStartTime") or "9999") for m in mkts if m.get("gameStartTime")), default="9999")
    triple = {}
    for m in mkts:
        q = norm(m.get("question"))
        px = parse_px(m)
        if px is None:
            continue
        if "end in a draw" in q:
            triple["draw"] = px[0]
        elif "monza" in q and "win" in q:
            triple["home"] = px[0]
        elif "fiorentina" in q and "win" in q:
            triple["away"] = px[0]
        elif "brentford" in q and "win" in q:
            triple["home"] = px[0]
        elif "everton" in q and "win" in q:
            triple["away"] = px[0]
    pbm.append({"fixture": ev.get("title"), "league": label, "kickoff_utc": g[:16].replace(" ", "T") + ":00Z",
                "gamma_id": ev.get("id"), "ml_yes": triple,
                "liq_root_markets": round(sum(float(m.get("liquidityNum") or 0) for m in mkts), 2),
                "note": "BOTH clubs rated (Big-5 snapshot) - MODELABLE at next cycle; listed 2026-11-10"})
soccer["post_break_monday_nov23"] = pbm

# --- nations league ---
nl = load("tag_uefa_nations_league")
nlk = set()
for e in nl:
    for m in e.get("markets") or []:
        g = str(m.get("gameStartTime") or "")[:16]
        if g >= "2026-11-10":
            nlk.add((g, re.sub(r" - .*$", "", str(e.get("title")))))
nlk = sorted(nlk)
soccer["nations_league"] = {
    "first_fixtures": [{"kickoff_utc": g.replace(" ", "T") + ":00Z", "fixture": t} for g, t in nlk[:8]],
    "in_window_count": sum(1 for g, _ in nlk if "2026-11-10T01:10" <= g <= "2026-11-10T13:10"),
    "note": "Nations League kicks 2026-11-12; zero fixtures in the round-46 window" if not soccer["nations_league"] else "CHECK",
}

# ---------------- basketball ----------------
bkb = {}
# NBA Monday finals (ESPN 20261109 = US Mon slate, tips 00:00-03:00Z Nov 10)
nba_finals = []
sb = load("espn_nba_sb_20261109")
for e in sb.get("events") or []:
    comp = (e.get("competitions") or [{}])[0]
    sc = {}
    for c in comp.get("competitors") or []:
        ab = (c.get("team") or {}).get("abbreviation", "?")
        s = c.get("score")
        s = s.get("displayValue", "") if isinstance(s, dict) else str(s)
        sc["home" if c.get("homeAway") == "home" else "away"] = f"{ab} {s}"
    st = (e.get("status") or {}).get("type", {})
    tip = str(e.get("date"))[:19] + "Z" if str(e.get("date")).endswith("Z") is False else str(e.get("date"))[:19] + "Z"
    nba_finals.append({"tip_utc": str(e.get("date")), "game": e.get("name"),
                       "score": f"{sc.get('home','?')} vs {sc.get('away','?')}",
                       "state": st.get("state"), "detail": st.get("detail")})
bkb["nba_monday_us_slate_finals"] = nba_finals
bkb["nba_in_window_note"] = ("Only DEN@HOU tipped inside the window (01:30Z, ended ~04:10Z, "
                             "final HOU 110 - DEN 100 per ESPN; Gamma market resolved 0/1). "
                             "All other Monday tips were 00:00-03:00Z pre-window starts ending by ~05:30Z. "
                             "Next NBA tips ~00:00Z Wed Nov 11 (POR hosts OKC 04:00Z Wed).")

# next NBA tips (ESPN 20261110 = Wed 00:00Z+ slate)
nxt = []
try:
    sb2 = load("espn_nba_sb_20261110")
    for e in sb2.get("events") or []:
        nxt.append({"tip_utc": e.get("date"), "game": e.get("name")})
except Exception:
    pass
bkb["nba_next_tips_after_window"] = nxt

# in-window basketball (fresh prices + CLOB)
bw = load("window_basketball_details")
bb_rows = []
for eid, ev in bw.items():
    fe = fresh_event(eid)
    time.sleep(0.3)
    if not fe:
        fe = ev
    mk = (fe.get("markets") or [{}])[0]
    px = parse_px(mk)
    outs = []
    try:
        outs = json.loads(mk.get("outcomes") or "[]")
    except Exception:
        pass
    g = str(mk.get("gameStartTime") or "")[:16]
    tags = [t.get("slug") for t in (fe.get("tags") or [])]
    lg = "NBA" if "nba" in tags else ("NCAA MBB" if "ncaa-basketball" in tags else
         ("B.League (Japan)" if "bkjpn" in tags else ("KBL (Korea)" if "kbl" in tags else "/".join(tags[:3]))))
    row = {"kickoff_utc": g.replace(" ", "T") + ":00Z", "game": fe.get("title"), "league": lg,
           "gamma_id": eid, "prices_yes": px, "outcomes": outs,
           "bid/ask": [mk.get("bestBid"), mk.get("bestAsk")],
           "liq": mk.get("liquidityNum"), "vol24": mk.get("volume24hr"),
           "flags": flags_for(mk, px), "in_window": True}
    b = book_for(mk, "main")
    if b:
        row["clob_book"] = b
    bb_rows.append(row)
    print("BKB", g, str(fe.get("title"))[:44], lg, px, "liq", mk.get("liquidityNum"), row["flags"], flush=True)
bb_rows.sort(key=lambda r: r["kickoff_utc"])
bkb["in_window_board_only"] = bb_rows
bkb["ncaa_monday_finals_espn"] = [
    {"tip_utc": "2026-11-10T00:00Z", "game": "Wagner at UConn", "final": "UCONN 83 - WAG 41"},
    {"tip_utc": "2026-11-10T00:00Z", "game": "Grambling at Texas", "final": "TEX 93 - GRAM 62"},
    {"tip_utc": "2026-11-10T00:00Z", "game": "Radford at Tennessee", "final": "TENN 70 - RAD 47"},
    {"tip_utc": "2026-11-10T00:00Z", "game": "North Florida at Miami", "final": "MIA 89 - UNF 51"},
    {"tip_utc": "2026-11-10T00:30Z", "game": "Oakland at Alabama", "final": "ALA 109 - OAK 68"},
]
bkb["euroleague_note"] = ("EuroLeague not carried on Gamma game tags (futures + last round Nov 5-7 only; "
                          "tag euroleague = 0 events) and ESPN euroleague scoreboard returns 0; "
                          "Tuesday round games tip 17:30-20:00Z = OUTSIDE window; revisit next cycle "
                          "(if listed, board-only: no basketball model).")
bkb["cba_note"] = ("Chinese CBA on Gamma = futures only ('Chinese CBA: 2027 Champion'); "
                   "no CBA game markets exist. No Tuesday-noon CBA board.")

# POR section
por = {"monday": "POR idle Monday Nov 9 (last played Sat Nov 7 @LAL L 118-124 and Sun Nov 8 vs SA L 103-125)"}
ev = load("detail_por_playoffs")
for m in ev.get("markets") or []:
    if "blazer" in str(m.get("question", "")).lower():
        px = parse_px(m)
        b = book_for(m, "POR-make-playoffs-YES")
        por["make_playoffs_market"] = {
            "question": m.get("question"), "yes_price": px[0] if px else None,
            "bid/ask": [m.get("bestBid"), m.get("bestAsk")],
            "liq": m.get("liquidityNum"), "vol": m.get("volumeNum"), "vol24": m.get("volume24hr"),
            "clob_book": b,
        }
try:
    old = json.load(open("/home/ubuntu/paper-sim/round45/raw/nba_make_playoffs_event.json"))["data"]
    for m in old.get("markets") or []:
        if "blazer" in str(m.get("question", "")).lower():
            opx = parse_px(m)
            por["make_playoffs_round45_mark"] = opx[0] if opx else None
except Exception:
    por["make_playoffs_round45_mark"] = None
sch = load("espn_por_schedule_fresh")
nxt_por = []
for e in sch.get("events") or []:
    if str(e.get("date")) >= "2026-11-10":
        nxt_por.append({"tip_utc": e.get("date"), "game": e.get("name")})
        if len(nxt_por) >= 3:
            break
por["next_games"] = nxt_por
bkb["por_section"] = por

# ---------------- modelable check ----------------
modelable = []
for row in (soccer["in_window"] + soccer["copa_del_rey_tue_nov10"] +
            soccer["copa_del_rey_later"] + soccer["club_friendships_week"]):
    if row.get("modelable"):
        if "Copa del Rey" in row["league"]:
            row["modelable_note"] = ("TWO RATED CLUBS in Copa del Rey - dispatch exception: "
                                     "report as modelable, domestic path only, NO entry without "
                                     "coordinator arbitration.")
            modelable.append(row)
        else:
            row["modelable_note"] = "two rated clubs but competition is BOARD-ONLY (friendlies rule)"
            row["modelable"] = False

board = {
    "round": 46,
    "scan": "12h soccer+basketball board scan",
    "paper_only": True,
    "no_db_writes": True,
    "generated_utc": NOW.isoformat(),
    "window_utc": {"lo": LO, "hi": HI},
    "soccer": soccer,
    "basketball": bkb,
    "modelable_fixtures": modelable,
    "model_coverage": {
        "big5_domestic": "model exists (xG snapshot thru 2026-11-07); ZERO league fixtures in window (break Nov 9-17); leagues resume Nov 20-21",
        "efl_championship": "model exists; resume Nov 21 12:30Z (Millwall-QPR)",
        "eredivisie": "model exists; resume Nov 21 15:30Z (NEC-PSV)",
        "copa_del_rey": "NO model (cross-tier cup); all listed ties are rated-club-vs-minnow = MODEL-VOID, board-only",
        "club_friendlies_clf": "NO model (friendlies rule); board-only incl. in-window Paderborn-Braunschweig",
        "nations_league": "NO model; kicks Nov 12 17:00Z - nothing in window",
        "asian_australian_soccer": "no fixtures Nov 10 on ESPN feed; A-League last game Nov 8; J1/K1/CSL seasons ended; nothing on Gamma in window",
        "basketball_all": "NO basketball model exists (NBA/NCAA/EuroLeague/CBA/KBL/B.League all board-only)",
    },
    "decision": "ENTER NOTHING: zero modelable fixtures in window (board-only scan, no entries, $0)",
    "entries": [],
}
json.dump(board, open(f"{R46}/board.json", "w"), indent=1)
print("BOARD46 DONE ->", f"{R46}/board.json", flush=True)
print("modelable:", len(modelable), flush=True)
