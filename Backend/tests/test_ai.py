from unittest.mock import patch, MagicMock
from datetime import date
from app import models


def seed_rates(db_session, base, quote, rates_by_date):
    for d, r in rates_by_date.items():
        db_session.add(models.ExchangeRate(
            base_currency=base, quote_currency=quote,
            rate=r, date=d, source="test"
        ))
    db_session.commit()


def test_commentary_returns_text(client, db_session):
    rates = {date(2024, 1, i): 3.0 + i * 0.01 for i in range(1, 10)}
    seed_rates(db_session, "USD", "TND", rates)

    mock_groq = MagicMock()
    mock_groq.chat.completions.create.return_value.choices[0].message.content = (
        "USD/TND rose 0.3% today. This reflects moderate demand for US dollars."
    )

    with patch("app.services.ai_service.Groq", return_value=mock_groq):
        resp = client.post("/api/v1/ai/commentary", json={
            "base": "USD", "quote": "TND", "date": "2024-01-09"
        })

    assert resp.status_code == 200
    data = resp.json()
    assert "commentary" in data
    assert len(data["commentary"]) > 10
    assert data["cached"] is False


def test_commentary_is_cached_on_second_call(client, db_session):
    rates = {date(2024, 1, i): 3.0 + i * 0.01 for i in range(1, 10)}
    seed_rates(db_session, "USD", "TND", rates)
    db_session.add(models.AiCommentary(
        base_currency="USD", quote_currency="TND",
        date=date(2024, 1, 9),
        commentary="Cached commentary text."
    ))
    db_session.commit()

    resp = client.post("/api/v1/ai/commentary", json={
        "base": "USD", "quote": "TND", "date": "2024-01-09"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["commentary"] == "Cached commentary text."
    assert data["cached"] is True


def test_commentary_returns_502_on_groq_failure(client, db_session):
    rates = {date(2024, 1, i): 3.0 + i * 0.01 for i in range(1, 10)}
    seed_rates(db_session, "USD", "TND", rates)

    with patch("app.services.ai_service.Groq", side_effect=Exception("Groq down")):
        resp = client.post("/api/v1/ai/commentary", json={
            "base": "USD", "quote": "TND", "date": "2024-01-09"
        })
    assert resp.status_code == 502


from app.services import ai_service, news as news_service


def test_build_prompt_includes_headlines_and_omits_none(db_session):
    rates = {date(2024, 1, i): 3.0 + i * 0.01 for i in range(1, 10)}
    seed_rates(db_session, "USD", "TND", rates)
    fake = [models.NewsItem(pair_tag="TND", headline="Dinar steady", source="TAP",
                            url="http://x/1", fetched_date=date(2024, 1, 9))]
    with patch("app.services.ai_service.news.get_headlines", return_value=fake):
        ctx = ai_service.build_market_context(db_session, "USD", "TND", date(2024, 1, 9))
    prompt = ai_service.build_prompt(ctx)
    assert "Dinar steady (TAP)" in prompt
    assert "Pair: USD/TND" in prompt


def test_commentary_endpoint_returns_headlines(client, db_session):
    rates = {date(2024, 1, i): 3.0 + i * 0.01 for i in range(1, 10)}
    seed_rates(db_session, "USD", "TND", rates)
    fake = [models.NewsItem(pair_tag="TND", headline="Dinar steady", source="TAP",
                            url="http://x/1", fetched_date=date(2024, 1, 9))]
    mock_groq = MagicMock()
    mock_groq.chat.completions.create.return_value.choices[0].message.content = "Commentary body text here."
    with patch("app.services.ai_service.Groq", return_value=mock_groq), \
         patch("app.services.ai_service.news.get_headlines", return_value=fake):
        resp = client.post("/api/v1/ai/commentary", json={
            "base": "USD", "quote": "TND", "date": "2024-01-09"
        })
    assert resp.status_code == 200
    body = resp.json()
    assert body["headlines"][0]["headline"] == "Dinar steady"
    assert body["headlines"][0]["source"] == "TAP"
