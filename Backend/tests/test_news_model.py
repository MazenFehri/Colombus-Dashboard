from datetime import date, datetime
from app import models, schemas


def test_news_article_persists_and_serializes(db_session):
    art = models.NewsArticle(
        base_currency="EUR", quote_currency="USD", date=date(2026, 6, 5),
        title="ECB holds rates", url="https://example.com/a",
        source="example.com", published_at=datetime(2026, 6, 5, 12, 0, 0),
        language="english", relevance=0.9, is_top=True,
        explanation="The ECB held rates, removing a near-term catalyst for euro strength.",
    )
    db_session.add(art)
    db_session.commit()

    row = db_session.query(models.NewsArticle).filter_by(base_currency="EUR").one()
    assert row.title == "ECB holds rates"
    assert row.is_top is True
    assert row.explanation.startswith("The ECB held rates")

    out = schemas.NewsArticleOut.model_validate(row)
    assert out.url == "https://example.com/a"
    assert out.is_top is True
    assert out.explanation == row.explanation


def test_news_article_explanation_defaults_to_none(db_session):
    art = models.NewsArticle(
        base_currency="GBP", quote_currency="USD", date=date(2026, 6, 5),
        title="Sterling slips", url="https://example.com/b",
        source="example.com", published_at=None,
        language="english", relevance=0.5, is_top=False,
    )
    db_session.add(art)
    db_session.commit()
    row = db_session.query(models.NewsArticle).filter_by(base_currency="GBP").one()
    assert row.explanation is None
    out = schemas.NewsArticleOut.model_validate(row)
    assert out.explanation is None
