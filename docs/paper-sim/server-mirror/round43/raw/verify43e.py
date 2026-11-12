"""ROUND-43B market verification (paper-only): /markets/{id} checks for the
euro-night candidate set (question text + endDate + gameStartTime). The
Gamma ids= list param is BROKEN (r39 evidence); one fetch per market id.
Output name collision-proofed (euro_night_verify.json) because a sibling
Americas agent works in the same round43 directory.
Usage: python verify43e.py <market_id> [<market_id> ...]
"""
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone

BASE = "https://gamma-api.polymarket.com"
OUT = "/home/ubuntu/paper-sim/round43/raw/euro_night_verify.json"


def get(url, tries=5):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 (research)"})
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.load(r)
        except Exception as e:
            last = e
            time.sleep(1.5 + i)
    raise last


def norm_ts(ts):
    s = str(ts or "").strip()
    if not s:
        return ""
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return s


def main():
    ids = [a for a in sys.argv[1:] if a.strip().isdigit()]
    if not ids:
        print("no market ids given")
        return
    out = []
    for mid in ids:
        m = get(f"{BASE}/markets/{mid}")
        time.sleep(0.3)
        if not isinstance(m, dict):
            out.append({"id": mid, "ok": False})
            continue
        gs = norm_ts(m.get("gameStartTime"))
        ed = norm_ts(m.get("endDate"))
        endd_after_kick = None
        try:
            dd = (datetime.fromisoformat(ed.replace("Z", "+00:00"))
                  - datetime.fromisoformat(gs.replace("Z", "+00:00"))).total_seconds()
            endd_after_kick = 0 <= dd <= 60 * 60 * 30
        except Exception:
            pass
        out.append({
            "id": str(m.get("id")), "ok": True,
            "question": m.get("question"),
            "closed": m.get("closed"), "active": m.get("active"),
            "gameStartTime": gs, "endDate": ed,
            "endDate_after_kick_within_30h": endd_after_kick,
            "liquidityNum": m.get("liquidityNum"),
            "volumeNum": m.get("volumeNum"),
            "outcomes": m.get("outcomes"),
            "outcomePrices": m.get("outcomePrices"),
            "verified_utc": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ")})
        print("VERIFIED", mid, "|", m.get("question"), "| closed",
              m.get("closed"), "| end", ed, flush=True)
    json.dump(out, open(OUT, "w"), indent=1)
    print("saved", OUT, "| n =", len(out))


if __name__ == "__main__":
    main()
