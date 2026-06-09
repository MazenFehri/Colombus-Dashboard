from datetime import date
from unittest.mock import patch, MagicMock
from app.services.news_providers.gnews import GNewsProvider


def _resp(payload, status=200):
    m = MagicMock()
    m.status_code = status
    m.json.return_value = payload
    m.raise_for_status.return_value = None
    return m


def test_gnews_no_ops_without_key(monkeypatch):
    monkeypatch.setattr("app.services.news_providers.gnews.settings.gnews_api_key", "")
    with patch("app.services.news_providers.gnews.httpx.get") as g:
        out = GNewsProvider().fetch("EUR", "USD", date(2026, 6, 5))
    assert out == []
    g.assert_not_called()  # no key -> no network call at all


def test_gnews_parses_articles_with_key(monkeypatch):
    monkeypatch.setattr("app.services.news_providers.gnews.settings.gnews_api_key", "k")
    payload = {"articles": [
        {"title": "ECB holds rates", "url": "https://n/1",
         "source": {"name": "Reuters"}, "publishedAt": "2026-06-05T10:00:00Z"},
        {"title": None, "url": "https://n/2"},  # skipped: no title
    ]}
    with patch("app.services.news_providers.gnews.httpx.get", return_value=_resp(payload)):
        out = GNewsProvider().fetch("EUR", "USD", date(2026, 6, 5))
    assert len(out) == 1
    assert out[0].title == "ECB holds rates" and out[0].source == "Reuters"
    assert out[0].published_at.year == 2026


def test_gnews_degrades_on_quota(monkeypatch):
    monkeypatch.setattr("app.services.news_providers.gnews.settings.gnews_api_key", "k")
    with patch("app.services.news_providers.gnews.httpx.get", return_value=_resp({}, status=429)):
        out = GNewsProvider().fetch("EUR", "USD", date(2026, 6, 5))
    assert out == []
