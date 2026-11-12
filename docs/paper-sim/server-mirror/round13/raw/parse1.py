import json, sys

def games(fname, label):
    d = json.load(open("/home/ubuntu/paper-sim/round13/raw/" + fname))
    print("=" * 25, label)
    for ev in d.get("events", []):
        st = ev.get("status", {}).get("type", {})
        print("GAME:", ev.get("name", "?"), "|", st.get("description", "?"), "|", st.get("detail", ""))
        try:
            comp = ev["competitions"][0]
            for c in comp.get("competitors", []):
                print("   ", c.get("team", {}).get("abbreviation", "?"), c.get("score", "?"),
                      "HOME" if c.get("homeAway") == "home" else "AWAY",
                      c.get("records", [{}])[0].get("summary", "") if c.get("records") else "")
        except Exception as e:
            print("   parse err", e)

games("espn_nba_20261022.json", "NBA Thu Oct 22")
games("espn_nfl_20261022.json", "NFL Thu Oct 22 (TNF wk7)")
games("espn_mlb_now.json", "MLB now")
