#!/usr/bin/env python3
"""WP-P2a Phase A: fetch ESPN UCL/UEL completed results for 3 seasons. (v2)

v2: keep-alive HTTPSConnection with hard per-request watchdog, progress
prints every 20 days, and a JSONL checkpoint so a restart resumes where
the sweep stopped. Day-by-day sweep (range requests are HTTP 400).

Windows:
  2023-24 : 2023-09-01 .. 2024-06-30 (full season incl. knockouts + final)
  2024-25 : 2024-09-01 .. 2025-01-31 (league phase only, per WP-P2a spec)
  2025-26 : 2025-09-01 .. 2026-01-31 (league phase only, per WP-P2a spec)

Output: ~/paper-sim/round31/raw/espn_sweep_events.json (+ .ckpt.jsonl)
"""
import http.client
import json
import socket
import ssl
import sys
import time
from datetime import date, timedelta

HOST = "site.api.espn.com"
PATH = "/apis/site/v2/sports/soccer/{slug}/scoreboard?dates={day}"
COMPS = [("UCL", "uefa.champions"), ("UEL", "uefa.europa")]
WINDOWS = [
    ("2023-24", date(2023, 9, 1), date(2024, 6, 30)),
    ("2024-25", date(2024, 9, 1), date(2025, 1, 31)),
    ("2025-26", date(2025, 9, 1), date(2026, 1, 31)),
]
OUT = "/home/ubuntu/paper-sim/round31/raw/espn_sweep_events.json"
CKPT = OUT + ".ckpt.jsonl"
CTX = ssl.create_default_context()


def extract(d, comp, bucket):
    recs = []
    for e in d.get("events", []):
        st = e.get("status", {}).get("type", {})
        name = st.get("name", "")
        try:
            comp0 = e["competitions"][0]
        except (KeyError, IndexError):
            continue
        home = away = None
        hs = as_ = None
        for c in comp0.get("competitors", []):
            entry = {
                "id": c["team"].get("id"),
                "displayName": c["team"].get("displayName"),
                "shortName": c["team"].get("shortDisplayName"),
            }
            if c.get("homeAway") == "home":
                home = entry
                hs = c.get("score")
            else:
                away = entry
                as_ = c.get("score")
        recs.append({
            "event_id": e.get("id"),
            "date": e.get("date"),
            "comp": comp,
            "season_bucket": bucket,
            "espn_season_year": e.get("season", {}).get("year"),
            "espn_season_slug": e.get("season", {}).get("slug"),
            "status": name,
            "completed_flag": st.get("completed"),
            "home": home,
            "away": away,
            "score_home": hs,
            "score_away": as_,
            "notes": [n.get("headline") for n in comp0.get("notes", []) if n.get("headline")],
        })
    return recs


class Client:
    def __init__(self):
        self.conn = None

    def connect(self):
        self.conn = http.client.HTTPSConnection(HOST, timeout=15, context=CTX)

    def get(self, path, tries=4):
        for attempt in range(tries):
            try:
                if self.conn is None:
                    self.connect()
                self.conn.request("GET", path, headers={"User-Agent": "Mozilla/5.0 research", "Accept": "application/json"})
                resp = self.conn.getresponse()
                body = resp.read()
                if resp.status != 200:
                    raise OSError("http %d" % resp.status)
                return json.loads(body)
            except Exception:
                try:
                    self.conn.close()
                except Exception:
                    pass
                self.conn = None
                if attempt == tries - 1:
                    raise
                time.sleep(1.0 + attempt)


def day_list():
    days = []
    for bucket, d1, d2 in WINDOWS:
        cur = d1
        while cur <= d2:
            days.append((bucket, cur))
            cur += timedelta(days=1)
    return days


def main():
    t0 = time.time()
    done_keys = set()
    all_events = {}
    status_counts = {}
    req_log = []
    n_err = 0
    # resume from checkpoint
    try:
        with open(CKPT) as f:
            for line in f:
                rec = json.loads(line)
                if rec.get("status") == "OK":
                    done_keys.add(rec["key"])
                    req_log.append({"url": rec["url"], "ok": True, "events": rec["n_events"], "kept_ft": rec["kept_ft"]})
                    bucket = rec["key"].split("|")[0]
                    for sname, cnt in rec.get("statuses", {}).items():
                        sk = (rec["key"].split("|")[1], bucket, sname)
                        status_counts[sk] = status_counts.get(sk, 0) + cnt
                    for ev in rec.get("ft_events", []):
                        all_events.setdefault(f"{ev['comp']}:{ev['event_id']}", ev)
    except FileNotFoundError:
        pass
    print(f"resume: {len(done_keys)} day-comp cells already done, {len(all_events)} events", flush=True)

    cl = Client()
    ck = open(CKPT, "a")
    ndone = 0
    days = day_list()
    total_cells = len(days) * len(COMPS)
    for bucket, day in days:
        for comp, slug in COMPS:
            key = f"{bucket}|{comp}|{day}"
            if key in done_keys:
                continue
            path = PATH.format(slug=slug, day=day.strftime("%Y%m%d"))
            url = f"https://{HOST}{path}"
            try:
                data = cl.get(path)
                recs = extract(data, comp, bucket)
                n_ft = 0
                ft_events = []
                statuses = {}
                for r in recs:
                    statuses[r["status"]] = statuses.get(r["status"], 0) + 1
                    status_counts[(comp, bucket, r["status"])] = status_counts.get((comp, bucket, r["status"]), 0) + 1
                    if r["status"] == "STATUS_FULL_TIME" and r["home"] and r["away"]:
                        k2 = f"{comp}:{r['event_id']}"
                        if k2 not in all_events:
                            all_events[k2] = r
                            n_ft += 1
                        ft_events.append(r)
                ck.write(json.dumps({"key": key, "status": "OK", "url": url, "n_events": len(recs),
                                     "kept_ft": n_ft, "statuses": statuses, "ft_events": ft_events}) + "\n")
                req_log.append({"url": url, "ok": True, "events": len(recs), "kept_ft": n_ft})
            except Exception as e:
                n_err += 1
                ck.write(json.dumps({"key": key, "status": "ERR", "url": url, "error": str(e)}) + "\n")
                ck.flush()
                print(f"ERROR {key}: {e}", flush=True)
                time.sleep(2.0)
                continue
            ndone += 1
            if ndone % 40 == 0:
                ck.flush()
                print(f"[{time.time()-t0:6.1f}s] {ndone} cells | total_ft={len(all_events)}", flush=True)
        ck.flush()
    ck.close()
    out = {
        "fetched_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "endpoint_template": "https://" + HOST + PATH,
        "windows": [[b, str(a), str(z)] for b, a, z in WINDOWS],
        "comps": COMPS,
        "n_day_comp_cells": total_cells,
        "n_errors": n_err,
        "status_counts": {"|".join(k): v for k, v in sorted(status_counts.items())},
        "events": list(all_events.values()),
    }
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1)
    print(f"DONE errors={n_err} ft_events={len(all_events)} elapsed={time.time()-t0:.1f}s -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
