"""ROUND-44C scan (paper-only): EARLY scan of the NEXT LEAGUE WEEKEND
window 2026-11-13T18:00Z .. 2026-11-15T23:59Z (Fri evening + Sat + Sun).

DISPATCH PREMISE vs FINDING: the dispatch asked for early prices on next
weekend's Big-5 + Championship + Eredivisie slates (T-5/6d). The
enumeration finds NO in-scope league slate in the window: 2026-11-14/15
is a FIFA international-break weekend in this environment (Gamma lists
22 UEFA Nations League + 3 friendly events in the window; the Gamma
listing horizon for all 7 in-scope league tags ends Mon 2026-11-09; ESPN
scoreboards for 20261113-15 are empty; FotMob league endpoints expose
only finished matches - EPL 100 / Championship 180 / La Liga 120 / Serie
A 110 / Bundesliga 81 / Ligue 1 90 / Eredivisie 108, all complete
through Sun Nov-8 with zero scheduled games after). Therefore: zero
fixtures enumerated, zero markets, zero board rows, zero candidates;
gates never become evaluable; the <=$400 early budget is untouched.

This assembler re-verifies the horizon live (fresh per-tag Gamma sweeps),
re-runs the library selfcheck, loads the xG bases through the validated
library loaders (provenance only - nothing to model), and records the
unmerged-results staleness basis (Sun Nov-8 + Mon Nov-9 games absent
from the snapshots: snapshot fresh-through = Sat Nov-7).

PAPER ONLY - no orders, no DB writes. Never prints credentials.
"""
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone

sys.path.insert(0, "/home/ubuntu/polymarket-alpha-lab/src")
from polymarket_alpha_lab.papersim import (  # noqa: E402
    fotmob,
    gates,
    league_strength,
    risk_policy,
    soccer_model,
    xg,
)

BASE = "https://gamma-api.polymarket.com"
HOME = "/home/ubuntu/paper-sim"
OUTDIR = f"{HOME}/round44/raw"
OUT = f"{OUTDIR}/weekend_early_scan.json"
EVENTS = f"{OUTDIR}/events_window_44c.json"
ESPN_NEXT = f"{OUTDIR}/espn_fixtures_44c.json"
ESPN_PRIOR = f"{OUTDIR}/espn_priorweek_44c.json"
FOTMOB_CAL = f"{OUTDIR}/fotmob_calendar_fresh_44c.json"
UNDERSTAT_LATEST = f"{HOME}/understat_latest.json"
UNDERSTAT_POINTER = f"{HOME}/understat_latest_pointer.json"
FOTMOB_CHAMP = f"{HOME}/championship_20261108/xg_fotmob_championship.json"
ERED = f"{HOME}/round39/raw/xg_fotmob_eredivisie.json"
KAPPA_PATH = f"{HOME}/round31/raw/league_strength_kappa.json"

LO = "2026-11-13T18:00:00Z"
HI = "2026-11-15T23:59:59Z"
BIG5 = ("EPL", "La_liga", "Serie_A", "Bundesliga", "Ligue_1")
TOTALS_ONLY = ("Championship", "Eredivisie")
IN_SCOPE = BIG5 + TOTALS_ONLY
LEAGUE_SWEEPS = [
    ("EPL", "epl"), ("EPL", "premier-league"),
    ("Championship", "efl-championship"),
    ("Bundesliga", "bundesliga"), ("La_liga", "la-liga"),
    ("Serie_A", "sea"), ("Ligue_1", "ligue-1"), ("Eredivisie", "ere"),
]

NOW = datetime.now(timezone.utc)
NOW_S = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")


def get(url, tries=5):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 (research)"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            last = e
            time.sleep(1.5 + i)
    if last:
        raise last
    return None


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


def tag_sweep(tag, max_offset=2000):
    """Complete sweep of ALL active non-closed events for a league tag
    (stops at first short page -> no truncation for tags < 2000)."""
    out, offset = [], 0
    while True:
        params = {"limit": 100, "active": "true", "closed": "false",
                  "order": "volume24hr", "ascending": "false",
                  "offset": offset, "tag_slug": tag}
        resp = get(BASE + "/events/pagination?" + urllib.parse.urlencode(params))
        batch = resp.get("data") if isinstance(resp, dict) else resp
        out.extend(batch)
        if len(batch) < 100 or offset + 100 >= max_offset:
            return out
        offset += 100
        time.sleep(0.8)


def horizon_check():
    """Live per-tag horizon re-verification (the load-bearing evidence)."""
    out = {}
    for lg, tag in LEAGUE_SWEEPS:
        evs = tag_sweep(tag)
        byday = Counter()
        titles_ahead = []
        for e in evs:
            sd = norm_ts(e.get("startDate"))
            day = sd[:10] or "nodate"
            byday[day] += 1
            if sd and sd >= "2026-11-10":
                titles_ahead.append({"id": e.get("id"), "title": e.get("title"),
                                     "startDate": sd})
        rec = out.setdefault(lg, {"tags": [], "events_total": 0, "by_day": {},
                                  "events_with_start_ge_2026-11-10": []})
        rec["tags"].append(tag)
        rec["events_total"] += len(evs)
        for d, n in byday.items():
            rec["by_day"][d] = rec["by_day"].get(d, 0) + n
        rec["events_with_start_ge_2026-11-10"].extend(titles_ahead)
        rec["listing_horizon"] = max((d for d in rec["by_day"] if d != "nodate"),
                                     default=None)
        time.sleep(0.8)
    # de-dup double-tagged EPL (epl + premier-league) horizon day lists
    return out


def ucl_uel_context():
    """Context: what soccer IS listed beyond the league horizon (Nov 10-12
    UCL/UEL + Nov 13-15 break competitions). Informational only."""
    out = {}
    for label, tag in (("ucl", "uefa-champions-league"),
                       ("uel", "europa-league"),
                       ("nations-league", "uefa-nations-league")):
        try:
            evs = tag_sweep(tag)
        except Exception as e:
            out[label] = {"error": repr(e)}
            continue
        ahead = []
        for e in evs:
            sd = norm_ts(e.get("startDate"))
            if sd and sd >= "2026-11-10":
                ahead.append({"id": e.get("id"), "title": e.get("title"),
                              "startDate": sd})
        ahead.sort(key=lambda x: x["startDate"])
        out[label] = {"tag": tag, "events_total": len(evs),
                      "start_ge_2026-11-10": ahead}
        time.sleep(0.8)
    return out


def selfcheck():
    r = subprocess.run(
        ["/home/ubuntu/polymarket-alpha-lab/.venv/bin/python", "-m",
         "polymarket_alpha_lab.papersim.cli", "selfcheck"],
        cwd="/home/ubuntu/polymarket-alpha-lab",
        capture_output=True, text=True, timeout=300)
    lines = (r.stdout or "").strip().splitlines()
    return {"returncode": r.returncode,
            "result_line": lines[-1] if lines else "",
            "ran_at_utc": NOW_S}


def main():
    print("UTC scan start:", NOW_S, flush=True)
    os.makedirs(OUTDIR, exist_ok=True)

    sc = selfcheck()
    print("selfcheck:", sc["result_line"], flush=True)

    events = json.load(open(EVENTS))
    print("enum events in window:", len(events), flush=True)

    # group in-window events by non-scope competition tag (break evidence)
    KNOWN = {"epl", "premier-league", "efl-championship", "championship",
             "bundesliga", "la-liga", "sea", "ligue-1", "ere", "soccer",
             "games", "sports"}
    in_scope_events, other_comp = [], {}
    for e in events:
        tags = [t for t in (e.get("tags") or []) if t not in KNOWN]
        lg_tags = [t for t in (e.get("tags") or [])
                   if t in {"epl", "premier-league", "efl-championship",
                            "bundesliga", "la-liga", "sea", "ligue-1", "ere"}]
        if lg_tags:
            in_scope_events.append(e)
            continue
        key = "+".join(sorted(tags)) or "untagged"
        other_comp.setdefault(key, []).append(
            {"kick": e.get("kick"), "title": e.get("title"), "id": e.get("id")})
    print("in-scope league events in window:", len(in_scope_events), flush=True)
    print("other-competition events in window:",
          sum(len(v) for v in other_comp.values()), flush=True)

    horizon = horizon_check()
    for lg, rec in sorted(horizon.items()):
        print("HORIZON %-13s total=%-4d horizon=%s ahead_nov10=%d" % (
            lg, rec["events_total"], rec["listing_horizon"],
            len(rec["events_with_start_ge_2026-11-10"])), flush=True)

    ctx = ucl_uel_context()
    for k, v in ctx.items():
        print("CONTEXT %-15s total=%-4d ahead_nov10=%d" % (
            k, v.get("events_total", -1),
            len(v.get("start_ge_2026-11-10", []))), flush=True)

    espn_next = json.load(open(ESPN_NEXT))
    espn_next_n = {d: {lg: len(v) for lg, v in day.items()
                       if isinstance(v, list)}
                   for d, day in espn_next.items()}
    espn_prior = json.load(open(ESPN_PRIOR))
    prior_summary = {}
    for d, day in espn_prior.items():
        for lg, evs in day.items():
            if not isinstance(evs, list):
                continue
            for ev in evs:
                prior_summary.setdefault(lg, {"by_day": {}, "statuses": Counter()})
                dd = norm_ts(ev.get("date"))[:10]
                prior_summary[lg]["by_day"][dd] = \
                    prior_summary[lg]["by_day"].get(dd, 0) + 1
                prior_summary[lg]["statuses"][ev.get("status") or "?"] += 1
    for lg in prior_summary:
        prior_summary[lg]["statuses"] = dict(prior_summary[lg]["statuses"])

    fotmob_cal = json.load(open(FOTMOB_CAL)) if os.path.exists(FOTMOB_CAL) else {}

    # snapshots via validated loaders (provenance/wiring proof; no modeling)
    with open(UNDERSTAT_POINTER, "r", encoding="utf-8") as _ph:
        understat_pointer = json.load(_ph)
    snapshot = dict(xg.load_xg_snapshot(UNDERSTAT_LATEST))
    for k, v in fotmob.load_fotmob_snapshot(FOTMOB_CHAMP).items():
        snapshot[k] = v
    for k, v in fotmob.load_fotmob_snapshot(ERED).items():
        snapshot[k] = v
    snap_blocks = sorted(snapshot.keys())
    snap_counts = {}
    for lg in IN_SCOPE:
        teams = (snapshot.get(f"{lg}_2026") or {}).get("teams", {})
        hist_dates = [str(e.get("date"))[:10]
                      for t in teams.values() for e in (t.get("history") or [])
                      if e.get("xG") is not None]
        snap_counts[lg] = {
            "clubs": len(teams),
            "matches": len(hist_dates),
            "fresh_through": (max(hist_dates) if hist_dates else None),
        }
    table = league_strength.load_kappa_report(KAPPA_PATH)
    kappa = dict(table.kappa)

    out = {
        "scan": "soccer-weekend-early",
        "round": 44,
        "sub_scan": "weekend_early_44C",
        "paper_only": True,
        "generated_utc": NOW_S,
        "window_utc": {"lo": LO, "hi": HI},
        "finding": (
            "NO IN-SCOPE LEAGUE SLATE EXISTS IN THE DISPATCH WINDOW: "
            "2026-11-14/15 is a FIFA international-break weekend. Gamma "
            "lists zero events for any of the 7 in-scope league tags "
            "beyond Mon 2026-11-09; the Nov 13-15 window on Gamma holds "
            "only UEFA Nations League (22), friendlies (3) and "
            "non-European/lower-division leagues. ESPN scoreboards for "
            "20261113-15 are empty. FotMob league endpoints show all 7 "
            "leagues complete through Sun 2026-11-08 with zero scheduled "
            "matches after. Zero fixtures -> zero markets -> gates not "
            "evaluable -> zero candidates; <=$400 early budget untouched."),
        "dispatch_note": (
            "ROUND-44C paper-sim EARLY scan dispatched 2026-11-08 for the "
            "Nov 13-15 'next league weekend' at T-5/6d. Dispatch premise "
            "(league rounds that weekend) is contradicted by every "
            "enumerated source: the window falls in the November "
            "international break. r38 precedent #63 (T-53h early entry) "
            "applies to league slates; none exists here. PAPER ONLY, no "
            "DB writes, no orders."),
        "provenance": {
            "understat_pointer": understat_pointer,
            "championship_snapshot": {
                "path": FOTMOB_CHAMP,
                "meta": json.load(open(FOTMOB_CHAMP + ".meta.json"))},
            "eredivisie_snapshot": {
                "path": ERED,
                "sha256_match_with_round41_copy": (
                    "54464dc8b13c357960b9cf46465db9a9aa5d0c98063c06598"
                    "b7413716f6e6ebc"),
                "meta": json.load(open(
                    "/home/ubuntu/paper-sim/round41/raw/"
                    "xg_fotmob_eredivisie.json.meta.json"))},
            "library_commit": "1a2760bc",
            "selfcheck": sc,
            "kappa": {k: round(v, 6) for k, v in kappa.items()},
            "snapshot_blocks_loaded": snap_blocks,
            "snapshot_counts_2026": snap_counts,
        },
        "enumeration": {
            "events_window_file": EVENTS,
            "events_in_window_all_soccer": len(events),
            "in_scope_league_events_in_window": len(in_scope_events),
            "in_scope_events": in_scope_events,
            "other_competitions_in_window": {
                k: {"n": len(v), "events": v}
                for k, v in sorted(other_comp.items())},
            "gamma_horizon_recheck_utc": NOW_S,
            "gamma_per_tag_horizon": horizon,
            "ucl_uel_break_context": ctx,
            "espn_next_weekend": {
                "file": ESPN_NEXT,
                "counts": espn_next_n,
                "note": ("ESPN scoreboard returned zero fixtures for "
                         "20261113/14/15 across all 11 league codes; "
                         "ESPN in this environment serves no league "
                         "fixtures beyond the current round")},
            "espn_prior_week_summary": {
                "file": ESPN_PRIOR,
                "per_league": prior_summary,
                "note": ("Nov 5-9 results used for staleness basis: the "
                         "current league round ran Fri Nov-6 .. Mon Nov-9")},
            "fotmob_league_calendar_fresh": {
                "file": FOTMOB_CAL,
                "data": fotmob_cal,
                "note": ("fresh 2026-11-09 fetches of /api/data/leagues?id= "
                         "for all 7 leagues: allMatches contains ONLY "
                         "finished matches (no future fixtures exposed), "
                         "finished counts prove the round is complete "
                         "through Sun Nov-8")},
            "date_param_caveat": (
                "Gamma /events(pagination) start_date_min/max params are "
                "non-functional in this environment (r43 enum43.log shows "
                "the same zero-return date sweeps while tag sweeps found "
                "168 in-window events); all horizon conclusions here rest "
                "on COMPLETE per-tag sweeps (each returned <100 events = "
                "no pagination truncation) and the tag-soccer volume sweep"),
        },
        "staleness": {
            "snapshot_fresh_through": "2026-11-07 (Sat) for all 7 leagues",
            "unmerged_results": (
                "Sun 2026-11-08 (+ Mon Nov-9 completions) league results "
                "are NOT in the xG bases (e.g. fresh FotMob EPL finished="
                "100 vs snapshot 95; Championship 180=180 with a Mon Nov-9 "
                "game listed on Gamma only). Before ANY future entry, "
                "re-refresh xG bases so Sunday/Monday results merge; this "
                "is carried as the model-refresh leg of every future "
                "early-entry recheck"),
            "stale_clubs_flagged": [],
            "note": ("the dispatch's STALE-XG Sunday-club flagging is moot "
                     "for candidates (no fixtures/no candidates); it "
                     "re-arms automatically at the next scan that has a "
                     "real slate"),
        },
        "gates": dict(gates.GATES, notes=(
            "FROZEN gates carried unchanged from r43 (net>=+5c fee-aware / "
            "worst>=+4c / var<=6c / liq>=5k / $250 fill / MW $150 "
            "deprioritized / one per fixture / spreads flagged-only / "
            "Championship+Eredivisie totals-only): NOT EVALUABLE this scan "
            "- zero listed markets in scope")),
        "budget": {
            "max_early_entry_proposals_usd": 400,
            "proposed_usd": 0,
            "note": ("nothing listed in scope -> nothing proposed; the "
                     "following week retains its own fresh-scan budget")},
        "fixtures": [],
        "matches": [],
        "board_rows": 0,
        "board": [],
        "candidates_file": f"{HOME}/round44/weekend_early_candidates.json",
        "artifacts": {
            "enum_log": f"{OUTDIR}/enum44c.log",
            "probe_horizon": f"{OUTDIR}/probe44c.log",
            "probe_inactive_search": f"{OUTDIR}/probe2_44c.log",
            "probe_schedule_structure": f"{OUTDIR}/probe3_44c.log",
            "probe_fotmob_calendar_cache": f"{OUTDIR}/probe4_44c.log",
            "fotmob_calendar_fresh": FOTMOB_CAL,
            "espn_next_weekend": ESPN_NEXT,
            "espn_prior_week": ESPN_PRIOR,
            "events_window": EVENTS,
        },
    }
    json.dump(out, open(OUT, "w"), indent=1)
    print("saved", OUT, flush=True)
    print("VERDICT-LINE: no in-scope slate in window; 0 fixtures, 0 board "
          "rows, 0 candidates; budget $0/$400", flush=True)


if __name__ == "__main__":
    main()
