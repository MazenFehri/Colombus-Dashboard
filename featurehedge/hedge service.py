"""
Hedge recommendation service.

Combines:
  A) heuristic signal from hedge_engine
  C) AI narrative from Groq (always fresh — no DB caching)
"""

from datetime import date, timedelta
from sqlalchemy.orm import Session
from groq import Groq

from app import models
from app.services import analytics, alert_engine
from app.services.hedge_engine import compute_signal, HedgeSignal
from app.config import settings


def get_hedge_recommendation(
    db: Session,
    base: str,
    quote: str,
    exposure: str,   # "importer" | "exporter"
    as_of: date,
) -> dict:
    """
    Returns a dict with:
      signal        – CONSIDER_FORWARD | SPOT_REASONABLE | NEUTRAL
      short_reason  – one-liner for the badge
      narrative     – AI plain-English explanation (always fresh)
      exposure      – echoed back
      as_of         – resolved trading date
      change_30d    – 30-day % change used in the signal
      volatility    – annualised vol used in the signal
      risk_level    – current risk level
    """
    from_date = as_of - timedelta(days=400)
    df = analytics.load_rates_df(db, base, quote, from_date, as_of)

    if df.empty:
        raise ValueError(f"No rate data available for {base}/{quote} up to {as_of}")

    # Resolve to nearest prior trading day
    import pandas as pd
    as_of_ts = pd.Timestamp(as_of)
    eligible = df[df["date"] <= as_of_ts]
    if eligible.empty:
        raise ValueError(f"No data at or before {as_of}")
    resolved_date = eligible.iloc[-1]["date"].date()

    # ── Metrics ─────────────────────────────────────────────────────────────
    try:
        perf = analytics.calc_performance(df, "monthly")
        change_30d = perf["change_pct"]
    except ValueError:
        change_30d = 0.0

    try:
        vol_data = analytics.calc_volatility(df)
        annualized_vol = vol_data["annualized_vol"]
    except ValueError:
        annualized_vol = 0.0

    try:
        daily = analytics.calc_daily_change(df)
        daily_change = daily["change_pct"]
    except ValueError:
        daily_change = 0.0

    spike = analytics.is_spike(df)
    risk_level, _ = alert_engine.classify_risk(daily_change, spike=spike, quote=quote)

    # ── Heuristic signal (Option A) ──────────────────────────────────────────
    hedge: HedgeSignal = compute_signal(
        base=base,
        quote=quote,
        exposure=exposure,
        change_30d_pct=change_30d,
        annualized_vol=annualized_vol,
        risk_level=risk_level,
    )

    # ── AI narrative (Option C) — always fresh ───────────────────────────────
    rate_history = [
        f"{row['date'].date()}: {row['rate']:.4f}"
        for _, row in df.tail(7).iterrows()
    ]
    history_str = ", ".join(rate_history)

    prompt = (
        f"You are a concise FX risk advisor. "
        f"A business is an {exposure.upper()} with {base}/{quote} exposure — "
        f"they will {'BUY' if exposure == 'importer' else 'SELL/RECEIVE'} {quote} in the future.\n\n"
        f"Here is the market context as of {resolved_date}:\n"
        f"{hedge.context}\n"
        f"Recent 7-day rate history: {history_str}\n\n"
        f"In 3-4 sentences, explain in plain business language:\n"
        f"1. What the market is doing and why this matters for this specific business.\n"
        f"2. Why the heuristic suggests '{hedge.signal}' for them.\n"
        f"3. One practical consideration they should keep in mind.\n"
        f"End with a one-sentence disclaimer that this is educational guidance, not financial advice.\n"
        f"Be direct. No bullet points."
    )

    try:
        client = Groq(api_key=settings.groq_api_key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=280,
            temperature=0.4,
        )
        narrative = response.choices[0].message.content.strip()
    except Exception as e:
        narrative = f"AI narrative unavailable: {e}"

    return {
        "signal": hedge.signal,
        "short_reason": hedge.short_reason,
        "narrative": narrative,
        "exposure": exposure,
        "as_of": resolved_date,
        "change_30d": round(change_30d, 4),
        "volatility": round(annualized_vol, 6),
        "risk_level": risk_level,
    }