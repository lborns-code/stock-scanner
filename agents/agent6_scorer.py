import logging
from agents.agent4_technical import get_action_recommendation

logger = logging.getLogger(__name__)

WEIGHTS = {
    "moat_score":              0.20,
    "fundamental_score":       0.18,
    "valuation_score":         0.12,
    "growth_score":            0.15,
    "technical_score":         0.13,
    "sentiment_score":         0.08,
    "aggressive_invest_score": 0.08,
    "intangible_score":        0.06,
}

BONUSES = {
    "wide_moat":               0.30,
    "pct_from_ath_under_20":   0.20,
    "multibagger_high":        0.35,
    "rsi_oversold":            0.20,
    "short_squeeze_potential": 0.15,
    "earnings_quality_high":   0.15,
}

PENALTIES = {
    "rsi_overbought":          -0.30,
    "bearish_trend":           -0.20,
    "negative_fcf":            -0.30,
    "earnings_quality_low":    -0.40,
    "heavy_dilution":          -0.25,
}


def score_stock(s: dict) -> float:
    base = sum(s.get(k, 5.0) * w for k, w in WEIGHTS.items())

    bonus = 0.0
    if s.get("moat_type") == "Wide":
        bonus += BONUSES["wide_moat"]
    if abs(s.get("pct_from_ath", 0)) < 20:
        bonus += BONUSES["pct_from_ath_under_20"]
    if s.get("multibagger_potential") in ["Very High", "High"]:
        bonus += BONUSES["multibagger_high"]
    if s.get("rsi_14", 50) < 35:
        bonus += BONUSES["rsi_oversold"]
    if s.get("short_squeeze_potential"):
        bonus += BONUSES["short_squeeze_potential"]
    if s.get("earnings_quality") == "High":
        bonus += BONUSES["earnings_quality_high"]

    penalty = 0.0
    if s.get("rsi_14", 50) > 75:
        penalty += PENALTIES["rsi_overbought"]
    if s.get("trend") == "Bearish":
        penalty += PENALTIES["bearish_trend"]
    if s.get("fcf_ttm", 0) < 0:
        penalty += PENALTIES["negative_fcf"]
    if s.get("earnings_quality") == "Low":
        penalty += PENALTIES["earnings_quality_low"]
    if s.get("shares_change_yoy", 0) > 0.10:
        penalty += PENALTIES["heavy_dilution"]

    quality_bonus = s.get("quality_score_bonus", 0)

    # ── Alternative Data Bonuses (V4) ──
    alt  = s.get("alt_data", {})
    darv = s.get("darvas", {})
    squ  = s.get("squeeze", {})

    if alt.get("insider", {}).get("cluster_buying"): bonus += 0.40
    if alt.get("insider", {}).get("ceo_buying"):     bonus += 0.30
    hiring = alt.get("jobs", {}).get("hiring_signals_found", 0)
    if hiring >= 3:   bonus += 0.25
    elif hiring >= 1: bonus += 0.10
    if alt.get("web_momentum", {}).get("web_momentum_score", 5) >= 7.5: bonus += 0.20

    if darv.get("confirmed_breakout"):  bonus += 0.50
    elif darv.get("near_breakout"):     bonus += 0.30
    elif darv.get("in_box") and darv.get("box_tightness_pct", 100) < 5: bonus += 0.20

    if squ.get("squeeze_active"):
        bonus += 0.25
        if "Up" in squ.get("breakout_direction", ""):
            bonus += 0.15

    # שלושה סיגנלים יחד = rare opportunity
    if (darv.get("near_breakout") and
            squ.get("squeeze_active") and
            alt.get("insider", {}).get("any_buy")):
        bonus += 0.40

    total = base + bonus + penalty + quality_bonus
    return round(min(max(total, 0), 10), 2)


def classify_basket(stock: dict, cfg: dict) -> str:
    """
    כל מניה שהסורק מזהה כהזדמנות קנייה אמיתית נכנסת לדוח.
    הסיווג קובע רק איך להציג אותה, לא אם להציג.
    """
    score = stock["total_score"]
    mcap = stock.get("market_cap", 0)
    moat = stock.get("moat_type", "None")
    min_score = cfg["filters"].get("min_score_for_report", 6.0)

    # תמיד: תיק קיים = סל C
    if stock.get("ticker") in cfg.get("watchlist", []):
        return "C"

    # מתחת לסף — לא מעניין
    if score < min_score:
        return None

    # סל B: חברות גדולות (market cap > $10B) עם חפיר או ציון גבוה
    if mcap >= 10_000_000_000 and (moat in ["Wide", "Narrow"] or score >= 7.5):
        return "B"

    # סל A: כל שאר ההזדמנויות — צמיחה, ערך, פריצה, penny, מידקאפ
    return "A"


def score_and_rank(stocks: list, cfg: dict) -> list:
    logger.info(f"Agent6: מחשב ציונות עבור {len(stocks)} מניות...")
    profile = cfg.get("investor_profile", {})
    total_capital = profile.get("total_capital_usd", 1100)
    position_max = profile.get("position_size_max", 300)

    scored = []
    for s in stocks:
        s["total_score"] = score_stock(s)
        s["basket"] = classify_basket(s, cfg)

        if s["basket"] is not None:
            rec = get_action_recommendation(s, s.get("fundamental_score", 5.0),
                                            total_capital, position_max)
            s.update(rec)
            scored.append(s)

    scored.sort(key=lambda x: x["total_score"], reverse=True)
    logger.info(f"Agent6: {len(scored)} מניות עם ציון + סיווג")
    return scored
