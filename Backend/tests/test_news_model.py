from datetime import date, datetime
from app import models, schemas


def test_news_article_persists_and_serializes(db_session):
    art = models.NewsArticle(
        base_currency="EUR", quote_currency="USD", date=date(2026, 6, 5),
        title="ECB holds rates", url="https://example.com/a",
        source="example.com", published_at=datetime(2026, 6, 5, 12, 0, 0),
        language="english", relevance=0.9, is_top=True,
    )
    db_session.add(art)
    db_session.commit()

    row = db_session.query(models.NewsArticle).filter_by(base_currency="EUR").one()
    assert row.title == "ECB holds rates"
    assert row.is_top is True

    out = schemas.NewsArticleOut.model_validate(row)
    assert out.url == "https://example.com/a"
    assert out.is_top is True
