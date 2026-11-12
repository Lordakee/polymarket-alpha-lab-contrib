import json, urllib.request, gzip, datetime, time

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
        return json.loads(data.decode())

print("UTC now:", datetime.datetime.now(datetime.timezone.utc).isoformat())
allev = []
d = datetime.date(2026, 9, 14)
while d <= datetime.date(2026, 10, 14):
    ds = d.strftime("%Y%m%d")
    url = "https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.champions/scoreboard?dates=" + ds
    try:
        r = get(url)
        for e in r.get("events", []):
            allev.append({"date": ds, "event": e})
    except Exception as e:
        print("ERR", ds, e)
    d += datetime.timedelta(days=1)
    time.sleep(0.25)
print("total UCL events:", len(allev))
json.dump(allev, open("/home/ubuntu/paper-sim/round3/raw/ucl_daily.json", "w"), indent=1)

seen = set()
tot_g = 0; n = 0; over25 = 0
for rec in allev:
    e = rec["event"]
    if e["id"] in seen: continue
    seen.add(e["id"])
    st = e.get("status", {}).get("type", {}).get("name", "")
    if st != "STATUS_FULL_TIME": continue
    c = e["competitions"][0]
    th = ta = None; sh = sa = 0
    for ct in c.get("competitors", []):
        nm = ct.get("team", {}).get("displayName", "?")
        sc = int(ct.get("score") or 0)
        if ct.get("homeAway") == "home": th, sh = nm, sc
        else: ta, sa = nm, sc
    if not th or not ta: continue
    g = sh + sa
    tot_g += g; n += 1
    if g >= 3: over25 += 1
    print("%s %-26s %d-%d %-26s" % (str(e.get("date"))[:10], str(th)[:26], sh, sa, str(ta)[:26]))
print()
print("FINISHED: %d  goals: %d  gpg: %.3f  over2.5: %d (%.1f%%)" % (n, tot_g, tot_g/max(n,1), over25, 100.0*over25/max(n,1)))
