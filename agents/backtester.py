import logging
import sqlite3
import yfinance as yf
from datetime import date, timedelta
from agents.database import DB_PATH

logger = logging.getLogger(__name__)


def update_performance():
    """מעדכן תשואות בפועל להמלצות קודמות."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""SELECT id, recommended_date, ticker, price_at_rec
                     FROM performance_tracking
                     WHERE price_365d IS NULL""")
        rows = c.fetchall()
        conn.close()

        today = date.today()
        for row_id, rec_date_str, ticker, price_at_rec in rows:
            try:
                rec_date = date.fromisoformat(rec_date_str)
                t = yf.Ticker(ticker)
                hist = t.history(period="400d")
                if hist.empty:
                    continue

                def price_on(target: date):
                    idx = hist.index.date
                    mask = idx <= target
                    if not mask.any():
                        return None
                    return float(hist["Close"][mask].iloc[-1])

                p7 = price_on(rec_date + timedelta(days=7))
                p30 = price_on(rec_date + timedelta(days=30))
                p90 = price_on(rec_date + timedelta(days=90))
                p365 = price_on(rec_date + timedelta(days=365))

                def pct(p):
                    if p and price_at_rec:
                        return round((p - price_at_rec) / price_at_rec * 100, 2)
                    return None

                conn = sqlite3.connect(DB_PATH)
                conn.execute("""UPDATE performance_tracking SET
                    price_7d=?, price_30d=?, price_90d=?, price_365d=?,
                    return_7d_pct=?, return_30d_pct=?, return_90d_pct=?, return_365d_pct=?
                    WHERE id=?""",
                    (p7, p30, p90, p365, pct(p7), pct(p30), pct(p90), pct(p365), row_id))
                conn.commit()
                conn.close()
            except Exception as e:
                logger.debug(f"Performance update {ticker}: {e}")

    except Exception as e:
        logger.warning(f"Backtester error: {e}")


def add_recommendations(stocks: list, session: str):
    """מוסיף המלצות חדשות למעקב."""
    today = date.today().isoformat()
    try:
        conn = sqlite3.connect(DB_PATH)
        for s in stocks:
            if s.get("basket") in ["A", "B"]:
                conn.execute("""INSERT OR IGNORE INTO performance_tracking
                    (recommended_date, ticker, price_at_rec, position_usd)
                    VALUES (?,?,?,?)""",
                    (today, s["ticker"], s.get("current_price", 0), s.get("position_usd", 0)))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Add recommendations: {e}")
