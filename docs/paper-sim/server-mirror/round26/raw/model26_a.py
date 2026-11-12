"""Round-26 scan A: model all 9 fixtures through the CANONICAL papersim library
(PYTHONPATH=/home/ubuntu/polymarket-alpha-lab/src), both directions, O/U + BTTS +
team totals + ML + spreads (spreads recorded only). Joins Gamma asks pre-CLOB."""
import json, time
from polymarket_alpha_lab.papersim import xg, soccer_model as sm

SNAP = '/home/ubuntu/paper-sim/round25/raw/xg_understat_25.json'
RAW = '/home/ubuntu/paper-sim/round26/raw'

FIX = [
    ("Como-Venezia", "Como", "Venezia", "Serie_A", "Como 1907", "Venezia FC", "2026-11-01T11:30:00Z"),
    ("Frosinone-Torino", "Frosinone", "Torino", "Serie_A", "Frosinone Calcio", "Torino FC", "2026-11-01T14:00:00Z"),
    ("Lazio-Cagliari", "Lazio", "Cagliari", "Serie_A", "SS Lazio", "Cagliari Calcio", "2026-11-01T14:00:00Z"),
    ("Lecce-Genoa", "Lecce", "Genoa", "Serie_A", "US Lecce", "Genoa CFC", "2026-11-01T17:00:00Z"),
    ("Juventus-Napoli", "Juventus", "Napoli", "Serie_A", "Juventus FC", "SSC Napoli", "2026-11-01T19:45:00Z"),
    ("Getafe-Sevilla", "Getafe", "Sevilla", "La_liga", "Getafe CF", "Sevilla FC", "2026-11-01T13:00:00Z"),
    ("RacingSantander-RealMadrid", "Racing Santander", "Real Madrid", "La_liga", "Real Racing Club", "Real Madrid CF", "2026-11-01T15:15:00Z"),
    ("Elche-Valencia", "Elche", "Valencia", "La_liga", "Elche CF", "Valencia CF", "2026-11-01T17:30:00Z"),
    ("Athletic-RealSociedad", "Athletic Club", "Real Sociedad", "La_liga", "Athletic Club", "Real Sociedad de Futbol", "2026-11-01T20:00:00Z"),
]

snap = xg.load_xg_snapshot(SNAP)
events = json.load(open(RAW + '/events_window_a.json'))

import unicodedata
def nrm(s):
    return " ".join("".join(c for c in unicodedata.normalize("NFD", s or "") if not unicodedata.combining(c)).lower().split())

med = sm.median

def agg(vals):
    return {"med": round(med(vals), 4), "min": round(min(vals), 4), "max": round(max(vals), 4),
            "spread": round(max(vals) - min(vals), 4), "qs": [round(v, 4) for v in vals]}

def form_dict(f):
    if f is None:
        return None
    d = {}
    for attr in ("games", "goals_for", "goals_against", "goals_per_game", "xg_per_game", "over_2_5_hits", "btts_hits"):
        v = getattr(f, attr, None)
        if v is not None:
            d[attr] = round(v, 2) if isinstance(v, float) else v
    return d

out_matches, out_rows = [], []
for label, uh, ua, lg, gh, ga, ko in FIX:
    variants = sm.fixture_variants(snap, uh, lg, ua, lg)
    if variants is None:
        print("REFUSED (library guard):", label)
        continue
    lh = med([v.lambdas[0] for v in variants])
    la = med([v.lambdas[1] for v in variants])
    fh = xg.recent_form(snap, uh)
    fa = xg.recent_form(snap, ua)
    out_matches.append({
        "match": label, "league": lg, "kickoff_utc": ko,
        "lambda_home": round(lh, 3), "lambda_away": round(la, 3), "lambda_total": round(lh + la, 3),
        "lambdas_per_variant": {v.spec.name: [round(v.lambdas[0], 3), round(v.lambdas[1], 3)] for v in variants},
        "form_home_last5": form_dict(fh), "form_away_last5": form_dict(fa),
    })
    sides = {}
    for key, pick in (("ml_home", lambda o: o.home_win), ("ml_draw", lambda o: o.draw), ("ml_away", lambda o: o.away_win)):
        sides[key] = agg([pick(v.outputs) for v in variants])
    for line in (0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5):
        ov = [sm.over_probability(v.outputs, line) for v in variants]
        sides["over_%s" % line] = agg(ov)
        sides["under_%s" % line] = agg([1 - p for p in ov])
    bt = [sm.both_teams_to_score(v.outputs) for v in variants]
    sides["btts_yes"] = agg(bt)
    sides["btts_no"] = agg([1 - p for p in bt])
    for side_key, team_key in (("tt_home", "home"), ("tt_away", "away")):
        for line in (0.5, 1.5, 2.5):
            sides["%s_over_%s" % (side_key, line)] = agg([sm.team_total_over(v.outputs, team_key, line) for v in variants])
            sides["%s_under_%s" % (side_key, line)] = agg([1 - sm.team_total_over(v.outputs, team_key, line) for v in variants])
    for sp_line in (-2.5, -1.5, 1.5, 2.5):
        sides["spread_home_%s" % sp_line] = agg([sm.cover_probability(v.outputs, "home", sp_line) for v in variants])
        sides["spread_away_%s" % (-sp_line)] = agg([sm.cover_probability(v.outputs, "away", -sp_line) for v in variants])

    # join gamma markets (unicode-normalized matching: Gamma uses accented names)
    n_gh, n_ga = nrm(gh), nrm(ga)
    hits = [e for e in events if n_gh in nrm(e.get('title')) and n_ga in nrm(e.get('title'))]
    main = [e for e in hits if ' - ' not in (e.get('title') or '') and nrm(e.get('title')).startswith(n_gh)]
    more = [e for e in hits if (e['title'] or '').endswith('More Markets')]
    gm = {}
    for e in main:
        for m in e['markets']:
            g = m['group'] or ''
            if nrm(g) == n_gh:
                gm[("ml_home", None)] = m
            elif nrm(g) == n_ga:
                gm[("ml_away", None)] = m
            elif g.startswith('Draw'):
                gm[("ml_draw", None)] = m
    for e in more:
        for m in e['markets']:
            g = m['group'] or ''
            q = m['q'] or ''
            half = ('1st Half' in q) or ('2nd Half' in q)
            if g.startswith('O/U ') and not half:
                line = float(g.split()[1])
                gm[("total", line)] = m
            elif g == 'Both Teams to Score':
                gm[("btts", None)] = m
            elif (nrm(g).startswith(n_gh + ' o/u') or nrm(g).startswith(n_ga + ' o/u')) and not half:
                team = 'tt_home' if nrm(g).startswith(n_gh) else 'tt_away'
                line = float(g.split()[-1])
                gm[(team, line)] = m

    def token_side(m, want):
        try:
            outs = json.loads(m['outcomes'] or '[]')
        except Exception:
            outs = []
        if not outs:
            return None, None, None
        wl = want.lower()
        idx = 0 if outs[0].lower().startswith(wl) else (1 if len(outs) > 1 else 0)
        if idx == 0:
            ask = float(m['bestAsk']) if m['bestAsk'] is not None else None
            bid = float(m['bestBid']) if m['bestBid'] is not None else None
        else:
            ask = (1 - float(m['bestBid'])) if m['bestBid'] is not None else None
            bid = (1 - float(m['bestAsk'])) if m['bestAsk'] is not None else None
        try:
            toks = json.loads(m['tokens'] or '[]')
        except Exception:
            toks = []
        tok = toks[idx] if idx < len(toks) else None
        return ask, bid, tok

    def want_word(key):
        if key.startswith("ml_"):
            return "yes"
        if key == "btts_yes":
            return "yes"
        if key == "btts_no":
            return "no"
        if key.startswith(("over_", "tt_home_over", "tt_away_over")):
            return "over"
        return "under"

    for key in list(sides.keys()):
        if key.startswith("spread_"):
            continue  # flagged-only; no join needed for entry scan
        m = None
        if key in ("ml_home", "ml_draw", "ml_away"):
            m = gm.get((key, None))
        elif key == "btts_yes" or key == "btts_no":
            m = gm.get(("btts", None))
        elif key.startswith("over_"):
            m = gm.get(("total", float(key.split("_")[1])))
        elif key.startswith("under_"):
            m = gm.get(("total", float(key.split("_")[1])))
        elif key.startswith("tt_home_over_"):
            m = gm.get(("tt_home", float(key.split("_")[-1])))
        elif key.startswith("tt_home_under_"):
            m = gm.get(("tt_home", float(key.split("_")[-1])))
        elif key.startswith("tt_away_over_"):
            m = gm.get(("tt_away", float(key.split("_")[-1])))
        elif key.startswith("tt_away_under_"):
            m = gm.get(("tt_away", float(key.split("_")[-1])))
        if m is None:
            continue
        ask, bid, tok = token_side(m, want_word(key))
        s = sides[key]
        out_rows.append({
            "fixture": label, "league": lg, "kickoff_utc": ko, "key": key,
            "model_med": s["med"], "model_min": s["min"], "model_max": s["max"], "var_spread": s["spread"],
            "qs_variants": s["qs"],
            "gamma_ask": ask, "gamma_bid": bid, "liq_gamma": float(m['liq'] or 0), "market_id": m['id'],
            "q": m['q'], "token": tok,
            "pre_clob_edge": round(s["med"] - ask, 4) if ask is not None else None,
        })

json.dump({"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "snapshot": SNAP, "library": "polymarket_alpha_lab.papersim @ 7b6cdd47",
           "matches": out_matches, "rows": out_rows},
          open(RAW + "/model26_a.json", "w"), indent=1)
print("fixtures modeled:", len(out_matches), "| gamma-joined rows:", len(out_rows))
for m in out_matches:
    print("%-26s lh=%.3f la=%.3f tot=%.3f" % (m["match"], m["lambda_home"], m["lambda_away"], m["lambda_total"]))
top = sorted([r for r in out_rows if r["pre_clob_edge"] is not None], key=lambda r: -r["pre_clob_edge"])[:30]
print("\nTOP PRE-CLOB EDGES:")
for r in top:
    print("%-26s %-18s med=%.3f ask=%.3f edge=%+.4f var=%.3f liq=%.0f" % (
        r["fixture"], r["key"], r["model_med"], r["gamma_ask"], r["pre_clob_edge"], r["var_spread"], r["liq_gamma"]))
