"""ROUND-46 fetch: 12h SOCCER+BASKETBALL board scan raw inputs. PAPER ONLY, no DB writes.

Window (kickoff/gameStartTime based): 2026-11-10T01:10:00Z .. 2026-11-10T13:10:00Z.
Gamma: soccer/basketball tag sweeps + date-window sweeps + public-search + detail
fetches (include_markets) for anything with gameStartTime near window + Copa del Rey
ties + the two Nov-23 Big-5 listings (Monza-Fiorentina 1352656, Brentford-Everton
1354164) + POR make-playoffs event 681898.
ESPN: soccer scoreboards 20261109/10/11 (Big-5 + Copa + NL + Asian/Aus + Americas),
NBA scoreboards 20261109/10/11, POR schedule, EuroLeague 20261110/11/12.
GET-only HTTP, no credentials, no orders, no DB writes.
"""
import json, urllib.request, urllib.parse, time, datetime, os

RAW = "/home/ubuntu/paper-sim/round46/raw"
os.makedirs(RAW, exist_ok=True)
NOW = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
LO = "2026-11-10T01:10:00Z"
HI = "2026-11-10T13:10:00Z"
print("now", NOW.isoformat(), "window", LO, "..", HI, flush=True)

def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except Exception as ex:
            print("ERR", url[:130], ex, flush=True)
            if i == tries - 1:
                return None
            time.sleep(2.5)

def dump(name, obj):
    json.dump({"fetched_at": NOW.isoformat(), "window": [LO, HI], "data": obj},
              open(f"{RAW}/{name}.json", "w"))

G = "https://gamma-api.polymarket.com"

# ---------- 1) Gamma tag sweeps (paginate) ----------
def sweep(tag, order="volume24hr", max_pages=10, extra=""):
    out, off = [], 0
    for _ in range(max_pages):
        d = get(f"{G}/events?tag_slug={tag}&closed=false&limit=100&offset={off}"
                f"&order={order}&ascending=false{extra}")
        if not d or not isinstance(d, list) or not d:
            break
        out.extend(d)
        if len(d) < 100:
            break
        off += 100
        time.sleep(0.35)
    return out

SOCCER_TAGS = [
    "soccer",              # generic: everything (ordered by recency too below)
    "copa-del-rey", "la-liga", "epl", "sea", "bundesliga", "ligue-1",
    "efl-championship", "ere",
    "nations-league", "uefa-nations-league", "friendlies", "world-cup-qualifiers-conmebol",
    "fa-cup", "efl-trophy",
    "mls", "mls-cup", "mex", "arg", "brazil-serie-a",
    "a-league", "a-league-men", "j-league", "k-league", "chinese-super-league",
    "saudi-pro-league", "indian-super-league", "afc-champions-league",
]
for tag in SOCCER_TAGS:
    evs = sweep(tag, order="volume24hr", max_pages=10)
    if evs is not None:
        dump(f"tag_{tag.replace('-', '_')}", evs)
        print(f"tag {tag}: {len(evs)}", flush=True)
    time.sleep(0.4)

# generic soccer by startDate ascending with date bound (catches new listings like
# Monza-Fiorentina / Brentford-Everton created hours ago)
d = get(f"{G}/events?tag_slug=soccer&closed=false&start_date_min=2026-11-09T00:00:00Z"
        f"&start_date_max=2026-11-25T00:00:00Z&limit=100&order=startDate&ascending=true")
if d is not None:
    dump("datewin_soccer_start", d)
    print("datewin soccer startDate asc:", len(d), flush=True)
time.sleep(0.4)
d = get(f"{G}/events?tag_slug=soccer&closed=false&start_date_min=2026-11-09T00:00:00Z"
        f"&start_date_max=2026-11-25T00:00:00Z&limit=100&order=volume24hr")
if d is not None:
    dump("datewin_soccer_vol", d)
    print("datewin soccer volume:", len(d), flush=True)

BKN_TAGS = ["nba", "euroleague", "eurocup", "basketball", "cba", "basketball-china",
            "kbl", "b-league", "fiba", "college-basketball"]
for tag in BKN_TAGS:
    evs = sweep(tag, order="volume24hr", max_pages=6)
    if evs is not None:
        dump(f"tag_{tag.replace('-', '_')}", evs)
        print(f"tag {tag}: {len(evs)}", flush=True)
    time.sleep(0.4)
d = get(f"{G}/events?tag_slug=basketball&closed=false&start_date_min=2026-11-09T00:00:00Z"
        f"&start_date_max=2026-11-25T00:00:00Z&limit=100&order=startDate&ascending=true")
if d is not None:
    dump("datewin_basketball_start", d)
    print("datewin basketball startDate asc:", len(d), flush=True)

# ---------- 2) public-search ----------
for q in ["Copa del Rey", "Nations League", "A-League", "EuroLeague", "CBA basketball",
          "Chinese Basketball", "B.League", "KBL"]:
    d = get(f"{G}/public-search?q={urllib.parse.quote(q)}&limit_per_type=25&events_status=active")
    if d is not None:
        dump(f"pubsearch_{q.replace(' ', '_').replace('.', '')}", d)
        evs = d.get("events", []) if isinstance(d, dict) else []
        print(f"[{q}]: {len(evs)} events", flush=True)
        for e in evs[:6]:
            print("   ", str(e.get("title"))[:80], str(e.get("startDate"))[:16], flush=True)
    time.sleep(0.4)

# ---------- 3) detail fetches ----------
# 3a) known event ids of interest (Nov-23 Big-5 listings + POR playoffs)
for eid, name in [(1352656, "detail_monza_fiorentina"), (1354164, "detail_brentford_everton"),
                  (681898, "detail_por_playoffs")]:
    ev = get(f"{G}/events/{eid}?include_markets=true")
    if ev:
        dump(name, ev)
        print("detail", name, "ok", flush=True)
    time.sleep(0.4)

# 3b) Copa del Rey: find event ids from tag sweep raw, fetch details
def load(name):
    return json.load(open(f"{RAW}/{name}.json"))["data"]

copa_ids = {}
try:
    for e in load("tag_copa_del_rey"):
        copa_ids[e.get("id")] = str(e.get("title"))
except Exception as ex:
    print("copa tag load ERR", ex, flush=True)
# also from generic soccer sweep: events whose title mentions Copa or whose tags do
try:
    for e in load("tag_soccer"):
        tt = " ".join(t.get("slug", "") for t in (e.get("tags") or []))
        if "copa-del-rey" in tt or "copa-del-rey" in str(e.get("slug", "")):
            copa_ids.setdefault(e.get("id"), str(e.get("title")))
except Exception as ex:
    print("soccer tag copa scan ERR", ex, flush=True)
print("copa candidate ids:", len(copa_ids), flush=True)
copa_details = {}
for eid, t in sorted(copa_ids.items()):
    ev = get(f"{G}/events/{eid}?include_markets=true")
    if ev:
        copa_details[eid] = ev
        mk = (ev.get("markets") or [{}])[0]
        print(f"  COPA {t[:44]:44s} gST={mk.get('gameStartTime')} px={mk.get('outcomePrices')}", flush=True)
    time.sleep(0.4)
dump("copa_details", copa_details)

# 3c) anything with gameStartTime inside [LO-2h, HI+4h] from all soccer sweeps -> details
def gST_in_window(e):
    for m in e.get("markets", []):
        g = str(m.get("gameStartTime") or "")
        if not g:
            continue
        iso = g.replace(" ", "T")
        if len(iso) >= 16:
            iso = iso[:19] + ("Z" if iso[19:20] not in ("Z", "+") else "")
        if LO[:19] <= iso[:19] <= HI[:19]:
            return True
    return False

seen_ids = set()
window_candidates = {}
for fn in [f"tag_{t.replace('-', '_')}" for t in SOCCER_TAGS] + ["datewin_soccer_start", "datewin_soccer_vol"]:
    try:
        for e in load(fn):
            if not isinstance(e, dict):
                continue
            eid = e.get("id")
            if eid in seen_ids:
                continue
            seen_ids.add(eid)
            if gST_in_window(e):
                window_candidates[eid] = str(e.get("title"))
    except Exception:
        pass
print("in-window (gameStartTime) soccer candidates:", len(window_candidates), flush=True)
wcd = {}
for eid, t in sorted(window_candidates.items()):
    ev = get(f"{G}/events/{eid}?include_markets=true")
    if ev:
        wcd[eid] = ev
        mk = (ev.get("markets") or [{}])[0]
        print(f"  WIN {t[:46]:46s} gST={mk.get('gameStartTime')}", flush=True)
    time.sleep(0.3)
dump("window_soccer_details", wcd)

# same for basketball
seenb, bwin = set(), {}
for fn in [f"tag_{t.replace('-', '_')}" for t in BKN_TAGS] + ["datewin_basketball_start"]:
    try:
        for e in load(fn):
            if not isinstance(e, dict):
                continue
            eid = e.get("id")
            if eid in seenb:
                continue
            seenb.add(eid)
            if gST_in_window(e):
                bwin[eid] = str(e.get("title"))
    except Exception:
        pass
print("in-window basketball candidates:", len(bwin), flush=True)
bwd = {}
for eid, t in sorted(bwin.items()):
    ev = get(f"{G}/events/{eid}?include_markets=true")
    if ev:
        bwd[eid] = ev
    time.sleep(0.3)
dump("window_basketball_details", bwd)

# ---------- 4) ESPN ----------
ESPN = "https://site.api.espn.com/apis/site/v2/sports"
def espn(path, fn):
    d = get(f"{ESPN}/{path}")
    if d is not None:
        dump(fn, d)
        n = len(d.get("events", []) or []) if isinstance(d, dict) else "?"
        print("espn", fn, "events:", n, flush=True)
    time.sleep(0.35)

SOCCER_CODES = {
    "esp.copa_del_rey": "Copa_del_Rey", "esp.1": "La_Liga", "esp.2": "La_Liga_2",
    "eng.1": "EPL", "eng.2": "Championship",
    "ita.1": "Serie_A", "ita.2": "Serie_B",
    "fra.1": "Ligue_1", "ger.1": "Bundesliga", "ned.1": "Eredivisie",
    "por.1": "Liga_Portugal", "por.2": "Liga_Portugal_2",
    "uefa.nations": "UEFA_Nations_League",
    "aus.1": "A-League", "jpn.1": "J1_League", "kor.1": "K_League_1",
    "chn.1": "Chinese_Super_League", "ksa.1": "Saudi_Pro_League",
    "ind.1": "Indian_Super_League", "tha.1": "Thai_League_1",
    "uae.1": "UAE_Pro_League", "qat.1": "Qatar_Stars_League",
    "afc.champions": "AFC_Champions_League_Elite", "afc.champions.two": "AFC_Champions_League_Two",
    "usa.1": "MLS", "mex.1": "Liga_MX", "arg.1": "Argentina_Primera", "bra.1": "Brasileirao",
}
for date in ["20261109", "20261110", "20261111"]:
    for code, label in SOCCER_CODES.items():
        espn(f"soccer/{code}/scoreboard?dates={date}", f"espn_soc_{label}_{date}")

for date in ["20261109", "20261110", "20261111"]:
    espn(f"basketball/nba/scoreboard?dates={date}", f"espn_nba_sb_{date}")
espn("basketball/nba/teams/por/schedule", "espn_por_schedule_fresh")
for date in ["20261110", "20261111", "20261112"]:
    espn(f"basketball/euroleague/scoreboard?dates={date}", f"espn_euroleague_sb_{date}")

print("FETCH46 DONE", flush=True)
