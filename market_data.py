"""
market_data.py
Free CoinGecko API wrapper: top coins, coin detail, simple RSI,
24h movers, and scored /picks shortlists (mainstream + early/small-cap).
"""

import time
import requests

COINGECKO_BASE = "https://api.coingecko.com/api/v3"

# Simple in-memory cache so we don't hammer the free CoinGecko rate limit
_cache = {}
CACHE_TTL = 60  # seconds


def _get(url, params=None, retries=3):
    """GET with basic retry/backoff for CoinGecko free-tier rate limits."""
    key = url + str(params)
    now = time.time()
    if key in _cache and now - _cache[key][0] < CACHE_TTL:
        return _cache[key][1]

    last_err = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 429:
                time.sleep(2 ** attempt * 2)
                continue
            resp.raise_for_status()
            data = resp.json()
            _cache[key] = (now, data)
            return data
        except Exception as e:
            last_err = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"CoinGecko request failed after retries: {last_err}")


def _risk_label(market_cap_rank, volatility_24h):
    if market_cap_rank is None:
        return "🔴 خیلی پرریسک (رنک نامشخص)"
    if market_cap_rank <= 50:
        return "🟢 کم‌ریسک (بزرگ)"
    if market_cap_rank <= 250:
        return "🟡 ریسک متوسط"
    if market_cap_rank <= 750:
        return "🟠 پرریسک (کوچک/جدید)"
    return "🔴 خیلی پرریسک (خیلی کوچک/جدید)"


def get_top_coins(limit=250, page=1):
    """Return top coins by market cap with key stats."""
    data = _get(
        f"{COINGECKO_BASE}/coins/markets",
        params={
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": min(limit, 250),
            "page": page,
            "price_change_percentage": "24h,7d",
        },
    )
    coins = []
    for c in data:
        coins.append({
            "id": c["id"],
            "symbol": c["symbol"].upper(),
            "name": c["name"],
            "price": c.get("current_price"),
            "market_cap_rank": c.get("market_cap_rank"),
            "volume_24h": c.get("total_volume"),
            "change_24h": c.get("price_change_percentage_24h"),
            "change_7d": c.get("price_change_percentage_7d_in_currency"),
            "risk": _risk_label(c.get("market_cap_rank"), c.get("price_change_percentage_24h") or 0),
        })
    return coins


def get_coin_detail(coin_id):
    """Full detail for one coin: price, age, sentiment, scam-risk flags, RSI."""
    data = _get(
        f"{COINGECKO_BASE}/coins/{coin_id}",
        params={
            "localization": "false",
            "tickers": "false",
            "market_data": "true",
            "community_data": "true",
            "developer_data": "true",
            "sparkline": "true",
        },
    )

    market = data.get("market_data", {})
    prices = market.get("sparkline_7d", {}).get("price", [])
    rsi = calculate_rsi(prices) if prices else None

    genesis_date = data.get("genesis_date")
    age_days = None
    if genesis_date:
        from datetime import datetime
        try:
            age_days = (datetime.utcnow() - datetime.strptime(genesis_date, "%Y-%m-%d")).days
        except Exception:
            age_days = None

    sentiment_up = data.get("sentiment_votes_up_percentage")

    scam_flags = []
    if age_days is not None and age_days < 30:
        scam_flags.append("کوین خیلی جدید (کمتر از ۳۰ روز)")
    if not data.get("links", {}).get("homepage", [None])[0]:
        scam_flags.append("وبسایت رسمی ثبت نشده")
    liquidity = market.get("total_volume", {}).get("usd", 0) or 0
    mcap = market.get("market_cap", {}).get("usd", 0) or 0
    if mcap and liquidity and (liquidity / mcap) < 0.02:
        scam_flags.append("نقدشوندگی/حجم معاملات خیلی پایین نسبت به مارکت‌کپ")
    if data.get("market_cap_rank") is None:
        scam_flags.append("در رنک‌بندی مارکت‌کپ نیست")

    explorer_links = []
    platforms = data.get("platforms", {}) or {}
    explorer_map = {
        "ethereum": "https://etherscan.io/address/",
        "binance-smart-chain": "https://bscscan.com/address/",
        "polygon-pos": "https://polygonscan.com/address/",
        "arbitrum-one": "https://arbiscan.io/address/",
    }
    for platform, address in platforms.items():
        if address and platform in explorer_map:
            explorer_links.append(explorer_map[platform] + address)

    return {
        "id": data.get("id"),
        "symbol": (data.get("symbol") or "").upper(),
        "name": data.get("name"),
        "price": market.get("current_price", {}).get("usd"),
        "market_cap_rank": data.get("market_cap_rank"),
        "change_24h": market.get("price_change_percentage_24h"),
        "change_7d": market.get("price_change_percentage_7d"),
        "rsi": rsi,
        "age_days": age_days,
        "sentiment_up_pct": sentiment_up,
        "scam_flags": scam_flags,
        "explorer_links": explorer_links,
        "risk": _risk_label(data.get("market_cap_rank"), market.get("price_change_percentage_24h") or 0),
    }


def calculate_rsi(prices, period=14):
    """Simple RSI over a price list (e.g. 7d hourly sparkline)."""
    if len(prices) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)


def get_movers(limit=250):
    """Flag coins with unusual 24h volume or price swings."""
    coins = get_top_coins(limit=limit)
    movers = []
    for c in coins:
        change = c["change_24h"] or 0
        if abs(change) >= 15:
            movers.append(c)
    movers.sort(key=lambda c: abs(c["change_24h"] or 0), reverse=True)
    return movers[:20]


def get_picks(early=False):
    """
    Scored shortlist:
    - early=False: ranks up to 500, positive weekly trend + liquidity + no sharp recent drop
    - early=True:  ranks ~250-750, same scoring, labeled very-high-risk
    """
    page1 = get_top_coins(limit=250, page=1)
    page2 = get_top_coins(limit=250, page=2)
    page3 = get_top_coins(limit=250, page=3) if early else []
    pool = page1 + page2 + (page3 if early else [])

    if early:
        pool = [c for c in pool if c["market_cap_rank"] and 250 <= c["market_cap_rank"] <= 750]
    else:
        pool = [c for c in pool if c["market_cap_rank"] and c["market_cap_rank"] <= 500]

    scored = []
    for c in pool:
        change_7d = c["change_7d"] or 0
        change_24h = c["change_24h"] or 0
        volume = c["volume_24h"] or 0

        if change_7d <= 0:
            continue
        if change_24h <= -12:  # sharp recent drop -> skip
            continue
        if volume < 100_000:  # liquidity floor
            continue

        score = change_7d * 1.0 + min(volume / 1_000_000, 10) * 2
        scored.append({**c, "score": round(score, 2)})

    scored.sort(key=lambda c: c["score"], reverse=True)
    top = scored[:8]
    if early:
        for c in top:
            c["risk"] = "🔴 خیلی پرریسک (Early Pick)"
    return top
