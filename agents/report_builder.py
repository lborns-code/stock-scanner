import logging
import sqlite3
from datetime import date, datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from agents.database import DB_PATH

logger = logging.getLogger(__name__)

REPORTS_DIR = Path("reports")


def _get_performance_history() -> list:
    """שולף המלצות עבר עם תשואות בפועל."""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""SELECT recommended_date, ticker, price_at_rec,
                            return_7d_pct, return_30d_pct, return_90d_pct, return_365d_pct
                     FROM performance_tracking
                     ORDER BY recommended_date DESC LIMIT 30""")
        rows = c.fetchall()
        conn.close()
        result = []
        for row in rows:
            result.append({
                "date": row[0],
                "ticker": row[1],
                "price_at_rec": row[2],
                "ret_7d": row[3],
                "ret_30d": row[4],
                "ret_90d": row[5],
                "ret_365d": row[6],
            })
        return result
    except Exception:
        return []


def _make_sparkline(prices: list, width: int = 120, height: int = 36) -> str:
    """מייצר SVG sparkline מרשימת מחירים."""
    if not prices or len(prices) < 2:
        return ""
    lo, hi = min(prices), max(prices)
    rng = hi - lo or 1
    pad = 2
    def x(i): return round(pad + i * (width - 2*pad) / (len(prices)-1), 1)
    def y(p): return round(pad + (1 - (p - lo) / rng) * (height - 2*pad), 1)
    pts = " ".join(f"{x(i)},{y(p)}" for i, p in enumerate(prices))
    color = "#3fb950" if prices[-1] >= prices[0] else "#f85149"
    return (f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
            f'xmlns="http://www.w3.org/2000/svg" style="display:block">'
            f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.5" '
            f'stroke-linejoin="round" stroke-linecap="round"/></svg>')


def build_report(stocks, macro, portfolio, session, today, prev_scores, cfg) -> Path:
    REPORTS_DIR.mkdir(exist_ok=True)

    max_stocks = cfg.get("filters", {}).get("max_stocks_in_report", 10)

    baskets = {"A": [], "B": [], "C": []}
    for s in stocks:
        b = s.get("basket")
        if b in baskets:
            baskets[b].append(s)

    # הגבלה ל-10 מניות (A+B ביחד, לפי ציון)
    ab_stocks = sorted(baskets["A"] + baskets["B"],
                       key=lambda x: x.get("total_score", 0), reverse=True)
    top_ab = ab_stocks[:max_stocks]
    baskets["A"] = [s for s in top_ab if s.get("basket") == "A"]
    baskets["B"] = [s for s in top_ab if s.get("basket") == "B"]

    no_report = len(top_ab) == 0

    # For basket C — ensure watchlist stocks appear even if not in scored list
    data_map = {s["ticker"]: s for s in stocks}
    for ticker in cfg.get("watchlist", []):
        if not any(s["ticker"] == ticker for s in baskets["C"]):
            if ticker in data_map:
                baskets["C"].append(data_map[ticker])

    # Changes vs previous run
    changes = []
    current_tickers = {s["ticker"] for s in stocks}
    prev_tickers = set(prev_scores.keys())
    new_entries = current_tickers - prev_tickers
    removed = prev_tickers - current_tickers
    for t in new_entries:
        s = data_map.get(t)
        if s:
            changes.append({"type": "new", "ticker": t, "score": s.get("total_score", 0)})
    for t in removed:
        changes.append({"type": "removed", "ticker": t, "score": prev_scores[t].get("total_score", 0)})
    for t in current_tickers & prev_tickers:
        s = data_map.get(t)
        if s:
            delta = round(s.get("total_score", 0) - prev_scores[t].get("total_score", 0), 2)
            if abs(delta) >= 0.3:
                changes.append({"type": "changed", "ticker": t,
                                 "score": s.get("total_score", 0), "delta": delta})

    # Generate sparklines per stock
    for s in stocks:
        s["sparkline_svg"] = _make_sparkline(s.get("price_history_30d", []))

    env = Environment(loader=FileSystemLoader("templates"), autoescape=True)
    env.globals["make_sparkline"] = _make_sparkline
    template = env.get_template("report.html")

    html = template.render(
        today=today,
        now=datetime.now().strftime("%H:%M"),
        session=session,
        macro=macro,
        baskets=baskets,
        portfolio=portfolio,
        changes=changes,
        prev_scores=prev_scores,
        performance_history=_get_performance_history(),
        cfg=cfg,
        no_report=no_report,
        all_stocks_json=__import__("json").dumps(
            [{k: v for k, v in s.items() if k not in ("sparkline_svg", "price_history_30d")}
             for s in stocks],
            ensure_ascii=False,
        ),
    )

    filename = (REPORTS_DIR / f"report_{today}_{session}.html").resolve()
    filename.write_text(html, encoding="utf-8")
    return filename
