import logging

logger = logging.getLogger(__name__)

ANALYST_QUALITY_WEIGHTS = {
    "RBC Capital":     1.4,
    "Oppenheimer":     1.4,
    "Bank of America": 1.3,
    "Evercore":        1.3,
    "Wedbush":         1.3,
    "Goldman Sachs":   1.2,
    "Morgan Stanley":  1.2,
    "JPMorgan":        1.1,
    "Rosenblatt":      1.2,
    "default":         1.0,
}


def get_weighted_analyst_score(data: dict) -> float:
    consensus = data.get("analyst_consensus", "hold") or "hold"
    count = data.get("analyst_count", 0) or 0
    target = data.get("analyst_target_mean", 0) or 0
    current = data.get("current_price", 1) or 1
    upside = (target - current) / current if current > 0 else 0

    score = 5.0
    if consensus in ["strongBuy", "buy"]:         score += 1.5
    elif consensus == "hold":                      score += 0.0
    elif consensus in ["sell", "underperform"]:    score -= 1.5

    if upside > 0.30:   score += 1.0
    elif upside > 0.15: score += 0.5
    elif upside < 0:    score -= 1.0

    if count > 20:  score += 0.5
    elif count < 5: score -= 0.3

    return round(min(max(score, 0), 10), 1)


def analyze_all(stocks: list) -> list:
    logger.info(f"Agent5: sentiment עבור {len(stocks)} מניות...")
    for s in stocks:
        s["sentiment_score"] = get_weighted_analyst_score(s)
    return stocks
