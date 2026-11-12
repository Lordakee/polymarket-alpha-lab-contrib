#!/usr/bin/env python3
"""WP-P3 Phase 1 production adapter: FotMob -> Understat xG snapshot (EFL Championship).

Server-side research tooling (NOT part of the repo; Phase 2 will review/promote
it after validation passes). Paper-only, no credentials: FotMob's public
unofficial JSON API, fetched politely (1 request / 1.3 s) with an on-disk
matchDetails cache so interrupted runs resume without refetching.

Pipeline per season (current 2026/27 -> block "Championship_2026", prior
2025/26 -> block "Championship_2025"):

  1. GET /api/data/leagues?id=48[&season=...] -> fixtures.allMatches
  2. keep only numeric league rounds 1..46 (playoff rounds "1/2"/"final"
     excluded), drop cancelled matches, drop unfinished matches
  3. GET /api/data/matchDetails?matchId=... for each kept match (cached)
  4. require score + "Expected goals (xG)" row; skip (and count) matches
     with neither; FAIL-CLOSED if the skip rate or dataset shape looks
     like an upstream schema change (nothing is written in that case)
  5. emit the Understat wire format consumed by
     polymarket_alpha_lab.papersim.xg (teams/dates only, no extra keys)

Output (atomic tmp+rename):
  <out>/xg_fotmob_championship.json           snapshot (Understat shape)
  <out>/xg_fotmob_championship.json.meta.json provenance + alias layer

Provenance lineage: PoC /tmp/xgsrc_probe/fotmob_to_understat_poc.py
(research, validated 2026-11-03); this is the productionized form.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

LEAGUE_ID = 48                       # FotMob: EFL Championship (ENG tier 2)
LEAGUE_KEY = "Championship"          # snapshot block prefix ("Championship_2026")
HOST = "www.fotmob.com"
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
SLEEP_S = 1.3                        # polite spacing between matchDetails fetches
MAX_ROUND = 46                       # Championship league phase (numeric only)
TEAM_COUNT = 24                      # Championship league size, both blocks

# (block_season_key, api_season_param_or_None, expected_selectedSeason)
SEASONS = (
    ("2026", None, "2026/2027"),
    ("2025", "2025/2026", "2025/2026"),
)

# Dataset-shape bounds: abort when the finished numeric-round count leaves
# these windows (upstream renumbering / truncated payload => schema change).
SHAPE_BOUNDS = {"2026": (100, 220), "2025": (540, 560)}
MAX_SKIP_RATE = 0.05                 # >5% matches without xG => fail-closed


class AdapterError(RuntimeError):
    """Fatal, fail-closed condition: nothing is written."""


def log(msg: str) -> None:
    print("[{}] {}".format(datetime.now(timezone.utc).strftime("%H:%M:%S"), msg), flush=True)


def doh_resolve(host: str, attempts: int = 3) -> str:
    """Resolve `host` via DNS-over-HTTPS (this host's passive DNS is pinned
    for some domains; same pattern as tools/understat_refresh.py)."""
    last = ""
    for attempt in range(attempts):
        try:
            proc = subprocess.run(
                ["curl", "-sS", "--max-time", "8",
                 "https://dns.google/resolve?name={}&type=A".format(host)],
                capture_output=True, text=True, timeout=12)
            data = json.loads(proc.stdout)
            ip = next(
                (a["data"] for a in data.get("Answer", []) if a.get("type") == 1), "")
            if ip:
                return ip
        except Exception as exc:  # noqa: BLE001 - retry any transport error
            last = str(exc)
        time.sleep(2 * (attempt + 1))
    raise AdapterError("DoH resolve failed for {}: {}".format(host, last))


def http_json(url: str, ip: str) -> object:
    """One HTTPS GET via curl --resolve (TLS/SNI stay under fotmob.com)."""
    proc = subprocess.run(
        ["curl", "-sS", "--connect-timeout", "10", "--max-time", "60",
         "--resolve", "{}:443:{}".format(HOST, ip), "-A", UA,
         "-H", "Accept: application/json", url],
        capture_output=True, text=True, timeout=70)
    if proc.returncode != 0:
        raise RuntimeError("curl rc={}: {}".format(proc.returncode, proc.stderr.strip()[:200]))
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("non-JSON response ({} bytes): {}".format(len(proc.stdout), exc)) from exc


def fetch_json(url: str, ip_holder: dict) -> object:
    """Fetch with retry/backoff; re-resolve DoH after transport failures."""
    last_exc: Exception | None = None
    for attempt in range(4):
        try:
            return http_json(url, ip_holder["ip"])
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            log("  fetch attempt {} failed ({}); backing off".format(attempt + 1, str(exc)[:120]))
            time.sleep(5 * (attempt + 1))
            if attempt >= 1:
                ip_holder["ip"] = doh_resolve(HOST)
                log("  re-resolved {} -> {}".format(HOST, ip_holder["ip"]))
    raise AdapterError("giving up after retries: {} ({})".format(url, last_exc))


# --------------------------------------------------------------------------
# payload extraction (fail-closed on shape drift)
# --------------------------------------------------------------------------

def parse_league_payload(data: object, season_key: str, expected: str) -> dict:
    """Validate the leagues endpoint payload shape and return allMatches."""
    if not isinstance(data, dict):
        raise AdapterError("leagues payload for {} is not an object".format(season_key))
    details = data.get("details")
    fixtures = data.get("fixtures")
    if not isinstance(details, dict) or not isinstance(fixtures, dict):
        raise AdapterError("leagues payload for {} missing details/fixtures".format(season_key))
    selected = details.get("selectedSeason")
    if selected != expected:
        raise AdapterError(
            "season drift for {}: selectedSeason={!r} expected={!r}".format(
                season_key, selected, expected))
    matches = fixtures.get("allMatches")
    if not isinstance(matches, list) or not matches:
        raise AdapterError("allMatches missing/empty for {}".format(season_key))
    for m in matches:
        if not isinstance(m, dict) or not isinstance(m.get("status"), dict):
            raise AdapterError("malformed fixture row in {}".format(season_key))
        for side in ("home", "away"):
            team = m.get(side)
            if not isinstance(team, dict) or "id" not in team or "name" not in team:
                raise AdapterError("malformed {} team in fixture {}".format(side, m.get("id")))
    return matches


def is_cancelled(match: dict) -> bool:
    """True for cancelled/abandoned fixtures (codex review #5, 2026-11-04).

    Cached FotMob sources contain abandoned games whose only markers are
    status.cancelled=true and reason longKey='aborted' while finished is
    also true (e.g. Blackburn-Ipswich 4825094 and its replay 5008942).
    The pre-fix text-only check matched 'cancel' and kept those rows,
    double-counting abandoned games alongside their replays. Reject the
    explicit boolean flag first, then match both 'cancel' and 'abort'
    reason keys. Mirrors the library filter in
    polymarket_alpha_lab/papersim/fotmob.py.
    """
    status = match.get("status") or {}
    if status.get("cancelled") is True:
        return True
    reason = status.get("reason")
    if isinstance(reason, dict):
        key = (str(reason.get("longKey", "")) + str(reason.get("shortKey", ""))).lower()
        return "cancel" in key or "abort" in key
    return False


def partition_matches(matches: list) -> dict:
    """Split fixtures into kept (numeric round, finished, not cancelled) and
    excluded buckets with reasons."""
    kept, playoff, cancelled, unfinished = [], [], [], []
    for m in matches:
        round_raw = str(m.get("round", ""))
        if not (round_raw.isdigit() and 1 <= int(round_raw) <= MAX_ROUND):
            playoff.append(m)
        elif is_cancelled(m):
            cancelled.append(m)
        elif not m["status"].get("finished"):
            unfinished.append(m)
        else:
            kept.append(m)
    return {"kept": kept, "playoff": playoff, "cancelled": cancelled,
            "unfinished": unfinished}


def extract_xg_pair(md: dict, title: str) -> tuple[str, str] | None:
    """First non-null [home, away] row named `title` in Periods.All stats."""
    try:
        groups = md["content"]["stats"]["Periods"]["All"]["stats"]
    except (KeyError, TypeError):
        return None
    if not isinstance(groups, list):
        return None
    for grp in groups:
        if not isinstance(grp, dict):
            continue
        for stat in grp.get("stats", []) or []:
            if not isinstance(stat, dict) or stat.get("title") != title:
                continue
            vals = stat.get("stats")
            if (isinstance(vals, list) and len(vals) == 2
                    and vals[0] is not None and vals[1] is not None):
                return str(vals[0]), str(vals[1])
    return None


def extract_score(md: dict) -> tuple[int, int] | None:
    try:
        home, away = md["header"]["teams"][0], md["header"]["teams"][1]
        if home.get("score") is not None and away.get("score") is not None:
            return int(home["score"]), int(away["score"])
    except (KeyError, TypeError, IndexError, ValueError):
        pass
    return None


def fmt_date(utc: str) -> str:
    """'2026-11-03T19:45:00.000Z' -> '2026-11-03 19:45:00' (Understat shape)."""
    return utc.replace("T", " ").replace("Z", "").split(".")[0]


def result_code(gf: int, ga: int) -> str:
    return "w" if gf > ga else ("d" if gf == ga else "l")


# --------------------------------------------------------------------------
# snapshot construction
# --------------------------------------------------------------------------

def build_block(season_key: str, kept: list, details: dict, teams_index: dict):
    """Build one Understat-format block {teams, dates} from kept fixtures."""
    histories: dict[str, list] = {}
    dates: list = []
    skipped: list = []
    for m in kept:
        mid = str(m["id"])
        md = details.get(mid)
        xg = extract_xg_pair(md, "Expected goals (xG)") if md else None
        score = extract_score(md) if md else None
        if xg is None or score is None:
            skipped.append(mid)
            continue
        npxg = extract_xg_pair(md, "xG non-penalty") or xg
        hg, ag = score
        hxg, axg = xg
        hnpxg, anpxg = npxg
        date_s = fmt_date(m["status"]["utcTime"])
        home, away = m["home"], m["away"]
        hid, aid = str(home["id"]), str(away["id"])
        histories.setdefault(hid, []).append({
            "h_a": "h", "xG": float(hxg), "xGA": float(axg),
            "npxG": float(hnpxg), "npxGA": float(anpxg),
            "scored": hg, "missed": ag,
            "result": result_code(hg, ag), "date": date_s,
        })
        histories.setdefault(aid, []).append({
            "h_a": "a", "xG": float(axg), "xGA": float(hxg),
            "npxG": float(anpxg), "npxGA": float(hnpxg),
            "scored": ag, "missed": hg,
            "result": result_code(ag, hg), "date": date_s,
        })
        dates.append({
            "id": mid, "isResult": True,
            "h": {"id": hid, "title": home["name"],
                  "short_title": home.get("shortName", "")},
            "a": {"id": aid, "title": away["name"],
                  "short_title": away.get("shortName", "")},
            "goals": {"h": str(hg), "a": str(ag)},
            "xG": {"h": hxg, "a": axg},
            "datetime": date_s,
        })
    teams = {}
    for tid, meta in teams_index.items():
        history = sorted(histories.get(tid, []), key=lambda e: e["date"])
        teams[tid] = {"id": tid, "title": meta["title"], "history": history}
    dates.sort(key=lambda d: d["datetime"])
    return {"teams": teams, "dates": dates}, skipped


def team_index(matches: list) -> dict:
    """id -> {title, short_title} over ALL fixtures (incl. playoffs)."""
    index: dict[str, dict] = {}
    for m in matches:
        for side in ("home", "away"):
            team = m[side]
            index[str(team["id"])] = {
                "title": team["name"],
                "short_title": team.get("shortName", ""),
            }
    return index


def atomic_write(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    shutil.move(str(tmp), str(path))


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main() -> int:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-dir", type=Path,
                        default=Path("/home/ubuntu/paper-sim/round31/raw"))
    parser.add_argument("--cache-dir", type=Path, default=here / "fotmob_cache")
    parser.add_argument("--sleep", type=float, default=SLEEP_S,
                        help="seconds between matchDetails fetches (default 1.3)")
    parser.add_argument("--max-fetch", type=int, default=1000,
                        help="hard bound on new matchDetails fetches per run")
    args = parser.parse_args()

    started = datetime.now(timezone.utc)
    md_dir = args.cache_dir / "md"
    fx_dir = args.cache_dir / "fixtures"
    md_dir.mkdir(parents=True, exist_ok=True)
    fx_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / "xg_fotmob_championship.json"
    meta_path = args.out_dir / "xg_fotmob_championship.json.meta.json"

    ip_holder = {"ip": doh_resolve(HOST)}
    log("DoH {} -> {}".format(HOST, ip_holder["ip"]))

    snapshot: dict[str, dict] = {}
    season_meta: dict[str, dict] = {}
    alias_meta: dict[str, dict] = {}
    new_fetches = 0
    cache_hits = 0

    for season_key, season_param, expected in SEASONS:
        url = "https://{}/api/data/leagues?id={}".format(HOST, LEAGUE_ID)
        if season_param:
            url += "&season=" + season_param.replace("/", "%2F")
        league = fetch_json(url, ip_holder)
        matches = parse_league_payload(league, season_key, expected)
        # freeze the fixtures payload for the validator (round map / exclusions)
        fx_cache = fx_dir / ("leagues_48_{}.json".format(season_key))
        atomic_write(fx_cache, json.dumps(league))
        parts = partition_matches(matches)
        kept = parts["kept"]
        lo, hi = SHAPE_BOUNDS[season_key]
        if not lo <= len(kept) <= hi:
            raise AdapterError(
                "season {}: kept {} finished numeric-round matches outside "
                "shape bounds [{},{}] - refusing to write".format(season_key, len(kept), lo, hi))
        log("season {}: {} fixtures | kept {} | playoff {} | cancelled {} | unfinished {}".format(
            season_key, len(matches), len(kept), len(parts["playoff"]),
            len(parts["cancelled"]), len(parts["unfinished"])))

        details: dict[str, dict] = {}
        for i, m in enumerate(kept, 1):
            mid = str(m["id"])
            cache_file = md_dir / "{}.json".format(mid)
            if cache_file.exists():
                cache_hits += 1
            else:
                if new_fetches >= args.max_fetch:
                    raise AdapterError(
                        "--max-fetch {} reached with matches still missing; "
                        "rerun to resume from cache".format(args.max_fetch))
                time.sleep(args.sleep)
                payload = fetch_json(
                    "https://{}/api/data/matchDetails?matchId={}".format(HOST, mid),
                    ip_holder)
                atomic_write(cache_file, json.dumps(payload))
                new_fetches += 1
                if new_fetches % 50 == 0:
                    log("  season {}: {}/{} matchDetails ({} new fetches)".format(
                        season_key, i, len(kept), new_fetches))
            details[mid] = json.loads(cache_file.read_text())

        index = team_index(matches)
        if len(index) != TEAM_COUNT:
            raise AdapterError("season {}: expected {} teams, got {}".format(
                season_key, TEAM_COUNT, len(index)))
        block, skipped = build_block(season_key, kept, details, index)
        skip_rate = len(skipped) / max(len(kept), 1)
        if skip_rate > MAX_SKIP_RATE or (len(kept) - len(skipped)) == 0:
            raise AdapterError(
                "season {}: xG-missing rate {:.1%} ({} of {}) exceeds fail-closed "
                "threshold - probable upstream schema change; nothing written".format(
                    season_key, skip_rate, len(skipped), len(kept)))
        titles = {row["title"] for row in block["teams"].values()}
        if len(titles) != TEAM_COUNT or len(block["teams"]) != TEAM_COUNT:
            raise AdapterError("season {}: block team table is not {} unique teams".format(
                season_key, TEAM_COUNT))
        snapshot["{}_{}".format(LEAGUE_KEY, season_key)] = block
        alias_meta["{}_{}".format(LEAGUE_KEY, season_key)] = index
        season_meta["{}_{}".format(LEAGUE_KEY, season_key)] = {
            "api_season_param": season_param or "(default=current)",
            "selected_season": expected,
            "fixtures_total": len(matches),
            "kept_finished_numeric": len(kept),
            "matches_with_xg": len(kept) - len(skipped),
            "skipped_no_xg": len(skipped),
            "skipped_no_xg_ids": skipped,
            "excluded_playoff": len(parts["playoff"]),
            "excluded_playoff_rounds": sorted({str(m.get("round")) for m in parts["playoff"]}),
            "excluded_playoff_ids": [str(m["id"]) for m in parts["playoff"]],
            "excluded_cancelled": len(parts["cancelled"]),
            "excluded_cancelled_ids": [str(m["id"]) for m in parts["cancelled"]],
            "excluded_unfinished": len(parts["unfinished"]),
            "dates_range": [block["dates"][0]["datetime"], block["dates"][-1]["datetime"]],
        }
        log("season {}: block built - {} dates, {} teams, {} skipped-no-xg".format(
            season_key, len(block["dates"]), len(block["teams"]), len(skipped)))

    ended = datetime.now(timezone.utc)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    atomic_write(out_path, json.dumps(snapshot, indent=1) + "\n")
    meta = {
        "generated_utc": ended.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "fetch_started_utc": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duration_s": round((ended - started).total_seconds(), 1),
        "provider": "fotmob.com/api/data (unofficial, no key, dataProvider=opta)",
        "league": "EFL Championship (FotMob league id {})".format(LEAGUE_ID),
        "league_key_in_snapshot": LEAGUE_KEY,
        "seasons": season_meta,
        "backfill_stats": {
            "matchdetails_needed": sum(s["kept_finished_numeric"] for s in season_meta.values()),
            "matchdetails_cache_hits": cache_hits,
            "matchdetails_new_fetches": new_fetches,
            "rate_limit_seconds_between_fetches": args.sleep,
            "doh_ip_used": ip_holder["ip"],
        },
        "filters": {
            "numeric_rounds_only": "1-46 (playoff rounds excluded)",
            "cancelled_excluded": True,
            "require_finished": True,
            "require_xg_row": True,
            "fail_closed_max_skip_rate": MAX_SKIP_RATE,
        },
        "team_aliases": alias_meta,
        "wire_format": ("Understat snapshot shape consumed by "
                        "polymarket_alpha_lab.papersim.xg; forecast/ppda/deep/xpts "
                        "fields absent (not FotMob fields, not read by papersim.xg)"),
        "fields_note": ("history xG/xGA/npxG/npxGA floats; dates xG.h/xG.a "
                        "strings; scored/missed are ACTUAL goals; date format "
                        "'YYYY-MM-DD HH:MM:SS' UTC"),
        "tool": "paper-sim/tools/fotmob_adapter.py (WP-P3 Phase 1)",
        "poc_lineage": "/tmp/xgsrc_probe/fotmob_to_understat_poc.py",
    }
    atomic_write(meta_path, json.dumps(meta, indent=1) + "\n")
    log("wrote {} ({} bytes)".format(out_path, out_path.stat().st_size))
    log("wrote {}".format(meta_path))
    log("backfill: {} matches | {} cache hits | {} new fetches | {:.0f}s".format(
        meta["backfill_stats"]["matchdetails_needed"], cache_hits, new_fetches,
        meta["duration_s"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
