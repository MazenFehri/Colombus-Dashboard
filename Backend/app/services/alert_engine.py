def classify_risk(daily_change_pct: float, spike: bool = False) -> tuple[str, str]:
    """Returns (risk_level, message)."""
    if spike:
        return "high", "Unusual spike detected (>3σ). High volatility — review FX exposure immediately."
    abs_change = abs(daily_change_pct)
    if abs_change < 0.5:
        return "low", "Normal movement. No action required."
    elif abs_change < 1.0:
        return "medium", "Moderate movement. Monitor closely."
    else:
        return "high", "Significant movement. Consider hedging or delaying FX transactions."
