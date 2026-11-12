import json, urllib.request

BOOKS = {
 "POR_playoffs_YES": "64003760005293798440477975810710541346676078429665210936606061785359470439701",
 "WS_champ_Rays": None,
}
# pull from shortlist.json tokens
sl = json.load(open("/home/ubuntu/paper-sim/round12/raw/shortlist.json"))
want = {
 "WS_champ_Rays": ("MLB World Series Champion 2026", 0),
 "WS_champ_Brewers": ("MLB World Series Champion 2026", 1),
 "WS_g1_Rays": ("Tampa Bay Rays vs. Milwaukee Brewers", 0),
 "WS_g1_Brewers": ("Tampa Bay Rays vs. Milwaukee Brewers", 1),
 "NFL_CIN": ("Bengals vs. Ravens", 0),
 "NFL_BAL": ("Bengals vs. Ravens", 1),
 "NFL_SF": ("49ers vs. Falcons", 0),
 "NFL_ATL": ("49ers vs. Falcons", 1),
 "NFL_CLE": ("Browns vs. Titans", 0),
 "NFL_TEN": ("Browns vs. Titans", 1),
 "NFL_KC": ("Chiefs vs. Seahawks", 0),
 "NFL_SEA": ("Chiefs vs. Seahawks", 1),
 "NFL_GB": ("Packers vs. Lions", 0),
 "NFL_DET": ("Packers vs. Lions", 1),
 "NFL_TB": ("Buccaneers vs. Panthers", 0),
 "NFL_CAR": ("Buccaneers vs. Panthers", 1),
 "NFL_LAC": ("Chargers" , 0),
 "NBA_CLE": ("Cavaliers vs. 76ers", 0),
 "NBA_PHI": ("Cavaliers vs. 76ers", 1),
 "NBA_DEN": ("Nuggets vs. Thunder", 0),
 "NBA_OKC": ("Nuggets vs. Thunder", 1),
 "NBA_POR": ("Trail Blazers vs. Kings", 0),
 "NBA_SAC": ("Trail Blazers vs. Kings", 1),
 "NBA_NYK": ("Knicks vs. Celtics", 0),
 "NBA_BOS": ("Knicks vs. Celtics", 1),
 "NFL_DAL": ("Cowboys vs. Eagles", 0),
 "NFL_PHI_E": ("Cowboys vs. Eagles", 1),
}
tokmap = {k: v[0] for k, v in BOOKS.items() if v}
for rec in sl:
    t = rec["event"]
    for m in rec["markets"]:
        for key, (ev, idx) in want.items():
            if ev == t and m["q"].strip() == t and len(m.get("tokens", [])) > idx:
                tokmap.setdefault(key, m["tokens"][idx])

out = {}
for key, tok in tokmap.items():
    if not tok:
        continue
    try:
        u = "https://clob.polymarket.com/book?token_id=%s" % tok
        r = json.load(urllib.request.urlopen(u, timeout=15))
        bids = sorted(r.get("bids", []), key=lambda x: -float(x["price"]))[:3]
        asks = sorted(r.get("asks", []), key=lambda x: float(x["price"]))[:3]
        def side(lst):
            return [(float(x["price"]), float(x["size"])) for x in lst]
        bidsum = sum(float(x["size"]) for x in r.get("bids", []) if float(x["price"]) >= 0.05)
        asksum = sum(float(x["size"]) for x in r.get("asks", []) if float(x["price"]) <= 0.95)
        out[key] = {"bids": side(bids), "asks": side(asks), "bid_depth": round(bidsum), "ask_depth": round(asksum)}
        print(key, "bids:", out[key]["bids"], "asks:", out[key]["asks"], "depth(b/a):", out[key]["bid_depth"], "/", out[key]["ask_depth"])
    except Exception as ex:
        print(key, "ERR", ex)
json.dump(out, open("/home/ubuntu/paper-sim/round12/raw/books.json", "w"), indent=1)
