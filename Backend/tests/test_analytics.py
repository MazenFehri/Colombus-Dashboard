import pandas as pd
import numpy as np
from datetime import date, timedelta
from app.services.analytics import (
    calc_daily_change, calc_performance, calc_high_low,
    calc_volatility, is_spike,
)


def make_df(rates: list[float], start: date = date(2024, 1, 2)) -> pd.DataFrame:
    dates = [start + timedelta(days=i) for i in range(len(rates))]
    df = pd.DataFrame({"date": pd.to_datetime(dates), "rate": rates})
    return df


def test_calc_daily_change_basic():
    df = make_df([3.10, 3.20])
    result = calc_daily_change(df)
    assert result["date"] == date(2024, 1, 3)
    assert abs(result["change_pct"] - ((3.20 - 3.10) / 3.10 * 100)) < 0.001


def test_calc_daily_change_needs_two_rows():
    import pytest
    df = make_df([3.10])
    with pytest.raises(ValueError, match="2 days"):
        calc_daily_change(df)


def test_calc_performance_weekly():
    rates = [3.0 + i * 0.01 for i in range(10)]
    df = make_df(rates)
    result = calc_performance(df, "weekly")
    assert result["period"] == "weekly"
    assert result["end_rate"] > result["start_rate"]


def test_calc_high_low():
    df = make_df([3.10, 3.30, 2.90, 3.20])
    result = calc_high_low(df)
    assert result["high"] == 3.30
    assert result["low"] == 2.90


def test_calc_volatility_needs_21_rows():
    import pytest
    df = make_df([3.0 + i * 0.01 for i in range(10)])
    with pytest.raises(ValueError, match="21 days"):
        calc_volatility(df)


def test_calc_volatility_returns_positive_values():
    rates = [3.0 + 0.01 * np.sin(i * 0.5) for i in range(30)]
    df = make_df(rates)
    result = calc_volatility(df)
    assert result["rolling_21d_std"] > 0
    assert result["annualized_vol"] > 0
    assert result["latest_date"] == date(2024, 1, 2) + timedelta(days=29)


def test_is_spike_false_for_normal_movement():
    rates = [3.0 + 0.005 * np.sin(i) for i in range(70)]
    df = make_df(rates)
    assert not is_spike(df)


def test_is_spike_true_for_large_jump():
    rates = [3.0] * 65 + [3.0, 3.0, 3.0, 6.0]  # last day: huge spike
    df = make_df(rates)
    assert is_spike(df)
