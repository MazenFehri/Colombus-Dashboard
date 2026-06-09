import pytest
from unittest.mock import patch
from datetime import datetime
from app.services.news_providers.base import Article


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    # The news endpoint enriches top articles via scraping + Groq; keep tests offline.
    monkeypatch.setattr("app.services.article_fetcher.fetch_article_text", lambda url: None)
    monkeypatch.setattr("app.services.news_explainer.explain_article", lambda *a, **k: None)


def _arts(n):
    return [Article(title=f"t{i}", url=f"https://x/{i}", source="x",
                    published_at=datetime(2026, 6, 5), language="english",
                    relevance=1.0 - i * 0.1) for i in range(n)]


def test_news_route_returns_top_and_more(client):
    with patch("app.services.news_service.DEFAULT_PROVIDERS",
               [type("P", (), {"name": "f", "fetch": lambda self, b, q, d: _arts(5)})()]):
        resp = client.get("/api/v1/news/EUR/USD?date=2026-06-05")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["top"]) == 3
    assert len(data["more"]) == 2
    assert data["top"][0]["is_top"] is True


def test_news_route_rejects_bad_pair(client):
    resp = client.get("/api/v1/news/XXX/YYY?date=2026-06-05")
    assert resp.status_code == 400


def test_news_route_empty_when_no_articles(client):
    with patch("app.services.news_service.DEFAULT_PROVIDERS",
               [type("P", (), {"name": "f", "fetch": lambda self, b, q, d: []})()]):
        resp = client.get("/api/v1/news/EUR/USD?date=2026-06-05")
    assert resp.status_code == 200
    assert resp.json()["top"] == []


def test_news_route_includes_effective_date(client):
    with patch("app.services.news_service.DEFAULT_PROVIDERS",
               [type("P", (), {"name": "f", "fetch": lambda self, b, q, d: _arts(2)})()]):
        resp = client.get("/api/v1/news/EUR/USD?date=2026-06-05")
    assert resp.status_code == 200
    assert resp.json()["effective_date"] == "2026-06-05"


def test_news_route_never_500_on_service_error(client):
    # Even if the service layer itself blows up, the route must not 500 — the UI
    # should show "no news", never "temporarily unavailable".
    with patch("app.services.news_service.get_news_nearest",
               side_effect=RuntimeError("service exploded")):
        resp = client.get("/api/v1/news/EUR/USD?date=2026-06-05")
    assert resp.status_code == 200
    assert resp.json()["top"] == [] and resp.json()["more"] == []
