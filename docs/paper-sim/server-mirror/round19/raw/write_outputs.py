import json, datetime

def devig(a, h):
    def imp(o):
        o = float(o)
        return abs(o) / (abs(o) + 100) if o < 0 else 100 / (o + 100)
    ia, ih = imp(a), imp(h)
    s = ia + ih
    return ia / s, ih / s

now = "2026-10-26T12:35:00Z"

nfl_wk7 = [
    {"game": "NE@CHI (Thu)", "score": "CHI 30-24"},
    {"game": "PIT@NO", "score": "PIT 16-10"},
    {"game": "SF@ATL", "score": "ATL 29-20"},
    {"game": "CLE@TEN", "score": "CLE 27-24"},
    {"game": "IND@MIN", "score": "MIN 16-10"},
    {"game": "MIA@NYJ", "score": "MIA 28-25"},
    {"game": "TB@CAR", "score": "TB 43-13"},
    {"game": "CIN@BAL", "score": "CIN 35-13", "note": "Lamar OUT (ankle, 3rd straight); Huntley 23/34 298yd 1TD/1INT; BAL led 13-0 half, 2nd-half collapse; Burrow 22/30 292yd 4TD/0INT"},
    {"game": "NYG@HOU (OT)", "score": "NYG 27-21"},
    {"game": "DEN@ARI", "score": "DEN 30-16"},
    {"game": "GB@DET", "score": "DET 20-17"},
    {"game": "LAR@LV", "score": "LAR 35-21"},
    {"game": "KC@SEA", "score": "SEA 20-3"},
    {"game": "DAL@PHI (MNF tonite)", "status": "scheduled 8:15pm ET Oct 26"},
]

mlb_ws = {
    "G1_fri_oct23": {"result": "MIL 3-2 TB (MIL home)", "note": "confirmed the 2-0 live score became a MIL win"},
    "G2_sat_oct24": {"result": "MIL 5-4 TB (MIL home)", "note": "TB up 4-0 after 1st, MIL chipped back"},
    "series": "MIL 2-0",
    "G3_mon_oct26": {"status": "tonight at TB (Tropicana), probable Gasser (MIL) vs F Peralta (TB)"},
    "G4_tue_oct27": {"status": "at TB; MIL starter TBA (Misiorowski on short rest possible)"},
}

nba_por = {
    "fri_por_sac": {"result": "POR 128 @ SAC 120", "dame": "33min 19pts 7-18FG 2-10 3PT 5reb 2ast +19", "ja": "27min 12pts 5-13FG 3reb 7ast +7", "scoot": "21min 4pts"},
    "weekend": "no POR games Sat/Sun (rest)",
    "record": "2-0 (beat PHX Oct 21, @SAC Oct 23); next @LAL Tue Oct 27",
}

por_futures = {
    "position": {"shares": 369.65, "avg": 0.612, "cost": 226.23},
    "pm_now": 0.625, "mtm_value": 231.03, "pnl": 4.80, "pnl_pct": 2.1,
    "liq": 2172.0, "vol": 1474.0,
    "books": {"make_playoffs": "-200 (devig ~0.625 w/ +150 pair)", "win_total": "41.5"},
    "thesis": "on track: 2-0, Dame back from Achilles, Ja 7ast; PM now = book fair",
    "action": "HOLD",
}

def edge(pm_a, pm_b, bk_a, bk_b):
    da, db = devig(bk_a, bk_b)
    return {"pm": [pm_a, pm_b], "book": [bk_a, bk_b], "devig": [round(da, 4), round(db, 4)],
            "edge_a_c": round(da - pm_a, 4), "edge_b_c": round(db - pm_b, 4)}

mlb_edges = {
    "G3_MIL@TB": dict(edge(0.485, 0.515, -102, -118), liq=589248, vol=21639, verdict="PASS (<=0.3c)"),
    "G4_MIL@TB": dict(edge(0.515, 0.485, -172, 148), liq=46995, vol=337, verdict="NEAR-MISS: MIL edge 9.6c < 10c bar; line contingent on unconfirmed MIL starter (Misiorowski short rest) - watchlist"),
    "series_MIL": dict(edge(0.835, 0.1655, -750, 475), liq=89652, vol=2293064, verdict="PASS (<=0.7c)"),
}

nba_mon_edges = {
    "WSH@CHA": dict(edge(0.465, 0.535, 110, -130), liq=225516, verdict="PASS 0.8c"),
    "MIN@CLE": dict(edge(0.385, 0.615, 150, -180), liq=211546, verdict="PASS 0.1c"),
    "CHI@BOS": dict(edge(0.135, 0.865, 525, -750), liq=161602, verdict="PASS 1.9c (CHI cheap)"),
    "DAL@MIA": dict(edge(0.255, 0.745, 260, -325), liq=138950, verdict="PASS 1.1c"),
    "IND@MIL": dict(edge(0.615, 0.385, -166, 140), liq=117812, verdict="PASS 1.5c"),
    "PHX@OKC": dict(edge(0.225, 0.775, 320, -410), liq=143636, verdict="PASS 0.4c"),
    "ATL@HOU": dict(edge(0.345, 0.655, 170, -205), liq=118802, verdict="PASS 1.0c"),
    "MEM@UTAH": dict(edge(0.495, 0.505, -108, -112), liq=124560, verdict="PASS 0.0c"),
    "GSW@DEN": dict(edge(0.285, 0.715, 235, -290), liq=123155, verdict="PASS 0.2c"),
}

other = {
    "MNF_DAL@PHI": dict(edge(0.665, 0.335, -222, 180), liq=959886, verdict="PASS 0.6c"),
    "NBA_tue_wed": "No book lines posted yet (ESPN pickcenter empty; Covers 2026 POR@LAL page all dashes; 'POR -3'/'LAL +127' hits were 2025 content). PM Tue/Wed liq 10-20k. No devig possible -> PASS.",
    "NFL_wk8": "PM wk8 Sunday events not listed yet (only wk8 Fri CAR@GB props + wk10+). Books lookahead BAL +3 @ BUF -3/-174 (SBD). Nothing tradeable -> PASS.",
    "injuries_absorbed": "DAL: Flagg/Aldama OUT; OKC: J Williams DTD; GSW: Porzingis/Moody OUT; CHA: White/Knueppel OUT; WSH: Dybantsa OUT; POR Tue: Sharpe OUT. PM prices already match books -> absorbed.",
}

scan = {
    "round": 19, "team": "us-sports", "asof_utc": now, "window": "through 2026-10-29",
    "results_nfl_wk7": nfl_wk7,
    "results_mlb_ws": mlb_ws,
    "results_nba_por": nba_por,
    "por_futures_mtm": por_futures,
    "edges_mlb": mlb_edges,
    "edges_nba_mon": nba_mon_edges,
    "edges_other": other,
    "bar": {"min_edge_c": 10, "min_liq": 10000, "max_bet": "1 x $200"},
}

candidates = {
    "round": 19, "team": "us-sports", "asof_utc": now,
    "passed_bar": False,
    "bets": [],
    "watchlist": [
        {"market": "mlb-mil-tb-2026-10-27 (WS G4 MIL YES)", "pm": 0.515, "book_devig": 0.611, "edge_c": 9.6,
         "liq": 46995, "blocker": "under 10c bar; MIL G4 starter unconfirmed (Misiorowski short rest 'if needed' vs TB #4). Re-check Tue AM if starters confirmed and PM still <=0.53."},
    ],
    "por_futures": {"action": "HOLD", "mtm": 231.03, "pnl": 4.80, "note": "PM 0.625 = book fair (-200 devig); liq thin ($2.2k); do not add"},
    "verdict": "PASS - 16th consecutive pass; no unabsorbed information >= 10c",
}

with open("/home/ubuntu/paper-sim/round19/raw/ussports_scan.json", "w") as f:
    json.dump(scan, f, indent=1)
with open("/home/ubuntu/paper-sim/round19/ussports_candidates.json", "w") as f:
    json.dump(candidates, f, indent=1)
print("written")
print(json.dumps(candidates, indent=1))
