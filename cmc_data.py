"""
cmc_data.py
Optional second data source (CoinMarketCap free tier) used in /coin
to cross-check price vs CoinGecko and flag significant gaps.
Works fine without a key -- cross-check is just skipped.
"""

import os
import requests

CMC_API_KEY = os.environ.get("CMC_API_KEY", "").strip()
CMC_BASE = "https://pro-api.coinmarketcap.com/v1"


def is_enabled():
    return bool(CMC_API_KEY)


def get_cmc_price(symbol):
    """Return CMC USD price for a symbol, or None if disabled/not found."""
    if not is_enabled():
        return None
    try:
        resp = requests.get(
            f"{CMC_BASE}/cryptocurrency/quotes/latest",
            headers={"X-CMC_PRO_API_KEY": CMC_API_KEY},
            params={"symbol": symbol.upper()},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        entry = data.get("data", {}).get(symbol.upper())
        if isinstance(entry, list):
            entry = entry[0] if entry else None
        if not entry:
            return None
        return entry["quote"]["USD"]["price"]
    except Exception:
        return None


def cross_check(symbol, coingecko_price):
    """
    Returns a dict with cmc_price and a warning string if the two
    sources disagree by more than 3%. Returns None if CMC is disabled.
    """
    cmc_price = get_cmc_price(symbol)
    if cmc_price is None or coingecko_price is None:
        return None

    diff_pct = abs(cmc_price - coingecko_price) / coingecko_price * 100
    warning = None
    if diff_pct > 3:
        warning = f"⚠️ اختلاف {diff_pct:.1f}% بین CoinGecko و CoinMarketCap"
    return {"cmc_price": cmc_price, "diff_pct": round(diff_pct, 2), "warning": warning}
