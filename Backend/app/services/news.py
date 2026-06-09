import calendar
import socket
import feedparser
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote_plus
from sqlalchemy.orm import Session
from app import models

_TAG_QUERIES = {
    "EURUSD": "EUR USD exchange rate",
    "GBPUSD": "GBP USD pound dollar exchange rate",
    "TND": "Tunisian dinar OR BCT OR Tunisia economy",
}

_LOOKBACK_HOURS = 48


def pair_to_tag(base: str, quote: str) -> str:
    """Map a currency pair to a news tag. TND (either side) groups together."""
    if base == "TND" or quote == "TND":
        return "TND"
    return f"{base}{quote}"


def _feed_url(tag: str) -> str:
    query = _TAG_QUERIES.get(tag, tag)
    return (
        "https://news.google.com/rss/search?q="
        f"{quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
    )


def _published(entry) -> datetime | None:
    pp = entry.get("published_parsed")
    if not pp:
        return None
    return datetime.fromtimestamp(calendar.timegm(pp), tz=timezone.utc)


def _source(entry) -> str:
    src = entry.get("source")
    if isinstance(src, dict) and src.get("title"):
        return src["title"]
    title = entry.get("title", "")
    if " - " in title:
        return title.rsplit(" - ", 1)[-1].strip()
    return "Google News"


def get_headlines(db: Session, tag: str, on_date: date, limit: int = 3) -> list[models.NewsItem]:
    """Cached-per-(tag, day) headlines. Never raises — returns [] on any failure."""
    cached = (
        db.query(models.NewsItem)
        .filter(models.NewsItem.pair_tag == tag, models.NewsItem.fetched_date == on_date)
        .order_by(models.NewsItem.published_at.desc().nullslast())
        .limit(limit)
        .all()
    )
    if cached:
        return cached
    try:
        return _fetch_and_store(db, tag, on_date, limit)
    except Exception:  # also absorbs IntegrityError from a concurrent insert racing on the UniqueConstraint (the constraint is the dedup safeguard)
        db.rollback()
        return []


def _fetch_and_store(db: Session, tag: str, on_date: date, limit: int) -> list[models.NewsItem]:
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(5)
    try:
        feed = feedparser.parse(_feed_url(tag))
    finally:
        socket.setdefaulttimeout(old_timeout)
    # Cutoff is relative to real current time (live-only feed), so fetching for a
    # past on_date will return nothing — by design.
    cutoff = datetime.now(timezone.utc) - timedelta(hours=_LOOKBACK_HOURS)
    items: list[models.NewsItem] = []
    for entry in feed.entries:
        published = _published(entry)
        if published is not None and published < cutoff:
            continue
        headline = (entry.get("title") or "").strip()
        url = (entry.get("link") or "").strip()
        if not headline or not url:
            continue
        items.append(models.NewsItem(
            pair_tag=tag,
            headline=headline,
            source=_source(entry),
            url=url,
            published_at=published.replace(tzinfo=None) if published else None,
            fetched_date=on_date,
        ))
        if len(items) >= limit:
            break
    if not items:
        return []
    for it in items:
        db.add(it)
    db.commit()
    for it in items:
        db.refresh(it)
    return items
