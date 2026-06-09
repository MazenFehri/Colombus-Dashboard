import time
from datetime import date, datetime, timezone, timedelta
from unittest.mock import patch
from app.services import news
from app import models


def _struct(dt):
    return dt.timetuple()


def _fake_feed(entries):
    class Feed:
        def __init__(self, entries):
            self.entries = entries
    return Feed(entries)


def _entry(title, link, source, hours_ago):
    published = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return {
        "title": title,
        "link": link,
        "source": {"title": source},
        "published_parsed": _struct(published),
    }


def test_pair_to_tag():
    assert news.pair_to_tag("EUR", "USD") == "EURUSD"
    assert news.pair_to_tag("GBP", "USD") == "GBPUSD"
    assert news.pair_to_tag("USD", "TND") == "TND"
    assert news.pair_to_tag("EUR", "TND") == "TND"


def test_get_headlines_fetches_caches_and_caps(db_session):
    entries = [
        _entry("Euro climbs vs dollar", "http://x/1", "Reuters", 2),
        _entry("ECB holds rates", "http://x/2", "Bloomberg", 5),
        _entry("Dollar mixed", "http://x/3", "FT", 10),
        _entry("Old news", "http://x/4", "AP", 100),  # >48h, excluded
    ]
    with patch("app.services.news.feedparser.parse", return_value=_fake_feed(entries)):
        result = news.get_headlines(db_session, "EURUSD", date(2024, 1, 9), limit=3)

    assert len(result) == 3
    assert result[0].headline == "Euro climbs vs dollar"
    assert all(r.pair_tag == "EURUSD" for r in result)
    assert db_session.query(models.NewsItem).count() == 3


def test_get_headlines_uses_cache_on_second_call(db_session):
    entries = [_entry("Euro up", "http://x/1", "Reuters", 1)]
    with patch("app.services.news.feedparser.parse", return_value=_fake_feed(entries)) as p:
        news.get_headlines(db_session, "EURUSD", date(2024, 1, 9))
        news.get_headlines(db_session, "EURUSD", date(2024, 1, 9))
    assert p.call_count == 1  # second call served from DB


def test_get_headlines_returns_empty_on_failure(db_session):
    with patch("app.services.news.feedparser.parse", side_effect=Exception("network down")):
        result = news.get_headlines(db_session, "EURUSD", date(2024, 1, 9))
    assert result == []
    assert db_session.query(models.NewsItem).count() == 0
