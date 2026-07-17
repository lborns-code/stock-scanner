import logging
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from agents.database import DB_PATH
import sqlite3
from datetime import date
import os

logger = logging.getLogger(__name__)


def send_email_summary(stocks: list, portfolio: dict, macro: dict,
                       session: str, cfg: dict, no_report: bool = False):
    """שולח סיכום יומי למייל."""
    email_cfg = cfg.get("email", {})
    if not email_cfg.get("enabled"):
        return

    recipient = email_cfg.get("recipient", "")
    smtp_user = os.environ.get("GMAIL_SENDER", "")
    smtp_pass = os.environ.get("GMAIL_APP_PASSWORD", "")
    if not recipient or not smtp_user or not smtp_pass:
        logger.info("Email: חסרים פרטי SMTP — מדלג")
        return

    today = date.today().strftime("%d/%m/%Y")
    session_heb = "בוקר ☀️" if session == "AM" else "ערב 🌙"
    subject = f"📊 Stock Scanner {today} {session_heb}"

    if no_report:
        body_html = f"""
        <div dir="rtl" style="font-family:Arial;max-width:600px;margin:0 auto">
          <h2>📊 Stock Scanner — {today} {session_heb}</h2>
          <div style="background:#1a1a2e;color:#e6edf3;padding:20px;border-radius:12px">
            <h3 style="color:#f85149">🚫 אין דוח היום</h3>
            <p>שום מניה לא עמדה בקריטריון הציון המינימלי (8.8/10).</p>
            <p>המשך להמתין — הסורק יתריע ברגע שתופיע הזדמנות אמיתית.</p>
          </div>
        </div>"""
    else:
        regime = macro.get("regime", {})
        top = [s for s in stocks if s.get("basket") in ["A", "B"]][:10]

        rows = ""
        for s in top:
            score = s.get("total_score", 0)
            color = "#3fb950" if score >= 9 else "#d29922"
            entry = s.get("entry_ideal", s.get("current_price", 0))
            tech = s.get("technical_summary_hebrew", "")[:120]
            fund = s.get("fundamental_explanation_hebrew", "")[:120]
            rows += f"""
            <tr>
              <td style="padding:10px;border-bottom:1px solid #30363d">
                <strong style="color:#58a6ff;font-size:16px">{s['ticker']}</strong>
                <span style="color:#8b949e;font-size:12px"> — {s.get('company_name','')}</span><br>
                <span style="color:#8b949e;font-size:11px">{s.get('sector','')}</span>
              </td>
              <td style="padding:10px;border-bottom:1px solid #30363d;text-align:center">
                <strong style="color:{color};font-size:20px">{score}</strong><br>
                <span style="color:#8b949e;font-size:11px">/10</span>
              </td>
              <td style="padding:10px;border-bottom:1px solid #30363d;text-align:center">
                <strong style="color:#3fb950">${entry}</strong><br>
                <span style="color:#8b949e;font-size:11px">מחיר כניסה</span>
              </td>
              <td style="padding:10px;border-bottom:1px solid #30363d;font-size:11px;color:#8b949e">
                {tech}<br><br>{fund}
              </td>
            </tr>"""

        body_html = f"""
        <div dir="rtl" style="font-family:Arial;max-width:700px;margin:0 auto;background:#0d1117;color:#e6edf3;padding:20px;border-radius:12px">
          <h2 style="color:#58a6ff">📊 Stock Scanner — {today} {session_heb}</h2>
          <p style="color:#8b949e">שוק: <strong>{regime.get('hebrew','')}</strong> | {regime.get('action','')}</p>
          <table style="width:100%;border-collapse:collapse;background:#161b22;border-radius:8px;overflow:hidden">
            <thead>
              <tr style="background:#21262d">
                <th style="padding:10px;text-align:right;color:#8b949e">מניה</th>
                <th style="padding:10px;color:#8b949e">ציון</th>
                <th style="padding:10px;color:#8b949e">כניסה</th>
                <th style="padding:10px;text-align:right;color:#8b949e">סיכום</th>
              </tr>
            </thead>
            <tbody>{rows}</tbody>
          </table>
          <p style="color:#8b949e;font-size:12px;margin-top:16px">
            📂 הדוח המלא זמין ב-GitHub Actions Artifacts
          </p>
        </div>"""

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = smtp_user
        msg["To"] = recipient
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, recipient, msg.as_string())
        logger.info(f"Email נשלח ל-{recipient}")
    except Exception as e:
        logger.warning(f"Email send failed: {e}")


def send_telegram(message: str, cfg: dict):
    tg = cfg.get("telegram", {})
    if not tg.get("enabled"):
        logger.debug("Telegram disabled in config")
        return
    token = tg.get("bot_token", "")
    chat_id = tg.get("chat_id", "")
    if not token or not chat_id:
        logger.warning("Telegram: missing bot_token or chat_id")
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        resp = requests.post(url, data={"chat_id": chat_id, "text": message, "parse_mode": "HTML"}, timeout=10)
        if not resp.ok:
            logger.warning(f"Telegram API error: {resp.status_code} {resp.text[:200]}")
        else:
            logger.info(f"Telegram sent ({len(message)} chars)")
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


def send_daily_digest(stocks: list, portfolio: dict, macro: dict, session: str, cfg: dict, no_report: bool = False):
    """שולח תקציר יומי מפורט לטלגרם."""
    tg = cfg.get("telegram", {})
    logger.info(f"send_daily_digest: telegram enabled={tg.get('enabled')}, no_report={no_report}, stocks={len(stocks)}")
    if not tg.get("enabled"):
        logger.warning("send_daily_digest: Telegram not enabled — skipping")
        return

    today = date.today().strftime("%d/%m/%Y")
    session_heb = "בוקר ☀️" if session == "AM" else "ערב 🌙"
    regime = macro.get("regime", {})
    regime_emoji = {"FEAR": "🟢", "VOLATILE": "⚠️", "EUPHORIA": "🔴", "NORMAL": "📊"}.get(
        regime.get("regime", "NORMAL"), "📊"
    )

    lines = [f"📊 <b>Stock Scanner — {today} {session_heb}</b>",
             f"{regime_emoji} שוק: {regime.get('hebrew','נורמלי')} | {regime.get('action','')}",
             ""]

    if no_report:
        lines += [
            "🚫 <b>אין דוח היום</b>",
            "שום מניה לא עמדה בציון מינימלי 8.8/10.",
            "הסורק ממשיך לעקוב — תקבל התראה ברגע שתופיע הזדמנות.",
        ]
        send_telegram("\n".join(lines), cfg)
        return

    top = [s for s in stocks if s.get("basket") in ["A", "B"]][:10]

    if not top:
        lines += ["🚫 <b>אין המלצות היום</b>"]
        send_telegram("\n".join(lines), cfg)
        return

    lines.append(f"🏆 <b>Top {len(top)} הזדמנויות — ציון 8.8+:</b>")
    lines.append("")

    for i, s in enumerate(top, 1):
        ticker = s["ticker"]
        score = s.get("total_score", 0)
        price = s.get("current_price", 0)
        entry = s.get("entry_ideal", price)
        target1y = s.get("target_1y", 0)
        moat = s.get("moat_type", "None")
        basket = s.get("basket", "")
        action = s.get("action", "⏳ המתן")
        rsi = s.get("rsi_14", 50)
        pct_ath = s.get("pct_from_ath", 0)
        pe = s.get("pe_forward", 0) or s.get("pe_ttm", 0) or 0
        analyst_target = s.get("analyst_target_mean", 0)
        analyst_count = s.get("analyst_count", 0)
        sector = s.get("sector", "")

        moat_emoji = {"Wide": "🏰", "Narrow": "🛡", "None": "—"}.get(moat, "—")
        score_emoji = "⭐⭐" if score >= 9.5 else "⭐" if score >= 9 else "🔶"

        lines.append(f"{i}. {score_emoji} <b>{ticker}</b> [{basket}] — <b>{score}/10</b>")
        lines.append(f"   📍 {s.get('company_name','')} | {sector}")
        lines.append(f"   💰 מחיר: ${price} | כניסה מומלצת: <b>${entry}</b> | Target 1y: ${target1y}")
        lines.append(f"   {action}")

        # טכני בעברית קצר
        tech_short = s.get("technical_summary_hebrew", "")
        if tech_short:
            lines.append(f"   📈 <i>{tech_short[:180]}</i>")

        # פונדמנטלס קצר
        fund_short = s.get("fundamental_explanation_hebrew", "")
        if fund_short:
            lines.append(f"   📊 <i>{fund_short[:180]}</i>")

        # חפיר + RSI + PE
        details = f"   {moat_emoji} חפיר: {moat} | RSI: {rsi}"
        if pe > 0:
            details += f" | P/E: {pe:.0f}"
        if pct_ath:
            details += f" | {pct_ath:.0f}% מהשיא"
        lines.append(details)

        # קונזנזוס אנליסטים
        if analyst_target and analyst_count >= 3:
            upside = ((analyst_target - price) / price * 100) if price else 0
            lines.append(f"   👥 {analyst_count} אנליסטים | Target: ${analyst_target:.0f} ({upside:+.0f}%)")

        # גיאופוליטי אם קיים
        geo = s.get("geopolitical_impact_hebrew", "")
        if geo:
            lines.append(f"   🌍 <i>{geo[:120]}</i>")

        lines.append("")

    # התראות פורטפוליו
    warnings = []
    for p in portfolio.get("positions", []):
        if not p.get("above_ma200"):
            warnings.append(f"🔴 {p['ticker']} מתחת MA200 — שקול stop loss")
        elif p.get("rsi_14", 50) > 72:
            warnings.append(f"⚠️ {p['ticker']} RSI גבוה ({p.get('rsi_14',0):.0f})")
    if warnings:
        lines.append("⚠️ <b>התראות תיק:</b>")
        lines.extend(warnings)
        lines.append("")

    lines.append("📂 <i>דוח מלא — GitHub Actions Artifacts</i>")

    # טלגרם מגביל הודעה ל-4096 תווים — שלח בחלקים אם צריך
    full_msg = "\n".join(lines)
    if len(full_msg) <= 4096:
        send_telegram(full_msg, cfg)
    else:
        # שלח ראש + כל מניה בנפרד
        send_telegram("\n".join(lines[:4]), cfg)
        chunk = []
        for line in lines[4:]:
            chunk.append(line)
            if len("\n".join(chunk)) > 3800:
                send_telegram("\n".join(chunk), cfg)
                chunk = []
        if chunk:
            send_telegram("\n".join(chunk), cfg)

    _log_alert("DIGEST", "DAILY_DIGEST", f"{today} {session_heb} — {len(top)} מניות", tg.get("enabled", False))


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

        # Alert when price hits support level (within 3%)
        support = s.get("support_1", 0)
        if support and price > 0 and score >= 7.0:
            pct_from_support = (price - support) / support * 100
            if 0 <= pct_from_support <= 3:
                msg = (f"🎯 <b>{ticker}</b> — הגיע לרמת תמיכה!\n"
                       f"מחיר: ${price:.2f} | Support: ${support:.2f}\n"
                       f"ציון: {score}/10 | ⚡ הזדמנות כניסה")
                send_telegram(msg, cfg)
                _log_alert(ticker, "AT_SUPPORT", msg, tg_enabled)
