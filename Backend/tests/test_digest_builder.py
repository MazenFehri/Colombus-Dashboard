from datetime import date
from types import SimpleNamespace
from app.services import digest_builder


def _item(headline, explanation=None):
    return SimpleNamespace(headline=headline, source="Reuters",
                           url="http://x", explanation=explanation)


def test_build_digest_html_contains_headlines(monkeypatch):
    def fake_news(db, base, quote, on_date):
        return [_item(f"{base}{quote} top", "because reasons")], [_item(f"{base}{quote} more")]
    monkeypatch.setattr(digest_builder.news_section, "get_pair_news", fake_news)

    subject, html = digest_builder.build_digest_html(db=None, on_date=date(2026, 6, 11))
    assert "2026-06-11" in subject
    assert "EURUSD top" in html
    assert "because reasons" in html
    assert "USDTND top" in html
