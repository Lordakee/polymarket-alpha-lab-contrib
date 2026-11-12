import json, urllib.request, gzip, time

LEAGUES = ["EPL", "La_liga", "Serie_A", "Bundesliga", "Ligue_1"]
SEASONS = ["2025", "2026"]

def get(url, referer):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": referer,
        "Accept-Encoding": "gzip",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
        return json.loads(data.decode())

out = {}
for lg in LEAGUES:
    for se in SEASONS:
        url = "https://understat.com/getLeagueData/" + lg + "/" + se
        ref = "https://understat.com/league/" + lg + "/" + se
        try:
            d = get(url, ref)
            out["%s_%s" % (lg, se)] = d
            teams = d.get("teams", {})
            n_hist = sum(len(t.get("history", [])) for t in teams.values())
            print("OK", lg, se, "teams=", len(teams), "matches_recorded=", n_hist // 2, flush=True)
        except Exception as e:
            print("ERR", lg, se, repr(e), flush=True)
        time.sleep(1.0)

json.dump(out, open("/home/ubuntu/paper-sim/round5/raw/xg_understat.json", "w"))
print("saved", len(out))

# freshness check on EPL 2026: last played dates
try:
    epl = out["EPL_2026"]
    res = [m for m in epl["dates"] if m.get("isResult")]
    res.sort(key=lambda m: m["datetime"])
    print("EPL26 results:", len(res))
    for m in res[-6:]:
        print(" ", m["datetime"], m["h"]["title"], "vs", m["a"]["title"])
except Exception as e:
    print("check err", e)
