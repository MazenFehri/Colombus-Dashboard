# TND is BCT-managed with typical daily moves of 0.01–0.15%; major pairs move 0.3–1%.
_THRESHOLDS: dict[str, tuple[float, float]] = {
    "TND": (0.10, 0.25),
    "default": (0.50, 1.00),
}


def classify_risk(daily_change_pct: float, spike: bool = False, quote: str = "") -> tuple[str, str]:
    """Returns (risk_level, message)."""
    if spike:
        return "high", "Unusual spike detected (>3σ). High volatility — review FX exposure immediately."
    abs_change = abs(daily_change_pct)
    low_thresh, high_thresh = _THRESHOLDS.get(quote, _THRESHOLDS["default"])
    if abs_change < low_thresh:
        return "low", "Normal movement. No action required."
    elif abs_change < high_thresh:
        return "medium", "Moderate movement. Monitor closely."
    else:
        return "high", "Significant movement. Consider hedging or delaying FX transactions."
