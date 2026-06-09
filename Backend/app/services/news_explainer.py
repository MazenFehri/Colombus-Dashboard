from datetime import date
from groq import Groq
from app.config import settings


def explain_article(
    base: str,
    quote: str,
    on_date: date,
    title: str,
    source: str,
    change_pct: float,
    risk_level: str,
    full_text: str | None = None,
) -> str | None:
    """Return a short paragraph explaining the article and how it relates to the
    pair's move on on_date. Uses full_text when available, else the headline.
    Returns None if the Groq call fails (caller degrades gracefully)."""
    pair = f"{base}/{quote}"
    context = (
        f"{pair} moved {change_pct:+.2f}% on {on_date} (risk level: {risk_level.upper()}). "
        f"News article from {source}, headline: \"{title}\"."
    )
    if full_text:
        body = f" Article text: {full_text}"
        instruction = (
            "In 2-3 sentences, explain what this article reports and how it relates to or "
            f"helps explain the {pair} movement for a business with {pair} exposure."
        )
    else:
        body = ""
        instruction = (
            "Based only on the headline, in 2-3 sentences explain what this news likely "
            f"concerns and how it might relate to the {pair} movement for a business with "
            f"{pair} exposure."
        )
    prompt = f"You are a concise FX analyst. {context}{body} {instruction}"

    try:
        client = Groq(api_key=settings.groq_api_key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return None
