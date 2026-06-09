from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session
from app import models
from app.services import analytics, alert_engine, article_fetcher, news_explainer
from app.services.news_config import TOP_N, TODAY_REFRESH_HOURS, NEAREST_DAY_WINDOW
from app.services.news_providers.gdelt import GdeltProvider
from app.services.news_providers.gnews import GNewsProvider

# GDELT first (free, no key); GNews as fallback for gaps GDELT can't cover
# (older dates, rate-limited bursts). GNews no-ops without an API key.
DEFAULT_PROVIDERS = [GdeltProvider(), GNewsProvider()]


def _cached(db: Session, base: str, quote: str, on_date: date) -> list[models.NewsArticle]:
    return (
        db.query(models.NewsArticle)
        .filter_by(base_currency=base, quote_currency=quote, date=on_date)
        .order_by(models.NewsArticle.is_top.desc(), models.NewsArticle.relevance.desc())
        .all()
    )


def _is_fresh(rows: list[models.NewsArticle], on_date: date) -> bool:
    if not rows:
        return False
    if on_date < date.today():
        return True  # past news never changes
    newest = max((r.fetched_at for r in rows if r.fetched_at), default=None)
    if newest is None:
        return False
    return datetime.utcnow() - newest < timedelta(hours=TODAY_REFRESH_HOURS)


def _store(db: Session, base: str, quote: str, on_date: date, articles) -> None:
    # replace existing rows for this pair/date (handles today-refresh + dedupe)
    db.query(models.NewsArticle).filter_by(
        base_currency=base, quote_currency=quote, date=on_date
    ).delete()
    seen: set[str] = set()
    rank = 0
    for a in articles:
        if a.url in seen:
            continue
        seen.add(a.url)
        db.add(models.NewsArticle(
            base_currency=base, quote_currency=quote, date=on_date,
            title=a.title, url=a.url, source=a.source,
            published_at=a.published_at, language=a.language,
            relevance=a.relevance, is_top=(rank < TOP_N),
        ))
        rank += 1
    db.commit()


def _rate_context(db: Session, base: str, quote: str, on_date: date) -> tuple[float, str]:
    """Best-effort daily % move + risk level for the pair on on_date.
    Falls back to (0.0, "low") when rate data is unavailable."""
    try:
        df = analytics.load_rates_df(db, base, quote, on_date - timedelta(days=10), on_date)
        change_pct = analytics.calc_daily_change(df)["change_pct"]
        spike = analytics.is_spike(df)
        risk_level, _ = alert_engine.classify_risk(change_pct, spike=spike)
        return change_pct, risk_level
    except Exception:
        return 0.0, "low"


def _enrich_top(db: Session, base: str, quote: str, on_date: date,
                rows: list[models.NewsArticle]) -> None:
    """For the top (is_top) articles, scrape the body and generate a Groq
    explanation, storing it on each row. Best-effort: any failure leaves
    explanation as None so the item degrades to a plain link."""
    top_rows = [r for r in rows if r.is_top]
    if not top_rows:
        return
    change_pct, risk_level = _rate_context(db, base, quote, on_date)
    changed = False
    for r in top_rows:
        full_text = article_fetcher.fetch_article_text(r.url)
        explanation = news_explainer.explain_article(
            base, quote, on_date, r.title, r.source,
            change_pct, risk_level, full_text=full_text,
        )
        if explanation:
            r.explanation = explanation
            changed = True
    if changed:
        db.commit()


def get_or_fetch_news(db: Session, base: str, quote: str, on_date: date, providers=None):
    providers = providers if providers is not None else DEFAULT_PROVIDERS
    cached = _cached(db, base, quote, on_date)
    if _is_fresh(cached, on_date):
        return cached

    fetched = []
    for provider in providers:
        try:
            fetched = provider.fetch(base, quote, on_date)
        except Exception:
            fetched = []
        if fetched:
            break

    if not fetched:
        return cached  # may be [] — degrade gracefully

    _store(db, base, quote, on_date, fetched)
    rows = _cached(db, base, quote, on_date)
    _enrich_top(db, base, quote, on_date, rows)
    return _cached(db, base, quote, on_date)


def get_news_nearest(db: Session, base: str, quote: str, on_date: date,
                     window: int = NEAREST_DAY_WINDOW, providers=None):
    """News for on_date, or the closest day within ±window that has any.
    Returns (rows, effective_date). Used so calendar time-travel to a date with
    no coverage still shows the nearest available news instead of nothing."""
    rows = get_or_fetch_news(db, base, quote, on_date, providers=providers)
    if rows:
        return rows, on_date
    today = date.today()
    for offset in range(1, window + 1):
        for cand in (on_date - timedelta(days=offset), on_date + timedelta(days=offset)):
            if cand > today:
                continue
            rows = get_or_fetch_news(db, base, quote, cand, providers=providers)
            if rows:
                return rows, cand
    return [], on_date
