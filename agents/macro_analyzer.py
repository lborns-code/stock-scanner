import logging
import yfinance as yf

logger = logging.getLogger(__name__)

MACRO_TICKERS = {
    "SPY": "S&P 500",
    "QQQ": "Nasdaq",
    "^VIX": "VIX פחד",
    "DX-Y.NYB": "דולר DXY",
    "TLT": "אג\"ח ארוך",
    "GLD": "זהב",
}


def get_macro_data() -> dict:
    result = {}
    for symbol, name in MACRO_TICKERS.items():
        try:
            t = yf.Ticker(symbol)
            hist = t.history(period="5d")
            if hist.empty:
                continue
            close = hist["Close"]
            price = float(close.iloc[-1])
            prev = float(close.iloc[-2]) if len(close) >= 2 else price
            week_ago = float(close.iloc[0])
            chg_1d = (price - prev) / prev * 100 if prev else 0
            chg_1w = (price - week_ago) / week_ago * 100 if week_ago else 0
            result[symbol] = {
                "name": name,
                "price": round(price, 2),
                "chg_1d": round(chg_1d, 2),
                "chg_1w": round(chg_1w, 2),
            }
        except Exception as e:
            logger.debug(f"Macro {symbol}: {e}")

    return result


def get_market_regime(macro: dict) -> dict:
    vix_data = macro.get("^VIX", {})
    spy_data = macro.get("SPY", {})
    vix = vix_data.get("price", 20)
    spy_week_chg = spy_data.get("chg_1w", 0)

    if vix > 35:
        return {
            "regime": "FEAR",
            "hebrew": "פחד בשוק — VIX גבוה מאוד",
            "action": "🟢 הזדמנות היסטורית לקנות",
            "color": "green",
            "weight_adjustment": {"technical": +0.05, "valuation": +0.05},
        }
    elif vix > 25:
        return {
            "regime": "VOLATILE",
            "hebrew": "תנודתיות גבוהה — זהירות",
            "action": "⏳ קנה רק את הטובות ביותר",
            "color": "orange",
            "weight_adjustment": {},
        }
    elif vix < 15 and spy_week_chg > 1.5:
        return {
            "regime": "EUPHORIA",
            "hebrew": "שוק חגיגי — פחות הזדמנויות",
            "action": "⚠️ קשה למצוא כניסות טובות — סבלנות",
            "color": "yellow",
            "weight_adjustment": {"valuation": +0.05},
        }
    else:
        return {
            "regime": "NORMAL",
            "hebrew": "שוק רגיל",
            "action": "📊 עבוד לפי האלגוריתם הרגיל",
            "color": "blue",
            "weight_adjustment": {},
        }


def analyze() -> dict:
    macro = get_macro_data()
    regime = get_market_regime(macro)
    return {"macro": macro, "regime": regime}
