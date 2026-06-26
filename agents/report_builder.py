import logging
from datetime import date, datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

REPORTS_DIR = Path("reports")


def build_report(stocks, macro, portfolio, session, today, prev_scores, cfg) -> Path:
    REPORTS_DIR.mkdir(exist_ok=True)

    baskets = {"A": [], "B": [], "C": []}
    for s in stocks:
        b = s.get("basket")
        if b in baskets:
            baskets[b].append(s)

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

    env = Environment(loader=FileSystemLoader("templates"), autoescape=True)
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
        cfg=cfg,
    )

    filename = (REPORTS_DIR / f"report_{today}_{session}.html").resolve()
    filename.write_text(html, encoding="utf-8")
    return filename
