from datetime import date
from unittest.mock import patch, MagicMock
from app.services.frankfurter import fetch_rates, _fetch_frankfurter
import pytest


def make_frankfurter_response(base, quote, rates_by_date):
    """Build a mock Frankfurter API JSON response."""
    return {
        "base": base,
        "rates": {d: {quote: r} for d, r in rates_by_date.items()},
    }


def test_fetch_rates_returns_dict_of_date_to_float(monkeypatch):
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = make_frankfurter_response(
        "USD", "TND",
        {"2024-01-02": 3.12, "2024-01-03": 3.15}
    )
    with patch("httpx.get", return_value=mock_resp):
        result = fetch_rates("USD", "TND", date(2024, 1, 2), date(2024, 1, 3))
    assert len(result) == 2
    assert result[date(2024, 1, 2)] == 3.12
    assert result[date(2024, 1, 3)] == 3.15


def test_fetch_rates_falls_back_on_frankfurter_failure(monkeypatch):
    fallback_resp = MagicMock()
    fallback_resp.raise_for_status = MagicMock()
    fallback_resp.json.return_value = {"usd": {"tnd": 3.20}}

    def mock_get(url, **kwargs):
        if "frankfurter" in url:
            raise Exception("Frankfurter down")
        return fallback_resp

    with patch("httpx.get", side_effect=mock_get):
        result = fetch_rates("USD", "TND", date(2024, 1, 2), date(2024, 1, 2))
    assert date(2024, 1, 2) in result
    assert result[date(2024, 1, 2)] == 3.20


def test_fetch_rates_raises_when_both_fail(monkeypatch):
    with patch("httpx.get", side_effect=Exception("network error")):
        with pytest.raises(RuntimeError, match="unavailable"):
            fetch_rates("USD", "TND", date(2024, 1, 2), date(2024, 1, 2))
