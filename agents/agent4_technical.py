import logging
import yfinance as yf
import pandas as pd

logger = logging.getLogger(__name__)


def analyze(ticker: str, history: pd.DataFrame | None = None) -> dict | None:
    try:
        if history is None or history.empty:
            t = yf.Ticker(ticker)
            history = t.history(period="1y")

        if history.empty or len(history) < 50:
            return None

        # flatten MultiIndex columns if needed
        if isinstance(history.columns, pd.MultiIndex):
            history.columns = history.columns.get_level_values(0)

        close = history["Close"].squeeze()
        high = history["High"].squeeze()
        low = history["Low"].squeeze()
        volume = history["Volume"].squeeze()
        current = float(close.iloc[-1])

        ma20 = float(close.rolling(20).mean().iloc[-1])
        ma50 = float(close.rolling(50).mean().iloc[-1])
        ma200 = float(close.rolling(min(200, len(close))).mean().iloc[-1])

        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss
        rsi = float(100 - 100 / (1 + rs).iloc[-1]) if float(loss.iloc[-1]) != 0 else 50.0

        ema12 = close.ewm(span=12).mean()
        ema26 = close.ewm(span=26).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9).mean()
        macd_hist = float((macd_line - signal_line).iloc[-1])

        std20 = close.rolling(20).std()
        bb_upper = float((close.rolling(20).mean() + 2 * std20).iloc[-1])
        bb_lower = float((close.rolling(20).mean() - 2 * std20).iloc[-1])
        bb_pct = (current - bb_lower) / (bb_upper - bb_lower) if bb_upper != bb_lower else 0.5

        support_1 = float(low.rolling(20).min().iloc[-1])
        support_2 = float(low.rolling(min(60, len(low))).min().iloc[-1])
        resistance_1 = float(high.rolling(20).max().iloc[-1])
        high_52w = float(high.rolling(min(252, len(high))).max().iloc[-1])

        vol_avg = float(volume.rolling(20).mean().iloc[-1])
        vol_ratio = float(volume.iloc[-1] / vol_avg) if vol_avg > 0 else 1.0
        pct_from_ath = round((current - high_52w) / high_52w * 100, 1) if high_52w else 0

        score = 5.0
        if current > ma200:     score += 1.5
        if current > ma50:      score += 0.8
        if rsi < 32:            score += 1.5
        elif rsi < 40:          score += 1.0
        elif rsi > 75:          score -= 1.5
        if macd_hist > 0:       score += 0.5
        if vol_ratio > 1.5:     score += 0.4
        if pct_from_ath < -20:  score += 0.6
        if bb_pct < 0.15:       score += 0.5

        return {
            "current_price": round(current, 2),
            "ma20": round(ma20, 2),
            "ma50": round(ma50, 2),
            "ma200": round(ma200, 2),
            "above_ma50": current > ma50,
            "above_ma200": current > ma200,
            "rsi_14": round(rsi, 1),
            "rsi_signal": "Oversold" if rsi < 35 else "Overbought" if rsi > 70 else "Neutral",
            "macd_bullish": macd_hist > 0,
            "bb_pct": round(bb_pct, 2),
            "support_1": round(support_1, 2),
            "support_2": round(support_2, 2),
            "resistance_1": round(resistance_1, 2),
            "high_52w": round(high_52w, 2),
            "pct_from_ath": pct_from_ath,
            "volume_ratio": round(vol_ratio, 2),
            "technical_score": round(min(max(score, 0), 10), 1),
            "trend": "Bullish" if current > ma200 and current > ma50
                     else "Mixed" if current > ma200 else "Bearish",
        }
    except Exception as e:
        logger.debug(f"Technical analysis {ticker}: {e}")
        return None


def _calc_target_1y(tech: dict, current: float) -> float:
    """Target 1y: מעדיף analyst consensus, אחרת growth-adjusted."""
    analyst_mean = tech.get("analyst_target_mean", 0)
    analyst_count = tech.get("analyst_count", 0)
    if analyst_mean and analyst_mean > current and analyst_count >= 3:
        # ממוצע אנליסטים + 10% discount (לא תמיד מגיעים ל-target)
        return round(analyst_mean * 0.90, 2)
    growth = tech.get("revenue_growth_yoy", 0)
    mult = 1.50 if growth > 0.30 else (1.35 if growth > 0.15 else 1.20)
    return round(current * mult, 2)


def _calc_target_3y(tech: dict, current: float) -> float:
    """Target 3y: לפי פוטנציאל multibagger + מגמה."""
    multi = tech.get("multibagger_potential", "Low")
    growth = tech.get("revenue_growth_yoy", 0)
    analyst_high = tech.get("analyst_target_high", 0)
    mult = {"Very High": 4.0, "High": 3.0, "Medium": 2.0, "Low": 1.5}.get(multi, 2.0)
    if growth > 0.40:
        mult = max(mult, 3.5)
    # אם יש analyst target גבוה — השתמש בו כ-floor
    base = round(current * mult, 2)
    if analyst_high and analyst_high > base:
        return round(analyst_high * 1.5, 2)
    return base


def get_action_recommendation(tech: dict, fund_score: float,
                               total_capital: float, position_max: float) -> dict:
    rsi = tech.get("rsi_14", 50)
    trend = tech.get("trend")
    above_200 = tech.get("above_ma200")
    macd_bull = tech.get("macd_bullish")
    pct_ath = tech.get("pct_from_ath", -5)
    support_1 = tech.get("support_1", 0)
    support_2 = tech.get("support_2", 0)
    current = tech.get("current_price", 0)
    bb_pct = tech.get("bb_pct", 0.5)

    buy_signals = []
    sell_signals = []
    wait_signals = []

    if rsi < 30:
        buy_signals.append(f"RSI {rsi:.0f} — oversold קיצוני, לחץ מכירה מוגזם")
    elif rsi < 40:
        buy_signals.append(f"RSI {rsi:.0f} — oversold, הזדמנות")
    elif rsi > 75:
        sell_signals.append(f"RSI {rsi:.0f} — overbought, לא עכשיו")

    if trend == "Bullish":
        buy_signals.append("מגמה עולה — מעל MA50 וMA200")
    elif not above_200:
        sell_signals.append("מתחת MA200 — מגמה יורדת")
    else:
        wait_signals.append("מעל MA200 אך מתחת MA50 — תיקון בתוך עלייה")

    if macd_bull:
        buy_signals.append("MACD חיובי — מומנטום עולה")
    if bb_pct < 0.15:
        buy_signals.append("ליד Bollinger התחתון — לחץ מכירה מוגזם")
    if -25 <= pct_ath <= -10:
        buy_signals.append(f"{pct_ath:.0f}% מה-ATH — pullback בריא")

    if len(sell_signals) >= 2:
        action, color = "❌ אל תיכנס", "red"
        explanation = "מספר סיגנלים שליליים — המתן"
    elif len(buy_signals) >= 2 and fund_score >= 7.0:
        action, color = "✅ קנה עכשיו", "green"
        explanation = "סיגנלים חיוביים + פונדמנטלי חזק"
    elif len(buy_signals) >= 1 and fund_score >= 7.5:
        action, color = "✅ צבור הדרגתית", "green"
        explanation = "כניסה ראשונית — קנה חצי, הוסף בתיקון"
    else:
        action, color = "⏳ המתן לתמיכה", "amber"
        explanation = "מניה טובה אבל הטיימינג לא אידיאלי"

    risk = current - support_2 * 0.97 if support_2 > 0 else current * 0.10
    reward_est = current * 0.30
    rr_ratio = round(reward_est / risk, 1) if risk > 0 else 0

    if "✅" in action and rr_ratio > 3 and fund_score >= 8:
        position_usd = min(position_max, total_capital * 0.25)
        size_note = f"${position_usd:.0f} — ביטחון גבוה (25% מהתיק)"
    elif "✅" in action:
        position_usd = min(position_max, total_capital * 0.15)
        size_note = f"${position_usd:.0f} — כניסה בינונית (15%)"
    elif "צבור" in action:
        position_usd = min(position_max * 0.5, total_capital * 0.10)
        size_note = f"${position_usd:.0f} — כניסה ראשונית בלבד (10%)"
    else:
        position_usd = 0
        size_note = "לא להיכנס עדיין"

    dca_plan = []
    if position_usd > 0:
        third = position_usd / 3
        dca_plan = [
            f"כניסה ראשונה: ${third:.0f} עכשיו @ ${current:.2f}",
            f"כניסה שנייה: ${third:.0f} אם ירד ל-${support_1:.2f}",
            f"כניסה שלישית: ${third:.0f} אם ירד ל-${support_2:.2f}",
        ]

    return {
        "action": action,
        "action_color": color,
        "explanation": explanation,
        "buy_signals": buy_signals,
        "sell_signals": sell_signals,
        "wait_signals": wait_signals,
        "position_usd": round(position_usd, 0),
        "position_note": size_note,
        "dca_plan": dca_plan,
        "entry_now": round(current, 2),
        "entry_ideal": round(support_1 * 1.01, 2) if support_1 else round(current * 0.95, 2),
        "entry_patient": round(support_2 * 1.02, 2) if support_2 else round(current * 0.90, 2),
        "stop_loss": round(support_2 * 0.97, 2) if support_2 else round(current * 0.88, 2),
        "stop_loss_note": "אם נשבר — צא. לא לנחש.",
        "target_1y": _calc_target_1y(tech, current),
        "target_3y": _calc_target_3y(tech, current),
        "risk_reward": rr_ratio,
        "rr_note": "מצוין" if rr_ratio > 3 else "סביר" if rr_ratio > 2 else "נמוך מדי",
    }


def calc_darvas_box(history) -> dict:
    """Darvas Box — consolidation לפני פריצה."""
    try:
        close  = history["Close"]
        high   = history["High"]
        volume = history["Volume"]
        current   = float(close.iloc[-1])
        box_top   = float(high.rolling(20).max().iloc[-1])
        box_bottom = float(high.rolling(20).max().iloc[-21:-1].min()) if len(high) > 21 else float(high.min())
        vol_avg   = float(volume.rolling(20).mean().iloc[-1])
        vol_today = float(volume.iloc[-1])

        in_box        = box_bottom <= current <= box_top * 1.02
        box_tightness = (box_top - box_bottom) / box_bottom if box_bottom > 0 else 1
        breakout      = current > box_top * 1.01 and vol_today > vol_avg * 1.3
        near_breakout = box_top * 0.97 <= current <= box_top * 1.01

        score = 5.0
        if in_box and box_tightness < 0.08: score += 2.0
        elif in_box:                         score += 1.0
        if near_breakout:                    score += 1.5
        if breakout:                         score += 2.5

        return {
            "darvas_box_top":     round(box_top, 2),
            "darvas_box_bottom":  round(box_bottom, 2),
            "in_box":             in_box,
            "box_tightness_pct":  round(box_tightness * 100, 1),
            "near_breakout":      near_breakout,
            "confirmed_breakout": breakout,
            "darvas_score":       round(min(score, 10), 1),
            "signal": "🚀 פריצה מאושרת!" if breakout
                      else "⚡ קרוב לפריצה" if near_breakout
                      else "📦 Consolidating" if in_box
                      else "⚪ אין box",
        }
    except Exception:
        return {"darvas_score": 5.0, "signal": "N/A", "confirmed_breakout": False,
                "near_breakout": False, "in_box": False, "box_tightness_pct": 100,
                "darvas_box_top": 0, "darvas_box_bottom": 0}


def calc_bollinger_squeeze(history) -> dict:
    """Bollinger Band Squeeze — לפני תנועה גדולה."""
    try:
        close = history["Close"]
        std20 = close.rolling(20).std()
        ma20  = close.rolling(20).mean()
        bb_upper = ma20 + 2 * std20
        bb_lower = ma20 - 2 * std20
        bandwidth = ((bb_upper - bb_lower) / ma20).dropna()

        if len(bandwidth) < 126:
            return {"squeeze_active": False, "squeeze_score": 5.0,
                    "bw_percentile": 50, "breakout_direction": "N/A",
                    "signal": "⚪ אין מספיק נתונים"}

        current_bw   = float(bandwidth.iloc[-1])
        bw_6m_min    = float(bandwidth.iloc[-126:].min())
        bw_6m_max    = float(bandwidth.iloc[-126:].max())
        bw_percentile = (current_bw - bw_6m_min) / (bw_6m_max - bw_6m_min) \
                        if bw_6m_max != bw_6m_min else 0.5
        squeeze_active = bw_percentile < 0.20

        ema12 = close.ewm(span=12).mean()
        ema26 = close.ewm(span=26).mean()
        macd  = float((ema12 - ema26).iloc[-1])
        direction = "🟢 Up" if macd > 0 else "🔴 Down"

        score = 5.0
        if bw_percentile < 0.10:  score += 3.0
        elif bw_percentile < 0.20: score += 2.0
        elif bw_percentile < 0.30: score += 1.0

        return {
            "squeeze_active":     squeeze_active,
            "bw_percentile":      round(bw_percentile * 100, 1),
            "breakout_direction": direction if squeeze_active else "N/A",
            "squeeze_score":      round(min(score, 10), 1),
            "signal": f"🔥 Squeeze פעיל! {direction}" if squeeze_active
                      else "📊 ללא squeeze כרגע",
        }
    except Exception:
        return {"squeeze_active": False, "squeeze_score": 5.0,
                "bw_percentile": 50, "breakout_direction": "N/A",
                "signal": "⚪ שגיאה"}


def analyze_all(stocks: list) -> list:
    logger.info(f"Agent4: ניתוח טכני עבור {len(stocks)} מניות...")
    results = []
    for s in stocks:
        try:
            t = yf.Ticker(s["ticker"])
            history = t.history(period="1y")
        except Exception:
            history = pd.DataFrame()

        tech = analyze(s["ticker"], history if not history.empty else None)
        if tech is None:
            continue
        s.update(tech)

        # Darvas Box + Bollinger Squeeze
        if not history.empty and len(history) >= 50:
            s["darvas"]  = calc_darvas_box(history)
            s["squeeze"] = calc_bollinger_squeeze(history)
        else:
            s["darvas"]  = {"darvas_score": 5.0, "signal": "N/A", "confirmed_breakout": False,
                            "near_breakout": False, "in_box": False, "box_tightness_pct": 100,
                            "darvas_box_top": 0, "darvas_box_bottom": 0}
            s["squeeze"] = {"squeeze_active": False, "squeeze_score": 5.0,
                            "bw_percentile": 50, "breakout_direction": "N/A",
                            "signal": "⚪ אין נתונים"}

        results.append(s)
    logger.info(f"Agent4: {len(results)} מניות עם ניתוח טכני")
    return results
