from unittest.mock import patch, MagicMock
from datetime import date, timedelta
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


from app.services import ai_service


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
    # Only 9 rows of history: trend (needs 30) and vol regime (needs 111) are None,
    # so their lines must be omitted from the prompt.
    assert "Trend (MA7" not in prompt
    assert "Volatility regime" not in prompt


def test_build_context_window_covers_vol_regime(db_session):
    # Regression: build_market_context must load enough trading rows that the
    # volatility regime is computed (needs >=111 rows). A too-narrow window left
    # it silently None in the live prompt.
    start = date(2023, 9, 1)
    rates = {start + timedelta(days=i): 3.0 + (i % 7) * 0.01 for i in range(140)}
    seed_rates(db_session, "USD", "TND", rates)
    target = start + timedelta(days=139)
    with patch("app.services.ai_service.news.get_headlines", return_value=[]):
        ctx = ai_service.build_market_context(db_session, "USD", "TND", target)
    assert ctx.vol_regime is not None
    prompt = ai_service.build_prompt(ctx)
    assert "Volatility regime:" in prompt
    assert "Trend (MA7" in prompt


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
