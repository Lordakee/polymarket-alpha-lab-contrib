"""Round45c: reconcile ESPN NBA scoreboards; POR results scores; F1 Abu Dhabi + UFC FN event details; CFB futures lines."""
import json, urllib.request, urllib.parse, time, datetime

RAW = "/home/ubuntu/paper-sim/round45/raw"
NOW = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)

def get(url, tries=2):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except Exception as ex:
            print("ERR", url[:130], ex, flush=True)
            if i == tries - 1:
                return None
            time.sleep(2)

def dump(name, obj):
    json.dump({"fetched_at": NOW.isoformat(), "data": obj}, open(f"{RAW}/{name}.json", "w"))

def load(name):
    return json.load(open(f"{RAW}/{name}.json"))["data"]

G = "https://gamma-api.polymarket.com"

# 1) ESPN NBA scoreboard Nov 9 + Nov 10
for fn in ["espn_nba_sb_1109", "espn_nba_sb_1110"]:
    try:
        sb = load(fn)
        evs = sb.get("events", [])
        print(f"=== {fn}: {len(evs)} games ===", flush=True)
        for e in evs:
            print("  ", str(e.get("name"))[:40], e.get("date", "")[:16], e.get("status", {}).get("type", {}).get("shortDetail", ""), flush=True)
    except Exception as ex:
        print(fn, "ERR", ex, flush=True)

# 2) POR results (raw scores, no status filter)
sch = load("espn_por_schedule")
print("=== POR all games with scores ===", flush=True)
for e in sch.get("events", []):
    comp = e.get("competitions", [{}])[0]
    parts = []
    for c in comp.get("competitors", []):
        ab = c.get("team", {}).get("abbreviation", "?")
        parts.append(f"{'H' if c.get('homeAway')=='home' else 'a'}{ab}:{c.get('score','')}")
    st = e.get("status", {}).get("type", {})
    print("  ", e.get("date", "")[:10], " ".join(parts), "state=", st.get("state", "?"), flush=True)

# 3) F1 Abu Dhabi: find event ids from pubsearch, fetch driver winner market
try:
    ps = load("pubsearch_abudhabi")
    evs = ps.get("events", [])
    for e in evs:
        t = str(e.get("title", ""))
        if t in ("Abu Dhabi Grand Prix: Driver Winner", "Abu Dhabi Grand Prix: Driver Podium Finish"):
            ev = get(f"{G}/events/{e.get('id')}?include_markets=true")
            if ev:
                safe = "abudhabi_winner" if "Winner" in t else "abudhabi_podium"
                dump(safe, ev)
                print(f"--- {t}: start={ev.get('startDate')} end={ev.get('endDate')}", flush=True)
                mkts = sorted(ev.get("markets", []), key=lambda m: -(float(m.get("liquidityNum") or 0)))
                for m in mkts[:12]:
                    try:
                        pr = json.loads(m.get("outcomePrices") or "[]")
                    except Exception:
                        pr = []
                    print(f"    {str(m.get('question'))[:52]:52s} px={pr} liq={m.get('liquidityNum')}", flush=True)
    time.sleep(0.3)
except Exception as ex:
    print("abudhabi ERR", ex, flush=True)

# 4) UFC Fight Night: dates + main card prices
try:
    ps = load("pubsearch_ufcfn")
    evs = ps.get("events", [])
    for e in evs[:10]:
        ev = get(f"{G}/events/{e.get('id')}?include_markets=true")
        if not ev:
            continue
        mk = (ev.get("markets") or [{}])[0]
        try:
            pr = json.loads(mk.get("outcomePrices") or "[]")
        except Exception:
            pr = []
        print(f"UFC: {str(ev.get('title'))[:60]:60s} start={str(ev.get('startDate'))[:16]} px={pr} liq={mk.get('liquidityNum')} vol={mk.get('volumeNum')}", flush=True)
        time.sleep(0.3)
    dump("ufc_fn_events", evs)
except Exception as ex:
    print("ufc ERR", ex, flush=True)

# 5) CFB futures: National Champion + CFP make playoffs top lines
for q, fn, keepn in [("NCAA Football 2027 National Champion", "cfb_champ", 8),
                     ("NCAA Football Team to make College Football Playoffs", "cfb_cfp_make", 12)]:
    d = get(f"{G}/public-search?q={urllib.parse.quote(q)}&limit_per_type=5&events_status=active")
    if d:
        for e in d.get("events", [])[:2]:
            ev = get(f"{G}/events/{e.get('id')}?include_markets=true")
            if ev:
                dump(fn, ev)
                mkts = sorted(ev.get("markets", []), key=lambda m: -(float(m.get("liquidityNum") or 0)))
                print(f"--- {ev.get('title')} end={str(ev.get('endDate'))[:10]}", flush=True)
                for m in mkts[:keepn]:
                    try:
                        pr = json.loads(m.get("outcomePrices") or "[]")
                    except Exception:
                        pr = []
                    print(f"    {str(m.get('question'))[:56]:56s} px={pr} liq={m.get('liquidityNum')}", flush=True)
                time.sleep(0.3)
print("RECON45 DONE", flush=True)
