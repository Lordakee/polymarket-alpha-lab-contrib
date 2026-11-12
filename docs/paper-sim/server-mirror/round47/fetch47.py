"""ROUND-47 fetch: 24h SOCCER+BASKETBALL board scan raw inputs. PAPER ONLY, no DB writes.

Window: 2026-11-12T01:15:00Z .. 2026-11-13T01:15:00Z (kickoff/tip based).
Gamma: soccer/basketball tag sweeps + date-window sweeps + public-search +
detail fetches (include_markets) for anything with gameStartTime near window
(UNL Nov-12 slate + Nov-13 games, Copa del Rey Nov-12 ties, clf friendlies,
NBA Wed-US leftovers + Thu-US edge slate, KBL/B.League/CBA boards).
ESPN: NBA scoreboards 20261111/12/13 (Wed-US finals + live, Thu-US slate),
soccer scoreboards (Copa del Rey, uefa.nations.league 12+13, friendlies feed),
POR schedule. GET-only HTTP, no credentials, no orders, no DB writes.
"""
import json, urllib.request, urllib.parse, time, datetime, os

RAW = "/home/ubuntu/paper-sim/round47/raw"
os.makedirs(RAW, exist_ok=True)
NOW = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
LO = "2026-11-12T01:15:00Z"
HI = "2026-11-13T01:15:00Z"
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

# ---------- 1) Gamma tag sweeps ----------
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
    "soccer",
    "uefa-nations-league", "nations-league", "friendlies", "clf",
    "copa-del-rey", "la-liga", "epl", "sea", "bundesliga", "ligue-1",
    "efl-championship", "ere", "fa-cup", "efl-trophy",
    "mls", "mex", "arg", "brazil-serie-a", "a-league", "a-league-men",
    "j-league", "k-league", "chinese-super-league", "saudi-pro-league",
    "indian-super-league", "afc-champions-league", "world-cup-qualifiers-conmebol",
]
for tag in SOCCER_TAGS:
    evs = sweep(tag, max_pages=10)
    if evs is not None:
        dump(f"tag_{tag.replace('-', '_')}", evs)
        print(f"tag {tag}: {len(evs)}", flush=True)
    time.sleep(0.4)

# date-window sweeps (catch freshly created listings)
for qs, name in [
    ("soccer&start_date_min=2026-11-11T00:00:00Z&start_date_max=2026-11-15T00:00:00Z", "datewin_soccer_start"),
    ("soccer&start_date_min=2026-11-11T00:00:00Z&start_date_max=2026-11-15T00:00:00Z&order=volume24hr", "datewin_soccer_vol"),
]:
    d = get(f"{G}/events?tag_slug={qs.split('&')[0]}&closed=false&" +
            "&".join(qs.split("&")[1:]) + "&limit=100" +
            ("&order=startDate&ascending=true" if "start" in name else ""))
    if d is not None:
        dump(name, d)
        print(name, len(d), flush=True)
    time.sleep(0.4)

BKN_TAGS = ["nba", "basketball", "kbl", "b-league", "cba", "basketball-china",
            "euroleague", "fiba", "college-basketball"]
for tag in BKN_TAGS:
    evs = sweep(tag, max_pages=6)
    if evs is not None:
        dump(f"tag_{tag.replace('-', '_')}", evs)
        print(f"tag {tag}: {len(evs)}", flush=True)
    time.sleep(0.4)
d = get(f"{G}/events?tag_slug=basketball&closed=false&start_date_min=2026-11-11T00:00:00Z"
        f"&start_date_max=2026-11-15T00:00:00Z&limit=100&order=startDate&ascending=true")
if d is not None:
    dump("datewin_basketball_start", d)
    print("datewin basketball startDate asc:", len(d), flush=True)

# ---------- 2) public-search ----------
for q in ["Nations League", "Copa del Rey", "NBA", "KBL", "B.League", "CBA basketball",
          "Chinese Basketball", "friendlies soccer"]:
    d = get(f"{G}/public-search?q={urllib.parse.quote(q)}&limit_per_type=25&events_status=active")
    if d is not None:
        dump(f"pubsearch_{q.replace(' ', '_').replace('.', '')}", d)
        evs = d.get("events", []) if isinstance(d, dict) else []
        print(f"[{q}]: {len(evs)} events", flush=True)
        for e in evs[:5]:
            print("   ", str(e.get("title"))[:80], str(e.get("startDate"))[:16], flush=True)
    time.sleep(0.4)

# ---------- 3) ESPN cross-checks ----------
E = "https://site.api.espn.com"
def espn(path, name):
    d = get(E + path)
    if d is not None:
        dump(name, d)
        n = len((d.get("events") or []))
        print(f"espn {name}: {n} events", flush=True)
    time.sleep(0.4)

# NBA: US Wed Nov 11 (tips Nov 12 00:00-04:30Z: POR@OKC B2B g2 + Wed leftovers),
# US Thu Nov 12 (tips Nov 13 00:00Z+: edge-of-window slate), US Fri Nov 13 (out).
for ymd, nm in [("20261111", "espn_nba_sb_20261111"), ("20261112", "espn_nba_sb_20261112"),
                ("20261113", "espn_nba_sb_20261113")]:
    espn(f"/apis/site/v2/sports/basketball/nba/scoreboard?dates={ymd}", nm)
espn("/apis/site/v2/sports/basketball/nba/teams/por/schedule", "espn_por_schedule")

# soccer: Copa del Rey + Nations League Nov 12/13 + generic soccer feeds
for ymd in ["20261112", "20261113"]:
    espn(f"/apis/site/v2/sports/soccer/copa.del.rey/scoreboard?dates={ymd}", f"espn_soc_Copa_del_Rey_{ymd}")
    espn(f"/apis/site/v2/sports/soccer/uefa.nations.league/scoreboard?dates={ymd}", f"espn_soc_Nations_League_{ymd}")
    espn(f"/apis/site/v2/sports/soccer/all/scoreboard?dates={ymd}", f"espn_soc_all_{ymd}")

print("FETCH47 DONE", datetime.datetime.now(datetime.timezone.utc).isoformat(), flush=True)
