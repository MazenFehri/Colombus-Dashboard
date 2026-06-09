"""
Heuristic spot-vs-forward signal (Option A).

Given trend direction, volatility level, and the user's exposure direction
(importer = will BUY foreign currency later; exporter = will SELL/receive it),
return a signal and a plain-English reason.

This is directional guidance only — not a forward price quote.
"""

from dataclasses import dataclass

# Annualised volatility thresholds (fraction, not %).
# TND pairs are BCT-managed so "elevated" kicks in at a much lower level.
_VOL_ELEVATED: dict[str, float] = {
    "TND": 0.03,   # ~3 % annualised is elevated for a managed currency
    "default": 0.07,
}

SIGNAL_CONSIDER_FORWARD = "CONSIDER_FORWARD"
SIGNAL_SPOT_REASONABLE  = "SPOT_REASONABLE"
SIGNAL_NEUTRAL          = "NEUTRAL"


@dataclass
class HedgeSignal:
    signal: str          # one of the three constants above
    short_reason: str    # one-line summary for the badge
    context: str         # richer bullet-point context fed to the AI


def compute_signal(
    base: str,
    quote: str,
    exposure: str,          # "importer" | "exporter"
    change_30d_pct: float,  # 30-day % change in the rate (positive = quote strengthened vs base)
    annualized_vol: float,  # from calc_volatility
    risk_level: str,        # "low" | "medium" | "high"
) -> HedgeSignal:
    """Return a HedgeSignal for the given pair and exposure."""

    vol_threshold = _VOL_ELEVATED.get(quote, _VOL_ELEVATED["default"])
    vol_elevated = annualized_vol >= vol_threshold
    risk_high = risk_level == "high"

    # From the importer's perspective: a rising rate is BAD (they'll pay more).
    # From the exporter's perspective: a falling rate is BAD (they'll receive less).
    if exposure == "importer":
        rate_moving_against = change_30d_pct > 0   # foreign currency getting more expensive
    else:
        rate_moving_against = change_30d_pct < 0   # foreign currency getting cheaper

    rate_moving_in_favour = not rate_moving_against
    direction_word = "rising" if change_30d_pct > 0 else "falling"
    vol_word = "elevated" if vol_elevated else "low"

    # ── Decision logic ──────────────────────────────────────────────────────
    if rate_moving_against and (vol_elevated or risk_high):
        signal = SIGNAL_CONSIDER_FORWARD
        short_reason = (
            f"{base}/{quote} is {direction_word} ({change_30d_pct:+.1f}% / 30d) "
            f"and volatility is {vol_word} — locking in today's rate reduces risk."
        )

    elif rate_moving_in_favour and not vol_elevated and not risk_high:
        signal = SIGNAL_SPOT_REASONABLE
        short_reason = (
            f"{base}/{quote} is moving in your favour ({change_30d_pct:+.1f}% / 30d) "
            f"with {vol_word} volatility — staying on spot may be beneficial."
        )

    else:
        signal = SIGNAL_NEUTRAL
        short_reason = (
            f"No strong directional signal for {base}/{quote} "
            f"({change_30d_pct:+.1f}% / 30d, {vol_word} volatility)."
        )

    # ── Context block for the AI prompt ─────────────────────────────────────
    context = (
        f"Pair: {base}/{quote}\n"
        f"Exposure direction: {exposure.upper()} "
        f"({'will BUY foreign currency later' if exposure == 'importer' else 'will RECEIVE/SELL foreign currency later'})\n"
        f"30-day rate change: {change_30d_pct:+.2f}%  (positive = {quote} strengthened vs {base})\n"
        f"Annualised volatility: {annualized_vol:.2%}\n"
        f"Current risk level: {risk_level.upper()}\n"
        f"Heuristic signal: {signal}\n"
        f"Signal reason: {short_reason}"
    )

    return HedgeSignal(signal=signal, short_reason=short_reason, context=context)