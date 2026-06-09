from datetime import date
from groq import Groq
from app.config import settings


def explain_headline(base: str, quote: str, on_date: date, headline: str,
                     source: str, change_pct: float, risk_level: str) -> str | None:
    """A short Groq paragraph explaining how a headline relates to the pair's move.

    Headline-only (the RSS feed has no article body), grounded in the day's rate
    context. Best-effort: returns None on any failure so the caller degrades to a
    plain headline link. Never raises."""
    if not settings.groq_api_key:
        return None
    pair = f"{base}/{quote}"
    prompt = (
        "You are a concise FX analyst.\n"
        f"Pair {pair} moved {change_pct:+.2f}% on {on_date} (risk: {risk_level.upper()}).\n"
        f'News headline: "{headline}" — {source}.\n'
        "In 2-3 sentences, explain what this headline is about and how it could relate "
        f"to {pair}'s movement, and what it means for a business exposed to {pair}. "
        "If the headline is only loosely related to the pair, say so briefly rather than inventing a link."
    )
    try:
        client = Groq(api_key=settings.groq_api_key)
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=160,
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return None
