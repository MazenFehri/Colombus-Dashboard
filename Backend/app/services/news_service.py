from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session
from app import models
from app.services.news_config import TOP_N, TODAY_REFRESH_HOURS
from app.services.news_providers.gdelt import GdeltProvider

DEFAULT_PROVIDERS = [GdeltProvider()]


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
    return _cached(db, base, quote, on_date)
