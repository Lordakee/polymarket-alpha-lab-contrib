import json, glob

# Extract full token ids for key markets
targets = [
    ("gamma_mlb.json", "Tampa Bay Rays vs. Milwaukee Brewers", None),  # all main + WS champion
]

d = json.load(open("/home/ubuntu/paper-sim/round13/raw/gamma_mlb.json"))
keep = {}
for e in d.get("data", []):
    t = e.get("title") or ""
    if t in ("Tampa Bay Rays vs. Milwaukee Brewers", "MLB World Series Champion 2026"):
        for m in e.get("markets", []):
            q = m.get("question") or ""
            if (q in ("Tampa Bay Rays vs. Milwaukee Brewers", "Will the Tampa Bay Rays win the 2026 World Series?", "Will the Milwaukee Brewers win the 2026 World Series?")
                or "O/U 5.5" in q or "O/U 6.5" in q or q.startswith("Spread: Milwaukee Brewers (-1.5)")):
                toks = m.get("clobTokenIds", "")
                toks = json.loads(toks) if isinstance(toks, str) else toks
                print("EVENT:", t[:40], "| Q:", q[:60], "| close:", m.get("endDate"), "| p:", m.get("outcomePrices"))
                print("   tok0:", toks[0])
                print("   tok1:", toks[1] if len(toks) > 1 else None)

# NBA + NFL key markets
want_nba = ["Trail Blazers vs. Kings", "Knicks vs. Celtics"]
want_nfl = ["Bengals vs. Ravens", "Buccaneers vs. Panthers", "Rams vs. Raiders", "Cowboys vs. Eagles",
            "Chiefs vs. Seahawks", "Broncos vs. Cardinals", "49ers vs. Falcons", "Steelers vs. Saints",
            "Packers vs. Lions", "Dolphins vs. Jets"]
for fn, wants in [("gamma_nba.json", want_nba)] + [("nfl_p%d.json" % o, want_nfl) for o in (0, 100, 200, 300)]:
    d = json.load(open("/home/ubuntu/paper-sim/round13/raw/" + fn))
    for e in d.get("data", []):
        t = e.get("title") or ""
        for w in wants:
            if t == w:
                for m in e.get("markets", []):
                    q = m.get("question") or ""
                    if q == t:  # main moneyline only
                        toks = m.get("clobTokenIds", "")
                        toks = json.loads(toks) if isinstance(toks, str) else toks
                        print("EVENT:", t, "| p:", m.get("outcomePrices"), "| vol24:", m.get("volume24hr"))
                        print("   tok0:", toks[0])
                        print("   tok1:", toks[1] if len(toks) > 1 else None)

# POR playoffs YES token
d = json.load(open("/home/ubuntu/paper-sim/round13/raw/gamma_nba.json"))
for e in d.get("data", []):
    if e.get("title") == "NBA: Team to Make Playoffs":
        for m in e.get("markets", []):
            if "Portland Trail Blazers make the 2027" in (m.get("question") or ""):
                toks = json.loads(m.get("clobTokenIds")) if isinstance(m.get("clobTokenIds"), str) else m.get("clobTokenIds")
                print("POR playoffs YES p:", m.get("outcomePrices"), "vol24:", m.get("volume24hr"))
                print("   tokYes:", toks[0])
                print("   tokNo:", toks[1])
