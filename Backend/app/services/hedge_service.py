"""
Hedge recommendation service.

Combines:
  A) Heuristic signal    (hedge_engine.compute_signal)
  B) CIP forward rates   (hedge_engine.compute_forward_rates)
  C) AI narrative        (Groq, always fresh — not cached)
"""

from datetime import date, timedelta

import pandas as pd
from groq import Groq
from sqlalchemy.orm import Session

from app.config import settings
from app.services import alert_engine, analytics
from app.services.hedge_engine import HedgeSignal, compute_forward_rates, compute_signal


def get_hedge_recommendation(
    db: Session,
    base: str,
    quote: str,
    exposure: str,   # "importer" | "exporter"
    as_of: date,
) -> dict:
    from_date = as_of - timedelta(days=400)
    df = analytics.load_rates_df(db, base, quote, from_date, as_of)

    if df.empty:
        raise ValueError(f"No rate data available for {base}/{quote} up to {as_of}")

    # Resolve to the nearest prior trading day.
    eligible = df[df["date"] <= pd.Timestamp(as_of)]
    if eligible.empty:
        raise ValueError(f"No data at or before {as_of}")
    spot_row = eligible.iloc[-1]
    resolved_date: date = spot_row["date"].date()
    spot_rate = float(spot_row["rate"])

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

    # ── Option A: heuristic signal ───────────────────────────────────────────
    hedge: HedgeSignal = compute_signal(
        base=base,
        quote=quote,
        exposure=exposure,
        change_30d_pct=change_30d,
        annualized_vol=annualized_vol,
        risk_level=risk_level,
    )

    # ── Option B: CIP forward rates ──────────────────────────────────────────
    forward_rates = compute_forward_rates(spot_rate, base, quote)

    fwd_block = ""
    if forward_rates:
        lines = [
            f"  {fr.tenor}: {fr.rate:.4f} ({fr.pct_diff:+.2f}% vs spot)"
            for fr in forward_rates
        ]
        fwd_block = "CIP forward rates (indicative):\n" + "\n".join(lines) + "\n"

    # ── Option C: AI narrative ───────────────────────────────────────────────
    history_str = ", ".join(
        f"{row['date'].date()}: {row['rate']:.4f}"
        for _, row in df.tail(7).iterrows()
    )

    prompt = (
        f"You are a concise FX risk advisor. "
        f"A business is an {exposure.upper()} with {base}/{quote} exposure — "
        f"they will {'BUY' if exposure == 'importer' else 'SELL/RECEIVE'} {quote} in the future.\n\n"
        f"Market context as of {resolved_date}:\n"
        f"Spot rate: {spot_rate:.4f}\n"
        f"{fwd_block}"
        f"{hedge.context}\n"
        f"Recent 7-day history: {history_str}\n\n"
        f"In 3-4 sentences, explain in plain business language:\n"
        f"1. What the market is doing and why it matters for this business.\n"
        f"2. Why the signal suggests '{hedge.signal}' for them.\n"
        f"3. One practical consideration (reference the forward rate levels if available).\n"
        f"End with a one-sentence disclaimer that this is educational guidance, not financial advice.\n"
        f"Be direct. No bullet points."
    )

    try:
        client = Groq(api_key=settings.groq_api_key)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
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
        "spot_rate": round(spot_rate, 4),
        "change_30d": round(change_30d, 4),
        "volatility": round(annualized_vol, 6),
        "risk_level": risk_level,
        "forward_rates": [
            {"tenor": fr.tenor, "rate": fr.rate, "pct_diff": fr.pct_diff}
            for fr in forward_rates
        ],
    }
