"""Read-only scan-archive MAD diagnostics for WP-P4; never a Gate E approval.

The historical boards retain best bid/ask, not per-book acquisition timestamps.
``generated_utc`` is an explicit scan-report proxy: some scanners stamp it at
startup and others at completion. We do not rename Gamma prices to last trades,
reuse archived model predictions, normalize prices for the primary MAD, or infer
team aliases. This module reads existing research archives and returns values;
it does not fetch, persist, trade, or change the production scanner.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Callable, Mapping

UTC = timezone.utc
OUTCOMES = ("home", "draw", "away")
LEAGUES = frozenset({"EPL", "La_liga", "Serie_A", "Bundesliga", "Ligue_1",
                     "Championship", "Eredivisie"})
SCAN_NAMES = frozenset({"soccer_scan.json", "scan_full.json", "epl_scan.json",
    "bund_ligue_scan.json", "epl_champ_scan.json", "seriea_laliga_scan.json",
    "laliga_scan.json", "seriea_scan.json", "laliga_bund_scan.json",
    "ligue_rest_scan.json", "euro_ext_scan.json"})


def _utc(value: str | datetime) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    if not isinstance(parsed, datetime) or parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("market timestamps require an explicit UTC offset")
    return parsed.astimezone(UTC)


def _iso(value: datetime) -> str:
    return _utc(value).isoformat().replace("+00:00", "Z")


def _probability(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("boolean quote is invalid")
    number = float(value)
    if not math.isfinite(number) or not 0 <= number <= 1:
        raise ValueError("quote must be finite and in [0, 1]")
    return number


@dataclass(frozen=True)
class MarketQuote:
    outcome: str
    market_id: str
    bid: float | None
    ask: float | None
    last_trade: float | None = None

    def price(self, kind: str) -> float | None:
        if kind == "midpoint":
            return (self.bid + self.ask) / 2 if self.bid is not None and self.ask is not None else None
        if kind == "ask":
            return self.ask
        if kind == "last_trade":
            return self.last_trade
        raise ValueError("quote kind must be midpoint, ask, or last_trade")


@dataclass(frozen=True)
class MarketObservation:
    league: str
    home_team: str
    away_team: str
    kickoff: datetime
    scan_at: datetime
    title: str
    quotes: tuple[MarketQuote, ...]
    source_path: str
    mapping_references: tuple[str, ...]

    @property
    def fixture_id(self) -> tuple[str, str, str, datetime]:
        return self.league, self.home_team, self.away_team, self.kickoff


@dataclass(frozen=True)
class MarketAudit:
    observations: tuple[MarketObservation, ...]
    sources: tuple[dict, ...]
    exclusions: tuple[dict, ...]


@dataclass(frozen=True)
class TrainingProvenance:
    history_count: int
    latest_kickoff: datetime
    source_available_at: datetime
    source_paths: tuple[str, ...]
    configuration_reference: str
    selection_mode: str = "fixed_shadow"
    selection_cutoff: datetime | None = None
    original_publication_times_known: bool = False
    completed_current_rounds: tuple[int, ...] = ()


@dataclass(frozen=True)
class MarketPredictionPair:
    frozen10: tuple[float, float, float]
    recalibrated: tuple[float, float, float]
    provenance: TrainingProvenance
    variant_count: int = 10


@dataclass(frozen=True)
class MarketSkip:
    reason: str


Predictor = Callable[[MarketObservation], MarketPredictionPair | MarketSkip]


def _identity(fixture: dict) -> tuple[str, str, str, datetime] | None:
    home, away = fixture.get("understat_home"), fixture.get("understat_away")
    hl = fixture.get("home_league")
    al = fixture.get("away_league")
    if hl is not None or al is not None:
        if hl != al:
            return None
        league = hl
    else:
        league = fixture.get("league", fixture.get("league_tag"))
    if league not in LEAGUES or not isinstance(home, str) or not isinstance(away, str) or not home or not away or home == away:
        return None
    return league, home, away, _utc(fixture["kickoff_utc"])


def parse_scan(payload: dict, source_path: str) -> tuple[list[MarketObservation], list[dict]]:
    """Join board rows through exact archived IDs/titles and canonical mappings.

    ``comp`` and free-text fixture keys are not identity evidence. In particular,
    r38 contains copied competition labels that disagree with canonical leagues.
    Conflicting identities, repeated side quotes, and incomplete 1X2 are excluded.
    """
    observations, excluded = [], []

    def omit(reason: str, title: str | None = None):
        excluded.append({"source_path": source_path, "match": title, "reason": reason})

    if not isinstance(payload, dict) or not all(isinstance(payload.get(k), list) for k in ("fixtures", "matches", "board")):
        omit("unsupported_scan_schema")
        return observations, excluded
    try:
        stamp = _utc(payload["generated_utc"])
    except (KeyError, TypeError, ValueError):
        omit("missing_or_invalid_scan_report_timestamp")
        return observations, excluded
    match_rows, board_rows = defaultdict(list), defaultdict(list)
    for i, row in enumerate(payload["matches"]):
        if isinstance(row, dict) and isinstance(row.get("match"), str):
            match_rows[row["match"]].append((i, row))
    for i, row in enumerate(payload["board"]):
        if isinstance(row, dict) and row.get("kind") == "ml" and row.get("side") in OUTCOMES:
            board_rows[row.get("match")].append((i, row))
    for title, rows in sorted(board_rows.items(), key=lambda item: str(item[0])):
        if not isinstance(title, str) or title not in match_rows:
            omit("missing_exact_match_metadata", title)
            continue
        identities, refs = set(), set()
        try:
            for mi, match in match_rows[title]:
                kickoff = _utc(match["kickoff_utc"])
                ids = set(match.get("gamma_event_ids", []))
                for fi, fixture in enumerate(payload["fixtures"]):
                    if not isinstance(fixture, dict):
                        continue
                    if (fixture.get("title", fixture.get("match")) != title
                            and fixture.get("event_id") not in ids):
                        continue
                    ident = _identity(fixture)
                    if ident is None:
                        continue
                    if ident[-1] != kickoff:
                        raise ValueError("fixture kickoff disagreement")
                    for key in ("league", "home_league", "away_league"):
                        if match.get(key) is not None and match[key] != ident[0]:
                            raise ValueError("canonical league disagreement")
                    identities.add(ident)
                    refs.update((f"matches[{mi}]", f"fixtures[{fi}]"))
        except (KeyError, TypeError, ValueError):
            omit("conflicting_or_invalid_fixture_mapping", title)
            continue
        if len(identities) != 1:
            omit("missing_or_ambiguous_domestic_fixture_mapping", title)
            continue
        league, home, away, kickoff = identities.pop()
        if stamp >= kickoff:
            omit("scan_report_not_strictly_pre_kickoff", title)
            continue
        quotes = {}
        try:
            for bi, row in rows:
                if row.get("kickoff_utc") and _utc(row["kickoff_utc"]) != kickoff:
                    raise ValueError("board kickoff disagreement")
                side = row["side"]
                if side in quotes:
                    raise ValueError("multiple quotes for same outcome")
                market_id = str(row.get("id", ""))
                if not market_id:
                    raise ValueError("missing market ID")
                bid, ask = _probability(row.get("book_best_bid")), _probability(row.get("book_best_ask"))
                if bid is not None and ask is not None and bid > ask:
                    raise ValueError("crossed book")
                quotes[side] = MarketQuote(side, market_id, bid, ask,
                    _probability(row.get("book_last_trade_price")))
                refs.add(f"board[{bi}]")
            if set(quotes) != set(OUTCOMES) or len({q.market_id for q in quotes.values()}) != 3:
                raise ValueError("incomplete or aliased outcome set")
        except (TypeError, ValueError):
            omit("invalid_duplicate_or_incomplete_1x2_quotes", title)
            continue
        observations.append(MarketObservation(league, home, away, kickoff, stamp, title,
            tuple(quotes[o] for o in OUTCOMES), source_path, tuple(sorted(refs))))
    return observations, excluded


def load_market_archive(root: str | Path) -> MarketAudit:
    """Read a bounded set of soccer scan archives; never use mtimes as timestamps."""
    root = Path(root).resolve()
    sources, observations, exclusions = [], [], []
    rounds = sorted((p for p in root.glob("round[0-9]*") if p.name[5:].isdigit()),
                    key=lambda p: int(p.name[5:]))
    for folder in rounds:
        for name in sorted(SCAN_NAMES):
            path = folder / "raw" / name
            if not path.exists():
                continue
            if not path.resolve().is_relative_to(root):
                raise ValueError("market archive path escapes declared root")
            data = path.read_bytes()
            relative = str(path.relative_to(root))
            sources.append({"path": relative, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
            rows, omitted = parse_scan(json.loads(data), relative)
            observations.extend(rows)
            exclusions.extend(omitted)
    return MarketAudit(tuple(sorted(observations, key=lambda o: (o.scan_at, o.fixture_id, o.source_path))),
                       tuple(sources), tuple(exclusions))


def _vector(values: tuple[float, ...]) -> tuple[float, ...]:
    if len(values) != 3:
        raise ValueError("predictions require three coordinates")
    result = tuple(_probability(v) for v in values)
    if any(v is None for v in result) or math.fsum(result) <= 0:
        raise ValueError("prediction coordinates require positive total mass")
    return result


def _normalize(values: tuple[float, ...]) -> tuple[float, ...]:
    return tuple(v / math.fsum(values) for v in values)


def evaluate_market_mad(audit: MarketAudit, predictor: Predictor | None = None,
                        *, quote_kind: str = "midpoint") -> dict:
    """Descriptive first-usable-scan cohort; exact-timestamp Gate E is unavailable.

    Earliest usable scan per fixture is selected by source availability and quote
    completeness, never by forecast error. The paired primary MAD compares raw
    frozen coordinate medians / recalibrated probabilities to unnormalized market
    quotes. Normalized vectors are reported separately and do not replace it.
    """
    if quote_kind not in {"midpoint", "ask", "last_trade"}:
        raise ValueError("quote kind must be midpoint, ask, or last_trade")
    scored, skipped, used = [], list(audit.exclusions), set()
    for obs in sorted(audit.observations, key=lambda o: (o.scan_at, o.fixture_id, o.source_path)):
        common = {"source_path": obs.source_path, "match": obs.title, "league": obs.league,
                  "scan_at": _iso(obs.scan_at), "kickoff": _iso(obs.kickoff)}

        def omit(reason: str):
            skipped.append({**common, "reason": reason})

        if obs.fixture_id in used:
            omit("later_scan_duplicate_fixture")
            continue
        if _utc(obs.scan_at) >= _utc(obs.kickoff):
            omit("scan_report_not_strictly_pre_kickoff")
            continue
        if tuple(q.outcome for q in obs.quotes) != OUTCOMES:
            raise ValueError("quote coordinates must be ordered home/draw/away")
        raw_market = tuple(_probability(q.price(quote_kind)) for q in obs.quotes)
        if len(raw_market) != 3 or any(v is None for v in raw_market) or math.fsum(raw_market) <= 0:
            omit(f"incomplete_{quote_kind}_triplet")
            continue
        if predictor is None:
            omit("pre_scan_prediction_provider_unavailable")
            continue
        pair = predictor(obs)
        if isinstance(pair, MarketSkip):
            omit(pair.reason)
            continue
        provenance = pair.provenance
        if (isinstance(provenance.history_count, bool) or not isinstance(provenance.history_count, int)
                or provenance.history_count <= 0
                or _utc(provenance.latest_kickoff) + timedelta(hours=3) >= obs.scan_at):
            omit("training_not_completed_before_scan")
            continue
        if not provenance.source_paths or not provenance.configuration_reference:
            raise ValueError("prediction requires source paths and configuration provenance")
        if _utc(provenance.source_available_at) >= obs.scan_at:
            omit("training_snapshot_not_available_before_scan")
            continue
        if provenance.selection_mode not in {"fixed_shadow", "training_only"}:
            raise ValueError("configuration must be fixed_shadow or selected on prior training only")
        if provenance.selection_mode == "training_only" and (provenance.selection_cutoff is None
                or _utc(provenance.selection_cutoff) >= obs.scan_at):
            omit("configuration_not_selected_before_scan")
            continue
        if pair.variant_count != 10:
            raise ValueError("baseline must preserve all ten frozen variants")
        frozen, recal = _vector(pair.frozen10), _vector(pair.recalibrated)
        if not math.isclose(math.fsum(recal), 1.0, abs_tol=1e-9, rel_tol=0):
            raise ValueError("recalibrated probabilities must sum to one")
        used.add(obs.fixture_id)
        p = asdict(provenance)
        for key in ("latest_kickoff", "source_available_at", "selection_cutoff"):
            p[key] = _iso(p[key]) if p[key] is not None else None
        scored.append({**common, "home_team": obs.home_team, "away_team": obs.away_team,
            "market_ids": [q.market_id for q in obs.quotes], "quote_kind": quote_kind,
            "market_raw": raw_market, "market_coordinate_sum": math.fsum(raw_market),
            "frozen10_raw": frozen, "frozen10_coordinate_sum": math.fsum(frozen),
            "recalibrated_raw": recal, "recalibrated_coordinate_sum": math.fsum(recal),
            "market_normalized_diagnostic": _normalize(raw_market),
            "frozen10_normalized_diagnostic": _normalize(frozen),
            "recalibrated_normalized_diagnostic": _normalize(recal),
            "frozen10_absolute_errors_cents": tuple(100 * abs(p - q) for p, q in zip(frozen, raw_market)),
            "recalibrated_absolute_errors_cents": tuple(100 * abs(p - q) for p, q in zip(recal, raw_market)),
            "mapping_references": obs.mapping_references, "training": p})

    def summary(rows):
        count = len(rows)
        return {"matches": count, "outcomes": 3 * count,
            "frozen10_mad_cents": math.fsum(v for r in rows for v in r["frozen10_absolute_errors_cents"]) / (3 * count) if count else None,
            "recalibrated_mad_cents": math.fsum(v for r in rows for v in r["recalibrated_absolute_errors_cents"]) / (3 * count) if count else None,
            "scan_range": [min(r["scan_at"] for r in rows), max(r["scan_at"] for r in rows)] if count else None,
            "kickoff_range": [min(r["kickoff"] for r in rows), max(r["kickoff"] for r in rows)] if count else None}

    return {"status": "DESCRIPTIVE_SCAN_REPORT_PROXY" if scored else "SKIPPED_NO_PAIRED_PREDICTIONS",
        "paper_only": True, "report_only": True, "readonly": True,
        "certifying_gate_E": False, "strict_gate_E_status": "UNAVAILABLE",
        "strict_gate_E_reasons": ["per_book_acquisition_timestamps_not_retained",
            "original_xg_publication_and_revision_times_unknown", "retrospective_shadow_not_prospective_acceptance"],
        "quote_kind": quote_kind, "outcome_order": OUTCOMES,
        "reference_gate_E_bar_cents": 6.0,
        "selection": "earliest usable pre-kickoff scan per canonical fixture; no error-based selection",
        "scan_time_basis": "archive generated_utc; program start or completion, not exact quote acquisition",
        "configuration_policy": "fixed preregistered shadow configuration or prior-training-only selection; never selected from market MAD",
        "primary_metric": "mean absolute raw probability minus raw market quote, in cents; no coordinate normalization",
        "inventory": {"sources": len(audit.sources), "matched_scan_fixtures": len(audit.observations),
            "matched_scan_outcomes": 3 * len(audit.observations),
            "distinct_fixtures": len({o.fixture_id for o in audit.observations}),
            "scan_range": [_iso(min(o.scan_at for o in audit.observations)), _iso(max(o.scan_at for o in audit.observations))] if audit.observations else None},
        "overall": summary(scored),
        "by_league": {league: summary([r for r in scored if r["league"] == league]) for league in sorted({r["league"] for r in scored})},
        "exclusion_counts": dict(sorted(Counter(r["reason"] for r in skipped).items())),
        "exclusions": skipped, "sources": list(audit.sources), "rows": scored}


def archive_snapshot_availability(history_audit, root: str | Path) -> dict[str, datetime]:
    """Read hash-pinned metadata already inventoried by the history loader.

    These are availability bounds for the downloaded snapshot, not invented
    original publication dates for individual xG values. For the moving Big-5
    pointer use its later publication time rather than the merge's start time.
    """
    root = Path(root).resolve()
    manifest = {s["path"]: s for s in history_audit.sources}

    def pinned_json(relative: str):
        if relative not in manifest:
            raise ValueError(f"availability metadata absent from history manifest: {relative}")
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            raise ValueError("snapshot metadata path escapes declared root")
        data = path.read_bytes()
        source = manifest[relative]
        if len(data) != source["bytes"] or hashlib.sha256(data).hexdigest() != source["sha256"]:
            raise ValueError(f"snapshot metadata changed since history load: {relative}")
        return json.loads(data)

    result = {}
    for snapshot, metadata, field in [
        ("understat_latest.json", "understat_latest_pointer.json", "pointed_at_utc"),
        ("round31/raw/xg_fotmob_championship.json", "round31/raw/xg_fotmob_championship.json.meta.json", "generated_utc"),
        ("round39/raw/xg_fotmob_eredivisie.json", "round39/raw/xg_fotmob_eredivisie.json.meta.json", "fetched_utc"),
    ]:
        if snapshot not in manifest:
            continue
        payload = pinned_json(metadata)
        if snapshot == "understat_latest.json" and payload.get("sha256") != manifest[snapshot]["sha256"]:
            raise ValueError("snapshot pointer digest differs from loaded history")
        result[snapshot] = _utc(payload[field])
    return result


def fixed_shadow_predictor(history_audit, snapshot_available_at: Mapping[str, datetime]) -> Predictor:
    """Regenerate both models on identical completed history, with fixed 120d/k=8.

    This is a declared comparison configuration, not the tuned walk-forward
    winner and not a claim that k=8 passed promotion validation. Source snapshot
    times bound archive availability; final provider schedules remain replay
    evidence. Unknown schedules and missing prior seasons are explicit skips.
    """
    from tools.wp_p4_history import Fold, history_at, production_snapshot, to_model_history
    from polymarket_alpha_lab.papersim.recalib import Config, Fixture, fit
    from polymarket_alpha_lab.papersim.soccer_model import fixture_variants, median

    config = Config(half_life_days=120.0, team_prior_matches=8.0)
    cache = {}

    def predict(obs: MarketObservation) -> MarketPredictionPair | MarketSkip:
        schedules = [f for f in history_audit.schedule if (f.league, f.home_team, f.away_team, f.kickoff) == obs.fixture_id
                     and not f.cancelled and not f.awarded]
        if len(schedules) != 1:
            return MarketSkip("no_exact_official_schedule_match")
        target = schedules[0]
        key = obs.league, target.season, obs.scan_at
        if key not in cache:
            train, groups = history_at(history_audit, obs.league, target.season, obs.scan_at)
            sources = tuple(sorted({m.source_path for m in train}))
            if not train or any(source not in snapshot_available_at for source in sources):
                cache[key] = MarketSkip("training_snapshot_availability_unknown")
            else:
                available = max(_utc(snapshot_available_at[source]) for source in sources)
                if available >= obs.scan_at:
                    cache[key] = MarketSkip("training_snapshot_not_available_before_scan")
                else:
                    fold = Fold(obs.league, target.season, target.matchweek, obs.scan_at, train, (), groups)
                    snapshot = production_snapshot(history_audit, fold)
                    if snapshot is None:
                        cache[key] = MarketSkip("frozen10_prior_season_unavailable")
                    else:
                        provenance = TrainingProvenance(len(train), max(m.kickoff for m in train), available, sources,
                            "fixed shadow Config(half_life_days=120, team_prior_matches=8); other defaults unchanged",
                            completed_current_rounds=tuple(sorted(rnd for lg, yr, rnd in groups
                                if (lg, yr) == (obs.league, target.season) and rnd is not None)))
                        cache[key] = snapshot, fit(to_model_history(fold), config=config), provenance
        cached = cache[key]
        if isinstance(cached, MarketSkip):
            return cached
        snapshot, estimator, provenance = cached
        # A postponed older round can kick off after a later complete round.
        # The estimator deliberately does not support predicting that ordering;
        # keep the complete training groups and exclude only this target, not
        # every other fixture sharing the cached league/season/scan model.
        if (provenance.completed_current_rounds
                and target.matchweek <= max(provenance.completed_current_rounds)):
            return MarketSkip("target_round_not_after_fitted_current_rounds")
        variants = fixture_variants(snapshot, obs.home_team, obs.league, obs.away_team, obs.league, season=target.season)
        if variants is None or len(variants) != 10:
            return MarketSkip("frozen10_fixture_unavailable")
        forecast = estimator.predict(Fixture(obs.league, target.season, target.matchweek, obs.kickoff, obs.home_team, obs.away_team))
        frozen = tuple(median([getattr(v.outputs, coordinate) for v in variants]) for coordinate in ("home_win", "draw", "away_win"))
        return MarketPredictionPair(frozen, (forecast.home_win, forecast.draw, forecast.away_win), provenance)

    return predict
