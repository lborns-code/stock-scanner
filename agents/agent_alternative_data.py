"""
Alternative Data Agent — V4
מנתח נתונים לא מסורתיים: insider buying, job postings, web momentum
"""
import logging
import requests
from datetime import datetime, timedelta

try:
    import feedparser
    _FEEDPARSER_OK = True
except ImportError:
    _FEEDPARSER_OK = False

logger = logging.getLogger(__name__)


def _get_insider_data(ticker: str) -> dict:
    """Insider buying מ-OpenInsider (חינם, ללא API key)."""
    try:
        url = f"http://openinsider.com/screener?s={ticker}&fd=30&o=&b=1"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=8)
        text = resp.text

        buy_count = text.count("Purchase")
        cluster_buy = buy_count >= 2
        any_buy = buy_count >= 1
        ceo_buy = "CEO" in text or "Chief Executive" in text
        cfo_buy = "CFO" in text or "Chief Financial" in text

        score = 5.0
        if cluster_buy: score += 2.0
        elif any_buy:   score += 1.0
        if ceo_buy:     score += 1.5
        if cfo_buy:     score += 1.0

        return {
            "buy_count_30d":  buy_count,
            "cluster_buying": cluster_buy,
            "any_buy":        any_buy,
            "ceo_buying":     ceo_buy,
            "cfo_buying":     cfo_buy,
            "insider_score":  round(min(score, 10), 1),
            "signal": "🟢 Cluster Buy" if cluster_buy
                      else "🟡 Single Buy" if any_buy
                      else "⚪ No Activity",
        }
    except Exception as e:
        logger.debug(f"Insider data {ticker}: {e}")
        return {"insider_score": 5.0, "signal": "N/A",
                "cluster_buying": False, "any_buy": False, "ceo_buying": False,
                "buy_count_30d": 0}


def _get_job_trend(company_name: str) -> dict:
    """מגמת משרות דרך Google News RSS (חינם)."""
    if not _FEEDPARSER_OK:
        return {"job_trend_score": 5.0, "hiring_signals_found": 0, "signal": "N/A"}
    try:
        query = f"{company_name} hiring jobs expansion"
        url = f"https://news.google.com/rss/search?q={query.replace(' ', '+')}&hl=en"
        feed = feedparser.parse(url)
        entries = feed.entries[:10]

        hiring_signals = 0
        for e in entries:
            title = (e.get("title", "") + e.get("summary", "")).lower()
            if any(w in title for w in
                   ["hiring", "expanding", "growth", "new office",
                    "headcount", "workforce", "recruit", "jobs"]):
                hiring_signals += 1

        score = 5.0
        if hiring_signals >= 3: score += 2.0
        elif hiring_signals >= 1: score += 1.0

        return {
            "hiring_signals_found": hiring_signals,
            "job_trend_score":      round(min(score, 10), 1),
            "signal": "🟢 מגייסת אגרסיבית" if hiring_signals >= 3
                      else "🟡 מגייסת" if hiring_signals >= 1
                      else "⚪ לא נמצא מידע",
        }
    except Exception as e:
        logger.debug(f"Job trend {company_name}: {e}")
        return {"job_trend_score": 5.0, "hiring_signals_found": 0, "signal": "N/A"}


def _get_web_momentum(ticker: str, company_name: str) -> dict:
    """מומנטום מדיה דרך Yahoo Finance RSS (חינם)."""
    if not _FEEDPARSER_OK:
        return {"web_momentum_score": 5.0, "news_count_7d": 0, "signal": "N/A"}
    try:
        url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}"
        feed = feedparser.parse(url)
        week_ago = datetime.now() - timedelta(days=7)

        recent = []
        for e in feed.entries:
            try:
                if hasattr(e, "published_parsed") and e.published_parsed:
                    pub = datetime(*e.published_parsed[:6])
                    if pub > week_ago:
                        recent.append(e)
            except Exception:
                pass

        positive_words = ["surge", "jump", "beat", "record", "growth",
                          "upgrade", "buy", "strong", "bullish", "expand"]
        negative_words = ["fall", "miss", "drop", "cut", "weak",
                          "downgrade", "sell", "loss", "bearish"]

        pos = sum(1 for e in recent
                  if any(w in e.get("title", "").lower() for w in positive_words))
        neg = sum(1 for e in recent
                  if any(w in e.get("title", "").lower() for w in negative_words))

        score = 5.0
        if len(recent) > 10: score += 0.5
        if pos > neg * 2:    score += 1.5
        elif pos > neg:      score += 0.8
        elif neg > pos * 2:  score -= 1.5

        return {
            "news_count_7d":      len(recent),
            "positive_headlines": pos,
            "negative_headlines": neg,
            "web_momentum_score": round(min(max(score, 0), 10), 1),
            "signal": "🟢 מומנטום חיובי" if pos > neg
                      else "🔴 מומנטום שלילי" if neg > pos
                      else "⚪ ניטרלי",
        }
    except Exception as e:
        logger.debug(f"Web momentum {ticker}: {e}")
        return {"web_momentum_score": 5.0, "news_count_7d": 0, "signal": "N/A"}


def _calc_alt_score(results: dict) -> float:
    insider_score = results.get("insider", {}).get("insider_score", 5.0)
    job_score     = results.get("jobs", {}).get("job_trend_score", 5.0)
    web_score     = results.get("web_momentum", {}).get("web_momentum_score", 5.0)

    weighted = (
        insider_score * 0.45 +
        job_score     * 0.30 +
        web_score     * 0.25
    )
    if results.get("insider", {}).get("cluster_buying"): weighted += 0.5
    if results.get("insider", {}).get("ceo_buying"):     weighted += 0.3
    return round(min(max(weighted, 0), 10), 1)


def analyze(ticker: str, company_name: str) -> dict:
    results = {}
    results["insider"]      = _get_insider_data(ticker)
    results["jobs"]         = _get_job_trend(company_name)
    results["web_momentum"] = _get_web_momentum(ticker, company_name)
    results["alt_data_score"] = _calc_alt_score(results)
    return results
