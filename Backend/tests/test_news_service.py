from datetime import date, datetime, timedelta
from unittest.mock import patch
import pytest
from app import models
from app.services import news_service
from app.services.news_providers.base import Article


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    # Keep the cache-behaviour tests offline: no real scraping or Groq calls.
    monkeypatch.setattr("app.services.article_fetcher.fetch_article_text", lambda url: None)
    monkeypatch.setattr("app.services.news_explainer.explain_article",
                        lambda *a, **k: None)


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


def test_top_articles_get_explanations(db_session):
    p = FakeProvider(_arts(5))
    with patch("app.services.article_fetcher.fetch_article_text", return_value="Full article body text."), \
         patch("app.services.news_explainer.explain_article", return_value="Explained: affects the pair."):
        out = news_service.get_or_fetch_news(db_session, "EUR", "USD", date(2026, 6, 5), providers=[p])
    top = [a for a in out if a.is_top]
    more = [a for a in out if not a.is_top]
    assert len(top) == news_service.TOP_N
    assert all(a.explanation == "Explained: affects the pair." for a in top)
    assert all(a.explanation is None for a in more)
