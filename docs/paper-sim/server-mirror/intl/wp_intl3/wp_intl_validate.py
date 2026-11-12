"""WP-INTL-3 validation harness: international Elo-Poisson model gates.

Report-only evaluation of the WP-INTL-2 model (:mod:`intl_model`) on the
WP-INTL-1 snapshot (:mod:`intl_data`), mirroring the WP-NBA-3 /
WP-P3 A-E gate philosophy. This harness NEVER decides promotion: it
computes the gate numbers and writes ``report.md`` + ``results.json``
for the coordinator's review, plus a pretip shadow-recorder subcommand.

What it does (paper-only, read-only inputs, no DB writes, no entries):

- Gate A (data integrity): reload the snapshot through the adapter's
  fail-closed validator, optionally rebuild from the retained raw cache
  (results.csv + world.tsv) and compare matches/Elo tables.
- Walk-forward (gate D mirror): incremental strictly-causal Elo replay
  over the full corpus; every UEFA Nations League match 2018-2026 (762
  matches), optionally UEFA Euro 2024 + FIFA World Cup 2026 finals and
  2024-2026 friendlies between NL participants, predicted from
  strictly-earlier information only (ratings AND per-tournament mean
  totals AND causal H/D/A base rates).  1X2 Brier + log-loss and O/U 2.5
  log-loss vs (a) the model, (b) a tournament-mean-total Poisson
  baseline, (c) a coin; per-competition tables; nine-variant spread
  audit; slope sweep {0.40, 0.47, 0.55} (REPORT only); median-vs-variant
  comparison.  A self-check re-derives sampled predictions through
  ``intl_model.fixture_prediction`` on truncated snapshots and asserts
  equality with the fast path.
- Gate B (totals calibration): mean-total bias, O2.5 probability
  calibration + reliability bins, Pearson r(expected goal difference,
  actual margin).
- Gate C (Elo sanity): Spearman rho(full-history Elo, win% since 2018)
  over teams with >= 30 matches (the eloratings.net cross-check
  rho = 0.996 is retained probe evidence, referenced not recomputed).
- Gate E (market MAD): Polymarket CLOB ``prices-history`` closings for
  the Nov-2024 NL window (closed markets, verified retrievable by the
  round-47 probe) vs the same walk-forward model quotes, plus the
  Nov-12-2026 pretip board prices; 1X2 home/draw/away MAD (raw and
  devigged); O2.5 totals-MAD reported as unavailable-if-dust (R47
  finding: UNL O/U books are dust).
- ``shadow`` subcommand: given a date window, discover the NL fixtures
  on Polymarket (Gamma), price them with the model, and append pretip
  model-vs-market rows to a CSV whose columns mirror the NBA shadow
  JSON fields (label/tip_utc/game/model.*/market_ml.*/model_vs_market.*
  /final_score.*), idempotent per (kickoff, fixture).

Usage (ops host, the big compute)::

    python3 wp_intl_validate.py validate \
        --snapshot ~/paper-sim/intl/snapshot_20261112.json \
        --cache-dir ~/paper-sim/intl \
        --board ~/paper-sim/round47/board.json \
        --out-dir  ~/paper-sim/review/wp_intl_validation

    python3 wp_intl_validate.py shadow \
        --snapshot ~/paper-sim/intl/snapshot_20261112.json \
        --date-lo 2026-11-14 --date-hi 2026-11-14 \
        --csv ~/paper-sim/review/wp_intl_validation/shadow_nl_2026.csv

``--skip-pm`` disables the networked Polymarket part of validate.
Sibling-module deployment: when ``polymarket_alpha_lab/papersim/
{intl_model,intl_data,soccer_model,xg,league_strength}.py`` sit next to
this file (standalone server dir), they are imported from there;
otherwise the installed package is used (local worktree).

No credentials, no order paths, no persistence beyond the report files
and the shadow CSV. International 1X2 stays research-only
(:data:`intl_model.INTL_MW_RESEARCH_ONLY`); entry eligibility is not
decided here.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# module resolution: standalone dir (server) or installed package (worktree)
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve().parent
if (_HERE / "polymarket_alpha_lab" / "papersim" / "intl_model.py").is_file():
    sys.path.insert(0, str(_HERE))
    from polymarket_alpha_lab.papersim import intl_data, intl_model, soccer_model
else:  # local worktree: package importable from src/ (PYTHONPATH or install)
    from polymarket_alpha_lab.papersim import intl_data, intl_model, soccer_model

#: Log-loss clip floor (degenerate baseline probabilities).
_EPS = 1e-12

#: Kill bars from the round-47 feasibility study (§5/§7):
#: walk-forward log-loss gain < 1.5c vs baseline -> research-only;
#: closing MAD > 5c on main lines -> halt.
LL_GAIN_BAR_NATS = 0.015
GATE_E_MAX_MAD = 0.05

#: Other gate bars (mirrors WP-NBA-3 where the analog exists).
GATE_D_MIN_N = 20
GATE_C_MIN_RHO = 0.5
GATE_C_MIN_MATCHES = 30
GATE_B_MAX_TOTAL_BIAS = 0.15
GATE_B_MAX_PROB_BIAS = 0.05
GATE_B_MIN_GD_R = 0.15
GATE_E_MIN_GAMES = 10
VARIANT_SPREAD_BAR = 0.06

#: Fixed NL base rates from the round-47 probe (in-sample reference only;
#: the causal walk-forward baseline uses expanding tournament base rates).
NL_FIXED_BASE_RATES = (0.42, 0.25, 0.32)

#: Eval-set definitions.
NL_TOURNAMENT = "UEFA Nations League"
FINALS_TOURNAMENTS = ("UEFA Euro", "FIFA World Cup")
FINALS_FROM = "2024-01-01"
FRIENDLY_FROM = "2024-01-01"

#: PM event-slug family suffixes to strip when finding fixture roots.
_ROOT_SUFFIX_RE = re.compile(
    r" - (More Markets|Exact Score|Halftime Result|First Team to Score"
    r"|Second Half Result|Total Corners)$"
)

#: Polymarket display name -> martj42 corpus name (verified against the
#: 337-team vocabulary of snapshot_20261112 and the Nov-2024/Nov-2026
#: PM event titles; keys compare after exact match, then ascii-fold).
PM_NAME_TO_MARTJ42 = {
    "Czechia": "Czech Republic",
    "Türkiye": "Turkey",
    "Ireland": "Republic of Ireland",
    "Bosnia & Herzegovina": "Bosnia and Herzegovina",
    "United States": "United States",
    "Korea Republic": "South Korea",
    "Iran": "Iran",
    "Côte d'Ivoire": "Ivory Coast",
    "Cote d'Ivoire": "Ivory Coast",
    "Curaçao": "Curaçao",
    "DR Congo": "Congo DR",
    "Congo DR": "Congo DR",
}

_GAMMA_BASE = "https://gamma-api.polymarket.com"
_CLOB_BASE = "https://clob.polymarket.com"
_UA = "polymarket-alpha-lab/0.1 (wp-intl-3 validation; paper-only)"


# ---------------------------------------------------------------------------
# small statistics helpers (stdlib only)
# ---------------------------------------------------------------------------


def _mean(values: list[float]) -> float:
    return math.fsum(values) / len(values)


def _ranks(values: list[float]) -> list[float]:
    """Average ranks (ties share the mean rank)."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        average = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = average
        i = j + 1
    return ranks


def _corr_pvalue(r: float, n: int) -> float:
    """Two-sided p for a correlation via Fisher z (normal approx)."""
    if n < 4 or not math.isfinite(r) or abs(r) >= 1.0:
        return float("nan") if (n < 4 or not math.isfinite(r)) else 0.0
    z = 0.5 * math.log((1.0 + r) / (1.0 - r)) * math.sqrt(n - 3.0)
    return math.erfc(abs(z) / math.sqrt(2.0))


def pearson(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """(r, two-sided p) - NaN when either side is constant."""
    if len(xs) != len(ys) or len(xs) < 3:
        return (float("nan"), float("nan"))
    mx, my = _mean(xs), _mean(ys)
    cov = math.fsum((x - mx) * (y - my) for x, y in zip(xs, ys))
    var_x = math.fsum((x - mx) ** 2 for x in xs)
    var_y = math.fsum((y - my) ** 2 for y in ys)
    if var_x == 0.0 or var_y == 0.0:
        return (float("nan"), float("nan"))
    r = cov / math.sqrt(var_x * var_y)
    return (r, _corr_pvalue(r, len(xs)))


def spearman(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """(rho, approx two-sided p) on average ranks."""
    if len(xs) != len(ys) or len(xs) < 3:
        return (float("nan"), float("nan"))
    return pearson(_ranks(xs), _ranks(ys))


def multiclass_log_loss(records: list[dict], probs_key: str) -> tuple[float, int]:
    """(mean NLL, clip count) over 1X2 triples; probs_key -> (h, d, a)."""
    clipped = 0
    total = 0.0
    for record in records:
        probs = record[probs_key]
        outcome = record["outcome"]  # 0 home / 1 draw / 2 away
        p = probs[outcome]
        q = min(max(p, _EPS), 1.0 - _EPS)
        if q != p:
            clipped += 1
        total += -math.log(q)
    return total / len(records), clipped


def multiclass_brier(records: list[dict], probs_key: str) -> float:
    """Mean multiclass Brier: mean over matches of sum_k (p_k - o_k)^2."""
    return _mean(
        [
            math.fsum(
                (p - (1.0 if k == record["outcome"] else 0.0)) ** 2
                for k, p in enumerate(record[probs_key])
            )
            for record in records
        ]
    )


def binary_log_loss(probs: list[float], outcomes: list[int]) -> tuple[float, int]:
    clipped = 0
    total = 0.0
    for p, o in zip(probs, outcomes):
        q = min(max(p, _EPS), 1.0 - _EPS)
        if q != p:
            clipped += 1
        total += -(math.log(q) if o else math.log(1.0 - q))
    return total / len(probs), clipped


def ll_gain(model_ll: float, base_ll: float) -> dict:
    """Log-loss gain in nats and its probability-cents equivalent.

    cents = 100 * (exp(-LL_model) - exp(-LL_base)): the per-match
    geometric-mean probability picked up by the model over the baseline.
    Near the 1.5c bar the two readings coincide (0.015 nats ~ 1.49c);
    both are reported.
    """
    return {
        "delta_nats": base_ll - model_ll,
        "cents_equivalent": 100.0 * (math.exp(-model_ll) - math.exp(-base_ll)),
    }


# ---------------------------------------------------------------------------
# transport (read-only public GETs, polite)
# ---------------------------------------------------------------------------


def _get_json(url: str, *, timeout: float = 30.0, attempts: int = 3) -> object:
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": _UA, "Accept": "application/json"}
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read())
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            last = exc
            if attempt + 1 < attempts:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"GET failed after {attempts} attempts: {url} ({last})")


def _load_json_list(raw: object) -> list[str]:
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, list):
        raise ValueError(f"expected a JSON list, got {type(raw)!r}")
    return [str(item) for item in raw]


# ---------------------------------------------------------------------------
# Polymarket naming / event parsing
# ---------------------------------------------------------------------------


def norm(s: object) -> str:
    """Ascii-folded lowercase alnum normalization (boards47 convention)."""
    folded = unicodedata.normalize("NFKD", str(s or ""))
    folded = folded.encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]", "", folded.lower()).strip()


def pm_to_martj42(pm_name: str, known_teams: set[str]) -> str | None:
    """Map a PM display name to the martj42 corpus vocabulary."""
    name = pm_name.strip()
    if name in known_teams:
        return name
    if name in PM_NAME_TO_MARTJ42 and PM_NAME_TO_MARTJ42[name] in known_teams:
        return PM_NAME_TO_MARTJ42[name]
    folded = {
        "Turkiye": "Turkey",
        "Bosnia and Herzegovina": "Bosnia and Herzegovina",
    }
    ascii_name = "".join(
        ch for ch in unicodedata.normalize("NFKD", name) if not unicodedata.combining(ch)
    )
    if ascii_name in known_teams:
        return ascii_name
    if ascii_name in folded and folded[ascii_name] in known_teams:
        return folded[ascii_name]
    for team in known_teams:  # last resort: ascii-folded exact match
        if norm(team) == norm(name):
            return team
    return None


def family_root(title: str) -> str:
    """Fixture root of an event title (strip series prefix + sub-market suffix)."""
    root = _ROOT_SUFFIX_RE.sub("", str(title or "").strip())
    if ": " in root:
        head, _, tail = root.partition(": ")
        if norm(head) in ("uefa nations league", "nations league", "friendlies", "fifa friendly"):
            root = tail.strip()
    return root


def parse_kickoff(raw: object) -> datetime | None:
    """Parse Gamma gameStartTime ("2024-11-15 19:45:00+00" / ISO-Z)."""
    text = str(raw or "").strip()
    if not text:
        return None
    if text.endswith("+00"):
        text += ":00"
    text = text.replace(" ", "T", 1)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def classify_ml_market(question: str, home_pm: str, away_pm: str) -> str | None:
    """'home' / 'draw' / 'away' for a 2024-era ('Will X beat Y?') or
    2026-era ('Will X win on DATE?') NL moneyline question."""
    q = norm(question)
    if not q:
        return None
    if "end in a draw" in q:
        return "draw"
    home_n, away_n = norm(home_pm), norm(away_pm)
    if q.startswith("will "):
        for label, name in (("home", home_n), ("away", away_n)):
            if name and q.startswith(f"will {name} ") and (
                f"will {name} beat" in q or f"will {name} win" in q
            ):
                return label
    return None


def event_fixture(event: dict) -> dict | None:
    """(kickoff, root, home_pm, away_pm, event_id) for an NL fixture event."""
    root = family_root(event.get("title") or "")
    if " vs. " not in root:
        return None
    home_pm, _, away_pm = root.partition(" vs. ")
    home_pm, away_pm = home_pm.strip(), away_pm.strip()
    if not home_pm or not away_pm:
        return None
    kickoffs = [
        parse_kickoff(m.get("gameStartTime"))
        for m in event.get("markets") or []
        if m.get("gameStartTime")
    ]
    kickoffs = [k for k in kickoffs if k is not None]
    if not kickoffs:
        return None
    return {
        "event_id": str(event.get("id")),
        "slug": event.get("slug"),
        "root": root,
        "home_pm": home_pm,
        "away_pm": away_pm,
        "kickoff": min(kickoffs),
        "title": event.get("title"),
    }


def gamma_nl_events(*, closed: bool, tag: str = "uefa-nations-league",
                    max_pages: int = 8, end_min: str | None = None,
                    end_max: str | None = None) -> list[dict]:
    """Paginate Gamma events for the NL tag (read-only GETs).

    ``end_min``/``end_max`` (``YYYY-MM-DD``) add the ``end_date_min`` /
    ``end_date_max`` window - REQUIRED for older closed events: an
    unfiltered closed sweep is endDate-descending and buries the Nov-2024
    window hundreds of events deep (verified live: unfiltered 8 pages =
    800 events with zero Nov-2024 rows; the windowed query returns
    exactly the 20 fixture events).
    """
    out: list[dict] = []
    offset = 0
    for _ in range(max_pages):
        params = {
            "tag_slug": tag,
            "closed": "true" if closed else "false",
            "limit": 100,
            "offset": offset,
            "order": "endDate",
            "ascending": "true" if (end_min or end_max) else "false",
        }
        if end_min:
            params["end_date_min"] = f"{end_min}T00:00:00Z"
        if end_max:
            params["end_date_max"] = f"{end_max}T00:00:00Z"
        query = urllib.parse.urlencode(params)
        page = _get_json(f"{_GAMMA_BASE}/events?{query}")
        if not isinstance(page, list) or not page:
            break
        out.extend(page)
        if len(page) < 100:
            break
        offset += 100
        time.sleep(0.35)
    return out


def fetch_event_detail(event_id: str) -> dict | None:
    payload = _get_json(f"{_GAMMA_BASE}/events/{event_id}?include_markets=true")
    return payload if isinstance(payload, dict) else None


def closing_yes_price(token: str, kickoff_epoch: int) -> dict:
    """Last prices-history point strictly at/before kickoff for one token."""
    query = urllib.parse.urlencode(
        {
            "market": token,
            "startTs": int(kickoff_epoch - 3 * 86400),
            "endTs": int(kickoff_epoch),
            "fidelity": 5,
        }
    )
    payload = _get_json(f"{_CLOB_BASE}/prices-history?{query}")
    history = (payload or {}).get("history") or []
    before = [p for p in history if float(p["t"]) <= kickoff_epoch]
    if not before:
        return {"price": None, "points": len(history), "last_t": None}
    last = before[-1]
    return {
        "price": float(last["p"]),
        "points": len(history),
        "last_t": int(float(last["t"])),
        "minutes_before": (kickoff_epoch - int(float(last["t"]))) / 60.0,
    }


# ---------------------------------------------------------------------------
# walk-forward engine (incremental strictly-causal replay)
# ---------------------------------------------------------------------------


def _nl_cycle(date_str: str) -> str:
    year = int(date_str[:4])
    bucket = {2018: "2018-19", 2019: "2018-19", 2020: "2020-21", 2021: "2020-21",
              2022: "2022-23", 2023: "2022-23", 2024: "2024-25", 2025: "2024-25"}
    return bucket.get(year, "2026-27")


def eval_family(match: dict, nl_teams: set[str]) -> str | None:
    """Eval-set membership: 'unl' / 'finals' / 'friendlies' (None = skip)."""
    tournament = match["tournament"]
    if tournament == NL_TOURNAMENT:
        return "unl"
    if tournament in FINALS_TOURNAMENTS and match["date"] >= FINALS_FROM:
        return "finals"
    if (
        tournament == "Friendly"
        and match["date"] >= FRIENDLY_FROM
        and match["home"] in nl_teams
        and match["away"] in nl_teams
    ):
        return "friendlies"
    return None


def _variant_quote(
    elo_home: float,
    elo_away: float,
    total: float,
    slope: float,
    multiplier: float,
    neutral: bool,
) -> dict:
    """One envelope variant's outputs (exactly the model's arithmetic)."""
    lambdas = intl_model.pair_lambdas_from_elo(
        elo_home, elo_away, total * multiplier, slope=slope, neutral=neutral,
    )
    outputs = soccer_model.variant_outputs(lambdas[0], lambdas[1], rho=soccer_model.RHO_DC)
    return {
        "slope": slope,
        "multiplier": multiplier,
        "lambda_home": lambdas[0],
        "lambda_away": lambdas[1],
        "p_home": outputs.home_win,
        "p_draw": outputs.draw,
        "p_away": outputs.away_win,
        "p_over25": soccer_model.over_probability(outputs, 2.5),
        "btts": outputs.btts,
    }


class WalkForwardEngine:
    """Incremental Elo replay + causal calibration over the snapshot corpus.

    Float arithmetic mirrors :func:`intl_model._replay_elos` exactly (same
    update sequence; the self-check asserts equality against
    ``fixture_prediction`` on truncated snapshots).
    """

    def __init__(self, matches: list[dict]):
        self.matches = matches  # snapshot order: non-decreasing date
        self.ratings: dict[str, float] = {}
        self.games: dict[str, int] = {}
        # tournament -> [goals_sum, count, home_wins, draws, away_wins]
        self.tour: dict[str, list[float]] = {}

    # -- state update with one completed match ------------------------------

    def _apply(self, match: dict) -> None:
        home, away = match["home"], match["away"]
        rating_home = self.ratings.setdefault(home, intl_model.ELO_BASE)
        rating_away = self.ratings.setdefault(away, intl_model.ELO_BASE)
        advantage = 0.0 if match["neutral"] else intl_model.HOME_ADVANTAGE
        diff = rating_home + advantage - rating_away
        expected = 1.0 / (1.0 + 10.0 ** (-diff / 400.0))
        hg, ag = match["home_goals"], match["away_goals"]
        if hg > ag:
            result = 1.0
        elif hg == ag:
            result = 0.5
        else:
            result = 0.0
        delta = (
            intl_model.k_factor(match["tournament"])
            * intl_model.goal_difference_multiplier(abs(hg - ag))
            * (result - expected)
        )
        self.ratings[home] = rating_home + delta
        self.ratings[away] = rating_away - delta
        self.games[home] = self.games.get(home, 0) + 1
        self.games[away] = self.games.get(away, 0) + 1
        entry = self.tour.setdefault(
            match["tournament"], [0.0, 0.0, 0.0, 0.0, 0.0]
        )
        entry[0] += hg + ag
        entry[1] += 1.0
        entry[2 + (0 if hg > ag else (1 if hg == ag else 2))] += 1.0

    # -- prediction from the current state ----------------------------------

    def predict(
        self, home: str, away: str, tournament: str, *, neutral: bool
    ) -> dict | None:
        """Model quote for one fixture at the current (strictly-prior) state.

        Refusal (None) mirrors the model: a side with no strictly-prior
        match cannot be replay-rated. The nine-variant aggregation mirrors
        :func:`intl_model._aggregate` (per-quantity medians, away as the
        exact complement).
        """
        if self.games.get(home, 0) == 0 or self.games.get(away, 0) == 0:
            return None
        elo_home = self.ratings.get(home, intl_model.ELO_BASE)
        elo_away = self.ratings.get(away, intl_model.ELO_BASE)
        entry = self.tour.get(tournament)
        if entry is None or entry[1] == 0:
            total_base = intl_model.GLOBAL_FALLBACK_TOTAL
            tour_matches = 0
            base_rates = (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0)
        else:
            total_base = entry[0] / entry[1]
            tour_matches = int(entry[1])
            base_rates = (
                entry[2] / entry[1],
                entry[3] / entry[1],
                entry[4] / entry[1],
            )
        variants = [
            _variant_quote(
                elo_home, elo_away, total_base,
                spec.slope, spec.total_multiplier, neutral,
            )
            for spec in intl_model.VARIANTS
        ]
        p_home = soccer_model.median([v["p_home"] for v in variants])
        p_draw = soccer_model.median([v["p_draw"] for v in variants])
        p_over25 = soccer_model.median([v["p_over25"] for v in variants])
        lambda_home = soccer_model.median([v["lambda_home"] for v in variants])
        lambda_away = soccer_model.median([v["lambda_away"] for v in variants])
        # totals-only baseline: the same causal tournament mean, split
        # evenly with NO Elo bridge (slope 0 - constructed directly since
        # pair_lambdas_from_elo refuses slope <= 0)
        baseline_outputs = soccer_model.variant_outputs(
            total_base / 2.0, total_base / 2.0, rho=soccer_model.RHO_DC
        )
        baseline_over25 = soccer_model.over_probability(baseline_outputs, 2.5)
        spreads = {
            "p_home": max(v["p_home"] for v in variants) - min(v["p_home"] for v in variants),
            "p_draw": max(v["p_draw"] for v in variants) - min(v["p_draw"] for v in variants),
            "p_away": max(v["p_away"] for v in variants) - min(v["p_away"] for v in variants),
            "p_over25": max(v["p_over25"] for v in variants) - min(v["p_over25"] for v in variants),
        }
        return {
            "home": home,
            "away": away,
            "tournament": tournament,
            "neutral": neutral,
            "elo_home": elo_home,
            "elo_away": elo_away,
            "games_home": self.games.get(home, 0),
            "games_away": self.games.get(away, 0),
            "total_base": total_base,
            "tournament_matches": tour_matches,
            "base_rates_causal": base_rates,
            "p_home": p_home,
            "p_draw": p_draw,
            "p_away": 1.0 - p_home - p_draw,
            "p_over25": p_over25,
            "lambda_home": lambda_home,
            "lambda_away": lambda_away,
            "pred_total": lambda_home + lambda_away,
            "btts": soccer_model.median([v["btts"] for v in variants]),
            "exp_gd_default_slope": intl_model.expected_gd(
                elo_home, elo_away,
                slope=intl_model.DEFAULT_SLOPE, neutral=neutral,
            ),
            "baseline_over25": baseline_over25,
            "variant_spreads": spreads,
            "variants": variants,
        }


def run_walk_forward(
    matches: list[dict],
    nl_teams: set[str],
    *,
    requested: dict[str, list[dict]] | None = None,
    include_finals: bool = True,
    include_friendlies: bool = True,
) -> tuple[list[dict], dict[str, dict], dict]:
    """Replay the corpus once; score every eval-set match.

    Returns ``(records, requested_predictions, info)``. ``requested`` maps
    a fixture date to prediction requests
    (``home``/``away``/``tournament``/``neutral``); predictions are made
    from the state strictly before that date (the same barrier semantics
    as :func:`intl_model.fixture_prediction`).
    """
    requested = requested or {}
    engine = WalkForwardEngine(matches)
    records: list[dict] = []
    predictions: dict[str, dict] = {}
    refused = {"eval": 0, "requested": 0}
    by_date: dict[str, list[dict]] = {}
    for match in matches:
        by_date.setdefault(match["date"], []).append(match)
    all_dates = sorted(set(by_date) | set(requested))
    for date in all_dates:
        for request in requested.get(date, []):
            quote = engine.predict(
                request["home"], request["away"], request["tournament"],
                neutral=request.get("neutral", False),
            )
            key = f"{date}|{request['home']}|{request['away']}"
            if quote is None:
                refused["requested"] += 1
                predictions[key] = {"refused": True}
                continue
            quote["date"] = date
            predictions[key] = quote
        for match in by_date.get(date, []):
            family = eval_family(match, nl_teams)
            if family is None:
                pass  # still applied to the state below
            else:
                quote = engine.predict(
                    match["home"], match["away"], match["tournament"],
                    neutral=match["neutral"],
                )
                if quote is None:
                    refused["eval"] += 1
                else:
                    hg, ag = match["home_goals"], match["away_goals"]
                    outcome = 0 if hg > ag else (1 if hg == ag else 2)
                    quote.update(
                        {
                            "date": date,
                            "family": family,
                            "cycle": _nl_cycle(date) if family == "unl" else None,
                            "tournament": match["tournament"],
                            "home_goals": hg,
                            "away_goals": ag,
                            "outcome": outcome,
                            "total": hg + ag,
                            "over25": 1 if hg + ag >= 3 else 0,
                            "model_probs": (quote["p_home"], quote["p_draw"], quote["p_away"]),
                            "base_rate_probs": quote["base_rates_causal"],
                            "uniform_probs": (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0),
                            "fixed_nl_probs": NL_FIXED_BASE_RATES,
                        }
                    )
                    records.append(quote)
        for match in by_date.get(date, []):
            engine._apply(match)
    info = {
        "corpus_matches": len(matches),
        "eval_scored": len(records),
        "refusals": refused,
        "include_finals": include_finals,
        "include_friendlies": include_friendlies,
    }
    return records, predictions, info


# ---------------------------------------------------------------------------
# self-check: fast path vs intl_model.fixture_prediction on truncated snapshots
# ---------------------------------------------------------------------------


def self_check(
    snapshot: dict, records: list[dict], samples: list[dict]
) -> dict:
    """Assert the incremental engine equals the frozen model code path.

    For each sampled record the snapshot is truncated at the fixture date
    and ``intl_model.fixture_prediction`` runs on it (its replay + its
    per-tournament totals are then strictly causal by construction); the
    1X2 triple and O2.5 must agree to 1e-9.
    """
    rows = []
    mismatches = 0
    matches = snapshot["matches"]
    for record in samples:
        date = record["date"]
        truncated = [m for m in matches if m["date"] < date]
        mini = {
            "generated_at": snapshot["generated_at"],
            "teams": snapshot["teams"],
            "matches": truncated,
        }
        fixture = intl_model.IntlFixture(
            home=record["home"], away=record["away"], date=date,
            neutral=record["neutral"],
        )
        prediction = intl_model.fixture_prediction(
            mini, fixture, tournament=record["tournament"]
        )
        if prediction is None:
            rows.append({"date": date, "fixture": f"{record['home']} v {record['away']}",
                         "result": "REFUSED"})
            mismatches += 1
            continue
        model_over = prediction.over_line_prob(2.5).p_over
        deltas = {
            "p_home": abs(prediction.p_home - record["p_home"]),
            "p_draw": abs(prediction.p_draw - record["p_draw"]),
            "p_away": abs(prediction.p_away - record["p_away"]),
            "p_over25": abs(model_over - record["p_over25"]),
            "total_base": abs(prediction.total_base - record["total_base"]),
        }
        ok = all(delta <= 1e-9 for delta in deltas.values())
        if not ok:
            mismatches += 1
        rows.append({
            "date": date,
            "fixture": f"{record['home']} v {record['away']}",
            "result": "OK" if ok else "MISMATCH",
            "max_abs_delta": max(deltas.values()),
        })
    return {"samples": len(samples), "mismatches": mismatches, "rows": rows}


def pick_self_check_samples(records: list[dict], per_family: int = 4) -> list[dict]:
    """First + middle + last + a random-ish spread of each eval family."""
    samples: list[dict] = []
    for family in ("unl", "finals", "friendlies"):
        subset = [r for r in records if r["family"] == family]
        if not subset:
            continue
        picks = {
            0,
            len(subset) // 3,
            (2 * len(subset)) // 3,
            len(subset) - 1,
        }
        samples.extend(subset[i] for i in sorted(picks))
    return samples[: 3 * per_family + 3]


# ---------------------------------------------------------------------------
# metrics tables
# ---------------------------------------------------------------------------


def family_metrics(records: list[dict]) -> dict:
    """1X2 + O2.5 metrics with baselines for one record set."""
    if not records:
        return {"n": 0}
    model_ll, model_clips = multiclass_log_loss(records, "model_probs")
    base_ll, _ = multiclass_log_loss(records, "base_rate_probs")
    uniform_ll, _ = multiclass_log_loss(records, "uniform_probs")
    fixed_ll = None
    if records and all(r["family"] == "unl" for r in records):
        fixed_ll, _ = multiclass_log_loss(records, "fixed_nl_probs")
    model_brier = multiclass_brier(records, "model_probs")
    base_brier = multiclass_brier(records, "base_rate_probs")
    uniform_brier = multiclass_brier(records, "uniform_probs")
    over_probs = [r["p_over25"] for r in records]
    over_outcomes = [r["over25"] for r in records]
    over_ll, over_clips = binary_log_loss(over_probs, over_outcomes)
    baseline_probs = [r["baseline_over25"] for r in records]
    baseline_ll, _ = binary_log_loss(baseline_probs, over_outcomes)
    coin_ll, _ = binary_log_loss([0.5] * len(records), over_outcomes)
    return {
        "n": len(records),
        "date_range": [records[0]["date"], records[-1]["date"]],
        "home_draw_away_rates": [
            _mean([1.0 if r["outcome"] == k else 0.0 for r in records]) for k in range(3)
        ],
        "over25_rate": _mean(over_outcomes),
        "one_x_two": {
            "model": {"brier": model_brier, "log_loss": model_ll, "clipped": model_clips},
            "causal_base_rate": {
                "brier": base_brier, "log_loss": base_ll,
                "gain": ll_gain(model_ll, base_ll),
            },
            "uniform": {
                "brier": uniform_brier, "log_loss": uniform_ll,
                "gain": ll_gain(model_ll, uniform_ll),
            },
            **(
                {"fixed_nl_probe_rates": {
                    "log_loss": fixed_ll, "gain": ll_gain(model_ll, fixed_ll),
                }} if fixed_ll is not None else {}
            ),
        },
        "over25": {
            "model": {"log_loss": over_ll, "mean_prob": _mean(over_probs), "clipped": over_clips},
            "tournament_mean_total": {
                "log_loss": baseline_ll, "mean_prob": _mean(baseline_probs),
                "gain": ll_gain(over_ll, baseline_ll),
            },
            "coin": {"log_loss": coin_ll, "gain": ll_gain(over_ll, coin_ll)},
        },
    }


def competition_tables(records: list[dict]) -> list[dict]:
    """Per-competition metric tables: UNL by cycle, Euro/WC, friendlies."""
    groups: list[tuple[str, list[dict]]] = []
    unl = [r for r in records if r["family"] == "unl"]
    if unl:
        cycles = sorted({r["cycle"] for r in unl})
        for cycle in cycles:
            subset = [r for r in unl if r["cycle"] == cycle]
            metrics = family_metrics(subset)
            metrics["group"] = f"UNL {cycle}"
            groups.append((f"unl_{cycle}", metrics))
    for family, label in (("finals", "Euro/WC finals 2024-2026"),
                          ("friendlies", "Friendlies (NL teams) 2024-2026")):
        subset = [r for r in records if r["family"] == family]
        if subset:
            by_tour: dict[str, list[dict]] = {}
            for record in subset:
                by_tour.setdefault(record["tournament"], []).append(record)
            if family == "finals":
                for tournament in sorted(by_tour):
                    metrics = family_metrics(by_tour[tournament])
                    metrics["group"] = tournament
                    groups.append((f"finals_{tournament}", metrics))
            metrics = family_metrics(subset)
            metrics["group"] = label
            groups.append((family, metrics))
    return [dict(metrics, key=key) for key, metrics in groups]


def variant_and_slope_tables(unl_records: list[dict]) -> dict:
    """Per-variant + per-slope metrics, median-vs-variant verdict, spreads."""
    if not unl_records:
        return {"n": 0}
    median_ll, _ = multiclass_log_loss(unl_records, "model_probs")
    median_over_ll, _ = binary_log_loss(
        [r["p_over25"] for r in unl_records], [r["over25"] for r in unl_records]
    )
    variant_rows = []
    for index, spec in enumerate(intl_model.VARIANTS):
        stubs = [
            dict(
                r,
                model_probs=(
                    r["variants"][index]["p_home"],
                    r["variants"][index]["p_draw"],
                    r["variants"][index]["p_away"],
                ),
            )
            for r in unl_records
        ]
        ll, _ = multiclass_log_loss(stubs, "model_probs")
        brier = multiclass_brier(stubs, "model_probs")
        over_ll, _ = binary_log_loss(
            [r["variants"][index]["p_over25"] for r in unl_records],
            [r["over25"] for r in unl_records],
        )
        variant_rows.append({
            "variant": spec.name,
            "slope": spec.slope,
            "total_multiplier": spec.total_multiplier,
            "one_x_two_log_loss": ll,
            "one_x_two_brier": brier,
            "over25_log_loss": over_ll,
        })
    median_beats = {
        row["variant"]: {
            "one_x_two": median_ll < row["one_x_two_log_loss"],
            "over25": median_over_ll < row["over25_log_loss"],
        }
        for row in variant_rows
    }
    slope_rows = []
    for slope in intl_model.SWEEP_SLOPES:
        index = next(
            i for i, spec in enumerate(intl_model.VARIANTS)
            if spec.slope == slope and spec.total_multiplier == 1.0
        )
        row = next(r for r in variant_rows if r["variant"] == intl_model.VARIANTS[index].name)
        slope_rows.append({
            "slope": slope,
            "one_x_two_log_loss": row["one_x_two_log_loss"],
            "one_x_two_brier": row["one_x_two_brier"],
            "over25_log_loss": row["over25_log_loss"],
        })
    best_1x2 = min(slope_rows, key=lambda r: r["one_x_two_log_loss"])["slope"]
    best_over = min(slope_rows, key=lambda r: r["over25_log_loss"])["slope"]

    def spread_stats(key: str) -> dict:
        values = [r["variant_spreads"][key] for r in unl_records]
        ordered = sorted(values)
        return {
            "mean_cents": 100.0 * _mean(values),
            "median_cents": 100.0 * ordered[len(ordered) // 2],
            "p90_cents": 100.0 * ordered[min(len(ordered) - 1, int(math.ceil(0.9 * len(ordered))) - 1)],
            "max_cents": 100.0 * ordered[-1],
            "fraction_over_6c": sum(1 for v in values if v > VARIANT_SPREAD_BAR) / len(values),
        }

    return {
        "n": len(unl_records),
        "median": {"one_x_two_log_loss": median_ll, "over25_log_loss": median_over_ll},
        "variants": variant_rows,
        "median_beats_each_variant": median_beats,
        "median_beats_all_1x2": all(v["one_x_two"] for v in median_beats.values()),
        "median_beats_all_over25": all(v["over25"] for v in median_beats.values()),
        "slope_sweep": slope_rows,
        "slope_optimum_1x2": best_1x2,
        "slope_optimum_over25": best_over,
        "default_slope_is_optimum": (
            best_1x2 == intl_model.DEFAULT_SLOPE and best_over == intl_model.DEFAULT_SLOPE
        ),
        "spread_distribution": {k: spread_stats(k) for k in
                                ("p_home", "p_draw", "p_away", "p_over25")},
        "note": "slope sweep is REPORT-only; the nine-variant envelope already covers it",
    }


def calibration_bins(records: list[dict]) -> list[dict]:
    """O2.5 reliability bins (0.2-wide) over the record set."""
    bins = [
        {"lo": i / 5.0, "hi": (i + 1) / 5.0, "n": 0, "prob_sum": 0.0, "overs": 0}
        for i in range(5)
    ]
    for record in records:
        p = record["p_over25"]
        index = min(4, int(p * 5.0))
        bins[index]["n"] += 1
        bins[index]["prob_sum"] += p
        bins[index]["overs"] += record["over25"]
    out = []
    for bin_ in bins:
        entry = {"range": f"[{bin_['lo']:.1f},{bin_['hi']:.1f})", "n": bin_["n"]}
        if bin_["n"]:
            entry["predicted_mean"] = bin_["prob_sum"] / bin_["n"]
            entry["actual_over_rate"] = bin_["overs"] / bin_["n"]
        out.append(entry)
    return out


# ---------------------------------------------------------------------------
# gates
# ---------------------------------------------------------------------------


def gate_a_integrity(snapshot_path: Path, snapshot: dict, cache_dir: Path | None) -> dict:
    matches = snapshot["matches"]
    dates = [m["date"] for m in matches]
    nl = [m for m in matches if m["tournament"] == NL_TOURNAMENT]
    result = {
        "snapshot_path": str(snapshot_path),
        "reload_validation": "pass (load_intl_snapshot accepted)",
        "source": snapshot["source"],
        "generated_at": snapshot["generated_at"],
        "teams": len(snapshot["teams"]),
        "matches": len(matches),
        "elo_checkpoints": len(snapshot["elo_history"]),
        "date_range": [dates[0], dates[-1]],
        "nl_matches": len(nl),
        "nl_date_range": [nl[0]["date"], nl[-1]["date"]],
    }
    rebuild_equal = None
    if cache_dir is not None:
        results_csv = cache_dir / "results.csv"
        world_tsv = cache_dir / "world.tsv"
        if not results_csv.is_file() or not world_tsv.is_file():
            rebuild_equal = "raw cache incomplete (results.csv/world.tsv missing)"
        else:
            try:
                rebuilt = intl_data.build_snapshot(str(results_csv), str(world_tsv))
                rebuild_equal = (
                    rebuilt["matches"] == snapshot["matches"]
                    and {
                        name: block["elo"] for name, block in rebuilt["teams"].items()
                    } == {
                        name: block["elo"] for name, block in snapshot["teams"].items()
                    }
                )
            except Exception as exc:  # noqa: BLE001 - report, don't crash
                rebuild_equal = f"rebuild failed: {exc}"
    result["rebuild_from_cache_equal"] = rebuild_equal
    checks = [
        result["teams"] >= 300,
        result["matches"] >= 49000,
        result["nl_matches"] >= 700,
        rebuild_equal is True,
    ]
    result["passed"] = all(checks)
    return result


def gate_b_calibration(records: list[dict]) -> dict:
    unl = [r for r in records if r["family"] == "unl"]
    pooled = records
    pred_totals = [r["pred_total"] for r in pooled]
    actual_totals = [float(r["total"]) for r in pooled]
    mean_total_bias = _mean(pred_totals) - _mean(actual_totals)
    exp_gd = [r["exp_gd_default_slope"] for r in pooled]
    actual_margin = [float(r["home_goals"] - r["away_goals"]) for r in pooled]
    r_gd, p_gd = pearson(exp_gd, actual_margin)
    over_prob_bias = _mean([r["p_over25"] for r in unl]) - _mean([float(r["over25"]) for r in unl])
    per_family_bias = {}
    for family in ("unl", "finals", "friendlies"):
        subset = [r for r in records if r["family"] == family]
        if subset:
            per_family_bias[family] = {
                "mean_pred_total": _mean([r["pred_total"] for r in subset]),
                "mean_actual_total": _mean([float(r["total"]) for r in subset]),
                "bias": _mean([r["pred_total"] for r in subset])
                - _mean([float(r["total"]) for r in subset]),
                "mean_p_over25": _mean([r["p_over25"] for r in subset]),
                "actual_over25_rate": _mean([float(r["over25"]) for r in subset]),
            }
    passed = (
        len(unl) >= GATE_D_MIN_N
        and abs(mean_total_bias) <= GATE_B_MAX_TOTAL_BIAS
        and abs(over_prob_bias) <= GATE_B_MAX_PROB_BIAS
        and math.isfinite(r_gd)
        and r_gd >= GATE_B_MIN_GD_R
        and p_gd < 0.05
    )
    return {
        "n_unl": len(unl),
        "n_pooled": len(pooled),
        "mean_total_bias_goals": mean_total_bias,
        "o25_prob_bias": over_prob_bias,
        "pearson_exp_gd_vs_actual_margin": {"r": r_gd, "p": p_gd},
        "per_family": per_family_bias,
        "o25_reliability_bins_unl": calibration_bins(unl),
        "bar": (
            f"|mean-total bias| <= {GATE_B_MAX_TOTAL_BIAS} goals, "
            f"|O2.5 prob bias| <= {GATE_B_MAX_PROB_BIAS}, "
            f"Pearson r(E[gd], margin) >= {GATE_B_MIN_GD_R} with p < 0.05, n >= {GATE_D_MIN_N}"
        ),
        "passed": passed,
    }


def gate_c_sanity(snapshot: dict) -> dict:
    """Full-history Elo vs win% since 2018 (all competitions)."""
    since = "2018-01-01"
    table: dict[str, list[float]] = {}
    for match in snapshot["matches"]:
        if match["date"] < since:
            continue
        for team, goals_for, goals_against in (
            (match["home"], match["home_goals"], match["away_goals"]),
            (match["away"], match["away_goals"], match["home_goals"]),
        ):
            entry = table.setdefault(team, [0.0, 0.0, 0.0])  # games, points, gd
            entry[0] += 1.0
            entry[1] += 1.0 if goals_for > goals_against else (0.5 if goals_for == goals_against else 0.0)
            entry[2] += goals_for - goals_against
    rows = [
        {
            "team": team,
            "games": int(entry[0]),
            "score_rate": entry[1] / entry[0],  # win=1, draw=0.5, loss=0
            "elo": snapshot["teams"][team]["elo"],
        }
        for team, entry in table.items()
        if entry[0] >= GATE_C_MIN_MATCHES and team in snapshot["teams"]
    ]
    rho_win, p_win = spearman([r["elo"] for r in rows], [r["score_rate"] for r in rows])
    top10 = sorted(rows, key=lambda r: -r["elo"])[:10]
    passed = len(rows) >= 30 and math.isfinite(rho_win) and rho_win >= GATE_C_MIN_RHO
    return {
        "teams": len(rows),
        "min_matches": GATE_C_MIN_MATCHES,
        "spearman_elo_vs_win_pct": {"rho": rho_win, "p": p_win},
        "top10_by_elo": [(r["team"], round(r["elo"], 1)) for r in top10],
        "eloratings_crosscheck_note": (
            "self-Elo vs eloratings.net World.tsv Spearman rho=0.996 across 35 UEFA "
            "teams is retained probe evidence (round47/probe/elo_fit_out.txt); not "
            "recomputed here (World.tsv is code-keyed, no name map in the probe cache)"
        ),
        "bar": f"Spearman rho(Elo, win%) >= {GATE_C_MIN_RHO} over >= 30 teams "
               f"with >= {GATE_C_MIN_MATCHES} matches since 2018",
        "passed": passed,
        "table": rows,
    }


def gate_d_walk_forward(unl_metrics: dict, pooled_metrics: dict) -> dict:
    one_x_two = unl_metrics["one_x_two"]
    over25 = unl_metrics["over25"]
    beats = {
        "beats_causal_base_rate_ll": one_x_two["model"]["log_loss"] < one_x_two["causal_base_rate"]["log_loss"],
        "beats_uniform_ll": one_x_two["model"]["log_loss"] < one_x_two["uniform"]["log_loss"],
        "beats_tournament_total_ll": over25["model"]["log_loss"] < over25["tournament_mean_total"]["log_loss"],
        "beats_coin_ll": over25["model"]["log_loss"] < over25["coin"]["log_loss"],
    }
    n = unl_metrics["n"]
    over_gain = over25["tournament_mean_total"]["gain"]
    mw_gain = one_x_two["causal_base_rate"]["gain"]
    kill_bar_tripped = over_gain["cents_equivalent"] < 1.5
    if n < GATE_D_MIN_N:
        verdict = "INSUFFICIENT-DATA"
    else:
        verdict = "PASS" if all(beats.values()) else "FAIL"
    return {
        "n": n,
        "beats": beats,
        "entry_bar_1p5c": {
            "over25_gain_vs_tournament_total": over_gain,
            "one_x_two_gain_vs_causal_base_rate": mw_gain,
            "kill_bar_tripped_research_only": kill_bar_tripped,
            "note": (
                "feasibility kill bar: walk-forward log-loss gain < 1.5c vs baseline "
                "-> research-only; measured on the entry-relevant family (O/U 2.5) "
                "with the 1X2 number reported for research context"
            ),
        },
        "verdict": verdict,
        "pooled": pooled_metrics,
    }


def market_mad_rows(rows: list[dict]) -> dict:
    """MAD summary over model-vs-market comparison rows (None devs skipped)."""
    usable = [r for r in rows if r.get("abs_dev") is not None]
    if not usable:
        return {"n": 0, "skipped": len(rows)}
    devs = [r["abs_dev"] for r in usable]
    ordered = sorted(devs)
    return {
        "n": len(usable),
        "skipped": len(rows) - len(usable),
        "mad": _mean(devs),
        "median_ad": ordered[len(ordered) // 2],
        "max_ad": ordered[-1],
        "rows": rows,
    }


def gate_e_market(
    closing_rows: list[dict],
    pretip_rows: list[dict],
    totals_rows: list[dict],
    notes: dict,
) -> dict:
    closings = market_mad_rows(closing_rows)
    pretip = market_mad_rows(pretip_rows)
    totals = market_mad_rows(totals_rows)
    games = len({r["game"] for r in closing_rows if r.get("abs_dev") is not None})
    if closings["n"] == 0 or games < GATE_E_MIN_GAMES:
        verdict = "INSUFFICIENT-DATA"
    else:
        verdict = "PASS" if closings["mad"] <= GATE_E_MAX_MAD else "FAIL"
    return {
        "closing_1x2": closings,
        "closing_games": games,
        "pretip_nov12_2026": pretip,
        "totals_o25": totals,
        "totals_o25_status": (
            "unavailable-if-dust" if totals["n"] < GATE_E_MIN_GAMES else "measured"
        ),
        "notes": notes,
        "bar": f"closing MAD <= {GATE_E_MAX_MAD:.2f} (devigged 1X2) over >= {GATE_E_MIN_GAMES} games; "
               "MAD > 5c is the feasibility halt bar",
        "verdict": verdict,
    }


# ---------------------------------------------------------------------------
# Polymarket closing / pretip comparisons
# ---------------------------------------------------------------------------


def collect_nov2024_closings(
    predictions: dict[str, dict],
    known_teams: set[str],
    *,
    events: list[dict] | None = None,
    date_lo: str = "2024-11-14",
    date_hi: str = "2024-11-20",
) -> tuple[list[dict], list[dict], dict]:
    """Model-vs-PM-closing rows for the Nov-2024 NL window.

    Enumerates closed NL events from Gamma (paginated tag sweep), parses
    the three moneyline questions per event, pulls each outcome token's
    prices-history closing (last point at/before kickoff), devigs the
    triple, and compares against the walk-forward model quote (requested
    prediction at the event's UTC date). O/U 2.5 markets are searched in
    the same events; the R47 dust finding is expected to leave totals-MAD
    unavailable.
    """
    events = (
        events if events is not None
        else gamma_nl_events(closed=True, end_min="2024-11-01", end_max="2024-12-05")
    )
    fixtures = []
    for event in events:
        parsed = event_fixture(event)
        if parsed is None:
            continue
        if not (date_lo <= parsed["kickoff"].date().isoformat() <= date_hi):
            continue
        parsed["event"] = event
        fixtures.append(parsed)
    rows: list[dict] = []
    failures: list[dict] = []
    totals_rows: list[dict] = []
    for fixture in fixtures:
        home = pm_to_martj42(fixture["home_pm"], known_teams)
        away = pm_to_martj42(fixture["away_pm"], known_teams)
        game = f"{fixture['home_pm']} vs. {fixture['away_pm']}"
        if home is None or away is None:
            failures.append({"game": game, "reason": f"name mapping failed ({home}/{away})"})
            continue
        date = fixture["kickoff"].date().isoformat()
        key = f"{date}|{home}|{away}"
        quote = predictions.get(key)
        if quote is None or quote.get("refused"):
            failures.append({"game": game, "reason": f"no walk-forward prediction ({key})"})
            continue
        markets = {
            classify_ml_market(m.get("question") or "", fixture["home_pm"], fixture["away_pm"]): m
            for m in fixture["event"].get("markets") or []
        }
        tokens: dict[str, str] = {}
        for side in ("home", "draw", "away"):
            market = markets.get(side)
            if market is None:
                continue
            token_list = _load_json_list(market.get("clobTokenIds") or "[]")
            if token_list:
                tokens[side] = token_list[0]
        missing = [s for s in ("home", "draw", "away") if s not in tokens]
        if missing:
            failures.append({"game": game, "reason": f"missing ML markets {missing}"})
            continue
        kickoff_epoch = int(fixture["kickoff"].timestamp())
        prices: dict[str, float | None] = {}
        history_meta: dict[str, dict] = {}
        for side, token in tokens.items():
            result = closing_yes_price(token, kickoff_epoch)
            prices[side] = result["price"]
            history_meta[side] = result
            time.sleep(0.35)
        if any(prices[s] is None for s in tokens):
            failures.append({
                "game": game, "reason": "no pre-kickoff price history",
                "prices": prices,
            })
            continue
        raw = {s: prices[s] for s in ("home", "draw", "away")}  # type: ignore[union-attr]
        overround = sum(raw.values())
        devig = {s: raw[s] / overround for s in raw}
        model = {"home": quote["p_home"], "draw": quote["p_draw"], "away": quote["p_away"]}
        for side in ("home", "draw", "away"):
            rows.append({
                "date": date,
                "game": game,
                "side": side,
                "pm_raw": raw[side],
                "pm_devig": devig[side],
                "model": model[side],
                "abs_dev": abs(model[side] - devig[side]),
                "abs_dev_raw": abs(model[side] - raw[side]),
                "minutes_before_kickoff": history_meta[side].get("minutes_before"),
                "event_id": fixture["event_id"],
            })
        # O/U 2.5 in the same event family (expected dust per R47)
        ou_market = next(
            (
                m for m in fixture["event"].get("markets") or []
                if str(m.get("question") or "").rstrip().lower().endswith("o/u 2.5")
            ),
            None,
        )
        if ou_market is not None:
            token_list = _load_json_list(ou_market.get("clobTokenIds") or "[]")
            if token_list:
                result = closing_yes_price(token_list[0], kickoff_epoch)
                if result["price"] is not None:
                    totals_rows.append({
                        "date": date,
                        "game": game,
                        "pm_raw": result["price"],
                        "pm_devig": None,
                        "model": quote["p_over25"],
                        "abs_dev": abs(quote["p_over25"] - result["price"]),
                        "minutes_before_kickoff": result.get("minutes_before"),
                        "event_id": fixture["event_id"],
                    })
                time.sleep(0.35)
    overrounds = [
        sum(r["pm_raw"] for r in rows if r["game"] == game)
        for game in sorted({r["game"] for r in rows})
    ]
    meta = {
        "closed_events_fetched": len(events),
        "window_fixtures": len(fixtures),
        "games_with_closings": len(overrounds),
        "overround_mean": _mean(overrounds) if overrounds else None,
    }
    return rows, totals_rows, {"failures": failures, "meta": meta}


def collect_pretip_board(
    board_path: Path, predictions: dict[str, dict], known_teams: set[str]
) -> tuple[list[dict], list[dict], list[dict]]:
    """Model-vs-board pretip rows for the Nov-12-2026 NL slate."""
    with open(board_path, "r", encoding="utf-8") as handle:
        board = json.load(handle)
    rows: list[dict] = []
    totals_rows: list[dict] = []
    failures: list[dict] = []
    games = board.get("soccer", {}).get("nations_league_nov12", [])
    for game in games:
        fixture = str(game.get("fixture") or "")
        if " vs. " not in fixture:
            continue
        home_pm, _, away_pm = fixture.partition(" vs. ")
        home = pm_to_martj42(home_pm.strip(), known_teams)
        away = pm_to_martj42(away_pm.strip(), known_teams)
        kickoff = str(game.get("kickoff_utc") or "")
        date = kickoff[:10] or "2026-11-12"
        if home is None or away is None:
            failures.append({"game": fixture, "reason": "name mapping failed"})
            continue
        key = f"{date}|{home}|{away}"
        quote = predictions.get(key)
        if quote is None or quote.get("refused"):
            failures.append({"game": fixture, "reason": f"no prediction ({key})"})
            continue
        prices = game.get("ml_yes_prices") or {}
        raw = {
            "home": prices.get("home"),
            "draw": prices.get("draw"),
            "away": prices.get("away"),
        }
        if any(v is None for v in raw.values()):
            failures.append({"game": fixture, "reason": f"missing ML prices {raw}"})
            continue
        overround = sum(raw.values())
        model = {"home": quote["p_home"], "draw": quote["p_draw"], "away": quote["p_away"]}
        for side in ("home", "draw", "away"):
            rows.append({
                "date": date,
                "game": fixture,
                "side": side,
                "pm_raw": raw[side],
                "pm_devig": raw[side] / overround,
                "model": model[side],
                "abs_dev": abs(model[side] - raw[side] / overround),
                "abs_dev_raw": abs(model[side] - raw[side]),
                "board_generated_utc": board.get("generated_utc"),
            })
        ou25 = game.get("ou25_yes_price")
        if ou25 is not None:
            totals_rows.append({
                "date": date,
                "game": fixture,
                "pm_raw": ou25,
                "pm_devig": None,
                "model": quote["p_over25"],
                "abs_dev": abs(quote["p_over25"] - ou25),
                "board_generated_utc": board.get("generated_utc"),
            })
    return rows, totals_rows, failures


# ---------------------------------------------------------------------------
# report writing
# ---------------------------------------------------------------------------


def _fmt(value: object, digits: int = 4) -> str:
    if isinstance(value, float):
        if math.isnan(value):
            return "n/a"
        return f"{value:.{digits}f}"
    return str(value)


def _gate_line(letter: str, check: str, verdict: str, numbers: str) -> str:
    return f"| {letter} | {check} | **{verdict}** | {numbers} |"


def write_report(out_dir: Path, results: dict) -> Path:
    meta = results["meta"]
    gate_a = results["gate_a"]
    gate_b = results["gate_b"]
    gate_c = results["gate_c"]
    gate_d = results["gate_d"]
    gate_e = results["gate_e"]
    unl = results["unl_metrics"]
    slope = results["variant_slope"]
    lines: list[str] = []
    lines.append("# WP-INTL-3 international model validation - walk-forward + market gates")
    lines.append("")
    lines.append(f"- generated_at (UTC): {meta['generated_at']}")
    lines.append(f"- snapshot: `{meta['snapshot_path']}` (sha256 {meta['snapshot_sha256'][:16]}...)")
    lines.append(f"- corpus: {gate_a['teams']} teams, {gate_a['matches']} matches "
                 f"({gate_a['date_range'][0]}..{gate_a['date_range'][1]}), "
                 f"{gate_a['nl_matches']} NL matches")
    lines.append("- causality: incremental Elo replay strictly-before fixture DATE; per-tournament "
                 "mean totals and H/D/A base rates are the expanding strictly-prior counts "
                 "(the snapshot-level totals table is NOT used in the backtest)")
    lines.append(f"- self-check vs `intl_model.fixture_prediction` on truncated snapshots: "
                 f"{results['self_check']['samples']} samples, "
                 f"{results['self_check']['mismatches']} mismatches")
    lines.append("- paper-only / report-only: no entries, no DB writes; INTL_MW_RESEARCH_ONLY=True "
                 "is honored; promotion NOT decided here")
    lines.append("")

    lines.append("## Gate A - data integrity")
    lines.append("")
    lines.append(f"- reload through `load_intl_snapshot`: {gate_a['reload_validation']}")
    lines.append(f"- rebuild from raw cache byte-equal (matches + final Elo): {gate_a.get('rebuild_from_cache_equal')}")
    lines.append(f"- **{'PASS' if gate_a['passed'] else 'FAIL'}**")
    lines.append("")

    lines.append("## Walk-forward evaluation (gate D mirror)")
    lines.append("")
    one = unl["one_x_two"]
    over = unl["over25"]
    lines.append(f"- UNL 2018-2026: **n = {unl['n']}** (refusals {results['walk_forward_info']['refusals']}); "
                 f"H/D/A rates {unl['home_draw_away_rates'][0]:.3f}/{unl['home_draw_away_rates'][1]:.3f}/{unl['home_draw_away_rates'][2]:.3f}, "
                 f"O2.5 rate {unl['over25_rate']:.3f}")
    lines.append("")
    lines.append("| 1X2 | Brier | log-loss | model gain vs it |")
    lines.append("|---|---|---|---|")
    lines.append(f"| model (9-variant median) | {one['model']['brier']:.4f} | {one['model']['log_loss']:.4f} | - |")
    lines.append(f"| causal base rates | {one['causal_base_rate']['brier']:.4f} | {one['causal_base_rate']['log_loss']:.4f} | "
                 f"{one['causal_base_rate']['gain']['delta_nats']:+.4f} nats ({one['causal_base_rate']['gain']['cents_equivalent']:+.2f}c) |")
    lines.append(f"| uniform 1/3 | {one['uniform']['brier']:.4f} | {one['uniform']['log_loss']:.4f} | "
                 f"{one['uniform']['gain']['delta_nats']:+.4f} nats ({one['uniform']['gain']['cents_equivalent']:+.2f}c) |")
    if "fixed_nl_probe_rates" in one:
        fixed = one["fixed_nl_probe_rates"]
        lines.append(f"| fixed probe rates 0.42/0.25/0.32 | - | {fixed['log_loss']:.4f} | "
                     f"{fixed['gain']['delta_nats']:+.4f} nats ({fixed['gain']['cents_equivalent']:+.2f}c) |")
    lines.append("")
    lines.append("| O/U 2.5 | log-loss | mean prob | model gain vs it |")
    lines.append("|---|---|---|---|")
    lines.append(f"| model | {over['model']['log_loss']:.4f} | {over['model']['mean_prob']:.3f} | - |")
    lines.append(f"| tournament-mean-total Poisson | {over['tournament_mean_total']['log_loss']:.4f} | {over['tournament_mean_total']['mean_prob']:.3f} | "
                 f"{over['tournament_mean_total']['gain']['delta_nats']:+.4f} nats ({over['tournament_mean_total']['gain']['cents_equivalent']:+.2f}c) |")
    lines.append(f"| coin 0.5 | {over['coin']['log_loss']:.4f} | 0.500 | "
                 f"{over['coin']['gain']['delta_nats']:+.4f} nats ({over['coin']['gain']['cents_equivalent']:+.2f}c) |")
    lines.append("")

    lines.append("### Per-competition tables")
    lines.append("")
    lines.append("| group | n | 1X2 LL (model / base / uniform) | O2.5 LL (model / tot-base / coin) |")
    lines.append("|---|---|---|---|")
    for table in results["competition_tables"]:
        if table.get("n", 0) == 0:
            continue
        o = table["one_x_two"]
        v = table["over25"]
        lines.append(
            f"| {table['group']} | {table['n']} | "
            f"{o['model']['log_loss']:.4f} / {o['causal_base_rate']['log_loss']:.4f} / {o['uniform']['log_loss']:.4f} | "
            f"{v['model']['log_loss']:.4f} / {v['tournament_mean_total']['log_loss']:.4f} / {v['coin']['log_loss']:.4f} |"
        )
    lines.append("")

    lines.append("### Slope sensitivity (REPORT only)")
    lines.append("")
    lines.append("| slope | 1X2 LL | 1X2 Brier | O2.5 LL |")
    lines.append("|---|---|---|---|")
    for row in slope["slope_sweep"]:
        marker = " (default)" if row["slope"] == intl_model.DEFAULT_SLOPE else ""
        lines.append(f"| {row['slope']:.2f}{marker} | {row['one_x_two_log_loss']:.4f} | "
                     f"{row['one_x_two_brier']:.4f} | {row['over25_log_loss']:.4f} |")
    lines.append(f"- walk-forward optimum: 1X2 slope {slope['slope_optimum_1x2']:.2f}, "
                 f"O2.5 slope {slope['slope_optimum_over25']:.2f}; "
                 f"default 0.47 is the optimum on both: {slope['default_slope_is_optimum']}")
    lines.append("")

    lines.append("### Variant envelope (9 variants)")
    lines.append("")
    lines.append("| variant | 1X2 LL | O2.5 LL | median beats it (1X2 / O2.5) |")
    lines.append("|---|---|---|---|")
    for row in slope["variants"]:
        beats = slope["median_beats_each_variant"][row["variant"]]
        lines.append(f"| {row['variant']} | {row['one_x_two_log_loss']:.4f} | {row['over25_log_loss']:.4f} | "
                     f"{'yes' if beats['one_x_two'] else 'NO'} / {'yes' if beats['over25'] else 'NO'} |")
    lines.append(f"- median beats EVERY individual variant on 1X2: {slope['median_beats_all_1x2']}; "
                 f"on O2.5: {slope['median_beats_all_over25']}")
    for key in ("p_home", "p_draw", "p_away", "p_over25"):
        stats = slope["spread_distribution"][key]
        lines.append(f"- spread {key}: mean {stats['mean_cents']:.2f}c, median {stats['median_cents']:.2f}c, "
                     f"p90 {stats['p90_cents']:.2f}c, max {stats['max_cents']:.2f}c, "
                     f">6c fraction {stats['fraction_over_6c']:.3f}")
    lines.append("")

    lines.append("## Gate B - totals calibration")
    lines.append("")
    lines.append(f"- mean-total bias (pooled eval set): {gate_b['mean_total_bias_goals']:+.3f} goals")
    lines.append(f"- UNL O2.5 prob bias: {100 * gate_b['o25_prob_bias']:+.2f}c")
    lines.append(f"- Pearson r(E[gd] @0.47, actual margin): {gate_b['pearson_exp_gd_vs_actual_margin']['r']:.4f} "
                 f"(p = {gate_b['pearson_exp_gd_vs_actual_margin']['p']:.2e})")
    for family, entry in gate_b["per_family"].items():
        lines.append(f"- {family}: mean pred total {entry['mean_pred_total']:.3f} vs actual {entry['mean_actual_total']:.3f} "
                     f"(bias {entry['bias']:+.3f}); mean P(O2.5) {entry['mean_p_over25']:.3f} vs rate {entry['actual_over25_rate']:.3f}")
    lines.append(f"- bar: {gate_b['bar']}")
    lines.append(f"- **{'PASS' if gate_b['passed'] else 'FAIL'}**")
    lines.append("")
    lines.append("| UNL O2.5 bin | n | predicted mean | actual over rate |")
    lines.append("|---|---|---|---|")
    for bin_ in gate_b["o25_reliability_bins_unl"]:
        lines.append(f"| {bin_['range']} | {bin_['n']} | {_fmt(bin_.get('predicted_mean'))} | "
                     f"{_fmt(bin_.get('actual_over_rate'))} |")
    lines.append("")

    lines.append("## Gate C - Elo sanity")
    lines.append("")
    top = ", ".join(f"{t} {e}" for t, e in gate_c["top10_by_elo"][:5])
    lines.append(f"- Spearman rho(final Elo, win% since 2018) = {gate_c['spearman_elo_vs_win_pct']['rho']:.4f} "
                 f"(p = {gate_c['spearman_elo_vs_win_pct']['p']:.2e}) over {gate_c['teams']} teams")
    lines.append(f"- top-5 Elo: {top}")
    lines.append(f"- {gate_c['eloratings_crosscheck_note']}")
    lines.append(f"- bar: {gate_c['bar']}")
    lines.append(f"- **{'PASS' if gate_c['passed'] else 'FAIL'}**")
    lines.append("")

    lines.append("## Gate E - market MAD (PM closings + pretip)")
    lines.append("")
    closing = gate_e["closing_1x2"]
    if closing["n"]:
        per_side = {}
        for side in ("home", "draw", "away"):
            devs = [r["abs_dev"] for r in closing["rows"] if r["side"] == side]
            per_side[side] = _mean(devs) if devs else None
        lines.append(f"- Nov-2024 window closings (devigged 1X2): **MAD {closing['mad']:.4f} "
                     f"({100 * closing['mad']:.1f}c)** over {closing['n']} outcome comparisons "
                     f"({gate_e['closing_games']} games); median {closing['median_ad']:.4f}, max {closing['max_ad']:.4f}")
        lines.append(f"- per-side MAD: home {100 * per_side['home']:.1f}c, draw {100 * per_side['draw']:.1f}c, "
                     f"away {100 * per_side['away']:.1f}c (devigged)")
        raw_devs = [r["abs_dev_raw"] for r in closing["rows"] if r.get("abs_dev_raw") is not None]
        overround = results["gate_e"]["notes"].get("mean_overround")
        lines.append(
            f"- raw (undevigged) MAD {100 * _mean(raw_devs):.1f}c; mean overround "
            f"{overround:.3f}" if overround is not None else
            f"- raw (undevigged) MAD {100 * _mean(raw_devs):.1f}c"
        )
    else:
        lines.append("- Nov-2024 closings: none retrieved")
    failures = results["gate_e"]["notes"].get("failures") or []
    if failures:
        lines.append(f"- failures: {failures[:6]}")
    pretip = gate_e["pretip_nov12_2026"]
    if pretip["n"]:
        lines.append(f"- Nov-12-2026 pretip (board.json Gamma prices, devigged): MAD {pretip['mad']:.4f} "
                     f"({100 * pretip['mad']:.1f}c) over {pretip['n']} comparisons "
                     f"({pretip['n'] // 3} games)")
    totals = gate_e["totals_o25"]
    if totals["n"]:
        lines.append(f"- O/U 2.5: n = {totals['n']} comparisons, MAD {totals['mad']:.4f} "
                     f"({100 * totals['mad']:.1f}c) - status: {gate_e['totals_o25_status']}")
    else:
        lines.append(f"- O/U 2.5 totals-MAD: **{gate_e['totals_o25_status']}** "
                     "(R47 finding: UNL O/U CLOB books are dust; 2024 events carry no O/U ladder)")
    lines.append(f"- bar: {gate_e['bar']}")
    lines.append(f"- **{gate_e['verdict']}**")
    lines.append("")

    lines.append("## Gate table")
    lines.append("")
    lines.append("| gate | check | verdict | key numbers |")
    lines.append("|---|---|---|---|")
    gates = results["gates_detail"]
    for letter in ("A", "B", "C", "D", "E"):
        gate = gates[letter]
        lines.append(
            _gate_line(letter, gate["check"], results["gates"][letter], gate["numbers"])
        )
    lines.append("")

    lines.append("## Verdict notes (report only - promotion not decided here)")
    lines.append("")
    for note in results["verdict_notes"]:
        lines.append(f"- {note}")
    lines.append("")

    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "report.md"
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


# ---------------------------------------------------------------------------
# shadow recorder (NBA-shadow-compatible CSV rows)
# ---------------------------------------------------------------------------

#: CSV columns mirror the NBA shadow JSON field paths (round47/nba_shadow_rows.json).
SHADOW_COLUMNS = [
    "label", "recorded_utc", "tip_utc", "game", "home", "away", "home_disp", "away_disp",
    "date", "state_at_scan", "neutral", "tournament", "snapshot", "both_teams_rated",
    "model.p_home", "model.p_draw", "model.p_away",
    "model.p_home_variant_spread_cents", "model.p_draw_variant_spread_cents",
    "model.p_away_variant_spread_cents", "model.p_over_2p5",
    "model.p_over_2p5_variant_spread_cents", "model.btts",
    "model.lambda_home", "model.lambda_away", "model.total_base",
    "model.elo_home", "model.elo_away", "model.games_home", "model.games_away",
    "model.rating_source", "model.variant_p_home",
    "market_ml.prices.home", "market_ml.prices.draw", "market_ml.prices.away",
    "market_ml.bid.home", "market_ml.ask.home", "market_ml.bid.draw", "market_ml.ask.draw",
    "market_ml.bid.away", "market_ml.ask.away",
    "market_ml.volume.home", "market_ml.volume.draw", "market_ml.volume.away",
    "market_ml.tokens.home", "market_ml.tokens.draw", "market_ml.tokens.away",
    "market_ou25.yes", "market_ou25.bid", "market_ou25.ask", "market_ou25.volume",
    "market_ou25.token",
    "model_vs_market.cents.home", "model_vs_market.cents.draw",
    "model_vs_market.cents.away", "model_vs_market.cents.over_2p5",
    "model_vs_market.devig_cents.home", "model_vs_market.devig_cents.draw",
    "model_vs_market.devig_cents.away",
    "liquidity_sum", "vol24_sum", "gamma_event_ids",
    "final_score.home_goals", "final_score.away_goals", "final_score.outcome",
    "final_score.brier_1x2", "final_score.log_loss_1x2", "final_score.o25_outcome",
]


def _first_number(value: object) -> float | None:
    try:
        parsed = json.loads(value or "[]") if isinstance(value, str) else value
        if isinstance(parsed, list) and parsed:
            return float(parsed[0])
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return None


def record_shadow_rows(
    snapshot: dict,
    snapshot_path: str,
    csv_path: Path,
    *,
    date_lo: str,
    date_hi: str,
    dry_run: bool = False,
) -> dict:
    """Discover NL fixtures on PM for the date window; append pretip rows.

    Idempotent per (tip_utc, game): rows already present in the CSV are
    skipped, so the coordinator can rerun a matchday safely. Prices come
    from fresh Gamma event details (outcomePrices + bestBid/bestAsk at
    scan time); the model quote comes from
    ``intl_model.fixture_prediction`` on the full snapshot (the deployed
    shadow path: ratings replay strictly before the fixture date).
    """
    import csv as _csv

    known_teams = set(snapshot["teams"])
    events = gamma_nl_events(closed=False)
    families: dict[tuple[str, str], list[dict]] = {}
    for event in events:
        parsed = event_fixture(event)
        if parsed is None:
            continue
        if not (date_lo <= parsed["kickoff"].date().isoformat() <= date_hi):
            continue
        parsed["event"] = event  # raw payload for embedded-market fallback
        parsed["title_raw"] = str(event.get("title") or "")
        families.setdefault((parsed["kickoff"].isoformat(), parsed["root"]), []).append(parsed)
    existing: set[tuple[str, str]] = set()
    if csv_path.is_file():
        with open(csv_path, "r", encoding="utf-8", newline="") as handle:
            for row in _csv.DictReader(handle):
                existing.add((row.get("tip_utc", ""), row.get("game", "")))
    rows: list[dict] = []
    skipped: list[dict] = []
    failures: list[dict] = []
    for (kickoff_iso, root), members in sorted(families.items()):
        game = root
        if (kickoff_iso, game) in existing:
            skipped.append({"game": game, "kickoff": kickoff_iso, "reason": "already recorded"})
            continue
        home_pm, _, away_pm = root.partition(" vs. ")
        home = pm_to_martj42(home_pm, known_teams)
        away = pm_to_martj42(away_pm, known_teams)
        kickoff = datetime.fromisoformat(kickoff_iso)
        date = kickoff.date().isoformat()
        base = {
            "label": "INTL-SHADOW-MONITORING-ONLY - NO ENTRY (out-of-sample evidence, gate-E live bar)",
            "recorded_utc": datetime.now(timezone.utc).isoformat(),
            "tip_utc": kickoff_iso,
            "game": game,
            "home_disp": home_pm.strip(),
            "away_disp": away_pm.strip(),
            "date": date,
            "state_at_scan": "pre",
            "neutral": "False",
            "tournament": NL_TOURNAMENT,
            "snapshot": f"{snapshot_path} (generated {snapshot['generated_at']})",
            "gamma_event_ids": json.dumps([m["event_id"] for m in members]),
        }
        if home is None or away is None:
            base.update({"home": home_pm, "away": away_pm, "both_teams_rated": "False"})
            failures.append({"game": game, "reason": "name mapping failed"})
            rows.append(base)
            continue
        base.update({"home": home, "away": away})
        prediction = intl_model.fixture_prediction(
            snapshot,
            intl_model.IntlFixture(home=home, away=away, date=date, neutral=False),
            tournament=NL_TOURNAMENT,
        )
        if prediction is None:
            base["both_teams_rated"] = "False"
            failures.append({"game": game, "reason": "model refusal"})
            rows.append(base)
            continue
        base["both_teams_rated"] = "True"
        base.update({
            "model.p_home": round(prediction.p_home, 5),
            "model.p_draw": round(prediction.p_draw, 5),
            "model.p_away": round(prediction.p_away, 5),
            "model.p_home_variant_spread_cents": round(100 * prediction.p_home_variant_spread, 2),
            "model.p_draw_variant_spread_cents": round(100 * prediction.p_draw_variant_spread, 2),
            "model.p_away_variant_spread_cents": round(100 * prediction.p_away_variant_spread, 2),
            "model.p_over_2p5": round(prediction.over_line_prob(2.5).p_over, 5),
            "model.p_over_2p5_variant_spread_cents": round(
                100 * prediction.over_line_prob(2.5).variant_spread, 2
            ),
            "model.btts": round(prediction.btts, 5),
            "model.lambda_home": round(prediction.lambda_home, 4),
            "model.lambda_away": round(prediction.lambda_away, 4),
            "model.total_base": round(prediction.total_base, 4),
            "model.elo_home": round(prediction.elo_home, 2),
            "model.elo_away": round(prediction.elo_away, 2),
            "model.games_home": prediction.games_home,
            "model.games_away": prediction.games_away,
            "model.rating_source": prediction.rating_source,
            "model.variant_p_home": json.dumps({
                v.spec.name: round(v.outputs.home_win, 5) for v in prediction.variants
            }),
        })
        # flagship event = the family member whose title IS the fixture root
        # (sub-market events like "- More Markets" carry higher ids and no ML)
        flagship = next(
            (m for m in members if m["title_raw"] == root), members[0]
        )
        detail = None
        try:
            detail = fetch_event_detail(flagship["event_id"])
        except Exception:  # noqa: BLE001 - fall back to sweep-embedded markets
            detail = None
        markets = (detail or {}).get("markets") or []
        if not any(
            classify_ml_market(m.get("question") or "", home_pm, away_pm)
            for m in markets
        ):
            markets = (flagship.get("event") or {}).get("markets") or []
        liquidity_sum = 0.0
        vol24_sum = 0.0
        for market in markets:
            try:
                liquidity_sum += float(market.get("liquidityNum") or 0.0)
                vol24_sum += float(market.get("volume24hr") or 0.0)
            except (TypeError, ValueError):
                pass
        base["liquidity_sum"] = round(liquidity_sum, 2)
        base["vol24_sum"] = round(vol24_sum, 2)
        for side, pm_name in (("home", home_pm), ("away", away_pm), ("draw", None)):
            market = None
            for candidate in markets:
                if classify_ml_market(
                    candidate.get("question") or "", home_pm, away_pm
                ) == side:
                    market = candidate
                    break
            if market is None:
                failures.append({"game": game, "reason": f"no ML market for {side}"})
                continue
            token_list = _load_json_list(market.get("clobTokenIds") or "[]")
            base[f"market_ml.prices.{side}"] = _first_number(market.get("outcomePrices"))
            base[f"market_ml.bid.{side}"] = market.get("bestBid")
            base[f"market_ml.ask.{side}"] = market.get("bestAsk")
            base[f"market_ml.volume.{side}"] = market.get("volume")
            if token_list:
                base[f"market_ml.tokens.{side}"] = token_list[0]
        ou_market = next(
            (
                m for m in markets
                if str(m.get("question") or "").rstrip().lower().endswith("o/u 2.5")
            ),
            None,
        )
        if ou_market is None:
            # the O/U ladder lives in sibling family events (boards47 pattern)
            for member in members:
                for candidate in (member.get("event") or {}).get("markets") or []:
                    if str(candidate.get("question") or "").rstrip().lower().endswith("o/u 2.5"):
                        ou_market = candidate
                        break
                if ou_market is not None:
                    break
        if ou_market is not None:
            token_list = _load_json_list(ou_market.get("clobTokenIds") or "[]")
            base["market_ou25.yes"] = _first_number(ou_market.get("outcomePrices"))
            base["market_ou25.bid"] = ou_market.get("bestBid")
            base["market_ou25.ask"] = ou_market.get("bestAsk")
            base["market_ou25.volume"] = ou_market.get("volume")
            if token_list:
                base["market_ou25.token"] = token_list[0]
        model = {
            "home": prediction.p_home,
            "draw": prediction.p_draw,
            "away": prediction.p_away,
        }
        for side in ("home", "draw", "away"):
            price = base.get(f"market_ml.prices.{side}")
            if price is not None:
                base[f"model_vs_market.cents.{side}"] = round(100 * (model[side] - price), 2)
        raw = [base.get(f"market_ml.prices.{s}") for s in ("home", "draw", "away")]
        if all(v is not None for v in raw):
            total = sum(raw)
            for side in ("home", "draw", "away"):
                base[f"model_vs_market.devig_cents.{side}"] = round(
                    100 * (model[side] - float(base[f"market_ml.prices.{side}"]) / total), 2
                )
        if base.get("market_ou25.yes") is not None:
            base["model_vs_market.cents.over_2p5"] = round(
                100 * (float(base["model.p_over_2p5"]) - float(base["market_ou25.yes"])), 2
            )
        rows.append(base)
    written = 0
    if not dry_run and rows:
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        new_file = not csv_path.is_file()
        with open(csv_path, "a", encoding="utf-8", newline="") as handle:
            writer = _csv.DictWriter(handle, fieldnames=SHADOW_COLUMNS, extrasaction="ignore")
            if new_file:
                writer.writeheader()
            for row in rows:
                writer.writerow(row)
                written += 1
    return {
        "window": [date_lo, date_hi],
        "fixtures_found": len(families),
        "rows_recorded": written if not dry_run else 0,
        "rows_prepared": len(rows),
        "skipped_existing": skipped,
        "failures": failures,
        "dry_run": dry_run,
        "csv": str(csv_path),
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _build_requested(
    known_teams: set[str],
    board_path: Path | None,
    closed_events: list[dict] | None = None,
) -> dict[str, list[dict]]:
    """Prediction requests for Nov-2024 PM fixtures + the Nov-12-2026 board.

    Nov-2024 NL games are eval-set matches whose walk-forward records
    already exist; the requests here are a fallback for any PM fixture
    that fails to map to a corpus row (kept so gate E reports an explicit
    failure instead of silently missing a game).
    """
    requested: dict[str, list[dict]] = {}

    def add(date: str, home: str, away: str) -> None:
        requested.setdefault(date, []).append(
            {"home": home, "away": away, "tournament": NL_TOURNAMENT, "neutral": False}
        )

    if closed_events is not None:
        for event in closed_events:
            parsed = event_fixture(event)
            if parsed is None:
                continue
            date = parsed["kickoff"].date().isoformat()
            if not ("2024-11-01" <= date <= "2024-11-30"):
                continue
            home = pm_to_martj42(parsed["home_pm"], known_teams)
            away = pm_to_martj42(parsed["away_pm"], known_teams)
            if home is None or away is None:
                continue
            add(date, home, away)
    # NOTE: callers pass a WINDOWED closed-event list (Nov-2024); an
    # unfiltered closed sweep would miss it (see gamma_nl_events).
    if board_path is not None and board_path.is_file():
        with open(board_path, "r", encoding="utf-8") as handle:
            board = json.load(handle)
        for game in board.get("soccer", {}).get("nations_league_nov12", []):
            fixture = str(game.get("fixture") or "")
            if " vs. " not in fixture:
                continue
            home_pm, _, away_pm = fixture.partition(" vs. ")
            home = pm_to_martj42(home_pm.strip(), known_teams)
            away = pm_to_martj42(away_pm.strip(), known_teams)
            date = str(game.get("kickoff_utc") or "")[:10] or "2026-11-12"
            if home is not None and away is not None:
                add(date, home, away)
    return requested


def _nl_team_set(snapshot: dict) -> set[str]:
    return {
        match["home"]
        for match in snapshot["matches"]
        if match["tournament"] == NL_TOURNAMENT
    } | {
        match["away"]
        for match in snapshot["matches"]
        if match["tournament"] == NL_TOURNAMENT
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="WP-INTL-3 international model validation harness (report-only, paper-only)"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="full gate A-E validation run")
    validate_parser.add_argument("--snapshot", required=True, help="intl snapshot JSON path")
    validate_parser.add_argument("--cache-dir", default=None, help="raw cache dir (results.csv + world.tsv) for the gate-A rebuild")
    validate_parser.add_argument("--board", default=None, help="round47 board.json (Nov-12 pretip prices)")
    validate_parser.add_argument("--out-dir", required=True, help="review output dir (report.md, results.json)")
    validate_parser.add_argument("--skip-pm", action="store_true", help="skip the networked Polymarket part (gate E -> INSUFFICIENT)")
    validate_parser.add_argument("--self-check-samples", type=int, default=12)
    validate_parser.add_argument("--revision", default="uncommitted WP-INTL-2 modules (intl_data + intl_model)")

    shadow_parser = subparsers.add_parser("shadow", help="record pretip model-vs-market rows for an NL matchday")
    shadow_parser.add_argument("--snapshot", required=True, help="intl snapshot JSON path")
    shadow_parser.add_argument("--date-lo", required=True, help="first matchday date YYYY-MM-DD")
    shadow_parser.add_argument("--date-hi", default=None, help="last matchday date (default: --date-lo)")
    shadow_parser.add_argument("--csv", required=True, help="shadow CSV path (append; idempotent per fixture)")
    shadow_parser.add_argument("--dry-run", action="store_true", help="prepare rows but do not write")

    args = parser.parse_args(argv)

    if args.command == "shadow":
        snapshot = intl_data.load_intl_snapshot(args.snapshot)
        summary = record_shadow_rows(
            snapshot,
            args.snapshot,
            Path(args.csv),
            date_lo=args.date_lo,
            date_hi=args.date_hi or args.date_lo,
            dry_run=args.dry_run,
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    snapshot_path = Path(args.snapshot)
    snapshot = intl_data.load_intl_snapshot(str(snapshot_path))
    known_teams = set(snapshot["teams"])
    nl_teams = _nl_team_set(snapshot)

    # -- gate A
    cache_dir = Path(args.cache_dir) if args.cache_dir else None
    gate_a = gate_a_integrity(snapshot_path, snapshot, cache_dir)

    # -- walk-forward (the compute)
    closed_events: list[dict] = []
    requested: dict[str, list[dict]] = {}
    if not args.skip_pm:
        try:
            closed_events = gamma_nl_events(
                closed=True, end_min="2024-11-01", end_max="2024-12-05"
            )
            requested = _build_requested(
                known_teams, Path(args.board) if args.board else None, closed_events
            )
        except Exception as exc:  # noqa: BLE001 - PM enumeration is best-effort
            print(f"WARN: PM request enumeration failed ({exc}); gate E will be INSUFFICIENT")
    records, requested_predictions, info = run_walk_forward(
        snapshot["matches"], nl_teams, requested=requested
    )
    if not records:
        raise SystemExit("no walk-forward records produced; snapshot/eval-set mismatch")
    # merged quote index: eval-set records first (true neutral flag from the
    # corpus row), requested predictions as fallback for unmapped PM fixtures
    predictions: dict[str, dict] = dict(requested_predictions)
    for record in records:
        predictions.setdefault(f"{record['date']}|{record['home']}|{record['away']}", record)
    unl_records = [r for r in records if r["family"] == "unl"]
    unl_metrics = family_metrics(unl_records)
    pooled_metrics = family_metrics(records)
    tables = competition_tables(records)
    slope = variant_and_slope_tables(unl_records)

    # -- self-check (fast path vs frozen model code)
    samples = pick_self_check_samples(records)
    check = self_check(snapshot, records, samples[: args.self_check_samples])

    # -- gates B/C/D
    gate_b = gate_b_calibration(records)
    gate_c = gate_c_sanity(snapshot)
    gate_d = gate_d_walk_forward(unl_metrics, pooled_metrics)

    # -- gate E (network)
    closing_rows: list[dict] = []
    pretip_rows: list[dict] = []
    totals_rows: list[dict] = []
    gate_e_notes: dict = {}
    if not args.skip_pm:
        try:
            closing_rows, nov_totals, gate_e_notes = collect_nov2024_closings(
                predictions, known_teams, events=closed_events
            )
            totals_rows.extend(nov_totals)
            if args.board and Path(args.board).is_file():
                board_pretip, board_totals, board_failures = collect_pretip_board(
                    Path(args.board), predictions, known_teams
                )
                pretip_rows.extend(board_pretip)
                totals_rows.extend(board_totals)
                gate_e_notes.setdefault("failures", []).extend(board_failures)
        except Exception as exc:  # noqa: BLE001 - report, don't crash the backtest
            gate_e_notes = {"error": f"PM collection failed: {exc}"}
            closing_rows, pretip_rows, totals_rows = [], [], []
    overround_mean = (gate_e_notes.get("meta") or {}).get("overround_mean")
    if overround_mean is not None:
        gate_e_notes["mean_overround"] = overround_mean
    gate_e = gate_e_market(closing_rows, pretip_rows, totals_rows, gate_e_notes)

    # -- verdicts
    gates = {
        "A": "PASS" if gate_a["passed"] else "FAIL",
        "B": "PASS" if gate_b["passed"] else (
            "INSUFFICIENT-DATA" if gate_b["n_unl"] < GATE_D_MIN_N else "FAIL"
        ),
        "C": "PASS" if gate_c["passed"] else "FAIL",
        "D": gate_d["verdict"],
        "E": gate_e["verdict"],
    }
    gates_detail = {
        "A": {
            "check": "data integrity (adapter-enforced reload + raw-cache rebuild)",
            "numbers": f"{gate_a['teams']} teams, {gate_a['matches']} matches, "
                       f"{gate_a['nl_matches']} NL, rebuild-equal {gate_a.get('rebuild_from_cache_equal')}",
        },
        "B": {
            "check": "totals calibration (mean-total bias, O2.5 prob calibration, E[gd] fit)",
            "numbers": f"bias {gate_b['mean_total_bias_goals']:+.3f}g, "
                       f"O2.5 bias {100 * gate_b['o25_prob_bias']:+.2f}c, "
                       f"r(E[gd],margin) {gate_b['pearson_exp_gd_vs_actual_margin']['r']:.3f} "
                       f"(p {gate_b['pearson_exp_gd_vs_actual_margin']['p']:.1e})",
        },
        "C": {
            "check": "Elo sanity (vs win% since 2018; eloratings rho=0.996 is probe evidence)",
            "numbers": f"rho {gate_c['spearman_elo_vs_win_pct']['rho']:.4f} over {gate_c['teams']} teams",
        },
        "D": {
            "check": "walk-forward beats causal base rates (1X2) and tournament-total/coin (O2.5)",
            "numbers": (
                f"n={unl_metrics['n']}: 1X2 LL {unl_metrics['one_x_two']['model']['log_loss']:.4f} vs "
                f"base {unl_metrics['one_x_two']['causal_base_rate']['log_loss']:.4f}/uniform "
                f"{unl_metrics['one_x_two']['uniform']['log_loss']:.4f}; O2.5 LL "
                f"{unl_metrics['over25']['model']['log_loss']:.4f} vs tot-base "
                f"{unl_metrics['over25']['tournament_mean_total']['log_loss']:.4f}/coin "
                f"{unl_metrics['over25']['coin']['log_loss']:.4f}"
            ),
        },
        "E": {
            "check": f"market MAD <= {GATE_E_MAX_MAD:.2f} (Nov-2024 PM closings, devigged 1X2); pretip reported",
            "numbers": (
                (
                    f"closing MAD {100 * gate_e['closing_1x2']['mad']:.1f}c over "
                    f"{gate_e['closing_games']} games ({gate_e['closing_1x2']['n']} comparisons)"
                    if gate_e["closing_1x2"]["n"]
                    else "closing: not collected"
                )
                + "; "
                + (
                    f"pretip {100 * gate_e['pretip_nov12_2026']['mad']:.1f}c over "
                    f"{gate_e['pretip_nov12_2026']['n'] // 3} games"
                    if gate_e["pretip_nov12_2026"]["n"]
                    else "pretip: not collected"
                )
                + f"; O2.5 {gate_e['totals_o25_status']}"
            ),
        },
    }

    kill_tripped = gate_d["entry_bar_1p5c"]["kill_bar_tripped_research_only"]
    # Shadow cohort = record-only out-of-sample evidence: it proceeds on
    # model quality (A+D) and a non-failing market gate, independent of the
    # ENTRY kill bar, which governs eligibility (March 2027 at the earliest).
    shadow_confirmed = (
        gates["A"] == "PASS" and gates["D"] == "PASS" and gates["E"] != "FAIL"
    )
    verdict_notes = [
        f"Walk-forward n = {unl_metrics['n']} NL matches (2018-2026, all cycles pooled; per-cycle tables above); "
        f"friendlies/finals tables are context, not entry evidence.",
        f"Improvement bars (feasibility §5.1/§7): 1X2 vs causal base rates = "
        f"{gate_d['entry_bar_1p5c']['one_x_two_gain_vs_causal_base_rate']['cents_equivalent']:+.2f}c "
        f"({gate_d['entry_bar_1p5c']['one_x_two_gain_vs_causal_base_rate']['delta_nats']:+.4f} nats) - CLEARS the "
        f"1.5c bar; O2.5 vs tournament-mean-total baseline = "
        f"{gate_d['entry_bar_1p5c']['over25_gain_vs_tournament_total']['cents_equivalent']:+.2f}c "
        f"({gate_d['entry_bar_1p5c']['over25_gain_vs_tournament_total']['delta_nats']:+.4f} nats) - does NOT clear "
        f"it. The entry-eligible totals family therefore stays research-only; the strong 1X2 edge is "
        "policy-banned (INTL_MW_RESEARCH_ONLY).",
        f"Variant-consensus caveat: the O2.5 nine-variant spread exceeds the 6c entry-consensus bar on "
        f"{slope['spread_distribution']['p_over25']['fraction_over_6c']:.1%} of UNL matches (mean "
        f"{slope['spread_distribution']['p_over25']['mean_cents']:.1f}c) - the +/-5% total-multiplier "
        "dimension dominates; a totals entry would rarely reach consensus even if the LL bar were met.",
        f"Slope finding: walk-forward optima are {slope['slope_optimum_1x2']:.2f} (1X2) and "
        f"{slope['slope_optimum_over25']:.2f} (O2.5); default 0.47 is NOT the optimum on either "
        f"(differences are small and inside the envelope) - REPORT only, no default change recommended.",
        f"Variant median beats every individual variant: 1X2 {slope['median_beats_all_1x2']}, "
        f"O2.5 {slope['median_beats_all_over25']} (it is robust - within a few tenths of a cent of the "
        "best variant - but does not dominate).",
        f"Shadow status for the Nov 14-17 NL games: cohort {'CONFIRMED' if shadow_confirmed else 'NOT confirmed'} "
        f"(requires A PASS, D PASS, E not FAIL - recording evidence only, never entry). Entry stays deferred: "
        "earliest March 2027 per the feasibility calendar, and now conditional on the totals family clearing "
        "the 1.5c bar somewhere it currently does not; international 1X2 remains research-only.",
        "Promotion is NOT decided by this harness: these are the coordinator's gate inputs; "
        "an independent review (Project Iron Rule 4) precedes any shadow->entry transition.",
    ]

    results = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "harness": "tools/wp_intl_validate.py (WP-INTL-3)",
            "revision": args.revision,
            "snapshot_path": str(snapshot_path),
            "snapshot_sha256": _sha256(snapshot_path),
            "paper_only": True,
            "intl_mw_research_only": intl_model.INTL_MW_RESEARCH_ONLY,
            "params": {
                "skip_pm": args.skip_pm,
                "board": args.board,
                "cache_dir": args.cache_dir,
            },
        },
        "gate_a": gate_a,
        "walk_forward_info": info,
        "self_check": check,
        "unl_metrics": unl_metrics,
        "pooled_metrics": pooled_metrics,
        "competition_tables": tables,
        "variant_slope": slope,
        "gate_b": gate_b,
        "gate_c": {k: v for k, v in gate_c.items() if k != "table"},
        "gate_c_table": gate_c["table"],
        "gate_d": gate_d,
        "gate_e": gate_e,
        "gates": gates,
        "gates_detail": gates_detail,
        "verdict_notes": verdict_notes,
        "walk_forward_records": [
            {
                key: record[key]
                for key in (
                    "date", "family", "cycle", "tournament", "home", "away", "neutral",
                    "home_goals", "away_goals", "outcome", "total", "over25",
                    "elo_home", "elo_away", "games_home", "games_away",
                    "total_base", "tournament_matches", "p_home", "p_draw", "p_away",
                    "p_over25", "pred_total", "baseline_over25", "exp_gd_default_slope",
                )
            }
            for record in records
        ],
    }
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_target = out_dir / "results.json"
    with open(json_target, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, sort_keys=True, allow_nan=False)
    report_target = write_report(out_dir, results)

    print(f"WP-INTL-3 validation written: {report_target}")
    print(f"results: {json_target}")
    print(f"gates: {gates}")
    print(
        f"UNL walk-forward n={unl_metrics['n']}: 1X2 LL "
        f"{unl_metrics['one_x_two']['model']['log_loss']:.4f} "
        f"(base {unl_metrics['one_x_two']['causal_base_rate']['log_loss']:.4f}, "
        f"uniform {unl_metrics['one_x_two']['uniform']['log_loss']:.4f}); O2.5 LL "
        f"{unl_metrics['over25']['model']['log_loss']:.4f} "
        f"(tot-base {unl_metrics['over25']['tournament_mean_total']['log_loss']:.4f}, "
        f"coin {unl_metrics['over25']['coin']['log_loss']:.4f})"
    )
    if gate_e["closing_1x2"]["n"]:
        print(f"Nov-2024 closing MAD {100 * gate_e['closing_1x2']['mad']:.1f}c over "
              f"{gate_e['closing_games']} games")
    if gate_e["pretip_nov12_2026"]["n"]:
        print(f"Nov-12 pretip MAD {100 * gate_e['pretip_nov12_2026']['mad']:.1f}c over "
              f"{gate_e['pretip_nov12_2026']['n'] // 3} games")
    print(f"self-check: {check['samples']} samples, {check['mismatches']} mismatches")
    print(f"shadow cohort (Nov 14-17): {'CONFIRMED' if shadow_confirmed else 'NOT confirmed'}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI guard
    raise SystemExit(main())
