from datetime import date, datetime, timedelta
from app import models
from app.services import news_service
from app.services.news_providers.base import Article


def _arts(n):
    return [Article(title=f"t{i}", url=f"https://x/{i}", source="x",
                    published_at=datetime(2026, 6, 5), language="english",
                    relevance=1.0 - i * 0.1) for i in range(n)]


class FakeProvider:
    name = "fake"
    def __init__(self, arts): self.arts = arts; self.calls = 0
    def fetch(self, base, quote, on_date): self.calls += 1; return self.arts


def test_fetch_on_miss_then_cache_on_hit(db_session):
    p = FakeProvider(_arts(5))
    out1 = news_service.get_or_fetch_news(db_session, "EUR", "USD", date(2026, 6, 5), providers=[p])
    out2 = news_service.get_or_fetch_news(db_session, "EUR", "USD", date(2026, 6, 5), providers=[p])
    assert len(out1) == 5
    assert p.calls == 1  # second call served from cache


def test_top_n_marked(db_session):
    p = FakeProvider(_arts(5))
    out = news_service.get_or_fetch_news(db_session, "EUR", "USD", date(2026, 6, 5), providers=[p])
    assert sum(1 for a in out if a.is_top) == news_service.TOP_N


def test_dedupes_by_url(db_session):
    dupes = _arts(3) + _arts(3)  # same urls twice
    p = FakeProvider(dupes)
    out = news_service.get_or_fetch_news(db_session, "EUR", "USD", date(2026, 6, 5), providers=[p])
    assert len({a.url for a in out}) == len(out) == 3


def test_provider_chain_falls_back(db_session):
    class Boom:
        name = "boom"
        def fetch(self, *a): raise RuntimeError("down")
    good = FakeProvider(_arts(2))
    out = news_service.get_or_fetch_news(db_session, "EUR", "USD", date(2026, 6, 5), providers=[Boom(), good])
    assert len(out) == 2


def test_today_refetches_when_stale(db_session):
    p = FakeProvider(_arts(2))
    today = date.today()
    news_service.get_or_fetch_news(db_session, "EUR", "USD", today, providers=[p])
    for row in db_session.query(models.NewsArticle).all():
        row.fetched_at = datetime.utcnow() - timedelta(hours=news_service.TODAY_REFRESH_HOURS + 1)
    db_session.commit()
    news_service.get_or_fetch_news(db_session, "EUR", "USD", today, providers=[p])
    assert p.calls == 2  # refetched
