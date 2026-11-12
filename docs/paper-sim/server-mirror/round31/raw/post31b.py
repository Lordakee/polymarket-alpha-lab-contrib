"""Round-31 prices-only regeneration: replace the parse-taxonomy prices_only
section with verbatim gamma quotes for model-void fixtures (ENG2/MLS/etc).
The r31 scan's parse_market_sides(m, None, None) mislabeled sides on
model-void fixtures (canon None == home None -> every team 'home'); the
modelable board is unaffected. Prices-only gets verbatim q/outcomes/bid/ask."""
import json
import re

P = "/home/ubuntu/paper-sim/round31/raw/soccer_scan.json"
E = "/home/ubuntu/paper-sim/round31/raw/events_window_31.json"

d = json.load(open(P))
evs = json.load(open(E))

PRICES_ONLY_COMP = {"ENG2", "MLS", "EFL_TROPHY", "BRA", "MEX", "ARG"}


def base_title(t):
    return re.split(r"\s+-\s+", t, maxsplit=1)[0]


CORE = re.compile(
    r"(O/U |over/under|Both teams|win on 2026|end in a draw|Spread: |"
    r"to score over|to score under)", re.I)
SKIP = re.compile(
    r"(Exact Score|First Team|Halftime|Second Half|Corners|leading at "
    r"halftime|Neither team|score first|When|Which|Will both teams "
    r"score.*1st)", re.I)

by_fix = {}
for e in evs:
    bt = base_title(e.get("title") or "")
    k = (e["kick"], bt)
    by_fix.setdefault(k, {"kick": e["kick"], "base": bt, "markets": {}})
    for m in e["markets"]:
        q = m.get("q") or ""
        if SKIP.search(q):
            continue
        if not CORE.search(q):
            continue
        mid = str(m.get("id"))
        if mid not in by_fix[k]["markets"]:
            outs = m.get("outcomes") or []
            prs = m.get("prices") or []
            by_fix[k]["markets"][mid] = {
                "q": q, "outcomes": outs,
                "prices_by_outcome": dict(zip(outs, prs)) if outs else {},
                "bid": m.get("bestBid"), "ask": m.get("bestAsk"),
                "liq": m.get("liq"), "vol24": m.get("vol24")}

# figure out which fixtures are model-void-with-PM-markets: comp in
# PRICES_ONLY_COMP from the fixtures list
void_keys = set()
for f in d["fixtures"]:
    if f.get("comp") in PRICES_ONLY_COMP:
        bt = base_title(f["title"])
        void_keys.add((f["kickoff_utc"], bt))

new_prices = []
for k in sorted(void_keys):
    grp = by_fix.get(k)
    if not grp:
        continue
    new_prices.append({
        "match": k[1], "kickoff_utc": k[0],
        "note": ("model-void (league outside Understat Big-5 universe): "
                 "gamma quotes verbatim; no model, no gates, no candidacy"),
        "n_core_markets": len(grp["markets"]),
        "markets": sorted(grp["markets"].values(),
                          key=lambda m: (str(m["q"]))),
    })

d["prices_only"] = new_prices
d["prices_only_note"] = (
    "regenerated verbatim from gamma events post-scan: the in-scan "
    "parse taxonomy mislabeled sides on model-void fixtures "
    "(team_side_of None==None collision); quotes are the market's own "
    "bestBid/bestAsk/liquidity, not CLOB walks; CLOB ask-VWAP250s for "
    "ENG2 main markets are preserved in odds_board_31.json prices_only "
    "supersede this where present")
json.dump(d, open(P, "w"), indent=1)
print("prices_only fixtures:", len(new_prices))
for p in new_prices:
    print("  %-44s %s core_markets=%d" % (p["match"][:44], p["kickoff_utc"],
                                          p["n_core_markets"]))
# quick sample: Cardiff-West Ham full core board
for p in new_prices:
    if "Cardiff" in p["match"]:
        print()
        print("CARDIFF-WEST HAM core markets (gamma verbatim):")
        for m in p["markets"]:
            print("   %-72s outs=%s bid=%s ask=%s liq=$%s" % (
                m["q"][:72], m["outcomes"], m["bid"], m["ask"],
                int(m["liq"] or 0)))
