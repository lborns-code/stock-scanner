import json
import logging
import os

logger = logging.getLogger(__name__)

SECTOR_BENCHMARKS = {
    "Technology":             {"pe": 28, "ps": 6.5, "gross_margin": 0.55, "roic": 18},
    "Healthcare":             {"pe": 22, "ps": 3.5, "gross_margin": 0.58, "roic": 14},
    "Financials":             {"pe": 13, "ps": 2.8, "gross_margin": 0.45, "roic": 10},
    "Consumer Discretionary": {"pe": 24, "ps": 1.8, "gross_margin": 0.35, "roic": 12},
    "Industrials":            {"pe": 20, "ps": 1.5, "gross_margin": 0.30, "roic": 11},
    "Energy":                 {"pe": 12, "ps": 1.2, "gross_margin": 0.25, "roic": 9},
    "Communication Services": {"pe": 20, "ps": 3.0, "gross_margin": 0.50, "roic": 13},
    "Consumer Staples":       {"pe": 18, "ps": 1.2, "gross_margin": 0.32, "roic": 12},
    "Real Estate":            {"pe": 35, "ps": 4.0, "gross_margin": 0.60, "roic": 6},
    "Utilities":              {"pe": 16, "ps": 2.0, "gross_margin": 0.35, "roic": 7},
    "Materials":              {"pe": 15, "ps": 1.5, "gross_margin": 0.28, "roic": 10},
}


def worth_deep_analysis(data: dict, cfg: dict) -> bool:
    return (
        data.get("gross_margin", 0) > 0.15 and
        data.get("revenue_growth_yoy", -1) > -0.10 and
        data.get("debt_to_equity", 99) < 3.0 and
        data.get("current_ratio", 0) > 0.7
    )


def calc_aggressive_investment_score(data: dict) -> float:
    capex_growth = data.get("capex_growth_yoy", 0)
    rd_to_revenue = data.get("rd_expense", 0) / max(data.get("revenue_ttm", 1), 1)

    score = 5.0
    if capex_growth > 0.30:    score += 2.0
    elif capex_growth > 0.10:  score += 1.0
    elif capex_growth < -0.10: score -= 1.0

    if rd_to_revenue > 0.20:   score += 1.5
    elif rd_to_revenue > 0.10: score += 0.8
    elif rd_to_revenue < 0.02: score -= 0.5

    return round(min(max(score, 0), 10), 1)


def calc_intangible_score(data: dict) -> float:
    rd_to_rev = data.get("rd_expense", 0) / max(data.get("revenue_ttm", 1), 1)
    score = 5.0

    if rd_to_rev > 0.25:   score += 2.5
    elif rd_to_rev > 0.15: score += 1.5
    elif rd_to_rev > 0.08: score += 0.8
    elif rd_to_rev < 0.01: score -= 1.0

    return round(min(max(score, 0), 10), 1)


def _format_news(headlines: list) -> str:
    if not headlines:
        return "Recent News: N/A"
    lines = ["Recent News Headlines:"]
    for h in headlines[:5]:
        if h:
            lines.append(f"  - {h}")
    return "\n".join(lines)


def _build_prompt(data: dict) -> str:
    ticker = data["ticker"]
    sector = data.get("sector", "Unknown")
    bench = SECTOR_BENCHMARKS.get(sector, {"pe": 20, "ps": 3.0, "gross_margin": 0.40, "roic": 12})
    pe_fwd = data.get("pe_forward", 0) or 0
    sector_pe = bench["pe"]
    pe_vs_sector = ((pe_fwd - sector_pe) / sector_pe * 100) if sector_pe and pe_fwd else 0

    rev_ttm = data.get("revenue_ttm", 0)
    rev_str = f"${rev_ttm/1e9:.1f}B" if rev_ttm > 1e9 else f"${rev_ttm/1e6:.0f}M"
    short_pct = data.get("short_interest_pct", 0)
    short_squeeze = short_pct > 0.15

    return f"""You are analyzing {ticker} for an Israeli long-term investor seeking multibagger stocks.
Capital: ~$1,100 total. Position size: $100-300. Horizon: 3-10 years.

REAL DATA:
Company: {data.get('company_name', ticker)} | Sector: {sector} | Industry: {data.get('industry', '')}
Price: ${data.get('current_price', 0):.2f} | Market Cap: ${data.get('market_cap', 0)/1e9:.1f}B
Revenue TTM: {rev_str} | Growth YoY: {data.get('revenue_growth_yoy', 0):.1%}
Gross Margin: {data.get('gross_margin', 0):.1%} | FCF Margin: {data.get('fcf_margin', 0):.1%}
ROIC: {data.get('roic', 0):.1%} | ROE: {data.get('roe', 0):.1%} | Debt/Equity: {data.get('debt_to_equity', 0):.1f}
P/E Fwd: {pe_fwd} | PEG: {data.get('peg_ratio', 0)} | P/S: {data.get('ps_ratio', 0):.1f} | EV/EBITDA: {data.get('ev_ebitda', 0)}
R&D/Revenue: {data.get('rd_expense', 0)/max(data.get('revenue_ttm',1),1):.1%} | Capex Growth: {data.get('capex_growth_yoy', 0):.1%}
Short Interest: {short_pct:.1%} | Short Squeeze Risk: {"HIGH" if short_squeeze else "low"}
Shares Change YoY: {data.get('shares_change_yoy', 0):.1%} (dilution)
Earnings Quality: {data.get('earnings_quality', 'Unknown')}
Analysts: {data.get('analyst_count', 0)} analysts, mean target ${data.get('analyst_target_mean', 0):.2f}
Sector avg P/E: {sector_pe} | Stock vs sector: {pe_vs_sector:+.0f}%
% from ATH: {data.get('pct_from_ath', 0):.1f}%
{_format_news(data.get('news_headlines', []))}

Return JSON only, no markdown:
{{
  "what_company_does_hebrew": "תיאור קצר של מה החברה עושה ואיפה היא מובילה — 2 משפטים",
  "moat_type": "Wide/Narrow/None",
  "moat_sources": ["מקור חפיר 1", "מקור חפיר 2"],
  "moat_score": 0,
  "moat_durability_years": 5,
  "moat_explanation_hebrew": "הסבר קצר מדוע יש/אין חפיר — למה קשה לתחרות להעתיק",
  "pricing_power": "Strong/Moderate/Weak",
  "fundamental_score": 0,
  "growth_score": 0,
  "valuation_score": 0,
  "valuation_vs_sector": "Undervalued/Fair/Overvalued",
  "dcf_rough_range": "$X-Y",
  "multibagger_potential": "Very High/High/Medium/Low",
  "multibagger_reason_hebrew": "למה זו מניה עם פוטנציאל גדול — תהיה ספציפי",
  "years_to_potential_peak": "3-5 שנים",
  "key_strengths_hebrew": ["חוזק 1", "חוזק 2", "חוזק 3"],
  "key_risks_hebrew": ["סיכון 1", "סיכון 2"],
  "growth_drivers_hebrew": ["מנוע צמיחה 1", "מנוע 2"],
  "sector_verdict_hebrew": "ניתוח ביחס לסקטור — יקר/זול/הוגן ולמה",
  "earnings_quality_comment": "הערה על איכות הרווחים — FCF, accruals, חשבונאות",
  "short_squeeze_potential": false,
  "short_squeeze_hebrew": "האם יש פוטנציאל לשורט סקוויז ולמה — short interest, float",
  "insider_activity_hebrew": "הערכה לגבי פעילות בעלים/מנהלים — האם מכרו/קנו/לא פעלו לאחרונה",
  "geopolitical_impact_hebrew": "איך מגמות גיאופוליטיות (מלחמות סחר, AI race, אנרגיה, מזה\"ת) משפיעות — 2-3 משפטים",
  "why_now_hebrew": "למה עכשיו זה זמן טוב להיכנס (או לא) — קטליסטים קרובים, מחיר ביחס להיסטוריה",
  "bull_case_hebrew": "תרחיש אופטימי — מה צריך לקרות כדי שהמניה x2-x5",
  "bear_case_hebrew": "תרחיש פסימי — מה יכול להשמיד את ההשקעה",
  "psychology_note_hebrew": "תזכורת פסיכולוגית חשובה למשקיע ישראלי",
  "verdict_hebrew": "✅/⚠️/❌ המלצה סופית ברורה עם סיבה אחת מרכזית"
}}"""


def _fallback_analysis(data: dict) -> dict:
    gm = data.get("gross_margin", 0)
    growth = data.get("revenue_growth_yoy", 0)
    de = data.get("debt_to_equity", 99)
    fcf = data.get("fcf_margin", 0)
    pe = data.get("pe_forward", 0) or data.get("pe_ttm", 0)

    moat_score = 5.0
    if gm > 0.50: moat_score += 2
    elif gm > 0.35: moat_score += 1
    if de < 0.5: moat_score += 1
    if fcf > 0.10: moat_score += 1

    fund_score = 5.0
    if gm > 0.40: fund_score += 1
    if fcf > 0.05: fund_score += 1
    if de < 1: fund_score += 1

    growth_score = 5.0
    if growth > 0.30: growth_score += 2.5
    elif growth > 0.15: growth_score += 1.5
    elif growth > 0.05: growth_score += 0.5
    elif growth < 0: growth_score -= 1.5

    val_score = 5.0
    if pe > 0:
        if pe < 15: val_score += 2
        elif pe < 25: val_score += 1
        elif pe > 50: val_score -= 1
        elif pe > 80: val_score -= 2
    ps = data.get("ps_ratio", 0)
    if ps > 0:
        if ps < 3: val_score += 1.5
        elif ps < 8: val_score += 0.5
        elif ps > 20: val_score -= 1
    peg = data.get("peg_ratio", 0)
    if peg > 0:
        if peg < 1: val_score += 1.5
        elif peg < 2: val_score += 0.5
        elif peg > 3: val_score -= 1
    ev = data.get("ev_ebitda", 0)
    if ev > 0:
        if ev < 12: val_score += 1
        elif ev > 30: val_score -= 0.5

    multi = "Low"
    if growth > 0.30 and moat_score > 6: multi = "High"
    elif growth > 0.20: multi = "Medium"

    return {
        "moat_type": "Narrow" if moat_score >= 6 else "None",
        "moat_sources": ["גבוה gross margin"] if gm > 0.40 else [],
        "moat_score": round(min(max(moat_score, 0), 10), 1),
        "moat_durability_years": 5,
        "pricing_power": "Moderate",
        "fundamental_score": round(min(max(fund_score, 0), 10), 1),
        "growth_score": round(min(max(growth_score, 0), 10), 1),
        "valuation_score": round(min(max(val_score, 0), 10), 1),
        "valuation_vs_sector": "Fair",
        "dcf_rough_range": "N/A",
        "multibagger_potential": multi,
        "multibagger_reason_hebrew": "ניתוח אוטומטי — Claude לא זמין",
        "years_to_potential_peak": "3-5 שנים",
        "key_strengths_hebrew": ["נתונים פונדמנטליים סבירים"],
        "key_risks_hebrew": ["לא נותח על ידי Claude"],
        "growth_drivers_hebrew": ["צמיחה אורגנית"],
        "sector_verdict_hebrew": "ניתוח בסיסי בלבד",
        "earnings_quality_comment": data.get("earnings_quality", "Unknown"),
        "short_squeeze_potential": data.get("short_interest_pct", 0) > 0.15,
        "bull_case_hebrew": "צמיחה ממשיכה בקצב הנוכחי",
        "bear_case_hebrew": "האטה בצמיחה או תחרות גוברת",
        "psychology_note_hebrew": "זכור: השקעה לטווח ארוך — 3-10 שנים",
        "verdict_hebrew": "ניתוח אוטומטי — בדוק ידנית",
    }


def analyze_with_claude(data: dict, api_key: str) -> dict:
    if not api_key or api_key == "YOUR_KEY_HERE":
        return _fallback_analysis(data)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        prompt = _build_prompt(data)

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()

        # strip markdown fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()

        result = json.loads(text)
        return result

    except Exception as e:
        logger.warning(f"Claude analysis failed for {data.get('ticker')}: {e}")
        return _fallback_analysis(data)


def analyze_batch(stocks: list, cfg: dict) -> list:
    api_key = cfg.get("anthropic_api_key", "")
    logger.info(f"Agent3: מנתח {len(stocks)} מניות...")
    results = []
    for i, s in enumerate(stocks):
        if not worth_deep_analysis(s, cfg):
            logger.debug(f"  {s['ticker']}: דלג — לא עומד בסינון")
            analysis = _fallback_analysis(s)    
        else:
            analysis = analyze_with_claude(s, api_key)

        s["what_company_does_hebrew"] = analysis.get("what_company_does_hebrew", "")
        s["moat_type"] = analysis.get("moat_type", "None")
        s["moat_sources"] = analysis.get("moat_sources", [])
        s["moat_score"] = analysis.get("moat_score", 5.0)
        s["moat_durability_years"] = analysis.get("moat_durability_years", 5)
        s["moat_explanation_hebrew"] = analysis.get("moat_explanation_hebrew", "")
        s["pricing_power"] = analysis.get("pricing_power", "Moderate")
        s["fundamental_score"] = analysis.get("fundamental_score", 5.0)
        s["growth_score"] = analysis.get("growth_score", 5.0)
        s["valuation_score"] = analysis.get("valuation_score", 5.0)
        s["valuation_vs_sector"] = analysis.get("valuation_vs_sector", "Fair")
        s["dcf_rough_range"] = analysis.get("dcf_rough_range", "N/A")
        s["multibagger_potential"] = analysis.get("multibagger_potential", "Low")
        s["multibagger_reason_hebrew"] = analysis.get("multibagger_reason_hebrew", "")
        s["years_to_potential_peak"] = analysis.get("years_to_potential_peak", "5+ שנים")
        s["key_strengths_hebrew"] = analysis.get("key_strengths_hebrew", [])
        s["key_risks_hebrew"] = analysis.get("key_risks_hebrew", [])
        s["growth_drivers_hebrew"] = analysis.get("growth_drivers_hebrew", [])
        s["sector_verdict_hebrew"] = analysis.get("sector_verdict_hebrew", "")
        s["earnings_quality_comment"] = analysis.get("earnings_quality_comment", "")
        s["short_squeeze_potential"] = analysis.get("short_squeeze_potential", False)
        s["short_squeeze_hebrew"] = analysis.get("short_squeeze_hebrew", "")
        s["insider_activity_hebrew"] = analysis.get("insider_activity_hebrew", "")
        s["geopolitical_impact_hebrew"] = analysis.get("geopolitical_impact_hebrew", "")
        s["why_now_hebrew"] = analysis.get("why_now_hebrew", "")
        s["bull_case_hebrew"] = analysis.get("bull_case_hebrew", "")
        s["bear_case_hebrew"] = analysis.get("bear_case_hebrew", "")
        s["psychology_note_hebrew"] = analysis.get("psychology_note_hebrew", "")
        s["verdict_hebrew"] = analysis.get("verdict_hebrew", "")

        s["aggressive_invest_score"] = calc_aggressive_investment_score(s)
        s["intangible_score"] = calc_intangible_score(s)

        results.append(s)
        if (i + 1) % 10 == 0:
            logger.info(f"  {i+1}/{len(stocks)} נותחו")

    logger.info(f"Agent3: {len(results)} מניות עברו ניתוח מעמיק")
    return results
