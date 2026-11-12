"""ROUND-47 NBA shadow predictions vs market. SHADOW-MONITORING-ONLY.
PAPER ONLY: no orders, no DB writes, no entries. These rows are out-of-sample
evidence for the NBA re-validation (gate-E convergence check).

For every NBA game tipping inside 2026-11-12T01:15Z..2026-11-13T01:15Z with
both teams present in the refreshed ESPN snapshot
(/home/ubuntu/paper-sim/nba/snapshot_20261112.json, games through 2026-11-11):
run papersim nba_model.fixture_prediction (six-variant envelope) with
before_date = the game's EASTERN date (strictly-causal ratings), rest/b2b
derived from the snapshot, and record p_home / exp_total / variant spread next
to the market prices (live for upcoming, CLOB prices-history pre-tip close for
finished games). Structured JSON at ~/paper-sim/round47/nba_shadow_rows.json.
"""
import json, re, sys, time, datetime, urllib.request
from datetime import date, timedelta, timezone

sys.path.insert(0, "/home/ubuntu/polymarket-alpha-lab/src")
from polymarket_alpha_lab.papersim import nba_model  # noqa: E402

R47 = "/home/ubuntu/paper-sim/round47"
RAW = f"{R47}/raw"
SNAP_PATH = "/home/ubuntu/paper-sim/nba/snapshot_20261112.json"
CLOB = "https://clob.polymarket.com"
NOW = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
LOn, HIn = "2026-11-12 01:15", "2026-11-13 01:15"

def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except Exception as ex:
            print("ERR", url[:110], ex, flush=True)
            time.sleep(2.0)
    return None

def n16(s):
    return str(s)[:16].replace("T", " ")

def et_date(tip_utc):
    """Eastern-Time calendar date of a UTC tip (EST = UTC-5 after 2026-11-01)."""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})", tip_utc)
    y, mo, d, hh, mi = map(int, m.groups())
    t = datetime.datetime(y, mo, d, hh, mi, tzinfo=timezone.utc) - timedelta(hours=5)
    return t.date()

snapshot = json.load(open(SNAP_PATH))
print("snapshot", snapshot["generated_at"], "teams", len(snapshot["teams"]), flush=True)
games_by_team = {}
for ab, t in snapshot["teams"].items():
    games_by_team[ab] = sorted(g["date"] for g in t["games"])

# ---- fixtures: ESPN scoreboards (authoritative home/away/finals) ----
games = []
for sb_name in ["espn_nba_sb_20261111", "espn_nba_sb_20261112"]:
    sb = json.load(open(f"{RAW}/{sb_name}.json"))["data"]
    for e in sb.get("events") or []:
        tip = n16(e.get("date"))
        if not (LOn <= tip <= HIn):
            continue
        comp = (e.get("competitions") or [{}])[0]
        home = away = None
        hscore = ascore = None
        hdisp = adisp = None
        for c in comp.get("competitors") or []:
            tm = c.get("team") or {}
            ab = tm.get("abbreviation")
            disp = tm.get("displayName") or tm.get("name") or ""
            s = c.get("score")
            s = s.get("displayValue") if isinstance(s, dict) else s
            if c.get("homeAway") == "home":
                home, hscore, hdisp = ab, s, disp
            else:
                away, ascore, adisp = ab, s, disp
        st = (e.get("status") or {}).get("type", {})
        games.append({"tip_utc": tip.replace(" ", "T") + ":00Z", "home": home, "away": away,
                      "home_disp": hdisp, "away_disp": adisp,
                      "name": e.get("shortName") or e.get("name"),
                      "state": st.get("state"), "detail": st.get("detail"),
                      "final_home_pts": hscore, "final_away_pts": ascore})
print("in-window NBA games:", [(g["name"], g["tip_utc"]) for g in games], flush=True)

# ---- Gamma detail side (ML/spread/totals + tokens), from boards47 dump or refetch ----
try:
    det = json.load(open(f"{RAW}/nba_event_details.json"))["data"]
except Exception:
    det = {}
G = "https://gamma-api.polymarket.com"
def _core_tokens(name):
    """Distinctive lowercase tokens of a team display name (drop city words)."""
    stop = {"golden", "state", "portland", "trail", "city", "san", "antonio", "los",
            "angeles", "angeleslakers", "new", "orleans", "orlean", "york", "oklahoma",
            "salt", "lake", "washington", "indiana", "minnesota", "philadelphia", "phila"}
    toks = [t for t in re.split(r"[^a-z0-9]+", str(name).lower()) if t]
    toks = [t for t in toks if t not in stop] or toks
    return set(t for t in toks if len(t) >= 4)
def gamma_for(g):
    """Match the Gamma event by tip time + both teams' name tokens."""
    want = _core_tokens(g.get("home_disp") or "") | _core_tokens(g.get("away_disp") or "")
    tip = n16(g["tip_utc"])
    for eid, ev in det.items():
        title = str(ev.get("title"))
        if " vs. " not in title:
            continue
        gsts = {n16(m.get("gameStartTime")) for m in (ev.get("markets") or []) if m.get("gameStartTime")}
        if gsts and tip not in gsts:
            continue
        tt = _core_tokens(title.replace(" vs. ", " "))
        if not (want and (want & tt)):
            continue
        ml, spreads, totals = None, {}, {}
        for m in ev.get("markets") or []:
            q = str(m.get("question") or "")
            try:
                px = [float(x) for x in json.loads(m.get("outcomePrices") or "[]")]
            except Exception:
                px = None
            if q == title:
                try:
                    outs = json.loads(m.get("outcomes") or "[]")
                    toks = json.loads(m.get("clobTokenIds") or "[]")
                except Exception:
                    outs, toks = [], []
                ml = {"prices": px, "outcomes": outs, "tokens": toks,
                      "bid/ask": [m.get("bestBid"), m.get("bestAsk")],
                      "vol24": m.get("volume24hr"), "liq": m.get("liquidityNum"),
                      "closed": m.get("closed")}
            mq = re.match(r"Spread: (.+) \(([-+]?\d+\.\d)\)$", q)
            if mq and px:
                spreads[mq.group(2)] = {"team": mq.group(1), "yes": px[0]}
            mo = re.search(r"O/U (\d+(?:\.\d)?)$", q)
            if mo and px:
                totals[float(mo.group(1))] = px[0]
        return ml, spreads, totals
    return None, {}, {}

# ---- shadow predictions ----
rows = []
for g in sorted(games, key=lambda x: x["tip_utc"]):
    home, away = g["home"], g["away"]
    etd = et_date(g["tip_utc"])
    rated = home in games_by_team and away in games_by_team
    row = {
        "label": "SHADOW-MONITORING-ONLY",
        "tip_utc": g["tip_utc"], "game": g["name"], "home": home, "away": away,
        "home_disp": g.get("home_disp"), "away_disp": g.get("away_disp"),
        "et_date": str(etd), "state_at_scan": g["state"], "espn_detail": g["detail"],
        "snapshot": "snapshot_20261112.json (games through 2026-11-11)",
        "both_teams_rated": bool(rated),
    }
    # market side
    ml, spreads, totals = gamma_for(g)
    row["market_ml"] = ml
    row["market_spread_rungs"] = spreads
    row["market_total_rungs"] = {str(k): v for k, v in sorted(totals.items())}
    if ml and ml.get("tokens"):
        b = get(f"{CLOB}/book?token_id={ml['tokens'][0]}")
        if b:
            row["market_ml_clob_book"] = {"bids": (b.get("bids") or [])[:3], "asks": (b.get("asks") or [])[:3]}
        time.sleep(0.25)
    # model side
    if not rated:
        row["model"] = None
        row["refusal"] = "team missing from snapshot"
        rows.append(row)
        print("SKIP", g["name"], "unrated", flush=True)
        continue
    hg = [d for d in games_by_team[home] if d < str(etd)]
    ag = [d for d in games_by_team[away] if d < str(etd)]
    rest_home = (etd - date.fromisoformat(max(hg))).days if hg else None
    rest_away = (etd - date.fromisoformat(max(ag))).days if ag else None
    reason = nba_model.refusal_reason(snapshot, nba_model.NbaFixture(
        home=home, away=away, rest_home=rest_home, rest_away=rest_away,
        b2b_home=rest_home == 1, b2b_away=rest_away == 1), before_date=str(etd))
    row["rest_days"] = {"home": rest_home, "away": rest_away}
    row["b2b"] = {"home": rest_home == 1, "away": rest_away == 1}
    if reason is not None:
        row["model"] = None
        row["refusal"] = reason
        rows.append(row)
        print("REFUSE", g["name"], reason, flush=True)
        continue
    try:
        pred = nba_model.fixture_prediction(
            snapshot,
            nba_model.NbaFixture(home=home, away=away, rest_home=rest_home,
                                 rest_away=rest_away, b2b_home=rest_home == 1,
                                 b2b_away=rest_away == 1),
            before_date=str(etd))
    except Exception as ex:
        row["model"] = None
        row["refusal"] = f"hard error: {ex}"
        rows.append(row)
        print("ERROR", g["name"], ex, flush=True)
        continue
    if pred is None:
        row["model"] = None
        row["refusal"] = "prediction returned None"
        rows.append(row)
        continue
    # totals quote at nearest market rung(s)
    total_quotes = {}
    if totals:
        near = sorted(totals, key=lambda L: abs(L - pred.exp_total))[:3]
        for L in near:
            tq = pred.total_line_prob(L)
            total_quotes[str(L)] = {
                "market_yes_over": totals[L],
                "model_p_over": round(tq.p_over, 4), "model_p_under": round(tq.p_under, 4),
                "variant_spread_cents": round(tq.variant_spread * 100, 2),
                "model_minus_market_cents": round((tq.p_over - totals[L]) * 100, 2),
            }
    model_sign = 1 if (ml and ml.get("outcomes") and ml["outcomes"][0] == home) else -1
    mkt_p_home = None
    if ml and ml.get("prices"):
        mkt_p_home = ml["prices"][0] if model_sign == 1 else ml["prices"][1]
    row["model"] = {
        "p_home": round(pred.p_home, 4), "p_away": round(pred.p_away, 4),
        "exp_pts_home": round(pred.exp_pts_home, 2), "exp_pts_away": round(pred.exp_pts_away, 2),
        "exp_margin_home_minus_away": round(pred.exp_margin, 2),
        "exp_total": round(pred.exp_total, 2),
        "p_home_variant_spread_cents": round(pred.p_home_variant_spread * 100, 2),
        "exp_total_variant_spread_pts": round(pred.exp_total_variant_spread, 2),
        "exp_margin_variant_spread_pts": round(pred.exp_margin_variant_spread, 2),
        "p_home_range": [round(x, 4) for x in pred.p_home_range],
        "exp_total_range": [round(x, 2) for x in pred.exp_total_range],
        "sigma_margin": round(pred.sigma_margin, 2), "sigma_total": round(pred.sigma_total, 2),
        "sigma_residuals": pred.sigma_margin_residuals,
        "hca": round(pred.hca, 2), "b2b_penalty": round(pred.b2b_penalty, 2),
        "league_pace": round(pred.league_pace, 2), "pace_estimate": round(pred.pace_estimate, 2),
        "variant_p_home": {v.spec.name: round(v.p_home, 4) for v in pred.variants},
        "variant_exp_total": {v.spec.name: round(v.exp_total, 2) for v in pred.variants},
    }
    row["model_vs_market"] = {
        "market_p_home": mkt_p_home,
        "model_minus_market_p_home_cents": (round((pred.p_home - mkt_p_home) * 100, 2)
                                            if mkt_p_home is not None else None),
        "totals": total_quotes,
    }
    if g["state"] == "post" or (g["final_home_pts"] not in (None, "")):
        try:
            row["final_score"] = {"home_pts": int(g["final_home_pts"]), "away_pts": int(g["final_away_pts"])}
            row["final_score"]["model_p_home_pre_game"] = round(pred.p_home, 4)
            row["final_score"]["home_won"] = int(g["final_home_pts"]) > int(g["final_away_pts"])
            row["final_score"]["actual_total"] = int(g["final_home_pts"]) + int(g["final_away_pts"])
            row["final_score"]["actual_margin"] = int(g["final_home_pts"]) - int(g["final_away_pts"])
        except Exception:
            row["final_score_raw"] = [g["final_home_pts"], g["final_away_pts"]]
    rows.append(row)
    print("SHADOW", g["name"], g["tip_utc"], "p_home", round(pred.p_home, 3),
          "exp_total", round(pred.exp_total, 1), "mkt_p_home", mkt_p_home,
          "state", g["state"], flush=True)

# ---- pre-tip close for finished games via prices-history ----
for row in rows:
    if row.get("state_at_scan") == "post" and row.get("market_ml", {}) and row["market_ml"].get("tokens"):
        tip = row["tip_utc"]
        t_tip = datetime.datetime.fromisoformat(tip.replace("Z", "+00:00")).timestamp()
        tok = row["market_ml"]["tokens"][0]
        h = get(f"{CLOB}/prices-history?market={tok}&startTs={int(t_tip-21600)}&endTs={int(t_tip-60)}&fidelity=1")
        if h and h.get("history"):
            hs = h["history"]
            row["market_ml_pretip_close"] = {
                "outcome": (row["market_ml"].get("outcomes") or ["?"])[0],
                "last_pretip_p": hs[-1].get("p"), "t": hs[-1].get("t"),
                "n_points": len(hs), "min_p": min(x["p"] for x in hs), "max_p": max(x["p"] for x in hs),
            }
        time.sleep(0.3)

out = {
    "round": 47,
    "label": "SHADOW-MONITORING-ONLY - NO ENTRY (monitoring evidence for NBA re-validation, gate-E convergence check)",
    "paper_only": True, "no_db_writes": True, "no_entries": True,
    "generated_utc": NOW.isoformat(),
    "window_utc": {"lo": "2026-11-12T01:15:00Z", "hi": "2026-11-13T01:15:00Z"},
    "snapshot": {"path": SNAP_PATH, "generated_at": snapshot["generated_at"],
                 "games_through": "2026-11-11", "n_teams": len(snapshot["teams"])},
    "model": "polymarket_alpha_lab.papersim.nba_model.fixture_prediction (six-variant envelope, "
             "before_date=ET game date, rest/b2b from snapshot; injury stub default 1.0)",
    "schema_note": "each row: model.* = prediction; market_* = Polymarket Gamma/CLOB at scan time "
                   "(or pre-tip close via prices-history for finished games); model_vs_market in cents. "
                   "settlement: use final_score where present.",
    "rows": rows,
}
json.dump(out, open(f"{R47}/nba_shadow_rows.json", "w"), indent=1)
print("SHADOW47 DONE ->", f"{R47}/nba_shadow_rows.json", flush=True)
