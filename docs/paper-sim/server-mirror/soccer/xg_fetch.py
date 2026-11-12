import json, urllib.request, gzip, time, os

os.makedirs("/home/ubuntu/paper-sim/soccer/raw/xg", exist_ok=True)
LEAGUES = ["EPL", "La_liga"]          # understat league codes
SEASONS = ["2025", "2026"]            # 2025=2025/26 completed, 2026=2026/27 current

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

for lg in LEAGUES:
    for se in SEASONS:
        url = "https://understat.com/getLeagueData/" + lg + "/" + se
        ref = "https://understat.com/league/" + lg + "/" + se
        try:
            d = get(url, ref)
            fn = "/home/ubuntu/paper-sim/soccer/raw/xg/%s_%s.json" % (lg, se)
            with open(fn, "w") as f:
                json.dump(d, f)
            teams = d.get("teams", {})
            n_hist = sum(len(t.get("history", [])) for t in teams.values())
            print("OK", lg, se, "teams=", len(teams), "matches_recorded=", n_hist // 2)
        except Exception as e:
            print("ERR", lg, se, e)
        time.sleep(1.0)

# quick sanity dump for current EPL season
fn = "/home/ubuntu/paper-sim/soccer/raw/xg/EPL_2026.json"
d = json.load(open(fn))
teams = d["teams"]
print()
print("EPL 2026/27 (current) per-team summary:")
for tid, t in sorted(teams.items(), key=lambda kv: -sum(1 for h in kv[1]["history"] if h["h_a"] == "h") if False else 0):
    hist = t["history"]
    if not hist:
        print("  ", t["title"], "NO MATCHES YET")
        continue
    xg_for = sum(float(h["xG"]) for h in hist)
    xg_ag = sum(float(h["xGA"]) for h in hist)
    n = len(hist)
    print("  %-28s n=%2d xG/g=%5.2f xGA/g=%5.2f pts=%d" % (
        t["title"], n, xg_for / n, xg_ag / n, sum(int(h["pts"]) for h in hist)))
