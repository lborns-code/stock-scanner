import logging
import pandas as pd

try:
    import feedparser
    _FEEDPARSER_OK = True
except ImportError:
    _FEEDPARSER_OK = False
import re

logger = logging.getLogger(__name__)

SMALL_CAP_WATCHLIST = [
    # AI & Tech
    "IONQ", "RXRX", "APLD", "SOUN", "BBAI", "KULR", "IREN",
    # Biotech / Aviation
    "ACHR", "JOBY", "SPCE", "RKLB",
    # Fintech
    "AFRM", "UPST", "DAVE", "MQ",
    # Energy & Climate
    "PLUG", "FCEL", "BLNK", "CHPT",
    # Defense & Space
    "PL", "ASTS",
    # Consumer / Health
    "HIMS", "NTRA", "TMDX",
    # Quantum & Deep Tech
    "QUBT", "RGTI", "QBTS",
]

# רשימת fallback — מניות איכותיות מכל הסקטורים כשהאינטרנט נכשל
FALLBACK_LARGE_CAP = [
    # Mega-cap Tech / AI
    "NVDA", "MSFT", "AAPL", "GOOGL", "META", "AMZN", "TSLA", "AVGO",
    "AMD", "ORCL", "CRM", "NOW", "ADBE", "SNOW", "PLTR", "DDOG",
    "MDB", "NET", "CRWD", "ZS", "PANW", "FTNT",
    # Semiconductor
    "TSM", "ASML", "AMAT", "KLAC", "LRCX", "MRVL", "QCOM", "TXN", "INTC",
    # Healthcare / Biotech
    "LLY", "NVO", "UNH", "ABBV", "JNJ", "TMO", "ISRG", "DXCM", "MRNA",
    "REGN", "VRTX", "GILD", "BMY", "PFE",
    # Finance
    "BRK-B", "JPM", "V", "MA", "GS", "MS", "BAC", "AXP", "COIN", "HOOD",
    # Consumer
    "COST", "AMZN", "SBUX", "MCD", "NKE", "LULU", "DECK", "TPR",
    # Industrials / Defense
    "CAT", "HON", "RTX", "LMT", "NOC", "GE", "DE", "ETN",
    # Energy
    "XOM", "CVX", "COP", "SLB", "OXY", "FANG",
    # Communication
    "NFLX", "DIS", "SPOT", "RBLX", "TTD", "PINS",
    # Real Estate / Infrastructure
    "AMT", "EQIX", "PLD", "WELL",
    # Mid-cap growth
    "CELH", "DUOL", "ENPH", "SMCI", "ARM", "AXON", "MSTR", "CAVA",
    "BKNG", "UBER", "LYFT", "DASH", "ABNB", "APP",
]

RSS_FEEDS = [
    "https://feeds.finance.yahoo.com/rss/2.0/headline",
    "https://www.marketwatch.com/rss/topstories",
]

TICKER_PATTERN = re.compile(r'\b([A-Z]{2,5})\b')

KNOWN_NON_TICKERS = {
    "THE", "AND", "FOR", "BUT", "NOT", "WITH", "FROM", "THAT", "THIS",
    "WILL", "HAVE", "MORE", "BEEN", "THEY", "WERE", "ARE", "ALL", "HAS",
    "ITS", "NEW", "CAN", "MAY", "CEO", "CFO", "IPO", "ETF", "GDP", "CPI",
    "FED", "SEC", "FDA", "WHO", "IMF", "ECB", "EUR", "USD", "JPY", "GBP",
    "AI", "US", "UK", "EU", "Q1", "Q2", "Q3", "Q4",
}


def get_sp500_tickers() -> list:
    try:
        tables = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
        df = tables[0]
        return df["Symbol"].str.replace(".", "-", regex=False).tolist()
    except Exception as e:
        logger.warning(f"SP500 fetch failed: {e}")
        return []


def get_nasdaq100_tickers() -> list:
    try:
        tables = pd.read_html("https://en.wikipedia.org/wiki/Nasdaq-100")
        for df in tables:
            if "Ticker" in df.columns:
                return df["Ticker"].tolist()
            if "Symbol" in df.columns:
                return df["Symbol"].tolist()
        return []
    except Exception as e:
        logger.warning(f"Nasdaq100 fetch failed: {e}")
        return []


def get_rss_tickers() -> list:
    if not _FEEDPARSER_OK:
        return []
    found = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:20]:
                text = (entry.get("title", "") + " " + entry.get("summary", ""))
                matches = TICKER_PATTERN.findall(text)
                for m in matches:
                    if m not in KNOWN_NON_TICKERS and len(m) >= 2:
                        found.append(m)
        except Exception as e:
            logger.warning(f"RSS feed {url} failed: {e}")
    return list(set(found))


def passes_initial_filter(info: dict, cfg: dict) -> bool:
    return (
        info.get("marketCap", 0) >= cfg["filters"]["min_market_cap_usd"] and
        info.get("averageVolume", 0) >= cfg["filters"]["min_daily_volume"] and
        info.get("grossMargins", 0) >= cfg["filters"]["min_gross_margin"]
    )


def build_universe(cfg: dict) -> list:
    logger.info("Agent1: בונה universe מניות...")
    tickers = set()

    # Watchlist קבועה
    for t in cfg.get("watchlist", []):
        tickers.add(t)

    # Small caps קבועים
    for t in SMALL_CAP_WATCHLIST:
        tickers.add(t)

    import random

    # S&P 500
    sp500 = get_sp500_tickers()
    logger.info(f"  S&P 500: {len(sp500)} מניות")
    for t in random.sample(sp500, min(40, len(sp500))):
        tickers.add(t)

    # Nasdaq 100
    nq100 = get_nasdaq100_tickers()
    logger.info(f"  Nasdaq 100: {len(nq100)} מניות")
    for t in random.sample(nq100, min(30, len(nq100))):
        tickers.add(t)

    # Fallback: אם Wikipedia נכשל — השתמש ברשימה קשיחה
    if not sp500 and not nq100:
        logger.info("  Wikipedia נכשל — משתמש ב-fallback list")
        for t in FALLBACK_LARGE_CAP:
            tickers.add(t)
    elif len(sp500) + len(nq100) < 50:
        # נוסיף חלק מה-fallback אם מעט מדי מניות
        for t in random.sample(FALLBACK_LARGE_CAP, 20):
            tickers.add(t)

    # RSS
    rss = get_rss_tickers()
    logger.info(f"  RSS tickers: {len(rss)}")
    for t in rss[:10]:
        tickers.add(t)

    result = sorted(tickers)
    logger.info(f"Agent1: סה\"כ {len(result)} מניות לסריקה")
    return result
