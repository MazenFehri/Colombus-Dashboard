from datetime import date, timedelta
from sqlalchemy.orm import Session
from app import models
from app.services import analytics, alert_engine, news, news_explainer

TOP_N = 3      # how many headlines get a Groq "why it moved" paragraph
LIMIT = 8      # total headlines fetched (top + more)


def _rate_context(db: Session, base: str, quote: str, on_date: date) -> tuple[float, str]:
    """Best-effort daily %% move + risk level to ground the explanations.
    Falls back to (0.0, 'low') when rate data is unavailable."""
    try:
        df = analytics.load_rates_df(db, base, quote, on_date - timedelta(days=400), on_date)
        change_pct = analytics.calc_daily_change(df)["change_pct"]
        spike = analytics.is_spike(df)
        risk_level, _ = alert_engine.classify_risk(change_pct, spike=spike, quote=quote)
        return change_pct, risk_level
    except Exception:
        return 0.0, "low"


def get_pair_news(db: Session, base: str, quote: str, on_date: date
                  ) -> tuple[list[models.NewsItem], list[models.NewsItem]]:
    """Return (top, more) headlines for the pair, sourced from the keyless RSS feed.
    The top items are enriched with a cached Groq explanation; 'more' are plain.
    Enrichment is best-effort and stored on the NewsItem row so it is generated once."""
    tag = news.pair_to_tag(base, quote)
    items = news.get_headlines(db, tag, on_date, limit=LIMIT)
    top, more = items[:TOP_N], items[TOP_N:]
    if not top:
        return top, more

    change_pct, risk_level = _rate_context(db, base, quote, on_date)
    changed = False
    for it in top:
        if it.explanation:
            continue  # already enriched on a previous fetch
        ex = news_explainer.explain_headline(
            base, quote, on_date, it.headline, it.source, change_pct, risk_level,
        )
        if ex:
            it.explanation = ex
            changed = True
    if changed:
        try:
            db.commit()
        except Exception:
            db.rollback()
    return top, more
