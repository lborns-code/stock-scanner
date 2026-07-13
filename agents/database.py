import sqlite3
from pathlib import Path

DB_PATH = Path("data/scanner.db")


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS daily_scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT, session TEXT, ticker TEXT,
        total_score REAL, basket TEXT,
        action TEXT, position_usd REAL,
        entry_price REAL, stop_loss REAL,
        target_1y REAL, target_3y REAL,
        multibagger_potential TEXT,
        verdict TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS performance_tracking (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        recommended_date TEXT, ticker TEXT,
        price_at_rec REAL, position_usd REAL,
        price_7d REAL, price_30d REAL,
        price_90d REAL, price_365d REAL,
        return_7d_pct REAL, return_30d_pct REAL,
        return_90d_pct REAL, return_365d_pct REAL
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS alerts_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT, ticker TEXT,
        alert_type TEXT, message TEXT, sent INTEGER
    )""")

    conn.commit()
    conn.close()


def save_scores(date: str, session: str, stocks: list):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for s in stocks:
        c.execute("""INSERT INTO daily_scores
            (date, session, ticker, total_score, basket, action, position_usd,
             entry_price, stop_loss, target_1y, target_3y, multibagger_potential, verdict)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (date, session, s.get("ticker"), s.get("total_score"),
             s.get("basket"), s.get("action"), s.get("position_usd"),
             s.get("entry_now"), s.get("stop_loss"), s.get("target_1y"),
             s.get("target_3y"), s.get("multibagger_potential"),
             s.get("verdict_hebrew", "")))
    conn.commit()
    conn.close()


def get_previous_scores(date: str, session: str) -> dict:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""SELECT ticker, total_score, basket FROM daily_scores
                 WHERE date < ? ORDER BY date DESC LIMIT 500""", (date,))
    rows = c.fetchall()
    conn.close()
    result = {}
    for ticker, score, basket in rows:
        if ticker not in result:
            result[ticker] = {"total_score": score, "basket": basket}
    return result


def get_ticker_history(ticker: str) -> list:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT date, total_score FROM daily_scores WHERE ticker=? ORDER BY date DESC LIMIT 30", (ticker,))
    rows = c.fetchall()
    conn.close()
    return rows
