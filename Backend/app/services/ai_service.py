from dataclasses import dataclass
from datetime import date, timedelta
from sqlalchemy.orm import Session
from groq import Groq
from app import models
from app.services import analytics, alert_engine, news
from app.config import settings


@dataclass
class MarketContext:
    pair: str
    date: date
    change_pct: float
    risk_level: str
    spike: bool
    rate_history: list[str]
    trend_direction: str | None
    vol_regime: str | None
    momentum: float | None
    headlines: list[models.NewsItem]


def build_market_context(db: Session, base: str, quote: str, target_date: date) -> MarketContext:
    """Assemble everything the AI needs. The only I/O is the cached news fetch."""
    # 120 days back covers the 30-day trend MA and the ~111 rows vol-regime needs.
    from_date = target_date - timedelta(days=120)
    df = analytics.load_rates_df(db, base, quote, from_date, target_date)
    if len(df) < 2:
        raise ValueError("Not enough data to generate commentary")

    change_pct = analytics.calc_daily_change(df)["change_pct"]
    spike = analytics.is_spike(df)
    risk_level, _ = alert_engine.classify_risk(change_pct, spike=spike, quote=quote)

    trend_info = analytics.calc_trend(df)
    rate_history = [f"{r['date'].date()}: {r['rate']:.4f}" for _, r in df.tail(7).iterrows()]

    tag = news.pair_to_tag(base, quote)
    headlines = news.get_headlines(db, tag, target_date)

    return MarketContext(
        pair=f"{base}/{quote}",
        date=target_date,
        change_pct=change_pct,
        risk_level=risk_level,
        spike=spike,
        rate_history=rate_history,
        trend_direction=trend_info["direction"] if trend_info else None,
        vol_regime=analytics.calc_vol_regime(df),
        momentum=analytics.calc_momentum(df),
        headlines=headlines,
    )


def build_prompt(ctx: MarketContext) -> str:
    lines = [
        "You are a concise FX analyst.",
        f"Pair: {ctx.pair}",
        f"Date: {ctx.date}",
        f"Daily move: {ctx.change_pct:+.2f}%",
        f"Risk level: {ctx.risk_level.upper()}",
        f"7-day rate history: {', '.join(ctx.rate_history)}",
    ]
    if ctx.trend_direction:
        lines.append(f"Trend (MA7 vs MA30): {ctx.trend_direction}")
    if ctx.vol_regime:
        lines.append(f"Volatility regime: {ctx.vol_regime}")
    if ctx.momentum is not None:
        lines.append(f"Momentum: {ctx.momentum:+.2f}")
    if ctx.headlines:
        lines.append("Recent headlines:")
        for h in ctx.headlines:
            lines.append(f"  - {h.headline} ({h.source})")
    lines.append(
        "In 3-4 sentences, explain what likely drove this movement (use the headlines "
        "if relevant), what the trend and volatility context imply, and what this means "
        f"for a business with {ctx.pair} exposure (importer or exporter)."
    )
    return "\n".join(lines)


def get_or_generate_commentary(
    db: Session, base: str, quote: str, target_date: date
) -> tuple[str, bool, list]:
    """Returns (commentary_text, is_cached, headlines)."""
    existing = db.query(models.AiCommentary).filter_by(
        base_currency=base, quote_currency=quote, date=target_date
    ).first()
    if existing:
        return existing.commentary, True, []

    ctx = build_market_context(db, base, quote, target_date)
    prompt = build_prompt(ctx)

    client = Groq(api_key=settings.groq_api_key)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=250,
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
            return existing.commentary, True, []

    return commentary, False, ctx.headlines
