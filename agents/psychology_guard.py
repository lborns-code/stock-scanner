def get_psychology_note(ticker: str, action: str,
                        pct_from_ath: float, history: list) -> str:
    notes = []

    if pct_from_ath < -40:
        notes.append(
            f"⚠️ {ticker} ירדה {abs(pct_from_ath):.0f}% מהשיא. "
            f"זה לא סיבה למכור — זו הסיבה שבדקנו אותה. "
            f"בדוק: האם התזה המקורית עדיין תקפה?")

    if len(history) >= 5:
        notes.append(
            f"📊 {ticker} מופיעה ברשימה {len(history)} פעמים. "
            f"העקביות מחזקת את הסיגנל.")

    if "✅" in action:
        notes.append(
            "💡 זכור: המטרה היא 3-10 שנים. "
            "ירידה של 20% בדרך היא נורמלית לחלוטין. "
            "אל תמכור מפחד — מכור רק אם התזה השתנתה.")

    return " | ".join(notes) if notes else "זכור את האופק שלך: 3-10 שנים."
