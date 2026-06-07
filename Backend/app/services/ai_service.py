from datetime import date, timedelta
from sqlalchemy.orm import Session
from groq import Groq
from app import models
from app.services import analytics, alert_engine
from app.config import settings


def get_or_generate_commentary(
    db: Session, base: str, quote: str, target_date: date,
    headlines: list[str] | None = None,
) -> tuple[str, bool]:
    """Returns (commentary_text, is_cached)."""
    existing = db.query(models.AiCommentary).filter_by(
        base_currency=base, quote_currency=quote, date=target_date
    ).first()
    if existing:
        return existing.commentary, True

    from_date = target_date - timedelta(days=10)
    df = analytics.load_rates_df(db, base, quote, from_date, target_date)

    if len(df) < 2:
        raise ValueError("Not enough data to generate commentary")

    change_data = analytics.calc_daily_change(df)
    change_pct = change_data["change_pct"]
    spike = analytics.is_spike(df)
    risk_level, _ = alert_engine.classify_risk(change_pct, spike=spike)

    rate_history = [
        f"{r['date'].date()}: {r['rate']:.4f}"
        for _, r in df.tail(7).iterrows()
    ]
    history_str = ", ".join(rate_history)

    prompt = (
        f"You are a concise FX analyst. {base}/{quote} moved {change_pct:+.2f}% on {target_date} "
        f"(risk level: {risk_level.upper()}). "
        f"7-day rate history: {history_str}. "
        f"In 2-3 sentences, explain what happened and what this means for a business "
        f"with {base}/{quote} exposure (importer or exporter)."
    )

    if headlines:
        joined = "; ".join(headlines[:3])
        prompt += (
            f" Recent headlines: {joined}. "
            f"Reference them only if they plausibly relate to the move."
        )

    client = Groq(api_key=settings.groq_api_key)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
        temperature=0.3,
    )
    commentary = response.choices[0].message.content.strip()

    try:
        db.add(models.AiCommentary(
            base_currency=base,
            quote_currency=quote,
            date=target_date,
            commentary=commentary,
        ))
        db.commit()
    except Exception:
        db.rollback()
        existing = db.query(models.AiCommentary).filter_by(
            base_currency=base, quote_currency=quote, date=target_date
        ).first()
        if existing:
            return existing.commentary, True

    return commentary, False
