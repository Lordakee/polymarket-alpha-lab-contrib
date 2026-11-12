#!/usr/bin/env python3
"""One bounded, cron-safe Understat recovery attempt; no database or trading imports.

Refresh the five 2026 getLeagueData endpoints used by round27. Carry the complete
2025 blocks forward from round25, explicitly recording that provenance. Publish
round28 only when every league includes its known completed 2026-11-01 fixtures.

2026-11-04 (codex review finding #11): every successful validation also
re-points the stable latest-snapshot symlink ~/paper-sim/understat_latest.json
(sidecar understat_latest_pointer.json) at the validated output, so active
scanners -- which resolve that pointer instead of a hard-coded
roundNN/raw/xg_understat_NN.json path -- pick up recovered data on their next
run. Failures never touch the pointer; it keeps naming the last validated
snapshot.
"""

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import ipaddress
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
LEAGUES = ("EPL", "La_liga", "Serie_A", "Bundesliga", "Ligue_1")
TEAM_COUNTS = dict(zip(LEAGUES, (20, 20, 20, 18, 18)))
SUNDAY_COUNTS = dict(zip(LEAGUES, (1, 4, 5, 2, 4)))
SEASON = "2026"
TARGET_DAY = "2026-11-01"
INTERVAL_SECONDS = 3
CURL = ["/usr/bin/curl", "--disable", "--noproxy", "*", "--silent",
        "--show-error", "--fail", "--proto", "=https"]


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def atomic_json(path, value):
    """Keep the previous complete file intact until the replacement is durable."""
    path = Path(path)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix="." + path.name + ".", delete=False) as f:
            temp = Path(f.name)
            json.dump(value, f, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def emit(log, event, **fields):
    record = {"at_utc": utcnow(), "event": event, **fields}
    line = json.dumps(record, ensure_ascii=False, allow_nan=False)
    with Path(log).open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line, flush=True)
    return record


def publish_latest(output, latest, latest_meta, log, summaries):
    """Point the stable latest-snapshot symlink at the newest validated file.

    Codex review finding #11 (2026-11-04): recovery wrote
    round28/raw/xg_understat_28.json while the active scanner kept reading
    round25/raw/xg_understat_25.json, so even a successful recovery never
    reached scanning. Every successful validation -- a fresh recovery or
    the idempotent already_complete re-run -- atomically re-points the
    understat_latest.json symlink and refreshes the sidecar
    understat_latest_pointer.json, so scans resolve the newest valid
    snapshot without hard-coded round numbers. A failed attempt never
    calls this: the pointer keeps naming the last validated snapshot.
    """
    latest = Path(latest)
    latest_meta = Path(latest_meta)
    target = Path(output).resolve()
    digest = sha256(target.read_bytes())
    # legacy seed snapshots (round25) carry no _provenance block; the sidecar
    # then records nulls for the unknown provenance fields instead of failing
    provenance = json.loads(target.read_text()).get("_provenance") or {}
    temp = latest.with_name("." + latest.name + ".swap")
    temp.unlink(missing_ok=True)
    os.symlink(os.path.relpath(target, start=latest.parent), temp)
    os.replace(temp, latest)
    atomic_json(latest_meta, {
        "target": str(target),
        "sha256": digest,
        "status": "complete",
        "paper_only": True,
        "fetched_at_utc": provenance.get("fetched_at_utc"),
        "required_results_date": provenance.get("required_results_date"),
        "leagues": {lg: {"completed_matches": s["completed_matches"],
                         "latest_match_date": s["latest_match_date"]}
                    for lg, s in summaries.items()},
        "pointed_at_utc": utcnow(),
    })
    emit(log, "latest_pointer_updated", latest=str(latest),
         target=str(target), sha256=digest)


def command(argv, timeout):
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "bounded subprocess timeout"


def public_ip(value):
    try:
        return str(ipaddress.ip_address(value)) if ipaddress.ip_address(value).is_global else None
    except ValueError:
        return None


def resolve_addresses(log):
    """Use live DNS only. Never trust a stale passive-DNS address automatically."""
    addresses = {}
    for record_type in ("A", "AAAA"):
        rc, out, err = command(["/usr/bin/dig", "+time=3", "+tries=1", "+noall",
                                "+comments", "+answer", "understat.com", record_type], 5)
        emit(log, "dns_probe", resolver="system", record_type=record_type,
             exit_code=rc, answer=out, error=err)
        if rc == 0 and "status: NOERROR" in out:
            for line in out.splitlines():
                fields = line.split()
                if len(fields) == 5 and fields[3] == record_type:
                    address = public_ip(fields[4])
                    if address:
                        addresses[address] = "system-dns"
    if addresses:
        return addresses
    for base in ("https://dns.google/resolve", "https://cloudflare-dns.com/dns-query"):
        for record_type, type_number in (("A", 1), ("AAAA", 28)):
            url = base + "?name=understat.com&type=" + record_type
            rc, out, err = command(CURL + ["--connect-timeout", "5", "--max-time", "10",
                                           "-H", "Accept: application/dns-json", url], 12)
            try:
                data = json.loads(out) if rc == 0 else {}
                if not isinstance(data, dict):
                    raise ValueError("DNS response must be an object")
            except ValueError:
                data = {}
                err = (err + " invalid DNS JSON").strip()
            emit(log, "dns_probe", resolver=base, record_type=record_type,
                 exit_code=rc, answer=data, error=err)
            if data.get("Status") == 0:
                for answer in data.get("Answer") or []:
                    address = public_ip(str(answer.get("data", "")))
                    if answer.get("type") == type_number and address:
                        addresses[address] = base
        if addresses:
            break
    return addresses


def fetch_league(league, addresses, staging):
    url = "https://understat.com/getLeagueData/" + league + "/" + SEASON
    ref = "https://understat.com/league/" + league + "/" + SEASON
    # --resolve changes only the connection address; TLS identity and SNI stay understat.com.
    ips = sorted(addresses, key=lambda ip: (ipaddress.ip_address(ip).version, ip))
    pinned = ",".join("[" + ip + "]" if ":" in ip else ip for ip in ips)
    body_path = Path(staging) / (league + ".json")
    rc, out, err = command(CURL + [
        "--compressed", "--connect-timeout", "10", "--max-time", "45",
        "--max-filesize", "20000000", "--resolve", "understat.com:443:" + pinned,
        "--user-agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
        "-H", "X-Requested-With: XMLHttpRequest", "--referer", ref,
        "--output", str(body_path), "--write-out", "%{json}", url], 50)
    if rc:
        raise ValueError(f"{league}: curl exit {rc}: {err.strip()}")
    meta = json.loads(out)
    if meta.get("http_code") != 200 or meta.get("ssl_verify_result") != 0:
        raise ValueError(f"{league}: HTTP/TLS validation failed")
    if meta.get("url_effective") != url or meta.get("remote_ip") not in addresses:
        raise ValueError(f"{league}: unexpected response origin")
    body = body_path.read_bytes()
    provenance = {"fetched_at_utc": utcnow(), "source_url": url,
                  "source_ip": meta["remote_ip"],
                  "resolution_source": addresses[meta["remote_ip"]],
                  "http_status": meta["http_code"], "tls_verified": True,
                  "response_sha256": sha256(body)}
    return json.loads(body), provenance


def nonnegative(value, label, integer=False):
    if isinstance(value, bool):
        raise ValueError(label + ": invalid boolean")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(label + ": missing/invalid number") from exc
    if not math.isfinite(number) or number < 0 or (integer and number != int(number)):
        raise ValueError(label + ": invalid number")
    return number


def validate_league(league, data, baseline, require_sunday=True):
    teams, dates = data["teams"], data["dates"]
    if not isinstance(teams, dict) or len(teams) != TEAM_COUNTS[league]:
        raise ValueError(league + ": wrong team count")
    if set(teams) != set(baseline["teams"]):
        raise ValueError(league + ": team identities changed")
    if not isinstance(dates, list) or not dates or not isinstance(data["players"], list):
        raise ValueError(league + ": malformed league payload")
    ids = [str(m["id"]) for m in dates]
    if len(ids) != len(set(ids)):
        raise ValueError(league + ": duplicate fixture IDs")
    results = {str(m["id"]): m for m in dates if m.get("isResult") is True}
    previous = {str(m["id"]) for m in baseline["dates"] if m.get("isResult") is True}
    sunday = {str(m["id"]): m for m in baseline["dates"]
              if m["datetime"].startswith(TARGET_DAY)}
    if not previous.issubset(results):
        raise ValueError(league + ": previously completed matches are missing")
    if len(sunday) != SUNDAY_COUNTS[league]:
        raise ValueError(league + ": seed does not contain the expected Sunday schedule")
    if require_sunday and not sunday.keys() <= results.keys():
        raise ValueError(league + ": Sunday results are still missing")
    for match_id in sunday.keys() & results.keys():
        old, new = sunday[match_id], results[match_id]
        if any(str(old[side]["id"]) != str(new[side]["id"]) for side in ("h", "a")):
            raise ValueError(league + ": Sunday fixture identities changed")
        if not new["datetime"].startswith(TARGET_DAY):
            raise ValueError(league + ": Sunday fixture date changed")
    histories = {}
    for team_id, team in teams.items():
        for history in team["history"]:
            key = (str(team_id), history["date"], history["h_a"])
            if key in histories:
                raise ValueError(league + ": duplicate team history")
            histories[key] = history
    if len(histories) != 2 * len(results):
        raise ValueError(league + ": results and team history counts differ")
    used_histories = set()
    for match in results.values():
        dt = datetime.strptime(match["datetime"], "%Y-%m-%d %H:%M:%S")
        if dt < datetime(int(SEASON), 7, 1) or dt > datetime.now(timezone.utc).replace(tzinfo=None):
            raise ValueError(league + ": completed match outside the current season/time")
        for side, other in (("h", "a"), ("a", "h")):
            key = (str(match[side]["id"]), match["datetime"], side)
            if key not in histories or key in used_histories:
                raise ValueError(league + ": missing or reused team history")
            used_histories.add(key)
            history = histories[key]
            for field, expected in (("xG", match["xG"][side]), ("xGA", match["xG"][other]),
                                    ("scored", match["goals"][side]), ("missed", match["goals"][other])):
                integer = field in ("scored", "missed")
                if not math.isclose(nonnegative(history[field], field, integer),
                                    nonnegative(expected, field, integer), rel_tol=1e-5, abs_tol=1e-4):
                    raise ValueError(league + ": fixture/history values disagree")
    return {"season": SEASON, "teams": len(teams), "completed_matches": len(results),
            "latest_match_date": max((m["datetime"] for m in results.values()), default=None),
            "sunday_completed_matches": len(sunday.keys() & results.keys()),
            "required_sunday_matches": len(sunday),
            "required_sunday_match_ids": sorted(sunday)}


def validate_snapshot(snapshot, seed):
    summaries = {lg: validate_league(lg, snapshot[lg + "_2026"], seed[lg + "_2026"])
                 for lg in LEAGUES}
    for lg in LEAGUES:
        if snapshot[lg + "_2025"] != seed[lg + "_2025"]:
            raise ValueError(lg + ": historical block changed")
    provenance = snapshot["_provenance"]
    if provenance["status"] != "complete" or provenance["required_results_date"] != TARGET_DAY:
        raise ValueError("snapshot lacks completed recovery provenance")
    for lg, summary in summaries.items():
        recorded = provenance["leagues"][lg]
        if any(recorded.get(k) != v for k, v in summary.items()):
            raise ValueError(lg + ": provenance counts differ from the data")
        if not recorded.get("tls_verified") or not recorded.get("source_ip"):
            raise ValueError(lg + ": missing verified source provenance")
    return summaries


def recover(args):
    started = utcnow()
    emit(args.log, "probe_started", output=str(args.output))
    seed_bytes = args.seed.read_bytes()
    seed = json.loads(seed_bytes)
    for lg in LEAGUES:
        validate_league(lg, seed[lg + "_2026"], seed[lg + "_2026"], require_sunday=False)
        if not seed[lg + "_2025"].get("teams"):
            raise ValueError(lg + ": historical seed is absent")
    if args.output.exists():
        try:
            summaries = validate_snapshot(json.loads(args.output.read_text()), seed)
        except (ValueError, KeyError, TypeError) as exc:
            emit(args.log, "existing_snapshot_invalid", reason=str(exc))
        else:
            record = emit(args.log, "already_complete", output=str(args.output), leagues=summaries)
            atomic_json(args.status, record)
            publish_latest(args.output, args.latest, args.latest_meta, args.log, summaries)
            return 0
    addresses = resolve_addresses(args.log)
    if not addresses:
        record = emit(args.log, "waiting_for_dns", next_probe="cron: every 30 minutes",
                      output_created=False)
        atomic_json(args.status, record)
        return 1
    emit(args.log, "dns_recovered", addresses=addresses)
    snapshot = {lg + "_2025": seed[lg + "_2025"] for lg in LEAGUES}
    sources = {}
    with tempfile.TemporaryDirectory(prefix=".understat-attempt-", dir=args.output.parent) as staging:
        for index, lg in enumerate(LEAGUES):
            if index:
                time.sleep(INTERVAL_SECONDS)
            data, source = fetch_league(lg, addresses, staging)
            summary = validate_league(lg, data, seed[lg + "_2026"])
            snapshot[lg + "_2026"] = data
            sources[lg] = {**source, **summary}
            emit(args.log, "league_validated", league=lg, **sources[lg])
    snapshot["_provenance"] = {
        "status": "complete", "paper_only": True, "fetch_started_at_utc": started,
        "fetched_at_utc": utcnow(), "required_results_date": TARGET_DAY,
        "source_path": "https://understat.com/getLeagueData/{league}/2026",
        "resolution": addresses, "leagues": sources,
        "league_match_counts": {lg: sources[lg]["completed_matches"] for lg in LEAGUES},
        "preserved_historical_season": {"season": "2025", "source_file": str(args.seed),
                                         "source_sha256": sha256(seed_bytes), "refetched": False},
        "request_interval_seconds": INTERVAL_SECONDS,
    }
    summaries = validate_snapshot(snapshot, seed)
    atomic_json(args.output, snapshot)
    digest = sha256(args.output.read_bytes())
    record = emit(args.log, "recovered", output=str(args.output), sha256=digest, leagues=summaries)
    atomic_json(args.status, record)
    publish_latest(args.output, args.latest, args.latest_meta, args.log, summaries)
    return 0


def run_once(args):
    for path in (args.output, args.log, args.status, args.latest, args.latest_meta):
        path.parent.mkdir(parents=True, exist_ok=True)
    with args.output.with_suffix(".lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            emit(args.log, "skipped_locked")
            return 0
        try:
            return recover(args)
        except Exception as exc:
            record = emit(args.log, "refresh_failed", error_type=type(exc).__name__,
                          reason=str(exc), output_preserved=True)
            atomic_json(args.status, record)
            return 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, default=ROOT / "round25/raw/xg_understat_25.json")
    parser.add_argument("--output", type=Path, default=ROOT / "round28/raw/xg_understat_28.json")
    parser.add_argument("--log", type=Path, default=ROOT / "round28/raw/understat_recovery.jsonl")
    parser.add_argument("--status", type=Path, default=ROOT / "round28/raw/understat_recovery_status.json")
    parser.add_argument("--latest", type=Path, default=ROOT / "understat_latest.json",
                        help="stable symlink scanners resolve for the newest valid snapshot")
    parser.add_argument("--latest-meta", type=Path, default=ROOT / "understat_latest_pointer.json",
                        help="sidecar pointer metadata (target, sha256, per-league counts)")
    return run_once(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
