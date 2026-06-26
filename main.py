import schedule
import time
import logging
import sys
from pathlib import Path
from agents.orchestrator import Orchestrator
from agents.database import init_db

log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(
            log_dir / f"{__import__('datetime').date.today()}.log",
            encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

US_HOLIDAYS = {
    "2025-01-01", "2025-01-20", "2025-02-17", "2025-04-18",
    "2025-05-26", "2025-06-19", "2025-07-04", "2025-09-01",
    "2025-11-27", "2025-12-25", "2026-01-01", "2026-01-19",
    "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19",
    "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
}


def is_trading_day() -> bool:
    import datetime
    t = datetime.date.today()
    return t.weekday() < 5 and t.isoformat() not in US_HOLIDAYS


def run(session: str):
    if not is_trading_day():
        logging.info("לא יום מסחר — מדלג")
        return
    logging.info(f"=== מתחיל סריקה {session} ===")
    try:
        Orchestrator(session=session).run()
        logging.info(f"=== סריקה {session} הושלמה ===")
    except Exception as e:
        logging.error(f"שגיאה: {e}", exc_info=True)


if __name__ == "__main__":
    init_db()

    if "--demo" in sys.argv:
        from agents.demo_data import DEMO_STOCKS, DEMO_PORTFOLIO, DEMO_MACRO
        from agents.report_builder import build_report
        from datetime import date
        import json
        from pathlib import Path
        cfg = json.loads(Path("config.json").read_text(encoding="utf-8"))
        session = "PM" if "--pm" in sys.argv else "AM"
        today = date.today().isoformat()
        path = build_report(
            stocks=DEMO_STOCKS,
            macro=DEMO_MACRO,
            portfolio=DEMO_PORTFOLIO,
            session=session,
            today=today,
            prev_scores={},
            cfg=cfg,
        )
        logging.info(f"דוח דמו: {path}")
        if cfg.get("open_browser"):
            import webbrowser
            webbrowser.open(path.as_uri())
        sys.exit(0)

    if "--now" in sys.argv:
        session = "PM" if "--pm" in sys.argv else "AM"
        run(session)
    else:
        from json import load
        cfg = load(open("config.json", encoding="utf-8"))
        morning = cfg["run_times"]["morning"]
        evening = cfg["run_times"]["evening"]

        schedule.every().day.at(morning).do(run, "AM")
        schedule.every().day.at(evening).do(run, "PM")

        logging.info(f"פעיל — בוקר: {morning} | ערב: {evening}")
        while True:
            schedule.run_pending()
            time.sleep(30)
