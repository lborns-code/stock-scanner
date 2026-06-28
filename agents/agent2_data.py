import logging
import json
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import yfinance as yf
import pandas as pd

logger = logging.getLogger(__name__)

CACHE_DIR = Path("data/cache")
CACHE_HOURS = 4


def _cache_path(ticker: str) -> Path:
    return CACHE_DIR / f"{ticker}.json"


def _load_cache(ticker: str) -> dict | None:
    p = _cache_path(ticker)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        cached_at = datetime.fromisoformat(data.get("_cached_at", "2000-01-01"))
        if datetime.now() - cached_at < timedelta(hours=CACHE_HOURS):
            return data
    except Exception:
        pass
    return None


def _save_cache(ticker: str, data: dict):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    data["_cached_at"] = datetime.now().isoformat()
    try:
        _cache_path(ticker).write_text(
            json.dumps(data, ensure_ascii=False, default=str), encoding="utf-8"
        )
    except Exception:
        pass


def check_earnings_quality(data: dict) -> dict:
    net_income = data.get("net_margin", 0) * data.get("revenue_ttm", 0)
    fcf = data.get("fcf_ttm", 0)
    assets = data.get("market_cap", 1) * 0.5

    accruals = (net_income - fcf) / assets if assets > 0 else 0

    flags = []
    if accruals > 0.1:
        flags.append("⚠️ רווחים גבוהים מ-FCF — איכות נמוכה")
    if data.get("shares_change_yoy", 0) > 0.05:
        flags.append("⚠️ דילול מניות משמעותי")
    if data.get("revenue_growth_yoy", 0) < 0 and data.get("net_margin", 0) > 0:
        flags.append("⚠️ הכנסות יורדות אבל רווח עולה — חשוד")

    return {
        "accruals_ratio": round(accruals, 3),
        "earnings_quality": "High" if len(flags) == 0 else "Medium" if len(flags) == 1 else "Low",
        "earnings_flags": flags,
        "quality_score_bonus": 0.5 if len(flags) == 0 else -0.3 * len(flags),
    }


def fetch_ticker(ticker: str) -> dict | None:
    cached = _load_cache(ticker)
    if cached:
        return cached

    try:
        t = yf.Ticker(ticker)
        info = t.info or {}

        if not info.get("regularMarketPrice") and not info.get("currentPrice"):
            return None

        history = t.history(period="1y")
        if history.empty or len(history) < 50:
            return None

        current_price = info.get("currentPrice") or info.get("regularMarketPrice") or float(history["Close"].iloc[-1])
        high_52w = info.get("fiftyTwoWeekHigh") or float(history["High"].max())
        low_52w = info.get("fiftyTwoWeekLow") or float(history["Low"].min())

        close = history["Close"]
        price_1m = float(close.iloc[-22]) if len(close) > 22 else current_price
        price_3m = float(close.iloc[-63]) if len(close) > 63 else current_price
        price_1m_pct = (current_price - price_1m) / price_1m if price_1m else 0
        price_3m_pct = (current_price - price_3m) / price_3m if price_3m else 0

        revenue_ttm = info.get("totalRevenue", 0) or 0
        revenue_growth = info.get("revenueGrowth", 0) or 0
        gross_margin = info.get("grossMargins", 0) or 0
        op_margin = info.get("operatingMargins", 0) or 0
        net_margin = info.get("profitMargins", 0) or 0

        fcf_ttm = info.get("freeCashflow", 0) or 0
        fcf_margin = fcf_ttm / revenue_ttm if revenue_ttm else 0

        total_assets = info.get("totalAssets", 0) or 1
        net_income = net_margin * revenue_ttm
        roic_approx = net_income / (info.get("totalDebt", 1) + info.get("totalStockholderEquity", 1) or 1)
        roe = info.get("returnOnEquity", 0) or 0

        rd_expense = info.get("researchAndDevelopment", 0) or 0
        capex = abs(info.get("capitalExpenditures", 0) or 0)

        data = {
            "ticker": ticker,
            "company_name": info.get("longName", ticker),
            "sector": info.get("sector", "Unknown"),
            "industry": info.get("industry", "Unknown"),
            "current_price": round(current_price, 2),
            "price_52w_high": round(high_52w, 2),
            "price_52w_low": round(low_52w, 2),
            "pct_from_52w_high": round((current_price - high_52w) / high_52w * 100, 1) if high_52w else 0,
            "price_change_1m_pct": round(price_1m_pct * 100, 1),
            "price_change_3m_pct": round(price_3m_pct * 100, 1),
            "avg_volume_30d": info.get("averageVolume", 0) or 0,
            "today_volume": info.get("volume", 0) or 0,
            "market_cap": info.get("marketCap", 0) or 0,
            "revenue_ttm": revenue_ttm,
            "revenue_growth_yoy": revenue_growth,
            "gross_margin": gross_margin,
            "operating_margin": op_margin,
            "net_margin": net_margin,
            "fcf_ttm": fcf_ttm,
            "fcf_margin": round(fcf_margin, 3),
            "roic": round(roic_approx, 3),
            "roe": roe,
            "debt_to_equity": info.get("debtToEquity", 0) or 0,
            "current_ratio": info.get("currentRatio", 0) or 0,
            "cash": info.get("totalCash", 0) or 0,
            "eps_ttm": info.get("trailingEps", 0) or 0,
            "eps_growth_yoy": info.get("earningsGrowth", 0) or 0,
            "rd_expense": rd_expense,
            "capex": capex,
            "capex_growth_yoy": 0,
            "shares_outstanding": info.get("sharesOutstanding", 0) or 0,
            "shares_change_yoy": info.get("sharesPercentSharesOut", 0) or 0,
            "short_interest_pct": info.get("shortPercentOfFloat", 0) or 0,
            "short_ratio": info.get("shortRatio", 0) or 0,
            "pe_ttm": info.get("trailingPE", 0) or 0,
            "pe_forward": info.get("forwardPE", 0) or 0,
            "ps_ratio": info.get("priceToSalesTrailing12Months", 0) or 0,
            "pb_ratio": info.get("priceToBook", 0) or 0,
            "ev_ebitda": info.get("enterpriseToEbitda", 0) or 0,
            "peg_ratio": info.get("pegRatio", 0) or 0,
            "analyst_consensus": info.get("recommendationKey", "hold") or "hold",
            "analyst_target_mean": info.get("targetMeanPrice", 0) or 0,
            "analyst_target_high": info.get("targetHighPrice", 0) or 0,
            "analyst_target_low": info.get("targetLowPrice", 0) or 0,
            "analyst_count": info.get("numberOfAnalystOpinions", 0) or 0,
            "days_to_earnings": None,
            "history_rows": len(history),
        }

        quality = check_earnings_quality(data)
        data.update(quality)

        # News headlines (last 5, free via yfinance)
        try:
            news_items = t.news or []
            data["news_headlines"] = [
                n.get("content", {}).get("title", "") or n.get("title", "")
                for n in news_items[:5]
                if (n.get("content", {}).get("title") or n.get("title", ""))
            ]
        except Exception:
            data["news_headlines"] = []

        # Price history for sparkline (last 30 days close prices)
        try:
            hist30 = history["Close"].iloc[-30:].round(2).tolist()
            data["price_history_30d"] = hist30
        except Exception:
            data["price_history_30d"] = []

        _save_cache(ticker, data)
        return data

    except Exception as e:
        logger.debug(f"fetch {ticker} failed: {e}")
        return None


def fetch_all(tickers: list, max_workers: int = 10) -> list:
    logger.info(f"Agent2: שולף נתונים עבור {len(tickers)} מניות...")
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(fetch_ticker, t): t for t in tickers}
        for i, future in enumerate(as_completed(futures)):
            ticker = futures[future]
            try:
                data = future.result()
                if data:
                    results.append(data)
            except Exception as e:
                logger.debug(f"{ticker}: {e}")
            if (i + 1) % 20 == 0:
                logger.info(f"  {i+1}/{len(tickers)} הושלמו, {len(results)} תקינות")

    logger.info(f"Agent2: {len(results)} מניות עם נתונים")
    return results
