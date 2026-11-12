"""Round45b: POR results with scores; NBA slate board; NFL/CFB week markets; F1 Abu Dhabi; UFC next card; tennis/cricket top boards."""
import json, urllib.request, urllib.parse, time, datetime, os

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

# ---- 1) POR results with scores ----
sch = load("espn_por_schedule")
print("=== POR results ===", flush=True)
for e in sch.get("events", []):
    comp = e.get("competitions", [{}])[0]
    parts = []
    for c in comp.get("competitors", []):
        ab = c.get("team", {}).get("abbreviation", "?")
        sc = c.get("score", "")
        wl = ""
        try:
            agg = c.get("series", {}).get("aggregate", "")
        except Exception:
            agg = ""
        parts.append(f"{'H' if c.get('homeAway')=='home' else 'a'}{ab} {sc}")
    st = e.get("status", {}).get("type", {})
    if st.get("completed"):
        print(" ", e.get("date", "")[:10], " ".join(parts), "FINAL", flush=True)

# ---- 2) NBA slate Nov 9-11 board ----
slate = load("nba_slate")
print(f"=== NBA slate Nov9-11: {len(slate)} events ===", flush=True)
rows = []
for e in slate:
    mk = None
    for m in e.get("markets", []):
        if str(m.get("question", "")).lower().find("win") >= 0 or str(m.get("outcomes", "")).count("Yes") == 0:
            mk = m
            break
    mk = mk or (e.get("markets") or [{}])[0]
    try:
        prices = json.loads(mk.get("outcomePrices") or "[]")
    except Exception:
        prices = []
    rows.append({
        "ev": e.get("title"), "start": e.get("startDate"), "end": e.get("endDate"),
        "q": mk.get("question"), "prices": prices, "liq": mk.get("liquidityNum"),
        "vol": mk.get("volumeNum"), "bid": mk.get("bestBid"), "ask": mk.get("bestAsk"),
        "vol24": mk.get("volume24hr"),
    })
    print(f"  {str(e.get('title'))[:44]:44s} start={str(e.get('startDate'))[:16]} px={prices} liq={mk.get('liquidityNum')} vol24={mk.get('volume24hr')}", flush=True)
dump("nba_slate_board", rows)

# ---- 3) NFL: tag nfl wide, filter endDate window ----
alln = []
for off in [0, 200, 400, 600]:
    d = get(f"{G}/events?tag_slug=nfl&closed=false&limit=200&offset={off}")
    if not d:
        break
    alln.extend(d)
    time.sleep(0.4)
print("nfl tag total:", len(alln), flush=True)
nfl_rows = []
for e in alln:
    ed = str(e.get("endDate") or "")[:10]
    sd = str(e.get("startDate") or "")[:10]
    title = str(e.get("title", ""))
    if " vs" in title or " @ " in title or "vs." in title:
        # game-like event; keep if it plausibly resolves in week window
        if ed >= "2026-11-09" and ed <= "2026-11-18":
            mk = (e.get("markets") or [{}])[0]
            try:
                prices = json.loads(mk.get("outcomePrices") or "[]")
            except Exception:
                prices = []
            nfl_rows.append({"ev": title, "start": e.get("startDate"), "end": e.get("endDate"),
                             "q": mk.get("question"), "prices": prices, "liq": mk.get("liquidityNum"),
                             "vol": mk.get("volumeNum"), "vol24": mk.get("volume24hr")})
print(f"NFL game events ending Nov 9-18: {len(nfl_rows)}", flush=True)
for r in sorted(nfl_rows, key=lambda x: -(x["liq"] or 0))[:25]:
    print(f"  {r['ev'][:46]:46s} end={str(r['end'])[:16]} px={r['prices']} liq={r['liq']} vol24={r['vol24']}", flush=True)
dump("nfl_week_board", nfl_rows)

# ---- 4) CFB: tag ncaaf wide, filter endDate window ----
allc = []
for off in [0, 200, 400]:
    d = get(f"{G}/events?tag_slug=ncaaf&closed=false&limit=200&offset={off}")
    if not d:
        break
    allc.extend(d)
    time.sleep(0.4)
print("ncaaf tag total:", len(allc), flush=True)
cfb_rows = []
for e in allc:
    ed = str(e.get("endDate") or "")[:10]
    title = str(e.get("title", ""))
    if ("vs" in title or " @ " in title) and ed >= "2026-11-09" and ed <= "2026-11-18":
        mk = (e.get("markets") or [{}])[0]
        try:
            prices = json.loads(mk.get("outcomePrices") or "[]")
        except Exception:
            prices = []
        cfb_rows.append({"ev": title, "end": e.get("endDate"), "prices": prices,
                         "liq": mk.get("liquidityNum"), "vol": mk.get("volumeNum")})
print(f"CFB game events ending Nov 9-18: {len(cfb_rows)}", flush=True)
for r in sorted(cfb_rows, key=lambda x: -(x["liq"] or 0))[:15]:
    print(f"  {r['ev'][:50]:50s} px={r['prices']} liq={r['liq']} vol={r['vol']}", flush=True)
dump("cfb_week_board", cfb_rows)

# ---- 5) F1 + UFC targeted searches ----
for q, fn in [("Abu Dhabi Grand Prix", "pubsearch_abudhabi"), ("UFC 335", "pubsearch_ufc335"), ("UFC Fight Night", "pubsearch_ufcfn")]:
    d = get(f"{G}/public-search?q={urllib.parse.quote(q)}&limit_per_type=25&events_status=active")
    if d is not None:
        dump(fn, d)
        print(f"[{q}]", flush=True)
        for e in d.get("events", [])[:12]:
            print("   ", str(e.get("title"))[:90], flush=True)
    time.sleep(0.4)

# ---- 6) tennis + cricket: top by liquidity from earlier fetches ----
for fn, label in [("tennis_slate", "TENNIS"), ("cricket_slate", "CRICKET")]:
    try:
        evs = load(fn)
        rows = []
        for e in evs:
            mk = (e.get("markets") or [{}])[0]
            try:
                prices = json.loads(mk.get("outcomePrices") or "[]")
            except Exception:
                prices = []
            rows.append({"ev": e.get("title"), "start": e.get("startDate"), "prices": prices,
                         "liq": mk.get("liquidityNum"), "vol": mk.get("volumeNum")})
        rows.sort(key=lambda x: -(x["liq"] or 0))
        dump(f"{fn}_board", rows)
        print(f"=== {label} top by liq ({len(rows)} events) ===", flush=True)
        for r in rows[:12]:
            print(f"  {str(r['ev'])[:52]:52s} start={str(r['start'])[:16]} px={r['prices']} liq={r['liq']} vol={r['vol']}", flush=True)
    except Exception as ex:
        print(fn, "ERR", ex, flush=True)
print("BOARDS45B DONE", flush=True)
