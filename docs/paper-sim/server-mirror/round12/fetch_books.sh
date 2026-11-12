#!/bin/bash
TOK_PY=/home/ubuntu/paper-sim/round12/tokens.json
python3 - << "PYEOF" > "$TOK_PY"
import json
sl = json.load(open("/home/ubuntu/paper-sim/round12/raw/shortlist.json"))
want = {
 "WS_champ_Rays": ("MLB World Series Champion 2026", 0),
 "WS_champ_Brewers": ("MLB World Series Champion 2026", 1),
 "WS_g1_Rays": ("Tampa Bay Rays vs. Milwaukee Brewers", 0),
 "WS_g1_Brewers": ("Tampa Bay Rays vs. Milwaukee Brewers", 1),
 "NFL_CIN": ("Bengals vs. Ravens", 0), "NFL_BAL": ("Bengals vs. Ravens", 1),
 "NFL_SF": ("49ers vs. Falcons", 0), "NFL_ATL": ("49ers vs. Falcons", 1),
 "NFL_CLE": ("Browns vs. Titans", 0), "NFL_TEN": ("Browns vs. Titans", 1),
 "NFL_KC": ("Chiefs vs. Seahawks", 0), "NFL_SEA": ("Chiefs vs. Seahawks", 1),
 "NFL_GB": ("Packers vs. Lions", 0), "NFL_DET": ("Packers vs. Lions", 1),
 "NFL_TB": ("Buccaneers vs. Panthers", 0), "NFL_CAR": ("Buccaneers vs. Panthers", 1),
 "NBA_CLE": ("Cavaliers vs. 76ers", 0), "NBA_PHI": ("Cavaliers vs. 76ers", 1),
 "NBA_DEN": ("Nuggets vs. Thunder", 0), "NBA_OKC": ("Nuggets vs. Thunder", 1),
 "NBA_POR": ("Trail Blazers vs. Kings", 0), "NBA_SAC": ("Trail Blazers vs. Kings", 1),
 "NBA_NYK": ("Knicks vs. Celtics", 0), "NBA_BOS": ("Knicks vs. Celtics", 1),
 "NFL_DAL": ("Cowboys vs. Eagles", 0), "NFL_PHI_E": ("Cowboys vs. Eagles", 1),
}
tokmap = {"POR_playoffs_YES": "64003760005293798440477975810710541346676078429665210936606061785359470439701"}
for rec in sl:
    t = rec["event"]
    for m in rec["markets"]:
        for key, (ev, idx) in want.items():
            if ev == t and m["q"].strip() == t and len(m.get("tokens", [])) > idx:
                tokmap.setdefault(key, m["tokens"][idx])
print(json.dumps(tokmap))
PYEOF
mkdir -p /home/ubuntu/paper-sim/round12/raw/books
for key in $(python3 -c "import json; print(\" \".join(json.load(open(\"$TOK_PY\")).keys()))"); do
  tok=$(python3 -c "import json; print(json.load(open(\"$TOK_PY\"))[\"$key\"])")
  curl -s "https://clob.polymarket.com/book?token_id=$tok" -o /home/ubuntu/paper-sim/round12/raw/books/$key.json
  echo "$key done ($(wc -c < /home/ubuntu/paper-sim/round12/raw/books/$key.json) bytes)"
done
