import logging
import requests
from agents.database import DB_PATH
import sqlite3
from datetime import date

logger = logging.getLogger(__name__)


def send_telegram(message: str, cfg: dict):
    tg = cfg.get("telegram", {})
    if not tg.get("enabled"):
        return
    token = tg.get("bot_token", "")
    chat_id = tg.get("chat_id", "")
    if not token or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, data={"chat_id": chat_id, "text": message, "parse_mode": "HTML"}, timeout=10)
    except Exception as e:
        logger.warning(f"Telegram send failed: {e}")


def _log_alert(ticker: str, alert_type: str, message: str, sent: bool):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO alerts_log (date, ticker, alert_type, message, sent) VALUES (?,?,?,?,?)",
            (date.today().isoformat(), ticker, alert_type, message, int(sent))
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def send_daily_digest(stocks: list, portfolio: dict, macro: dict, session: str, cfg: dict):
    """שולח תקציר יומי לטלגרם — Top picks + פורטפוליו + מאקרו."""
    tg = cfg.get("telegram", {})
    if not tg.get("enabled"):
        return

    today = date.today().strftime("%d/%m/%Y")
    session_heb = "בוקר ☀️" if session == "AM" else "ערב 🌙"

    regime = macro.get("regime", {})
    regime_emoji = {"FEAR": "🟢", "VOLATILE": "⚠️", "EUPHORIA": "🔴", "NORMAL": "📊"}.get(
        regime.get("regime", "NORMAL"), "📊"
    )
    regime_text = regime.get("hebrew", "נורמלי")

    lines = [
        f"📊 <b>Stock Scanner — {today} {session_heb}</b>",
        f"{regime_emoji} שוק: {regime_text}",
        "",
        "🏆 <b>Top Picks היום:</b>",
    ]

    top = [s for s in stocks if s.get("basket") in ["A", "B"]][:5]
    for i, s in enumerate(top, 1):
        ticker = s["ticker"]
        score = s.get("total_score", 0)
        action = s.get("action", "⏳ המתן")
        price = s.get("current_price", 0)
        multi = s.get("multibagger_potential", "Low")
        basket = s.get("basket", "")
        multi_emoji = {"Very High": "🚀🚀", "High": "🚀", "Medium": "📈"}.get(multi, "")
        lines.append(f"{i}. <b>{ticker}</b> [{basket}] — {score}/10 {multi_emoji}")
        lines.append(f"   ${price} | {action}")

    # Portfolio alerts
    warnings = []
    for p in portfolio.get("positions", []):
        if not p.get("above_ma200"):
            warnings.append(f"🔴 {p['ticker']} מתחת MA200")
        elif p.get("rsi_14", 50) > 72:
            warnings.append(f"⚠️ {p['ticker']} RSI גבוה ({p.get('rsi_14',0):.0f})")

    if warnings:
        lines.append("")
        lines.append("⚠️ <b>התראות פורטפוליו:</b>")
        lines.extend(warnings)

    lines.append("")
    lines.append("📂 <i>הדוח המלא ב-GitHub Actions Artifacts</i>")

    send_telegram("\n".join(lines), cfg)
    _log_alert("DIGEST", "DAILY_DIGEST", "\n".join(lines[:3]), tg.get("enabled", False))


def check_and_alert(stocks: list, cfg: dict):
    tg_enabled = cfg.get("telegram", {}).get("enabled", False)

    for s in stocks:
        ticker = s["ticker"]
        rsi = s.get("rsi_14", 50)
        score = s.get("total_score", 0)
        price = s.get("current_price", 0)
        pct_ath = s.get("pct_from_ath", 0)

        if rsi < 32 and score >= 7.0:
            msg = (f"🟢 <b>{ticker}</b> — RSI {rsi:.0f} (oversold)\n"
                   f"ציון: {score}/10 | מחיר: ${price}\n"
                   f"⚡ שקול כניסה")
            send_telegram(msg, cfg)
            _log_alert(ticker, "RSI_OVERSOLD", msg, tg_enabled)

        if pct_ath < -30 and score >= 7.5:
            msg = (f"📉 <b>{ticker}</b> — {pct_ath:.0f}% מה-ATH\n"
                   f"ציון: {score}/10 | מחיר: ${price}\n"
                   f"⚡ Pullback משמעותי על מניה איכותית")
            send_telegram(msg, cfg)
            _log_alert(ticker, "PULLBACK", msg, tg_enabled)

        days = s.get("days_to_earnings")
        if days and 3 <= days <= 7:
            msg = (f"⚠️ <b>{ticker}</b> — Earnings בעוד {days:.0f} ימים\n"
                   f"שקול להמתין לפני כניסה")
            send_telegram(msg, cfg)

        if score >= 9.0:
            msg = (f"⭐ <b>TOP PICK: {ticker}</b>\n"
                   f"ציון: {score}/10\n"
                   f"כניסה: ${s.get('entry_ideal')} | Target 3y: ${s.get('target_3y')}")
            send_telegram(msg, cfg)
            _log_alert(ticker, "TOP_PICK", msg, tg_enabled)

        if ticker in cfg.get("watchlist", []) and not s.get("above_ma200"):
            msg = (f"🔴 <b>{ticker}</b> (בפורטפוליו) — ירד מתחת MA200\n"
                   f"שקול stop loss")
            send_telegram(msg, cfg)
            _log_alert(ticker, "BELOW_MA200", msg, tg_enabled)
