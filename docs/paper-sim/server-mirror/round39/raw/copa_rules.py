"""Quick: full /markets/{id} verification + rules text for the Copa do Brasil
semifinal second legs (the only knockout fixtures in the round-39B window)."""
import json
import re
import time
import urllib.parse
import urllib.request

BASE = "https://gamma-api.polymarket.com"
HOME = "/home/ubuntu/paper-sim"
OUT = f"{HOME}/round39/raw/copadobrasil_rules.json"
LO = "2026-11-06T13:30:00Z"
HI = "2026-11-08T23:59:59Z"


def get(url, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 (research)"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 + i)
    raise last


def norm_ts(ts):
    s = str(ts or "").strip()
    if not s:
        return ""
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    from datetime import datetime, timezone
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:  # noqa: BLE001
        return s


def parse_listy(raw):
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:  # noqa: BLE001
            return []
    return raw or []


from datetime import datetime, timezone  # noqa: E402

out = {"tag": "soccer-brco",
       "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
       "markets": []}
# enumerate events by tag
events, offset = [], 0
while True:
    params = {"limit": 100, "active": "true", "closed": "false",
              "order": "volume24hr", "ascending": "false",
              "offset": offset, "tag_slug": "soccer-brco"}
    resp = get(BASE + "/events/pagination?" + urllib.parse.urlencode(params))
    batch = resp.get("data") if isinstance(resp, dict) else resp
    events.extend(batch)
    if len(batch) < 100:
        break
    offset += 100
    time.sleep(1.0)

n = 0
for e in events:
    for m in (e.get("markets") or []):
        if m.get("closed"):
            continue
        gs = norm_ts(m.get("gameStartTime"))
        if not (LO <= gs <= HI):
            continue
        vm = get(BASE + "/markets/" + str(m.get("id")))
        desc = re.sub(r"\s+", " ", str(vm.get("description") or "")).strip()
        n += 1
        print("MID", vm.get("id"), "|", vm.get("question"), "| closed:",
              vm.get("closed"), "| gST:", norm_ts(vm.get("gameStartTime")),
              "| endDate:", norm_ts(vm.get("endDate")))
        # print the resolution-relevant core sentence(s)
        for kw in ("90 minutes", "extra time", "penalt", "aggregate", "regular"):
            for mth in re.finditer(re.escape(kw), desc.lower()):
                print("   >", desc[max(0, mth.start() - 130):mth.end() + 170])
                break
        out["markets"].append({
            "market_id": str(vm.get("id")), "question": vm.get("question"),
            "event_title": e.get("title"), "gameStartTime": gs,
            "endDate": norm_ts(vm.get("endDate")), "closed": vm.get("closed"),
            "active": vm.get("active"), "description_full": desc})
        time.sleep(0.25)

out["n_markets"] = n
json.dump(out, open(OUT, "w"), indent=1)
print("wrote", OUT, "markets:", n)
