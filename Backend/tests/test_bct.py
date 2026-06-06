from unittest.mock import patch, MagicMock
from datetime import date
from app.services import bct

MOCK_HTML = """
<html><body>
<table>
  <tr><th>Monnaie</th><th>Sigle</th><th>Unite</th><th>Valeur</th></tr>
  <tr><td>Dollar Americain</td><td>USD</td><td>1</td><td>2,9131</td></tr>
  <tr><td>Euro</td><td>EUR</td><td>1</td><td>3,3865</td></tr>
</table>
</body></html>
"""


def _mock_response(status_code=200, html=MOCK_HTML):
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.text = html
    return mock_resp


def test_fetch_single_date_usd():
    with patch("httpx.get", return_value=_mock_response()):
        result = bct._fetch_single_date("USD", date(2026, 6, 3))
    assert result == 2.9131


def test_fetch_single_date_eur():
    with patch("httpx.get", return_value=_mock_response()):
        result = bct._fetch_single_date("EUR", date(2026, 6, 3))
    assert result == 3.3865


def test_fetch_single_date_returns_none_on_404():
    with patch("httpx.get", return_value=_mock_response(status_code=404)):
        result = bct._fetch_single_date("USD", date(2026, 6, 1))
    assert result is None


def test_fetch_single_date_returns_none_on_exception():
    with patch("httpx.get", side_effect=Exception("network error")):
        result = bct._fetch_single_date("USD", date(2026, 6, 1))
    assert result is None


def test_fetch_rates_skips_weekends():
    # Mon 2026-06-01 through Sun 2026-06-07 → only 5 weekday calls
    with patch("app.services.bct._fetch_single_date", return_value=2.91) as mock_fetch:
        bct.fetch_rates("USD", "TND", date(2026, 6, 1), date(2026, 6, 7))
    assert mock_fetch.call_count == 5


def test_fetch_rates_skips_none_results():
    # _fetch_single_date returns None for holidays
    call_count = [0]
    def side_effect(code, d):
        call_count[0] += 1
        return None if call_count[0] == 1 else 2.91

    with patch("app.services.bct._fetch_single_date", side_effect=side_effect):
        result = bct.fetch_rates("USD", "TND", date(2026, 6, 2), date(2026, 6, 3))
    # First day skipped (None), second day present
    assert date(2026, 6, 2) not in result
    assert result[date(2026, 6, 3)] == 2.91


def test_fetch_rates_raises_when_all_weekday_fetches_return_none():
    import pytest
    with patch("app.services.bct._fetch_single_date", return_value=None):
        with pytest.raises(RuntimeError, match="BCT data unavailable"):
            bct.fetch_rates("USD", "TND", date(2026, 6, 2), date(2026, 6, 3))


def test_fetch_rates_returns_dict_with_correct_dates():
    with patch("app.services.bct._fetch_single_date", return_value=2.9131):
        result = bct.fetch_rates("USD", "TND", date(2026, 6, 2), date(2026, 6, 3))
    assert date(2026, 6, 2) in result
    assert date(2026, 6, 3) in result
    assert result[date(2026, 6, 2)] == 2.9131
