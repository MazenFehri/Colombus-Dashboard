from unittest.mock import patch
from datetime import datetime
from app.services.news_providers.base import Article


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
