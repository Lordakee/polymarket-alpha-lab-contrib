"""ROUND-47 fixup b: correct ou25/total-ladder parsing for UNL + Copa rows.
The generic 'o/u N$' regex also matched 1st-half and team-total rungs; recompute
with exact-match on the main match-total question "<root>: O/U <N>".
PAPER ONLY - GET-only HTTP, no DB writes."""
import json, re, time, urllib.request, datetime

R47 = "/home/ubuntu/paper-sim/round47"
G = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"

def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except Exception as ex:
            print("ERR", url[:110], str(ex)[:60], flush=True)
            time.sleep(2.0)
    return None

# id -> title map from raw sweeps (to find the More Markets events)
id2title = {}
for src in ["tag_uefa_nations_league", "tag_copa_del_rey", "tag_soccer"]:
    try:
        evs = json.load(open(f"{R47}/raw/{src}.json"))["data"]
    except Exception:
        continue
    for e in evs:
        id2title[str(e.get("id"))] = str(e.get("title"))

board = json.load(open(f"{R47}/board.json"))
sections = [("nations_league_nov12", board["soccer"]["nations_league_nov12"]),
            ("copa_del_rey_nov12", board["soccer"]["copa_del_rey_nov12"])]
for sec, rows in sections:
    for row in rows:
        root = row["fixture"]
        mm_ids = [i for i in row["gamma_event_ids"]
                  if id2title.get(i, "").endswith(" - More Markets")]
        ou25 = None
        ladder = {}
        o25_m = None
        for eid in mm_ids:
            ev = get(f"{G}/events/{eid}?include_markets=true")
            time.sleep(0.3)
            if not ev:
                continue
            for m in ev.get("markets") or []:
                q = str(m.get("question") or "")
                mo = re.fullmatch(re.escape(root) + r": O/U (\d+\.\d)", q)
                if not mo:
                    continue
                try:
                    px = [float(x) for x in json.loads(m.get("outcomePrices") or "[]")]
                except Exception:
                    continue
                line = mo.group(1)
                ladder[line] = px[0]
                if line == "2.5":
                    ou25 = px[0]
                    o25_m = m
        row["ou25_yes_price"] = ou25
        row["total_ladder_prices"] = dict(sorted(ladder.items()))
        row["total_ladder_scope"] = "match totals only (exact '<root>: O/U N' match)"
        if o25_m:
            try:
                toks = json.loads(o25_m.get("clobTokenIds") or "[]")
                if toks:
                    b = get(f"{CLOB}/book?token_id={toks[0]}")
                    if b:
                        bids = sorted([(float(l["price"]), l["size"]) for l in (b.get("bids") or [])], key=lambda x: -x[0])[:3]
                        asks = sorted([(float(l["price"]), l["size"]) for l in (b.get("asks") or [])], key=lambda x: x[0])[:3]
                        row["clob_books"] = [x for x in (row.get("clob_books") or []) if x["label"] != "O2.5"]
                        row["clob_books"].append({"label": "O2.5(match-total, corrected)",
                                                  "token": str(toks[0])[:12] + "...",
                                                  "bids": bids, "asks": asks})
                    time.sleep(0.25)
            except Exception:
                pass
        print(sec[:4], root[:38], "O2.5", ou25, "ladder", ladder, flush=True)
board["fixup_b_utc"] = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
json.dump(board, open(f"{R47}/board.json", "w"), indent=1)
print("FIXUP47B DONE", flush=True)
