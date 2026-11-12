import json, urllib.request, gzip, datetime

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
        return json.loads(data.decode())

print("UTC now:", datetime.datetime.now(datetime.timezone.utc).isoformat())
out = {}
for label, dates in [("ucl_full", "20260914-20261013"), ("ucl_today", "20261013")]:
    url = "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.champions/scoreboard?dates=" + dates
    try:
        d = get(url)
        out[label] = d
        print("=== %s events: %d" % (label, len(d.get("events", []))))
    except Exception as e:
        print("ERR", label, e)
        continue
json.dump(out, open("/home/ubuntu/paper-sim/round3/raw/ucl_scoreboard.json", "w"), indent=1)

d = out.get("ucl_full", {})
tot_g = 0; n = 0
for e in d.get("events", []):
    comps = e.get("competitions", [])
    if not comps: continue
    c = comps[0]
    status = e.get("status", {}).get("type", {}).get("name", "")
    if status != "STATUS_FULL_TIME": continue
    teams = {}
    for ct in c.get("competitors", []):
        teams["H" if ct.get("homeAway") == "home" else "A"] = (ct.get("team", {}).get("displayName"), ct.get("score"))
    if "H" not in teams or "A" not in teams: continue
    try:
        g = int(teams["H"][1]) + int(teams["A"][1])
    except Exception:
        continue
    tot_g += g; n += 1
    print("%s %-28s %s-%s %-28s" % (str(e.get("date"))[:10], str(teams["H"][0])[:28], teams["H"][1], teams["A"][1], str(teams["A"][0])[:28]))
print()
print("FINISHED UCL matches: %d  total goals: %d  goals/match: %.3f" % (n, tot_g, tot_g / max(n, 1)))
ov = sum(1 for e in d.get("events", []) if e.get("status", {}).get("type", {}).get("name") == "STATUS_FULL_TIME" and sum(int(x.get("score") or 0) for x in [y for y in e["competitions"][0]["competitors"]]) >= 3)
print("matches with 3+ goals:", ov)
