"""FotMob xG snapshot adapter: polite fetch + Understat wire transform.

Single responsibility: wrap FotMob's public unofficial JSON API (no key,
no credentials) behind a rate-limited, fail-closed fetch layer, and
transform the fetched payloads into the Understat snapshot shape
consumed by :mod:`polymarket_alpha_lab.papersim.xg`. This is the WP-P3
mechanism that reaches domestic leagues OUTSIDE Understat's Big-5
coverage: the EFL Championship was validated in Phase 1 (five gates,
4 PASS) and Eredivisie is the next candidate (league id verified, the
adapter has not been run against it yet).

Canonical lineage: WP-P3 Phase 1 server-side tooling
``paper-sim/tools/fotmob_adapter.py`` -> ``fotmob_validate.py``
(validated 2026-11-03, report ``paper-sim/round31/
fotmob_validation_report.md``). This module is the Phase 2 promotion:
the fetch/transform core of that adapter as a stdlib-only library
module. The server-side tool keeps its DoH + ``curl --resolve``
transport and on-disk matchDetails cache; those stay outside the
library (hosts with pinned DNS for fotmob.com keep using the tool).

Network boundary (library convention, same as the usage doc): loaders
and transforms are PURE. Only :func:`fetch_fotmob_league` and
:func:`fetch_match_details` touch the network, via stdlib ``urllib``
only, and both share one module-wide polite-spacing guard
(:data:`SLEEP_S` = 1.3 s between any two requests, matching the Phase
1 fetch policy). No credentials, no cookies, paper-only.

Fail-closed contract (inherited from Phase 1): the transform refuses
to emit a block when the payload shape looks like an upstream schema
change — season drift (``selectedSeason`` vs the derived season
window), malformed fixture rows, a team table that does not match the
league size, or an xG-missing skip rate above :data:`MAX_SKIP_RATE`.
Nothing is returned in that case; a :class:`FotMobSchemaError` names
the offending condition. Mild per-match gaps (matchDetails absent or
missing the xG row) are skipped and counted, bounded by the skip-rate
ceiling.

Validation status (WP-P3 Phase 1, frozen 2026-11-03): gates A-D PASS
(schema/coverage, league goal fit, xG-goal correlation, walk-forward
backtest vs a league-average baseline); gate E FAIL — 1X2 favorite
flips when teams new to the snapshot season (relegated/promoted sides)
fall back to league-average multipliers. Championship snapshots are
therefore sanctioned for the totals-family channels (O/U, BTTS, team
totals) through the standard domestic 10-variant path; 1X2 stays
deprioritized under the frozen domestic match_winner policy.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from enum import Enum
from typing import Mapping

__all__ = [
    "FETCH_ATTEMPTS",
    "FETCH_TIMEOUT_S",
    "FotMobError",
    "FotMobLeague",
    "FotMobSchemaError",
    "HOST",
    "MAX_SKIP_RATE",
    "SLEEP_S",
    "USER_AGENT",
    "fetch_fotmob_league",
    "fetch_match_details",
    "fotmob_to_understat",
    "load_fotmob_snapshot",
]

#: FotMob public API host (unofficial, no key; data provider = Opta).
HOST = "www.fotmob.com"

#: Desktop browser UA, frozen from the Phase 1 adapter fetch policy.
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

#: Polite spacing between any two FotMob requests (Phase 1 policy).
SLEEP_S = 1.3

#: Per-attempt HTTPS timeout for the fetch functions.
FETCH_TIMEOUT_S = 30.0

#: Fetch attempts (transport errors only) before giving up.
FETCH_ATTEMPTS = 4

#: Fail-closed ceiling on the per-match xG-missing skip rate (>5% of
#: kept matches without an xG row => probable upstream schema change).
MAX_SKIP_RATE = 0.05

#: Module-wide monotonic timestamp of the last FotMob request; enforces
#: :data:`SLEEP_S` spacing across BOTH fetch functions. Tests reset it.
_last_fetch_monotonic: float | None = None


class FotMobError(RuntimeError):
    """Fatal FotMob fetch/parse failure (transport gave up, non-JSON)."""


class FotMobSchemaError(FotMobError):
    """Fail-closed upstream schema change; no snapshot block is emitted."""


class FotMobLeague(Enum):
    """Verified FotMob league ids usable with the fetch/transform pair.

    Members carry ``(league_id, league_key, max_round, team_count)``:
    the numeric API id, the Understat-style snapshot block key, the
    numeric league-phase round bound (playoff rounds excluded) and the
    league size used by the fail-closed team-table check.

    Verification provenance: ``CHAMPIONSHIP`` is the Phase 1 validated
    configuration (720 matches, 2026-11-03); ``EREDIVISIE`` had its id
    confirmed against the live API on 2026-11-04 but has NOT been run
    through the adapter yet — its shape constants are the league's
    standard format (18 clubs, 34 rounds). Further verified-as-existing
    ids (checked 2026-11-04, no adapter run): 47 Premier League, 55
    Serie A, 87 LaLiga, 53 Ligue 1, 54 Bundesliga — all Understat-
    covered, so the FotMob path is not the sanctioned source for them.
    Add new members only with a verified id and a validated adapter run
    recorded in the lineage above.
    """

    CHAMPIONSHIP = (48, "Championship", 46, 24)
    EREDIVISIE = (57, "Eredivisie", 34, 18)

    def __init__(
        self,
        league_id: int,
        league_key: str,
        max_round: int,
        team_count: int,
    ) -> None:
        self.league_id = league_id
        self.league_key = league_key
        self.max_round = max_round
        self.team_count = team_count


def _league_constants(league: str | FotMobLeague) -> tuple[str, int, int | None]:
    """Resolve ``(league_key, max_round, team_count)`` for a league spec.

    A :class:`FotMobLeague` member contributes its own constants; a bare
    string key keeps the Phase 1 Championship defaults (46 numeric
    rounds, no strict team-count check).
    """
    if isinstance(league, FotMobLeague):
        return league.league_key, league.max_round, league.team_count
    return str(league), 46, None


def _league_id(league: int | FotMobLeague) -> int:
    if isinstance(league, FotMobLeague):
        return league.league_id
    return int(league)


def _polite_pause() -> None:
    """Sleep the remainder of :data:`SLEEP_S` since the last request."""
    global _last_fetch_monotonic
    now = time.monotonic()
    if _last_fetch_monotonic is not None:
        remaining = SLEEP_S - (now - _last_fetch_monotonic)
        if remaining > 0.0:
            time.sleep(remaining)
    _last_fetch_monotonic = time.monotonic()


def _http_get_json(url: str, *, timeout: float) -> object:
    """One HTTPS GET returning parsed JSON (raises on transport/JSON errors)."""
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read()
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise FotMobError(
            f"non-JSON response from {url} ({len(body)} bytes): {exc}"
        ) from exc


def _fetch_json(url: str, *, timeout: float) -> object:
    """Fetch with retry/backoff and polite spacing; fail via FotMobError."""
    last_exc: Exception | None = None
    for attempt in range(FETCH_ATTEMPTS):
        _polite_pause()
        try:
            return _http_get_json(url, timeout=timeout)
        except (urllib.error.URLError, OSError, FotMobError) as exc:
            last_exc = exc
            if attempt < FETCH_ATTEMPTS - 1:
                time.sleep(5.0 * (attempt + 1))
    raise FotMobError(f"giving up after {FETCH_ATTEMPTS} attempts: {url} ({last_exc})")


def fetch_fotmob_league(
    league_id: int | FotMobLeague,
    season: str | None = None,
    *,
    timeout: float = FETCH_TIMEOUT_S,
) -> dict:
    """Fetch one league-season fixtures payload (NETWORK, rate-limited).

    ``GET https://www.fotmob.com/api/data/leagues?id=<league_id>`` with
    an optional ``season=YYYY%2FYYYY`` parameter (FotMob season strings
    like ``"2025/2026"``; ``None`` takes the current season). Returns
    the parsed payload verbatim (``details`` / ``fixtures.allMatches``
    shape) for feeding :func:`fotmob_to_understat`; no normalization,
    no caching — resumable on-disk caches stay with the server-side
    Phase 1 tool. Raises :class:`FotMobError` when the payload is not a
    JSON object or all retries fail.
    """
    url = f"https://{HOST}/api/data/leagues?id={_league_id(league_id)}"
    if season is not None:
        url += "&season=" + urllib.parse.quote(str(season), safe="")
    payload = _fetch_json(url, timeout=timeout)
    if not isinstance(payload, dict):
        raise FotMobSchemaError(f"leagues payload for {url} is not an object")
    return payload


def fetch_match_details(
    match_id: str | int,
    *,
    timeout: float = FETCH_TIMEOUT_S,
) -> dict:
    """Fetch one match's details payload (NETWORK, rate-limited).

    ``GET https://www.fotmob.com/api/data/matchDetails?matchId=<id>`` —
    the per-match payload holding the score header and the Periods.All
    xG rows the transform extracts. Same contract as
    :func:`fetch_fotmob_league`: parsed payload verbatim, no cache.
    """
    url = f"https://{HOST}/api/data/matchDetails?matchId={match_id}"
    payload = _fetch_json(url, timeout=timeout)
    if not isinstance(payload, dict):
        raise FotMobSchemaError(f"matchDetails payload for {url} is not an object")
    return payload


# --------------------------------------------------------------------------
# payload extraction (pure; fail-closed on shape drift)
# --------------------------------------------------------------------------

def _expected_season(season_key: str) -> str:
    """'2026' -> '2026/2027' (September-May season window)."""
    try:
        year = int(season_key)
    except ValueError as exc:
        raise FotMobSchemaError(
            f"season_key must be an integer year string, got {season_key!r}"
        ) from exc
    return f"{year}/{year + 1}"


def _parse_league_payload(data: object, season_key: str) -> list:
    """Validate the leagues payload shape and return ``fixtures.allMatches``."""
    if not isinstance(data, dict):
        raise FotMobSchemaError(f"leagues payload for {season_key} is not an object")
    details = data.get("details")
    fixtures = data.get("fixtures")
    if not isinstance(details, dict) or not isinstance(fixtures, dict):
        raise FotMobSchemaError(f"leagues payload for {season_key} missing details/fixtures")
    expected = _expected_season(season_key)
    selected = details.get("selectedSeason")
    if selected != expected:
        raise FotMobSchemaError(
            f"season drift for {season_key}: selectedSeason={selected!r} "
            f"expected={expected!r}"
        )
    matches = fixtures.get("allMatches")
    if not isinstance(matches, list) or not matches:
        raise FotMobSchemaError(f"allMatches missing/empty for {season_key}")
    for match in matches:
        if not isinstance(match, dict) or not isinstance(match.get("status"), dict):
            raise FotMobSchemaError(f"malformed fixture row in {season_key}")
        for side in ("home", "away"):
            team = match.get(side)
            if not isinstance(team, dict) or "id" not in team or "name" not in team:
                raise FotMobSchemaError(
                    f"malformed {side} team in fixture {match.get('id')}"
                )
    return matches


def _is_cancelled(match: Mapping[str, object]) -> bool:
    """True for cancelled/abandoned fixtures (codex review #5, 2026-11-04).

    Cached FotMob sources contain abandoned games whose only markers are
    ``status.cancelled=true`` and reason ``longKey="aborted"`` while
    ``finished`` is also true (e.g. Blackburn-Ipswich 4825094 and its
    replay 5008942). The pre-fix text-only check matched ``"cancel"`` and
    kept those rows, double-counting abandoned games alongside their
    replays. Reject the explicit boolean flag first, then match both
    ``cancel`` and ``abort`` reason keys.
    """
    status = match.get("status") or {}
    if status.get("cancelled") is True:
        return True
    reason = status.get("reason")
    if isinstance(reason, dict):
        key = (str(reason.get("longKey", "")) + str(reason.get("shortKey", ""))).lower()
        return "cancel" in key or "abort" in key
    return False


def _partition_matches(matches: list, max_round: int) -> dict[str, list]:
    """Split fixtures into kept (numeric round, finished, not cancelled)
    and excluded buckets (playoff / cancelled / unfinished) with reasons."""
    kept: list = []
    playoff: list = []
    cancelled: list = []
    unfinished: list = []
    for match in matches:
        round_raw = str(match.get("round", ""))
        if not (round_raw.isdigit() and 1 <= int(round_raw) <= max_round):
            playoff.append(match)
        elif _is_cancelled(match):
            cancelled.append(match)
        elif not match["status"].get("finished"):
            unfinished.append(match)
        else:
            kept.append(match)
    return {"kept": kept, "playoff": playoff, "cancelled": cancelled,
            "unfinished": unfinished}


def _extract_xg_pair(md: Mapping[str, object], title: str) -> tuple[str, str] | None:
    """First non-null ``[home, away]`` row named ``title`` in Periods.All."""
    try:
        groups = md["content"]["stats"]["Periods"]["All"]["stats"]
    except (KeyError, TypeError):
        return None
    if not isinstance(groups, list):
        return None
    for group in groups:
        if not isinstance(group, dict):
            continue
        for stat in group.get("stats", []) or []:
            if not isinstance(stat, dict) or stat.get("title") != title:
                continue
            values = stat.get("stats")
            if (isinstance(values, list) and len(values) == 2
                    and values[0] is not None and values[1] is not None):
                return str(values[0]), str(values[1])
    return None


def _extract_score(md: Mapping[str, object]) -> tuple[int, int] | None:
    try:
        home, away = md["header"]["teams"][0], md["header"]["teams"][1]
        if home.get("score") is not None and away.get("score") is not None:
            return int(home["score"]), int(away["score"])
    except (KeyError, TypeError, IndexError, ValueError):
        pass
    return None


def _fmt_date(utc: str) -> str:
    """'2026-11-03T19:45:00.000Z' -> '2026-11-03 19:45:00' (Understat shape)."""
    return utc.replace("T", " ").replace("Z", "").split(".")[0]


def _result_code(goals_for: int, goals_against: int) -> str:
    if goals_for > goals_against:
        return "w"
    if goals_for == goals_against:
        return "d"
    return "l"


def _team_index(matches: list) -> dict[str, dict[str, str]]:
    """``id -> {title, short_title}`` over ALL fixtures (incl. playoffs)."""
    index: dict[str, dict[str, str]] = {}
    for match in matches:
        for side in ("home", "away"):
            team = match[side]
            index[str(team["id"])] = {
                "title": team["name"],
                "short_title": team.get("shortName", ""),
            }
    return index


def _build_block(
    kept: list,
    details: Mapping[str, object],
    teams_index: Mapping[str, Mapping[str, str]],
) -> tuple[dict, list]:
    """Build one Understat-format block ``{teams, dates}`` plus skipped ids."""
    histories: dict[str, list] = {}
    dates: list = []
    skipped: list = []
    for match in kept:
        mid = str(match["id"])
        md = details.get(mid)
        xg = _extract_xg_pair(md, "Expected goals (xG)") if md else None
        score = _extract_score(md) if md else None
        if xg is None or score is None:
            skipped.append(mid)
            continue
        npxg = _extract_xg_pair(md, "xG non-penalty") or xg
        home_goals, away_goals = score
        home_xg, away_xg = xg
        home_npxg, away_npxg = npxg
        date_str = _fmt_date(match["status"]["utcTime"])
        home, away = match["home"], match["away"]
        home_id, away_id = str(home["id"]), str(away["id"])
        histories.setdefault(home_id, []).append({
            "h_a": "h", "xG": float(home_xg), "xGA": float(away_xg),
            "npxG": float(home_npxg), "npxGA": float(away_npxg),
            "scored": home_goals, "missed": away_goals,
            "result": _result_code(home_goals, away_goals), "date": date_str,
        })
        histories.setdefault(away_id, []).append({
            "h_a": "a", "xG": float(away_xg), "xGA": float(home_xg),
            "npxG": float(away_npxg), "npxGA": float(home_npxg),
            "scored": away_goals, "missed": home_goals,
            "result": _result_code(away_goals, home_goals), "date": date_str,
        })
        dates.append({
            "id": mid, "isResult": True,
            "h": {"id": home_id, "title": home["name"],
                  "short_title": home.get("shortName", "")},
            "a": {"id": away_id, "title": away["name"],
                  "short_title": away.get("shortName", "")},
            "goals": {"h": str(home_goals), "a": str(away_goals)},
            "xG": {"h": home_xg, "a": away_xg},
            "datetime": date_str,
        })
    teams: dict[str, dict] = {}
    for team_id, meta in teams_index.items():
        history = sorted(histories.get(team_id, []), key=lambda entry: entry["date"])
        teams[team_id] = {"id": team_id, "title": meta["title"], "history": history}
    dates.sort(key=lambda row: row["datetime"])
    return {"teams": teams, "dates": dates}, skipped


def fotmob_to_understat(
    raw: Mapping[str, object],
    league_key: str | FotMobLeague,
    season_key: str,
    *,
    max_round: int | None = None,
    team_count: int | None = None,
    max_skip_rate: float = MAX_SKIP_RATE,
) -> dict[str, Mapping[str, object]]:
    """Transform fetched FotMob payloads into one Understat snapshot block.

    ``raw`` is the two-fetch bundle: ``{"fixtures": <leagues payload
    from fetch_fotmob_league>, "details": {match_id: <matchDetails
    payload from fetch_match_details>}}``. PURE — no network access;
    per-match ``details`` entries may be missing (skipped and counted)
    so partially fetched inputs fail closed rather than silently shrink.

    Returns the single-block snapshot
    ``{f"{league_key}_{season_key}": {"teams": ..., "dates": ...}}`` in
    the exact wire shape :mod:`polymarket_alpha_lab.papersim.xg`
    consumes (history xG floats, dates xG strings,
    ``YYYY-MM-DD HH:MM:SS`` UTC datetimes), ready to merge into a
    larger snapshot mapping.

    Fail-closed (raises :class:`FotMobSchemaError`, returns nothing):
    season drift vs the derived ``YYYY/YYYY+1`` window, malformed
    fixture rows, a team table not matching ``team_count`` when the
    check is enabled, and an xG-missing skip rate above
    ``max_skip_rate`` (or zero usable matches). Pass a
    :class:`FotMobLeague` member as ``league_key`` to inherit its
    round/team constants; a bare string uses the Phase 1 Championship
    defaults (46 numeric rounds, no strict team-count check).
    """
    resolved_key, default_round, default_count = _league_constants(league_key)
    if max_round is None:
        max_round = default_round
    if team_count is None:
        team_count = default_count

    fixtures = raw.get("fixtures")
    if not isinstance(fixtures, dict):
        raise FotMobSchemaError(f"raw bundle for {resolved_key} missing fixtures payload")
    details = raw.get("details")
    if not isinstance(details, Mapping):
        raise FotMobSchemaError(f"raw bundle for {resolved_key} missing details mapping")

    matches = _parse_league_payload(fixtures, season_key)
    parts = _partition_matches(matches, max_round)
    kept = parts["kept"]

    index = _team_index(matches)
    if team_count is not None and len(index) != team_count:
        raise FotMobSchemaError(
            f"season {season_key}: expected {team_count} teams, got {len(index)}"
        )

    block, skipped = _build_block(kept, details, index)
    skip_rate = len(skipped) / max(len(kept), 1)
    if skip_rate > max_skip_rate or (len(kept) - len(skipped)) == 0:
        raise FotMobSchemaError(
            f"season {season_key}: xG-missing rate {skip_rate:.1%} ({len(skipped)} of "
            f"{len(kept)}) exceeds fail-closed threshold {max_skip_rate:.0%} - "
            "probable upstream schema change; no block emitted"
        )
    titles = {row["title"] for row in block["teams"].values()}
    if team_count is not None and (
        len(titles) != team_count or len(block["teams"]) != team_count
    ):
        raise FotMobSchemaError(
            f"season {season_key}: block team table is not {team_count} unique teams"
        )
    return {f"{resolved_key}_{season_key}": block}


def load_fotmob_snapshot(path: str) -> dict[str, Mapping[str, object]]:
    """Load a pre-fetched FotMob->Understat snapshot (PURE, no network).

    Structural validation with precise errors: the root must be a JSON
    object; every block must be a mapping with a non-empty ``teams``
    mapping and a ``dates`` list; every ``dates`` row must be a mapping
    with an ``xG`` object carrying ``h`` / ``a``. Returns the raw
    ``{"<League>_<season>": {"teams": ..., "dates": ...}}`` structure
    unmodified (raw payloads preserved before normalization), ready for
    :func:`polymarket_alpha_lab.papersim.xg.load_xg_payload`.
    """
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("FotMob snapshot root must be a JSON object")
    for key, block in payload.items():
        if not isinstance(block, Mapping):
            raise ValueError(f"snapshot block {key!r} must be an object")
        teams = block.get("teams")
        dates = block.get("dates")
        if not isinstance(teams, Mapping) or not teams:
            raise ValueError(f"snapshot block {key!r} has no teams mapping")
        if not isinstance(dates, list):
            raise ValueError(f"snapshot block {key!r} has no dates list")
        for row in dates:
            if not isinstance(row, Mapping):
                raise ValueError(f"snapshot block {key!r} has a non-object dates row")
            xg = row.get("xG")
            if not isinstance(xg, Mapping) or "h" not in xg or "a" not in xg:
                raise ValueError(
                    f"snapshot block {key!r} has a dates row without xG.h/xG.a"
                )
    return payload
