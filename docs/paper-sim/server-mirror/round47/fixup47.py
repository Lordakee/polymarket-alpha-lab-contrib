"""ROUND-47 fixup: merge POR-OKC price history into board.json, add pretip
model-vs-market to finished shadow rows, dedupe other-basketball rows, fix
depth stats. PAPER ONLY - no orders, no DB writes. GET-only HTTP."""
import json, time, datetime, urllib.request

R47 = "/home/ubuntu/paper-sim/round47"
CLOB = "https://clob.polymarket.com"

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

# ---------- 1) POR-OKC ML price history (24h pre-tip, correct epochs) ----------
det = json.load(open(f"{R47}/raw/nba_event_details.json"))["data"]
ev = det.get("1284280") or {}
ml = None
for m in ev.get("markets") or []:
    if str(m.get("question")) == "Thunder vs. Trail Blazers":
        ml = m
        break
tip = datetime.datetime(2026, 11, 12, 3, 0, tzinfo=datetime.timezone.utc)
t0, t1 = int(tip.timestamp() - 86400), int(tip.timestamp() - 60)
tok = json.loads(ml["clobTokenIds"])[0]
outs = json.loads(ml["outcomes"])
h = get(f"{CLOB}/prices-history?market={tok}&startTs={t0}&endTs={t1}&fidelity=10")
hist = {}
if h and h.get("history"):
    hs = sorted(h["history"], key=lambda x: x["t"])
    step = max(1, len(hs) // 48)
    hist = {
        "token0_outcome": outs[0], "window": ["tip-24h", "tip-1min"], "fidelity": "10m",
        "n_points": len(hs),
        "decimated": [{"t": x["t"], "iso": datetime.datetime.fromtimestamp(x["t"], datetime.timezone.utc).isoformat()[:19], "p": x["p"]} for x in hs[::step]],
        "first": hs[0], "last": hs[-1],
        "min": min(hs, key=lambda x: x["p"]), "max": max(hs, key=lambda x: x["p"]),
        "open_24h_out": hs[0]["p"], "close_pretip": hs[-1]["p"],
    }
    print("POR-OKC ML hist:", outs[0], hs[0]["p"], "->", hs[-1]["p"], "min", hist["min"]["p"], "max", hist["max"]["p"], flush=True)
else:
    hist = {"error": "no history returned", "queried": {"startTs": t0, "endTs": t1}}

board = json.load(open(f"{R47}/board.json"))
board["basketball"]["por_okc_ml_price_history"] = hist
board["fixup_utc"] = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()

# ---------- 2) dedupe other basketball rows ----------
rows = board["basketball"]["other_basketball_boards"]
seen, out = set(), []
for r in rows:
    k = (r["tip_utc"], r["game"])
    if k in seen:
        continue
    seen.add(k)
    out.append(r)
board["basketball"]["other_basketball_boards"] = out
print("dedupe other bkb:", len(rows), "->", len(out), flush=True)

# ---------- 3) depth stats (KBL/B.League/NBL/EuroLeague separately) ----------
def liq_of(r):
    try:
        return float(r.get("liq") or 0)
    except Exception:
        return 0.0
kbl = [r for r in out if "Pegasus" in r["game"] or "Sonic Boom" in r["game"]]
bleague = [r for r in out if any(x in r["game"] for x in ("Chiba", "Osaka Evessa", "Toyama", "Shiga", "Ryukyu", "Yokohama"))]
nbl = [r for r in out if any(x in r["game"] for x in ("36ers", "Wildcats", "JackJumpers", "Melbourne United"))]
euro = [r for r in out if any(x in r["game"] for x in ("Olympiacos", "Milano", "Zalgiris", "Valencia", "Real Madrid", "Crvena", "Maccabi", "Hapoel", "Skyliners", "Roma", "Ulmer"))]
def stat(rows_):
    liqs = sorted(liq_of(r) for r in rows_)
    return {"n": len(rows_), "liq_sum": round(sum(liqs), 2),
            "liq_median": round(liqs[len(liqs)//2], 2) if liqs else 0,
            "liq_min": round(liqs[0], 2) if liqs else 0, "liq_max": round(liqs[-1], 2) if liqs else 0}
board["depth_stats"]["kbl_in_window"] = stat(kbl)
board["depth_stats"]["b_league_in_window"] = stat(bleague)
board["depth_stats"]["nbl_au_in_window"] = stat(nbl)
board["depth_stats"]["euroleague_euro_bkb_in_window"] = stat(euro)

# ---------- 4) pretip model-vs-market for finished shadow rows ----------
sh = json.load(open(f"{R47}/nba_shadow_rows.json"))
for r in sh["rows"]:
    pt = r.get("market_ml_pretip_close")
    mm = r.get("model_vs_market") or {}
    if not pt or not r.get("model"):
        continue
    outs_ml = (r.get("market_ml") or {}).get("outcomes") or []
    if not outs_ml:
        continue
    # map outcome[0] nickname to home/away display name
    hd, ad = (r.get("home_disp") or "").lower(), (r.get("away_disp") or "").lower()
    o0 = str(outs_ml[0]).lower()
    if o0 and o0 in hd and o0 not in ad:
        model_p_o0 = r["model"]["p_home"]
    elif o0 and o0 in ad and o0 not in hd:
        model_p_o0 = r["model"]["p_away"]
    else:
        continue
    mm["pretip"] = {
        "outcome": outs_ml[0], "market_pretip_p": pt.get("last_pretip_p"),
        "model_p_same_outcome": model_p_o0,
        "model_minus_market_pretip_cents": round((model_p_o0 - pt.get("last_pretip_p")) * 100, 2),
        "note": "resolved 0/1 prices are NOT comparable; use this pretip line",
    }
    r["model_vs_market"] = mm
    print("PRETIP", r["game"], outs_ml[0], "mkt", pt.get("last_pretip_p"), "model", model_p_o0,
          "delta_c", mm["pretip"]["model_minus_market_pretip_cents"], flush=True)
json.dump(sh, open(f"{R47}/nba_shadow_rows.json", "w"), indent=1)
json.dump(board, open(f"{R47}/board.json", "w"), indent=1)
print("FIXUP47 DONE", flush=True)
