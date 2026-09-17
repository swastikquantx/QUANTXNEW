"""QuantX AI — LIVE crypto data via CoinGecko free public API (no key).

Simple in-memory TTL cache to respect rate limits. Falls back gracefully.
"""
import time
import requests

_CACHE = {}
_TTL = 60  # seconds

CG_MARKETS = "https://api.coingecko.com/api/v3/coins/markets"

# stable curated top set (ids) so the table is consistent
COIN_IDS = [
    "bitcoin", "ethereum", "tether", "binancecoin", "solana", "ripple",
    "usd-coin", "cardano", "dogecoin", "tron", "avalanche-2", "chainlink",
    "polkadot", "polygon-ecosystem-token", "litecoin", "shiba-inu",
    "uniswap", "cosmos", "stellar", "near",
]


def _cached(key):
    v = _CACHE.get(key)
    if v and (time.time() - v[0] < _TTL):
        return v[1]
    return None


def top_coins(limit: int = 20):
    key = f"markets:{limit}"
    hit = _cached(key)
    if hit is not None:
        return hit
    try:
        resp = requests.get(
            CG_MARKETS,
            params={
                "vs_currency": "usd",
                "ids": ",".join(COIN_IDS[:limit]),
                "order": "market_cap_desc",
                "per_page": limit,
                "page": 1,
                "sparkline": "false",
                "price_change_percentage": "24h",
            },
            headers={"accept": "application/json"},
            timeout=12,
        )
        resp.raise_for_status()
        data = resp.json()
        rows = []
        for c in data:
            change = c.get("price_change_percentage_24h") or 0.0
            direction = "BULLISH" if change > 0.3 else "BEARISH" if change < -0.3 else "NEUTRAL"
            rows.append({
                "symbol": (c.get("symbol") or "").upper(),
                "name": c.get("name"),
                "ltp": c.get("current_price"),
                "change_pct": round(change, 2),
                "market_cap": c.get("market_cap"),
                "volume": c.get("total_volume"),
                "confluence": None,
                "direction": direction,
                "data_source": "LIVE",
                "segment": "CRYPTO",
                "coin_id": c.get("id"),
            })
        _CACHE[key] = (time.time(), rows)
        return rows
    except Exception:
        stale = _CACHE.get(key)
        if stale:
            return stale[1]
        return []
