def get_portfolio_status(watchlist: list, current_data: dict,
                          total_capital: float) -> dict:
    positions = []

    for ticker in watchlist:
        data = current_data.get(ticker, {})
        price = data.get("current_price", 0)
        score = data.get("total_score", 0)
        trend = data.get("trend", "Unknown")
        pct_ath = data.get("pct_from_ath", 0)

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
        })

    return {
        "positions": positions,
        "total_stocks": len(positions),
    }
