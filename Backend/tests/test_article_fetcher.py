from unittest.mock import patch, MagicMock
from app.services.article_fetcher import fetch_article_text


def _resp(status, html):
    m = MagicMock()
    m.status_code = status
    m.text = html
    return m


SAMPLE_HTML = """
<html><head><title>x</title></head><body>
<nav>menu noise</nav>
<article>
  <p>The European Central Bank held interest rates steady on Thursday.</p>
  <p>Policymakers signaled caution amid persistent inflation concerns.</p>
</article>
<footer>copyright</footer>
</body></html>
"""


def test_extracts_paragraph_text():
    with patch("httpx.get", return_value=_resp(200, SAMPLE_HTML)):
        text = fetch_article_text("https://example.com/a")
    assert text is not None
    assert "European Central Bank held interest rates steady" in text
    assert "Policymakers signaled caution" in text


def test_non_200_returns_none():
    with patch("httpx.get", return_value=_resp(403, "<html></html>")):
        assert fetch_article_text("https://example.com/a") is None


def test_network_error_returns_none():
    with patch("httpx.get", side_effect=Exception("boom")):
        assert fetch_article_text("https://example.com/a") is None


def test_empty_body_returns_none():
    with patch("httpx.get", return_value=_resp(200, "<html><body></body></html>")):
        assert fetch_article_text("https://example.com/a") is None
