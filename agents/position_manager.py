import logging

logger = logging.getLogger(__name__)


def get_portfolio_status(watchlist: list, current_data: dict,
                          total_capital: float, positions_cfg: dict = None) -> dict:
    positions_cfg = positions_cfg or {}
    positions = []
    total_invested = 0
    total_current_value = 0

    for ticker in watchlist:
        data = current_data.get(ticker, {})
        price = data.get("current_price", 0)
        score = data.get("total_score", 0)
        trend = data.get("trend", "Unknown")
        pct_ath = data.get("pct_from_ath", 0)

        # P&L from config
        pos = positions_cfg.get(ticker, {})
        shares = pos.get("shares", 0)
        avg_cost = pos.get("avg_cost", 0)
        invested = pos.get("invested_usd", 0) or (shares * avg_cost)

        current_value = shares * price if shares > 0 and price > 0 else 0
        pnl_usd = current_value - invested if invested > 0 else None
        pnl_pct = (pnl_usd / invested * 100) if invested > 0 and pnl_usd is not None else None

        if invested > 0:
            total_invested += invested
        if current_value > 0:
            total_current_value += current_value

        if score >= 8.0 and trend == "Bullish":
            action_note = "✅ המשך להחזיק — חזק"
        elif score >= 6.5:
            action_note = "⏳ החזק — עדיין סביר"
        elif score < 5.5 and trend == "Bearish":
            action_note = "⚠️ שקול לצמצם"
        else:
            action_note = "👀 עקוב"

        positions.append({
            "ticker": ticker,
            "price": price,
            "score": score,
            "trend": trend,
            "pct_from_ath": pct_ath,
            "action": action_note,
            "above_ma200": data.get("above_ma200", True),
            "rsi_14": data.get("rsi_14", 50),
            "shares": shares,
            "avg_cost": avg_cost,
            "invested_usd": round(invested, 2),
            "current_value": round(current_value, 2),
            "pnl_usd": round(pnl_usd, 2) if pnl_usd is not None else None,
            "pnl_pct": round(pnl_pct, 1) if pnl_pct is not None else None,
        })

    total_pnl = total_current_value - total_invested if total_invested > 0 else None
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 and total_pnl is not None else None

    return {
        "positions": positions,
        "total_stocks": len(positions),
        "total_invested": round(total_invested, 2),
        "total_current_value": round(total_current_value, 2),
        "total_pnl_usd": round(total_pnl, 2) if total_pnl is not None else None,
        "total_pnl_pct": round(total_pnl_pct, 1) if total_pnl_pct is not None else None,
    }
