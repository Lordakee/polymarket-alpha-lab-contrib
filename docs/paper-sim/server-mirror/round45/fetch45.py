"""ROUND-45B fetch: SPORTS-OTHER paper-sim scan raw inputs. PAPER ONLY, no DB writes.
POR playoffs futures mark (Gamma + CLOB book), NBA slate Nov 9-11, NFL Nov 9(MNF)+Nov 12-16,
CFB/tennis/UFC/boxing/F1/cricket fortnight events, ESPN NBA standings + POR schedule.
"""
import json, urllib.request, urllib.parse, time, datetime, os

RAW = "/home/ubuntu/paper-sim/round45/raw"
os.makedirs(RAW, exist_ok=True)
NOW = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
print("now", NOW.isoformat(), flush=True)

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
            time.sleep(2.5)

def dump(name, obj):
    json.dump({"fetched_at": NOW.isoformat(), "data": obj}, open(f"{RAW}/{name}.json", "w"))

G = "https://gamma-api.polymarket.com"

# ---- 1) POR playoffs futures: search Trail Blazers markets ----
for q in ["Trail Blazers playoffs", "Trail Blazers"]:
    d = get(f"{G}/markets?search={urllib.parse.quote(q)}&closed=false&limit=100")
    if d is not None:
        safe = q.replace(" ", "_")
        dump(f"por_search_{safe}", d)
        n = len(d) if isinstance(d, list) else "obj"
        print(f"por search [{q}]: {n} markets", flush=True)
    time.sleep(0.5)

d = get(f"{G}/events?search={urllib.parse.quote('Trail Blazers playoffs')}&closed=false&limit=50")
if d is not None:
    dump("por_events_search", d)
    print("por events search:", len(d), flush=True)

# ---- 2) Sport slates Nov 9-17 ----
slates = [
    ("nba", "nba_slate", "2026-11-09T00:00:00Z", "2026-11-11T23:59:59Z"),
    ("nfl", "nfl_slate", "2026-11-09T00:00:00Z", "2026-11-17T00:00:00Z"),
    ("cfb", "cfb_slate", "2026-11-09T00:00:00Z", "2026-11-17T00:00:00Z"),
    ("ncaaf", "ncaaf_slate", "2026-11-09T00:00:00Z", "2026-11-17T00:00:00Z"),
    ("tennis", "tennis_slate", "2026-11-09T00:00:00Z", "2026-11-17T00:00:00Z"),
    ("ufc", "ufc_slate", "2026-11-09T00:00:00Z", "2026-11-17T00:00:00Z"),
    ("boxing", "boxing_slate", "2026-11-09T00:00:00Z", "2026-11-17T00:00:00Z"),
    ("f1", "f1_slate", "2026-11-09T00:00:00Z", "2026-11-24T00:00:00Z"),
    ("cricket", "cricket_slate", "2026-11-09T00:00:00Z", "2026-11-17T00:00:00Z"),
]
for tag, fn, lo, hi in slates:
    d = get(f"{G}/events?tag_slug={tag}&closed=false&start_date_min={lo}&start_date_max={hi}&limit=100&order=startDate&ascending=true")
    if d is not None:
        dump(fn, d)
        print(f"{tag}: {len(d)} events", flush=True)
    time.sleep(0.5)

# ---- 3) ESPN: NBA standings, POR schedule, NBA scoreboard, NFL scoreboard ----
def espn(url, fn):
    d = get(url)
    if d is not None:
        dump(fn, d)
        print("espn", fn, "ok", flush=True)

espn("https://site.api.espn.com/apis/v2/sports/basketball/nba/standings", "espn_nba_standings")
espn("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/por/schedule", "espn_por_schedule")
espn("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=20261109", "espn_nba_sb_1109")
espn("https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=20261110", "espn_nba_sb_1110")
espn("https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates=20261109-20261117", "espn_nfl_sb")
print("FETCH45 DONE", flush=True)
