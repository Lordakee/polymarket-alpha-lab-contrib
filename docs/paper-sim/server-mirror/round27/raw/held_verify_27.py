"""Round-27 held-position verification (T-minus ~13h pre-news window).

Paper-only: reads current CLOB books + Gamma mids for the two held paper
positions (#54 Sassuolo ML Yes, #50 Depor-Osasuna O2.5 Over Yes) and writes
round27/raw/held_books_27.json. No orders, no credentials.
"""
import json
import time
import urllib.request
from datetime import datetime, timezone

HELD = [
    {"pos_id": 54, "market_id": "5950736",
     "market": "Will US Sassuolo Calcio win on 2026-11-02? (Sassuolo vs Fiorentina)",
     "entry_side": "YES", "stake_usd": 150, "entry_price": 0.3374, "ceiling": 0.36},
    {"pos_id": 50, "market_id": "5963792",
     "market": "RC Deportivo A Coruna vs. CA Osasuna: O/U 2.5 Over (Mon 2026-11-02 20:00Z)",
     "entry_side": "Over YES", "stake_usd": 250, "entry_price": 0.425,
     "exit_ask_trigger": 0.50, "take_profit_bid": 0.51},
]
OUT = "/home/ubuntu/paper-sim/round27/raw/held_books_27.json"


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
    out = {"check_type": "round-27 Monday pre-news verification (T-13h)",
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
            asks = sorted(((float(l["price"]), float(l["size"])) for l in b.get("asks", [])),
                          reverse=True)
            bids = sorted(((float(l["price"]), float(l["size"])) for l in b.get("bids", [])),
                          reverse=True)
            book = {"bids_top8": bids[:8], "asks_top8": asks[:8],
                    "best_bid": bids[0][0] if bids else None,
                    "best_ask": asks[0][0] if asks else None,
                    "bid_size_top": bids[0][1] if bids else 0,
                    "ask_size_top": asks[0][1] if asks else 0,
                    "spread": (asks[0][0] - bids[0][0]) if bids and asks else None}
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
    print(json.dumps(out, indent=1))
    print("saved", OUT)


if __name__ == "__main__":
    main()
