from unittest.mock import patch, MagicMock
from datetime import date
from app.services.news_explainer import explain_article


def _groq_returning(text):
    captured = {}
    mock_groq = MagicMock()
    def create(**kwargs):
        captured["prompt"] = kwargs["messages"][0]["content"]
        r = MagicMock()
        r.choices[0].message.content = text
        return r
    mock_groq.chat.completions.create.side_effect = create
    return mock_groq, captured


def test_explains_with_full_text():
    mock_groq, captured = _groq_returning("The ECB hold removes a catalyst for euro strength.")
    with patch("app.services.news_explainer.Groq", return_value=mock_groq):
        out = explain_article(
            "EUR", "USD", date(2026, 6, 5),
            title="ECB holds rates", source="reuters.com",
            change_pct=-0.30, risk_level="low",
            full_text="The European Central Bank held interest rates steady on Thursday.",
        )
    assert out == "The ECB hold removes a catalyst for euro strength."
    # the article text and pair appear in the prompt
    assert "European Central Bank held interest rates steady" in captured["prompt"]
    assert "EUR/USD" in captured["prompt"]


def test_explains_from_headline_when_no_text():
    mock_groq, captured = _groq_returning("Based on the headline, sterling weakness pressured the pair.")
    with patch("app.services.news_explainer.Groq", return_value=mock_groq):
        out = explain_article(
            "GBP", "USD", date(2026, 6, 5),
            title="Sterling slips on BoE caution", source="bbc.com",
            change_pct=-0.5, risk_level="medium",
            full_text=None,
        )
    assert out.startswith("Based on the headline")
    assert "Sterling slips on BoE caution" in captured["prompt"]


def test_returns_none_on_groq_failure():
    with patch("app.services.news_explainer.Groq", side_effect=Exception("Groq down")):
        out = explain_article(
            "EUR", "USD", date(2026, 6, 5),
            title="ECB holds rates", source="reuters.com",
            change_pct=-0.30, risk_level="low", full_text="some text",
        )
    assert out is None
