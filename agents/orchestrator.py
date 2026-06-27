import json
import logging
import os
import webbrowser
from datetime import date
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from agents import (
    agent1_universe, agent2_data, agent3_moat,
    agent4_technical, agent5_sentiment, agent6_scorer,
    macro_analyzer, alerts, psychology_guard,
    position_manager, backtester, database
)
from agents.report_builder import build_report

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self, session: str = "AM"):
        self.session = session
        self.cfg = json.loads(Path("config.json").read_text(encoding="utf-8"))
        # allow override via environment variable
        if os.environ.get("ANTHROPIC_API_KEY"):
            self.cfg["anthropic_api_key"] = os.environ["ANTHROPIC_API_KEY"]
        if os.environ.get("TELEGRAM_BOT_TOKEN"):
            self.cfg.setdefault("telegram", {})["bot_token"] = os.environ["TELEGRAM_BOT_TOKEN"]
            self.cfg.setdefault("telegram", {})["enabled"] = True
        if os.environ.get("TELEGRAM_CHAT_ID"):
            self.cfg.setdefault("telegram", {})["chat_id"] = os.environ["TELEGRAM_CHAT_ID"]

    def run(self):
        today = date.today().isoformat()
        logger.info(f"=== Stock Scanner {today} {self.session} ===")

        # 1. Macro
        logger.info("שלב 1: Macro")
        macro_data = macro_analyzer.analyze()

        # 2. Universe
        logger.info("שלב 2: Universe")
        tickers = agent1_universe.build_universe(self.cfg)

        # 3. Data
        logger.info("שלב 3: Data")
        stocks = agent2_data.fetch_all(tickers)

        # 4. Moat / Claude
        logger.info("שלב 4: Moat Analysis")
        stocks = agent3_moat.analyze_batch(stocks, self.cfg)

        # 5. Technical
        logger.info("שלב 5: Technical")
        stocks = agent4_technical.analyze_all(stocks)

        # 6. Sentiment
        logger.info("שלב 6: Sentiment")
        stocks = agent5_sentiment.analyze_all(stocks)

        # 7. Score & Rank
        logger.info("שלב 7: Scoring")
        stocks = agent6_scorer.score_and_rank(stocks, self.cfg)

        # Previous scores for comparison
        prev_scores = database.get_previous_scores(today, self.session)

        # Psychology notes
        for s in stocks:
            hist = database.get_ticker_history(s["ticker"])
            s["psychology_note"] = psychology_guard.get_psychology_note(
                s["ticker"], s.get("action", ""), s.get("pct_from_ath", 0), hist
            )

        # Portfolio status
        data_map = {s["ticker"]: s for s in stocks}
        profile = self.cfg.get("investor_profile", {})
        portfolio = position_manager.get_portfolio_status(
            self.cfg.get("watchlist", []),
            data_map,
            profile.get("total_capital_usd", 1100)
        )

        # Alerts
        alerts.check_and_alert(stocks, self.cfg)
        alerts.send_daily_digest(stocks, portfolio, macro_data, self.session, self.cfg)

        # Save to DB
        database.save_scores(today, self.session, stocks)
        backtester.add_recommendations(stocks, self.session)

        # Report
        report_path = build_report(
            stocks=stocks,
            macro=macro_data,
            portfolio=portfolio,
            session=self.session,
            today=today,
            prev_scores=prev_scores,
            cfg=self.cfg,
        )
        logger.info(f"דוח נשמר: {report_path}")

        if self.cfg.get("open_browser") and report_path.exists():
            webbrowser.open(report_path.as_uri())

        return stocks
