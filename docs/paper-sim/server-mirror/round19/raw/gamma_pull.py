import json, urllib.request, urllib.parse, time

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def dump(name, obj):
    with open(name, "w") as f:
        json.dump(obj, f, indent=1)

def show_event(ev):
    t = ev.get("title", "?")
    sd = ev.get("startDate", "")
    out = [f"EV: {t} | start={sd} | slug={ev.get('slug','') } | id={ev.get('id','')}"]
    for m in ev.get("markets", [])[:6]:
        try:
            prices = json.loads(m.get("outcomePrices", "[]"))
        except Exception:
            prices = m.get("outcomePrices", [])
        outs = m.get("outcomes", "")
        liq = m.get("liquidityNum", "")
        vol = m.get("volumeNum", "")
        out.append(f"   MKT {m.get('question','?')[:70]} | {outs} | px={prices} | liq={liq} vol={vol} | closed={m.get('closed')} | end={m.get('endDate','')}")
    return "\n".join(out)

# --- MLB ---
try:
    d = get("https://gamma-api.polymarket.com/events?tag_slug=mlb&closed=false&limit=25&order=startDate&ascending=true")
    dump("gamma_mlb_events.json", d)
    print(f"--- MLB events: {len(d)} ---")
    for ev in d:
        print(show_event(ev))
except Exception as ex:
    print("ERR mlb", ex)
time.sleep(1.5)

# --- NBA upcoming games (near-term) ---
nba_all = []
try:
    d = get("https://gamma-api.polymarket.com/events?tag_slug=nba&closed=false&limit=40&order=startDate&ascending=true")
    nba_all.extend(d)
    dump("gamma_nba_events_p1.json", d)
    print(f"--- NBA events p1: {len(d)} ---")
    for ev in d:
        print(show_event(ev))
except Exception as ex:
    print("ERR nba p1", ex)
time.sleep(1.5)
if len(nba_all) == 40:
    try:
        d = get("https://gamma-api.polymarket.com/events?tag_slug=nba&closed=false&limit=40&offset=40&order=startDate&ascending=true")
        nba_all.extend(d)
        dump("gamma_nba_events_p2.json", d)
        print(f"--- NBA events p2: {len(d)} ---")
        for ev in d:
            print(show_event(ev))
    except Exception as ex:
        print("ERR nba p2", ex)
    time.sleep(1.5)

# --- POR futures search ---
for q in ("trail blazers playoffs", "trail blazers"):
    try:
        d = get("https://gamma-api.polymarket.com/public-search?q=" + urllib.parse.quote(q) + "&limit_per_type=15&events_status=active")
        dump("gamma_search_por.json", d)
        print(f"--- SEARCH: {q} ---")
        evs = d.get("events", []) if isinstance(d, dict) else []
        for ev in evs:
            print(show_event(ev))
        break
    except Exception as ex:
        print("ERR search", q, ex)
    time.sleep(1.5)

# --- NFL events ---
try:
    d = get("https://gamma-api.polymarket.com/events?tag_slug=nfl&closed=false&limit=25&order=startDate&ascending=true")
    dump("gamma_nfl_events.json", d)
    print(f"--- NFL events: {len(d)} ---")
    for ev in d:
        print(show_event(ev))
except Exception as ex:
    print("ERR nfl", ex)
