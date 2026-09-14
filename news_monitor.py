"""
news_monitor.py
Polls free crypto RSS feeds looking for mentions of notable figures
(e.g. Elon Musk) alongside coin names, for early alert purposes.
"""

import feedparser

RSS_FEEDS = [
    "https://cointelegraph.com/rss",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cryptoslate.com/feed/",
]

NOTABLE_FIGURES = [
    "elon musk", "donald trump", "michael saylor", "vitalik buterin",
    "cz binance", "changpeng zhao",
]

# Track which entry links we've already alerted on, to avoid duplicates
_seen_links = set()


def check_for_mentions():
    """
    Returns a list of {title, link, figure, source} for any new RSS
    entries that mention a notable figure. Call this on a schedule
    (e.g. every 5 minutes) from the bot's background job.
    """
    alerts = []
    for feed_url in RSS_FEEDS:
        try:
            parsed = feedparser.parse(feed_url)
        except Exception:
            continue

        for entry in parsed.entries[:30]:
            link = entry.get("link")
            if not link or link in _seen_links:
                continue

            text = (entry.get("title", "") + " " + entry.get("summary", "")).lower()
            for figure in NOTABLE_FIGURES:
                if figure in text:
                    alerts.append({
                        "title": entry.get("title"),
                        "link": link,
                        "figure": figure.title(),
                        "source": feed_url,
                    })
                    _seen_links.add(link)
                    break

    return alerts
