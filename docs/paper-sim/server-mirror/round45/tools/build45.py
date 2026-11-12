#!/usr/bin/env python3
import json, os
RAW = os.path.expanduser("~/paper-sim/round45/raw")
OUT = os.path.expanduser("~/paper-sim/round45/politics_macro_candidates.json")

def parse_p(p):
    if p is None: return None
    if isinstance(p, str):
        try: p = json.loads(p)
        except Exception: return None
    try: return float(p[0])
    except Exception: return None

def best(book, side):
    lv = (book or {}).get(side) or []
    if not lv: return None
    return min(float(x["price"]) for x in lv) if side == "asks" else max(float(x["price"]) for x in lv)

adv = json.load(open(os.path.join(RAW, "fr_advance_event.json")))["data"][0]
books = json.load(open(os.path.join(RAW, "clob_fr_key_books.json")))
ENTRY_TS = "2026-10-10T14:13"
legs = []
for m in adv.get("markets", []):
    q = m.get("question") or ""
    name = q.replace("Will ", "").replace(" advance to the second round of the next French presidential election?", "")
    yes = parse_p(m.get("outcomePrices"))
    ca = m.get("createdAt") or ""
    held = "MISSED-NOT-IN-BASKET" if "another person" in name else ("ADDED-POST-ENTRY-NOT-HELD" if ca > ENTRY_TS else "HELD-NO")
    b = books.get(q, {}).get("book") or {}
    ya, yb = best(b, "asks"), best(b, "bids")
    legs.append({"name": name, "held": held, "yes_mid": yes, "yes_ask": ya, "yes_bid": yb,
                 "no_bid_exec": round(1 - ya, 4) if ya else None, "no_ask_exec": round(1 - yb, 4) if yb else None,
                 "liquidity": m.get("liquidityNum"), "volume": m.get("volumeNum"), "closed": m.get("closed"),
                 "market_id": m.get("id")})

held_legs = [l for l in legs if l["held"] == "HELD-NO"]
syh = round(sum(l["yes_mid"] for l in held_legs), 4)
sya = round(sum(l["yes_mid"] for l in legs if l["yes_mid"] is not None), 4)
units = 496.0 / 32.996
audit = {
    "position": "#4 FR-2R-ADVANCE-BASKET (decisions.id=4)",
    "entry": {"date": "2026-10-10", "stake_usd": 496.0, "legs": 36, "no_ask_sum_per_unit": 32.996,
              "avg_no_price": 0.9166, "units": round(units, 3),
              "mechanism": "exactly 2 candidates advance (French constitution) -> payoff 36 - #advancers-among-our-legs per unit; resolves Apr 2027 on interieur.gouv.fr"},
    "current_field": {"markets_now": 38, "added_after_entry": ["Christine Lagarde (created 2026-11-06)"],
                      "at_entry_but_not_in_basket": ["another person (no CLOB book; excluded by manifest sum 32.996)"]},
    "current_state": {
        "sum_yes_mids_held_36": syh, "sum_yes_mids_all_38": sya,
        "implied_no_mid_sum_held": round(36 - syh, 4),
        "mid_mark_unrealized_usd": round(units * ((36 - syh) - 32.996), 2),
        "payoff_if_2_of_ours_advance": round(units * 34, 2),
        "payoff_if_1_slot_goes_to_lagarde_or_unlisted": round(units * 35, 2),
        "floor_profit_if_34": round(units * 34 - 496.0, 2),
        "breakeven_note": "3-way exact tie for 2nd (3 advance) -> 33/unit still above 32.996 cost; loss only on 4+ advancing (essentially impossible)"},
    "early_close_verdict": "HOLD all legs to resolution. Executable NO bids on locked-win tail legs are 0.945-0.98 vs 1.00 at Apr-2027 (2-5.5c discount = forgone yield); Le Pen NO salvage ~0.10 is EV-neutral vs 0.105 mid; no positive-expectancy close without a model.",
    "legs": legs,
}
json.dump(audit, open(os.path.join(RAW, "audit45.json"), "w"), indent=1)
print("audit legs:", len(held_legs), "sum YES held:", syh, "implied NO sum:", round(36 - syh, 4))
print("units:", round(units, 3), "payoff34:", round(units * 34, 2), "payoff35:", round(units * 35, 2), "floor profit:", round(units * 34 - 496.0, 2))
