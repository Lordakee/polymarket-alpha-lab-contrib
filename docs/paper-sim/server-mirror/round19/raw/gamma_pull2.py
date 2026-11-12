import json, urllib.request, urllib.parse, time

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def mkt_line(m):
    try:
        prices = json.loads(m.get("outcomePrices", "[]"))
    except Exception:
        prices = []
    return f"MKT {m.get('question','?')[:75]} | {m.get('outcomes','')} | px={prices} | liq={m.get('liquidityNum','')} vol={m.get('volumeNum','')} | closed={m.get('closed')} | slug={m.get('slug','')[:60]}"

# 1) POR playoffs market (event 681898 full)
try:
    d = get("https://gamma-api.polymarket.com/events/681898")
    json.dump(d, open("gamma_event_playoffs.json", "w"))
    for m in d.get("markets", []):
        q = m.get("question", "")
        if any(k in q for k in ("Portland", "Lakers", "Grizzlies", "Warriors", "Spurs", "Suns")):
            print("PORPLAYOFFS " + mkt_line(m))
except Exception as ex:
    print("ERR ev681898", ex)
time.sleep(1.6)

# 2) WS champion event 179312 full - MIL market
try:
    d = get("https://gamma-api.polymarket.com/events/179312")
    json.dump(d, open("gamma_event_ws.json", "w"))
    for m in d.get("markets", []):
        q = m.get("question", "")
        if "Brewers" in q or "Rays" in q:
            print("WSCHAMP " + mkt_line(m))
except Exception as ex:
    print("ERR ev179312", ex)
time.sleep(1.6)

# 3) MLB recent events (descending)
try:
    d = get("https://gamma-api.polymarket.com/events?tag_slug=mlb&closed=false&limit=30&order=startDate&ascending=false")
    json.dump(d, open("gamma_mlb_recent.json", "w"))
    print(f"--- MLB recent: {len(d)} ---")
    for ev in d:
        print(f"EV {ev.get('title','?')} | slug={ev.get('slug','')} | id={ev.get('id')}")
        for m in ev.get("markets", [])[:4]:
            print("   " + mkt_line(m))
except Exception as ex:
    print("ERR mlb desc", ex)
time.sleep(1.6)

# 4) search brewers rays game markets
try:
    d = get("https://gamma-api.polymarket.com/public-search?q=" + urllib.parse.quote("brewers rays") + "&limit_per_type=15&events_status=active")
    json.dump(d, open("gamma_search_brewersrays.json", "w"))
    print("--- SEARCH brewers rays ---")
    for ev in d.get("events", []):
        print(f"EV {ev.get('title','?')} | slug={ev.get('slug','')} | id={ev.get('id')}")
        for m in ev.get("markets", [])[:4]:
            print("   " + mkt_line(m))
except Exception as ex:
    print("ERR search br", ex)
time.sleep(1.6)

# 5) NFL recent events (descending) - wk8 lines?
try:
    d = get("https://gamma-api.polymarket.com/events?tag_slug=nfl&closed=false&limit=30&order=startDate&ascending=false")
    json.dump(d, open("gamma_nfl_recent.json", "w"))
    print(f"--- NFL recent: {len(d)} ---")
    for ev in d:
        print(f"EV {ev.get('title','?')} | slug={ev.get('slug','')} | id={ev.get('id')}")
        for m in ev.get("markets", [])[:3]:
            print("   " + mkt_line(m))
except Exception as ex:
    print("ERR nfl desc", ex)
