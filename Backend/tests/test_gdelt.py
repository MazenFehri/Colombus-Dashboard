from datetime import date
from unittest.mock import patch, MagicMock
from app.services.news_providers.gdelt import GdeltProvider


def _resp(articles):
    m = MagicMock()
    m.raise_for_status = MagicMock()
    m.json.return_value = {"articles": articles}
    return m


def test_fetch_parses_articles():
    sample = [{
        "url": "https://reuters.com/x", "title": "ECB holds rates",
        "seendate": "20260605T120000Z", "domain": "reuters.com",
        "language": "English", "sourcecountry": "United States",
    }]
    with patch("httpx.get", return_value=_resp(sample)) as g:
        arts = GdeltProvider().fetch("EUR", "USD", date(2026, 6, 5))
    assert len(arts) == 1
    assert arts[0].title == "ECB holds rates"
    assert arts[0].source == "reuters.com"
    assert arts[0].published_at is not None
    sent = g.call_args.kwargs["params"]["query"]
    assert "ECB" in sent
    assert "sourcelang:english" in sent


def test_fetch_empty_returns_empty_list():
    with patch("httpx.get", return_value=_resp([])):
        arts = GdeltProvider().fetch("EUR", "USD", date(2026, 6, 5))
    assert arts == []


def test_fetch_uses_timespan_for_today():
    with patch("httpx.get", return_value=_resp([])) as g:
        GdeltProvider().fetch("EUR", "USD", date.today())
    params = g.call_args.kwargs["params"]
    assert "timespan" in params
    assert "startdatetime" not in params
