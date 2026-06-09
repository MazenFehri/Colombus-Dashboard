"""
Heuristic spot-vs-forward signal (Option A) +
CIP forward rate computation (Option B).

Interest rates (as of 2026-06) are stored as constants here — no external
source required, and they can be updated in one place when policy rates change.
"""

from dataclasses import dataclass

# Annual policy/money-market rates used for covered-interest-parity computation.
# GBP intentionally absent — forward rates for GBP pairs are returned as empty.
_INTEREST_RATES: dict[str, float] = {
    "TND": 0.0700,  # BCT key rate
    "USD": 0.0370,  # Fed funds upper bound
    "EUR": 0.0210,  # ECB deposit rate
}

# Standard FX forward tenors and their year fractions.
_TENORS: dict[str, float] = {
    "1M": 1 / 12,
    "3M": 3 / 12,
    "6M": 6 / 12,
}

# Annualised volatility thresholds — above this level vol is "elevated".
# TND is BCT-managed, so the bar is much lower than for floating pairs.
_VOL_ELEVATED: dict[str, float] = {
    "TND": 0.03,
    "default": 0.07,
}

SIGNAL_CONSIDER_FORWARD = "CONSIDER_FORWARD"
SIGNAL_SPOT_REASONABLE  = "SPOT_REASONABLE"
SIGNAL_NEUTRAL          = "NEUTRAL"


@dataclass
class ForwardRate:
    tenor: str
    rate: float
    pct_diff: float   # (forward - spot) / spot * 100


@dataclass
class HedgeSignal:
    signal: str
    short_reason: str
    context: str      # richer block fed into the AI prompt


def compute_forward_rates(spot: float, base: str, quote: str) -> list[ForwardRate]:
    """Covered interest parity: Forward = Spot × (1 + r_quote × t) / (1 + r_base × t).

    A positive pct_diff means the quote currency weakens in the forward market
    (it costs more of quote to buy one unit of base).
    Returns [] when either currency has no configured interest rate (e.g. GBP).
    """
    r_base = _INTEREST_RATES.get(base)
    r_quote = _INTEREST_RATES.get(quote)
    if r_base is None or r_quote is None:
        return []
    results: list[ForwardRate] = []
    for tenor, t in _TENORS.items():
        fwd = spot * (1 + r_quote * t) / (1 + r_base * t)
        pct_diff = (fwd - spot) / spot * 100
        results.append(ForwardRate(tenor=tenor, rate=round(fwd, 4), pct_diff=round(pct_diff, 4)))
    return results


def compute_signal(
    base: str,
    quote: str,
    exposure: str,           # "importer" | "exporter"
    change_30d_pct: float,
    annualized_vol: float,
    risk_level: str,
) -> HedgeSignal:
    """Return a HedgeSignal for the given pair and exposure direction."""
    vol_threshold = _VOL_ELEVATED.get(quote, _VOL_ELEVATED["default"])
    vol_elevated = annualized_vol >= vol_threshold
    risk_high = risk_level == "high"

    # A rising rate hurts an importer (pays more); a falling rate hurts an exporter (earns less).
    rate_moving_against = (
        change_30d_pct > 0 if exposure == "importer" else change_30d_pct < 0
    )
    rate_moving_in_favour = not rate_moving_against
    direction_word = "rising" if change_30d_pct > 0 else "falling"
    vol_word = "elevated" if vol_elevated else "low"

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

    context = (
        f"Pair: {base}/{quote}\n"
        f"Exposure: {exposure.upper()} "
        f"({'will BUY {quote} later' if exposure == 'importer' else 'will SELL/RECEIVE {quote} later'})\n"
        f"30-day rate change: {change_30d_pct:+.2f}%\n"
        f"Annualised volatility: {annualized_vol:.2%}\n"
        f"Current risk level: {risk_level.upper()}\n"
        f"Heuristic signal: {signal}\n"
        f"Signal reason: {short_reason}"
    )

    return HedgeSignal(signal=signal, short_reason=short_reason, context=context)
