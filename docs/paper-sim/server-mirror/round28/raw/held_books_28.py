"""Round-28 held-position verification (T-5h before Sassuolo 17:30Z kickoff).

Paper-only: reads current Gamma meta + live CLOB books (FULL ladders) for the
two held paper positions (#54 Sassuolo ML Yes $150 @0.3374; #50 Depor-Osasuna
O2.5 Over $250 @0.425). Explicitly re-checks the r27 overnight ask-ladder
withdrawal anomaly on #54 (no asks < 0.87 at 04:55Z). No orders, no credentials.
"""
import json
import time
import urllib.request
from datetime import datetime, timezone

HELD = [
    {"pos_id": 54, "market_id": "5950736",
     "market": "Will US Sassuolo Calcio win on 2026-11-02? (Sassuolo vs Fiorentina)",
     "entry_side": "YES", "stake_usd": 150, "entry_price": 0.3374, "ceiling": 0.36,
     "anomaly_check": "r27 04:55Z: live CLOB asks nothing below 0.87 (sell side withdrawn)"},
    {"pos_id": 50, "market_id": "5963792",
     "market": "RC Deportivo A Coruna vs. CA Osasuna: O/U 2.5 Over (Mon 2026-11-02 20:00Z)",
     "entry_side": "Over YES", "stake_usd": 250, "entry_price": 0.425,
     "exit_ask_trigger": 0.50, "take_profit_bid": 0.51,
     "anomaly_check": "r27 04:55Z: no asks below 0.69 on this book too"},
]
OUT = "/home/ubuntu/paper-sim/round28/raw/held_books_28.json"


def get(url, tries=5):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research)"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2.0 + 2 * i)
    raise last


def main():
    out = {"check_type": "round-28 Monday T-5h held verification",
           "checked_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "paper_only": True, "positions": {}}
    for h in HELD:
        gamma = get("https://gamma-api.polymarket.com/markets/" + h["market_id"])
        tokens = gamma.get("clobTokenIds") or []
        tokens = json.loads(tokens) if isinstance(tokens, str) else tokens
        outcomes = gamma.get("outcomes") or []
        outcomes = json.loads(outcomes) if isinstance(outcomes, str) else outcomes
        prices = gamma.get("outcomePrices") or []
        prices = json.loads(prices) if isinstance(prices, str) else prices
        yes_idx = 0
        for i, o in enumerate(outcomes):
            if str(o).lower() in ("yes", "over"):
                yes_idx = i
        book = {}
        if tokens:
            b = get("https://clob.polymarket.com/book?token_id=" + tokens[yes_idx])
            asks = sorted(((float(l["price"]), float(l["size"])) for l in b.get("asks", [])))
            bids = sorted(((float(l["price"]), float(l["size"])) for l in b.get("bids", [])),
                          reverse=True)
            book = {"bids_top10": bids[:10], "asks_top10": asks[:10],
                    "n_ask_levels": len(asks), "n_bid_levels": len(bids),
                    "best_bid": bids[0][0] if bids else None,
                    "best_ask": asks[0][0] if asks else None,
                    "min_ask": asks[0][0] if asks else None,
                    "bid_size_top": bids[0][1] if bids else 0,
                    "ask_size_top": asks[0][1] if asks else 0,
                    "spread": (asks[0][0] - bids[0][0]) if bids and asks else None,
                    "ask_notional_first5": round(sum(p * s for p, s in asks[:5]), 0)}
        mid = None
        if book.get("best_bid") and book.get("best_ask"):
            mid = round((book["best_bid"] + book["best_ask"]) / 2, 4)
        out["positions"]["%d_%s" % (h["pos_id"], h["market_id"])] = {
            "entry": {k: h[k] for k in h if k not in ("market_id", "pos_id")},
            "gamma": {"question": gamma.get("question"),
                      "outcomes": outcomes, "prices": prices,
                      "bestBid": gamma.get("bestBid"), "bestAsk": gamma.get("bestAsk"),
                      "lastTradePrice": gamma.get("lastTradePrice"),
                      "liquidityNum": gamma.get("liquidityNum"),
                      "volumeNum": gamma.get("volumeNum"),
                      "volume24hr": gamma.get("volume24hr"),
                      "active": gamma.get("active"), "closed": gamma.get("closed"),
                      "gameStartTime": gamma.get("gameStartTime")},
            "clob": book, "mid": mid,
        }
        time.sleep(0.5)
    json.dump(out, open(OUT, "w"), indent=1)
    print(json.dumps({k: {"best_bid": v["clob"].get("best_bid"),
                          "best_ask": v["clob"].get("best_ask"),
                          "mid": v.get("mid"),
                          "n_ask_levels": v["clob"].get("n_ask_levels"),
                          "asks_top5": v["clob"].get("asks_top10", [])[:5]}
                     for k, v in out["positions"].items()}, indent=1))
    print("saved", OUT)


if __name__ == "__main__":
    main()
