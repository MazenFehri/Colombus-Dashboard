import pandas as pd
import numpy as np
import pytest
from datetime import date, timedelta
from app.services.analytics import (
    calc_daily_change, calc_performance, calc_high_low,
    calc_volatility, is_spike, build_snapshot,
    calc_trend, calc_vol_regime, calc_momentum,
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


# ----- build_snapshot -----

def test_build_snapshot_mid_history_all_fields():
    # 60 days of gently varying data; resolve to the last day.
    rates = [3.0 + 0.01 * np.sin(i * 0.4) for i in range(60)]
    df = make_df(rates, start=date(2024, 1, 1))
    as_of = date(2024, 1, 1) + timedelta(days=59)
    snap = build_snapshot(df, as_of, "TND")
    assert snap["resolved_date"] == as_of
    assert snap["rate"] == round(float(rates[-1]), 6)
    assert snap["d1"] is not None
    assert snap["d7"] is not None
    assert snap["d30"] is not None
    assert snap["high"] is not None
    assert snap["low"] is not None
    assert snap["volatility"] is not None
    assert snap["risk"] in ("low", "medium", "high")


def test_build_snapshot_insufficient_history_nulls():
    # Only 10 days of data -> volatility None (needs 21).
    rates = [3.0 + i * 0.001 for i in range(10)]
    df = make_df(rates, start=date(2024, 1, 1))
    as_of = date(2024, 1, 1) + timedelta(days=9)
    snap = build_snapshot(df, as_of, "TND")
    assert snap["resolved_date"] == as_of
    assert snap["volatility"] is None
    assert snap["d1"] is not None  # 2 rows present


def test_build_snapshot_single_row_d1_none_risk_low():
    df = make_df([3.0], start=date(2024, 1, 1))
    snap = build_snapshot(df, date(2024, 1, 1), "TND")
    assert snap["d1"] is None
    assert snap["d7"] is None
    assert snap["d30"] is None
    assert snap["volatility"] is None
    assert snap["risk"] == "low"
    assert snap["rate"] == 3.0


def test_build_snapshot_holiday_falls_back_to_prior_trading_day():
    # Weekday gap: data for Jan 1..3 and Jan 8.., picking Jan 5 (a hole) resolves to Jan 3.
    dates = [date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 8)]
    df = pd.DataFrame({"date": pd.to_datetime(dates), "rate": [3.0, 3.1, 3.2, 3.3]})
    snap = build_snapshot(df, date(2024, 1, 5), "TND")
    assert snap["resolved_date"] == date(2024, 1, 3)
    assert snap["rate"] == 3.2


def test_build_snapshot_no_data_before_as_of_raises():
    df = make_df([3.0, 3.1], start=date(2024, 1, 10))
    with pytest.raises(ValueError):
        build_snapshot(df, date(2024, 1, 1), "TND")


def test_calc_trend_none_under_30_rows():
    df = make_df([3.0 + i * 0.01 for i in range(20)])
    assert calc_trend(df) is None


def test_calc_trend_bullish():
    # Rising series: recent MA7 above MA30
    df = make_df([3.0 + i * 0.02 for i in range(40)])
    result = calc_trend(df)
    assert result is not None
    assert result["direction"] == "bullish"
    assert result["ma7"] > result["ma30"]


def test_calc_trend_bearish():
    df = make_df([4.0 - i * 0.02 for i in range(40)])
    result = calc_trend(df)
    assert result["direction"] == "bearish"


def test_calc_trend_neutral_flat():
    df = make_df([3.0 for _ in range(40)])
    assert calc_trend(df)["direction"] == "neutral"


def test_calc_vol_regime_none_when_short():
    df = make_df([3.0 + i * 0.01 for i in range(50)])
    assert calc_vol_regime(df) is None


def test_calc_vol_regime_elevated():
    import numpy as np
    rng = np.random.default_rng(0)
    calm = list(3.0 + np.cumsum(rng.normal(0, 0.001, 110)))
    shock = [calm[-1] * (1 + x) for x in rng.normal(0, 0.05, 5)]
    df = make_df(calm + shock)
    assert calc_vol_regime(df) == "elevated"


def test_calc_momentum_none_when_short():
    assert calc_momentum(make_df([3.0, 3.1])) is None


def test_calc_momentum_value():
    # Accelerating move => positive momentum
    df = make_df([3.00, 3.01, 3.04])
    result = calc_momentum(df)
    assert result is not None
    assert result > 0


def test_calc_vol_regime_normal():
    rng = np.random.default_rng(2)
    steady = list(3.0 + np.cumsum(rng.normal(0, 0.003, 140)))
    assert calc_vol_regime(make_df(steady)) == "normal"


def test_calc_vol_regime_compressed():
    rng = np.random.default_rng(1)
    volatile = list(3.0 + np.cumsum(rng.normal(0, 0.01, 110)))
    calm = list(volatile[-1] + np.cumsum(rng.normal(0, 0.0001, 25)))
    assert calc_vol_regime(make_df(volatile + calm)) == "compressed"


def test_calc_vol_regime_boundary_rows():
    rates = [3.0 + i * 0.001 for i in range(110)]
    assert calc_vol_regime(make_df(rates)) is None          # 110 rows -> 89 rolling obs
    rates2 = [3.0 + i * 0.001 for i in range(111)]
    assert calc_vol_regime(make_df(rates2)) is not None      # 111 rows -> 90 rolling obs


def test_calc_trend_exactly_30_rows():
    df = make_df([3.0 + i * 0.01 for i in range(30)])
    assert calc_trend(df) is not None


def test_calc_trend_zero_rate_guard():
    assert calc_trend(make_df([0.0 for _ in range(30)])) is None
