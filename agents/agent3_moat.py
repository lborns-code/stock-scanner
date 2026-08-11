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

SECTOR_COMPETITORS = {
    "Technology":             ["MSFT", "GOOGL", "AAPL", "AMZN", "META", "CRM", "NOW", "ADBE"],
    "Healthcare":             ["JNJ", "LLY", "UNH", "ABBV", "TMO", "ISRG", "VRTX", "REGN"],
    "Financials":             ["JPM", "BAC", "GS", "V", "MA", "BRK-B", "COIN"],
    "Consumer Discretionary": ["AMZN", "TSLA", "HD", "NKE", "LULU", "BKNG", "ABNB"],
    "Industrials":            ["CAT", "HON", "RTX", "LMT", "GE", "ETN", "DE"],
    "Energy":                 ["XOM", "CVX", "COP", "SLB", "OXY", "FANG"],
    "Communication Services": ["GOOGL", "META", "NFLX", "DIS", "SPOT", "TTD"],
    "Consumer Staples":       ["COST", "PG", "KO", "PEP", "MCD", "SBUX"],
    "Real Estate":            ["AMT", "EQIX", "PLD", "WELL"],
    "Utilities":              ["NEE", "DUK", "SO"],
    "Materials":              ["LIN", "APD", "NEM", "FCX"],
    "Semiconductors":         ["NVDA", "AMD", "AVGO", "QCOM", "MRVL", "INTC", "TSM", "ASML"],
    "Biotech":                ["MRNA", "GILD", "BIIB", "REGN", "VRTX", "ARWR"],
    "AI & Software":          ["NVDA", "MSFT", "PLTR", "AI", "SNOW", "DDOG", "MDB"],
    "Fintech":                ["COIN", "HOOD", "AFRM", "UPST", "SQ", "PYPL"],
    "Clean Energy":           ["ENPH", "FSLR", "PLUG", "BLNK", "CHPT", "NEE"],
}


def _get_sector_competitors(sector: str, industry: str) -> list:
    for key in SECTOR_COMPETITORS:
        if key.lower() in (sector or "").lower() or key.lower() in (industry or "").lower():
            return SECTOR_COMPETITORS[key][:4]
    return SECTOR_COMPETITORS.get(sector, ["SPY", "QQQ"])[:4]


def worth_deep_analysis(data: dict, cfg: dict) -> bool:
    return (
        data.get("gross_margin", 0) > 0.05 and
        data.get("revenue_growth_yoy", -1) > -0.20 and
        data.get("debt_to_equity", 99) < 5.0 and
        data.get("current_ratio", 0) > 0.3
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
    industry = data.get("industry", "")
    bench = SECTOR_BENCHMARKS.get(sector, {"pe": 20, "ps": 3.0, "gross_margin": 0.40, "roic": 12})
    pe_fwd = data.get("pe_forward", 0) or 0
    sector_pe = bench["pe"]
    sector_ps = bench["ps"]
    sector_gm = bench["gross_margin"]
    sector_roic = bench["roic"]
    pe_vs_sector = ((pe_fwd - sector_pe) / sector_pe * 100) if sector_pe and pe_fwd else 0
    ps = data.get("ps_ratio", 0) or 0
    ps_vs_sector = ((ps - sector_ps) / sector_ps * 100) if sector_ps and ps else 0
    gm = data.get("gross_margin", 0)
    gm_vs_sector = ((gm - sector_gm) / sector_gm * 100) if sector_gm else 0
    roic = data.get("roic", 0)
    roic_vs_sector = ((roic - sector_roic) / sector_roic * 100) if sector_roic else 0

    rev_ttm = data.get("revenue_ttm", 0)
    rev_str = f"${rev_ttm/1e9:.1f}B" if rev_ttm > 1e9 else f"${rev_ttm/1e6:.0f}M"
    short_pct = data.get("short_interest_pct", 0)
    short_squeeze = short_pct > 0.15
    competitors = ", ".join(_get_sector_competitors(sector, industry))

    return (
        f"You are a senior equity analyst evaluating {ticker} for an Israeli long-term investor.\n"
        f"Capital: ~$1,100 total. Position size: $100-300. Horizon: 3-10 years.\n\n"
        f"REAL DATA:\n"
        f"Company: {data.get('company_name', ticker)} | Sector: {sector} | Industry: {industry}\n"
        f"Price: ${data.get('current_price', 0):.2f} | Market Cap: ${data.get('market_cap', 0)/1e9:.1f}B\n"
        f"Revenue TTM: {rev_str} | Growth YoY: {data.get('revenue_growth_yoy', 0):.1%}\n"
        f"Gross Margin: {gm:.1%} (sector avg {sector_gm:.0%}, {gm_vs_sector:+.0f}% vs sector)\n"
        f"FCF Margin: {data.get('fcf_margin', 0):.1%}\n"
        f"ROIC: {roic:.1%} (sector avg {sector_roic}%, {roic_vs_sector:+.0f}% vs sector)\n"
        f"ROE: {data.get('roe', 0):.1%} | Debt/Equity: {data.get('debt_to_equity', 0):.1f}\n"
        f"P/E Fwd: {pe_fwd} (sector avg {sector_pe}, {pe_vs_sector:+.0f}% vs sector)\n"
        f"P/S: {ps:.1f} (sector avg {sector_ps:.1f}, {ps_vs_sector:+.0f}% vs sector)\n"
        f"PEG: {data.get('peg_ratio', 0)} | EV/EBITDA: {data.get('ev_ebitda', 0)}\n"
        f"R&D/Revenue: {data.get('rd_expense', 0)/max(data.get('revenue_ttm',1),1):.1%} | Capex Growth: {data.get('capex_growth_yoy', 0):.1%}\n"
        f"Short Interest: {short_pct:.1%} | Short Squeeze Risk: {'HIGH' if short_squeeze else 'low'}\n"
        f"Shares Change YoY: {data.get('shares_change_yoy', 0):.1%} (dilution)\n"
        f"Earnings Quality: {data.get('earnings_quality', 'Unknown')}\n"
        f"Analysts: {data.get('analyst_count', 0)} analysts, mean target ${data.get('analyst_target_mean', 0):.2f}\n"
        f"% from ATH: {data.get('pct_from_ath', 0):.1f}%\n"
        f"Key sector peers: {competitors}\n"
        f"{_format_news(data.get('news_headlines', []))}\n\n"
        f"IMPORTANT: Be specific with numbers and competitor names. "
        f"For ROCKET score consider: >30% revenue growth, expanding margins, short squeeze setup, breakout, strong catalyst, undervalued vs sector.\n\n"
        f"Return JSON only, no markdown:\n"
        "{{\n"
        '  "what_company_does_hebrew": "2 משפטים על מה החברה עושה ואיפה מובילה",\n'
        '  "fundamental_explanation_hebrew": "הסבר פונדמנטלי — הכנסות, רווחים, חוב, צמיחה, יתרונות וחסרונות — 3-4 משפטים",\n'
        '  "moat_type": "Wide/Narrow/None",\n'
        '  "moat_sources": ["מקור 1", "מקור 2"],\n'
        '  "moat_score": 0,\n'
        '  "moat_durability_years": 5,\n'
        '  "moat_explanation_hebrew": "למה יש/אין חפיר — קצר",\n'
        '  "pricing_power": "Strong/Moderate/Weak",\n'
        '  "fundamental_score": 0,\n'
        '  "growth_score": 0,\n'
        '  "valuation_score": 0,\n'
        '  "valuation_vs_sector": "Undervalued/Fair/Overvalued",\n'
        '  "dcf_rough_range": "$X-Y",\n'
        '  "sector_comparison_hebrew": "השווה במספרים ל-2 מתחרות ספציפיות — P/E, שולי רווח, צמיחה — 3-4 משפטים עם שמות חברות ומספרים",\n'
        '  "disruption_risk_hebrew": "אילו טכנולוגיות/מתחרות יכולים להרוס העסק — שמות ספציפיים — 2-3 משפטים",\n'
        '  "geopolitical_impact_hebrew": "השפעת גיאופוליטיקה ספציפית: מלחמות סחר, טריפים, רגולציה, AI race, מגמות תרבותיות — 2-3 משפטים",\n'
        '  "regulatory_risk_hebrew": "סיכון רגולטורי — אנטיטרסט, FDA, SEC, GDPR, חוקי AI — 1-2 משפטים",\n'
        '  "multibagger_potential": "Very High/High/Medium/Low",\n'
        '  "multibagger_reason_hebrew": "למה יש פוטנציאל גדול — ספציפי",\n'
        '  "rocket_score": 0,\n'
        '  "rocket_reason_hebrew": "ציון 0-10 לפוטנציאל התפוצצות: מומנטום, קטליסט, breakout, short squeeze, הערכת חסר — 2-3 משפטים ספציפיים",\n'
        '  "scenario_bull_hebrew": "תרחיש שורי: מה קורה + מחיר בעוד 3 שנים — משפט עם מספר",\n'
        '  "scenario_base_hebrew": "תרחיש בסיס: תשואה ריאלית + מחיר — משפט עם מספר",\n'
        '  "scenario_bear_hebrew": "תרחיש דובי: מה ישמיד + מחיר downside — משפט עם מספר",\n'
        '  "years_to_potential_peak": "3-5 שנים",\n'
        '  "key_strengths_hebrew": ["חוזק 1", "חוזק 2", "חוזק 3"],\n'
        '  "key_risks_hebrew": ["סיכון 1", "סיכון 2"],\n'
        '  "growth_drivers_hebrew": ["מנוע 1", "מנוע 2"],\n'
        '  "sector_verdict_hebrew": "ביחס לסקטור — יקר/זול/הוגן ולמה — קצר",\n'
        '  "earnings_quality_comment": "הערה על איכות הרווחים",\n'
        '  "short_squeeze_potential": false,\n'
        '  "short_squeeze_hebrew": "פוטנציאל שורט סקוויז — קצר",\n'
        '  "insider_activity_hebrew": "פעילות בעלים/מנהלים — קצר",\n'
        '  "why_now_hebrew": "למה עכשיו — קטליסטים קרובים, מחיר ביחס להיסטוריה",\n'
        '  "bull_case_hebrew": "תרחיש אופטימי — x2-x5",\n'
        '  "bear_case_hebrew": "תרחיש פסימי — מה ישמיד ההשקעה",\n'
        '  "psychology_note_hebrew": "תזכורת פסיכולוגית — משפט אחד",\n'
        '  "verdict_hebrew": "checkmark/warning/x המלצה סופית + סיבה מרכזית"\n'
        "}}"
    )


def _fallback_analysis(data: dict) -> dict:
    gm = data.get("gross_margin", 0)
    growth = data.get("revenue_growth_yoy", 0)
    de = data.get("debt_to_equity", 99)
    fcf = data.get("fcf_margin", 0)
    pe = data.get("pe_forward", 0) or data.get("pe_ttm", 0)

    moat_score = 5.0
    if gm > 0.60: moat_score += 2.5
    elif gm > 0.50: moat_score += 2.0
    elif gm > 0.35: moat_score += 1.0
    elif gm > 0.20: moat_score += 0.3
    if de < 0.3: moat_score += 1.5
    elif de < 0.5: moat_score += 1.0
    elif de < 1: moat_score += 0.3
    if fcf > 0.15: moat_score += 1.5
    elif fcf > 0.10: moat_score += 1.0
    elif fcf > 0.05: moat_score += 0.5

    fund_score = 5.0
    if gm > 0.50: fund_score += 2.0
    elif gm > 0.40: fund_score += 1.5
    elif gm > 0.25: fund_score += 0.8
    if fcf > 0.10: fund_score += 1.5
    elif fcf > 0.05: fund_score += 1.0
    elif fcf > 0: fund_score += 0.3
    if de < 0.5: fund_score += 1.0
    elif de < 1: fund_score += 0.5

    growth_score = 5.0
    if growth > 0.40: growth_score += 3.5
    elif growth > 0.25: growth_score += 2.5
    elif growth > 0.15: growth_score += 1.5
    elif growth > 0.05: growth_score += 0.8
    elif growth < -0.10: growth_score -= 1.5
    elif growth < 0: growth_score -= 0.5

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

    # Rocket score: automatic calculation
    rocket = 4.0
    if growth > 0.40: rocket += 3.0
    elif growth > 0.25: rocket += 2.0
    elif growth > 0.15: rocket += 1.0
    if data.get("short_interest_pct", 0) > 0.20: rocket += 1.5
    elif data.get("short_interest_pct", 0) > 0.15: rocket += 0.8
    if gm > 0.60: rocket += 1.0
    elif gm > 0.40: rocket += 0.5
    if fcf > 0.15: rocket += 0.5

    gm_heb = f"שולי רווח גולמי {gm:.0%}" + (" — גבוהים" if gm > 0.40 else " — ממוצע" if gm > 0.20 else " — נמוכים")
    growth_heb = f"צמיחה {growth:.0%} YoY" + (" — מהירה מאוד" if growth > 0.25 else " — טובה" if growth > 0.10 else " — איטית/שלילית")
    de_heb = f"חוב/הון {de:.1f}" + (" — מינוף נמוך" if de < 0.5 else " — סביר" if de < 2 else " — מינוף גבוה")
    fcf_heb = f"FCF margin {fcf:.0%}" + (" — תזרים חזק" if fcf > 0.10 else " — חיובי" if fcf > 0 else " — שלילי")
    fund_explain = f"{gm_heb}. {growth_heb}. {de_heb}. {fcf_heb}."

    return {
        "moat_type": "Narrow" if moat_score >= 6 else "None",
        "moat_sources": ["גבוה gross margin"] if gm > 0.40 else [],
        "moat_score": round(min(max(moat_score, 0), 10), 1),
        "moat_durability_years": 5,
        "pricing_power": "Moderate",
        "fundamental_score": round(min(max(fund_score, 0), 10), 1),
        "fundamental_explanation_hebrew": fund_explain,
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
        "sector_comparison_hebrew": "",
        "disruption_risk_hebrew": "",
        "geopolitical_impact_hebrew": "",
        "regulatory_risk_hebrew": "",
        "rocket_score": round(min(max(rocket, 0), 10), 1),
        "rocket_reason_hebrew": f"ציון אוטומטי — צמיחה {growth:.0%}, שורטים {data.get('short_interest_pct',0):.0%}",
        "scenario_bull_hebrew": "צמיחה ממשיכה — upside משמעותי",
        "scenario_base_hebrew": "תשואה ממוצעת לסקטור",
        "scenario_bear_hebrew": "האטה בצמיחה — downside אפשרי",
        "earnings_quality_comment": data.get("earnings_quality", "Unknown"),
        "short_squeeze_potential": data.get("short_interest_pct", 0) > 0.15,
        "short_squeeze_hebrew": "",
        "insider_activity_hebrew": "",
        "why_now_hebrew": "",
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
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()

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
    logger.info(f"Agent3: analyzing {len(stocks)} stocks...")
    results = []
    for i, s in enumerate(stocks):
        if not worth_deep_analysis(s, cfg):
            logger.debug(f"  {s['ticker']}: skip — filtered out")
            analysis = _fallback_analysis(s)
        else:
            analysis = analyze_with_claude(s, api_key)

        s["what_company_does_hebrew"] = analysis.get("what_company_does_hebrew", "")
        s["fundamental_explanation_hebrew"] = analysis.get("fundamental_explanation_hebrew", "")
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
        s["sector_comparison_hebrew"] = analysis.get("sector_comparison_hebrew", "")
        s["disruption_risk_hebrew"] = analysis.get("disruption_risk_hebrew", "")
        s["geopolitical_impact_hebrew"] = analysis.get("geopolitical_impact_hebrew", "")
        s["regulatory_risk_hebrew"] = analysis.get("regulatory_risk_hebrew", "")
        s["multibagger_potential"] = analysis.get("multibagger_potential", "Low")
        s["multibagger_reason_hebrew"] = analysis.get("multibagger_reason_hebrew", "")
        s["rocket_score"] = analysis.get("rocket_score", 0)
        s["rocket_reason_hebrew"] = analysis.get("rocket_reason_hebrew", "")
        s["scenario_bull_hebrew"] = analysis.get("scenario_bull_hebrew", "")
        s["scenario_base_hebrew"] = analysis.get("scenario_base_hebrew", "")
        s["scenario_bear_hebrew"] = analysis.get("scenario_bear_hebrew", "")
        s["years_to_potential_peak"] = analysis.get("years_to_potential_peak", "5+ שנים")
        s["key_strengths_hebrew"] = analysis.get("key_strengths_hebrew", [])
        s["key_risks_hebrew"] = analysis.get("key_risks_hebrew", [])
        s["growth_drivers_hebrew"] = analysis.get("growth_drivers_hebrew", [])
        s["sector_verdict_hebrew"] = analysis.get("sector_verdict_hebrew", "")
        s["earnings_quality_comment"] = analysis.get("earnings_quality_comment", "")
        s["short_squeeze_potential"] = analysis.get("short_squeeze_potential", False)
        s["short_squeeze_hebrew"] = analysis.get("short_squeeze_hebrew", "")
        s["insider_activity_hebrew"] = analysis.get("insider_activity_hebrew", "")
        s["why_now_hebrew"] = analysis.get("why_now_hebrew", "")
        s["bull_case_hebrew"] = analysis.get("bull_case_hebrew", "")
        s["bear_case_hebrew"] = analysis.get("bear_case_hebrew", "")
        s["psychology_note_hebrew"] = analysis.get("psychology_note_hebrew", "")
        s["verdict_hebrew"] = analysis.get("verdict_hebrew", "")

        s["aggressive_invest_score"] = calc_aggressive_investment_score(s)
        s["intangible_score"] = calc_intangible_score(s)

        results.append(s)
        if (i + 1) % 10 == 0:
            logger.info(f"  {i+1}/{len(stocks)} analyzed")

    logger.info(f"Agent3: {len(results)} stocks analyzed")
    return results
