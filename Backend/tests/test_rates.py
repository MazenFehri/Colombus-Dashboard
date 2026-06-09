from datetime import date, timedelta
from unittest.mock import patch
from app import models


def seed_rates(db_session, base, quote, rates_by_date):
    for d, r in rates_by_date.items():
        db_session.add(models.ExchangeRate(
            base_currency=base, quote_currency=quote,
            rate=r, date=d, source="test"
        ))
    db_session.commit()


SAMPLE_RATES = {
    date(2024, 1, 2): 3.10,
    date(2024, 1, 3): 3.15,
    date(2024, 1, 4): 3.08,
    date(2024, 1, 5): 3.20,
}


def test_get_historical_rates_returns_list(client, db_session):
    seed_rates(db_session, "USD", "TND", SAMPLE_RATES)
    with patch("app.routers.rates.frankfurter.fetch_rates", return_value={}):
        resp = client.get("/api/v1/rates/USD/TND?from_date=2024-01-02&to_date=2024-01-05")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 4
    assert data[0]["date"] == "2024-01-02"
    assert data[0]["rate"] == 3.10


def test_get_historical_rates_invalid_range(client):
    resp = client.get("/api/v1/rates/USD/TND?from_date=2024-06-01&to_date=2024-01-01")
    assert resp.status_code == 400


def test_get_historical_rates_unsupported_pair(client):
    resp = client.get("/api/v1/rates/USD/JPY?from_date=2024-01-01&to_date=2024-01-05")
    assert resp.status_code == 400


def test_get_daily_change(client, db_session):
    seed_rates(db_session, "USD", "TND", SAMPLE_RATES)
    with patch("app.routers.rates._ensure_rates_cached"):
        with patch("app.routers.rates.analytics.load_rates_df") as mock_load:
            with patch("app.routers.rates.analytics.calc_daily_change") as mock_calc:
                import pandas as pd
                mock_load.return_value = pd.DataFrame()
                mock_calc.return_value = {
                    "date": date(2024, 1, 3),
                    "rate": 3.15,
                    "prev_rate": 3.10,
                    "change_pct": 1.6129,
                }
                resp = client.get("/api/v1/rates/USD/TND/daily-change?date=2024-01-03")
    assert resp.status_code == 200
    data = resp.json()
    assert data["date"] == "2024-01-03"
    assert abs(data["change_pct"] - 1.6129) < 0.01


def test_get_performance_weekly(client, db_session):
    seed_rates(db_session, "USD", "TND", SAMPLE_RATES)
    with patch("app.routers.rates._ensure_rates_cached"):
        with patch("app.routers.rates.analytics.load_rates_df") as mock_load:
            with patch("app.routers.rates.analytics.calc_performance") as mock_calc:
                import pandas as pd
                mock_load.return_value = pd.DataFrame()
                mock_calc.return_value = {
                    "period": "weekly",
                    "start_date": date(2024, 1, 2),
                    "end_date": date(2024, 1, 5),
                    "start_rate": 3.10,
                    "end_rate": 3.20,
                    "change_pct": 3.2258,
                }
                resp = client.get("/api/v1/rates/USD/TND/performance?period=weekly")
    assert resp.status_code == 200
    data = resp.json()
    assert data["period"] == "weekly"
    assert "change_pct" in data


def test_get_high_low(client, db_session):
    seed_rates(db_session, "USD", "TND", SAMPLE_RATES)
    with patch("app.routers.rates._ensure_rates_cached"):
        with patch("app.routers.rates.analytics.load_rates_df") as mock_load:
            with patch("app.routers.rates.analytics.calc_high_low") as mock_calc:
                import pandas as pd
                mock_load.return_value = pd.DataFrame()
                mock_calc.return_value = {
                    "high": 3.20,
                    "high_date": date(2024, 1, 5),
                    "low": 3.08,
                    "low_date": date(2024, 1, 4),
                }
                resp = client.get("/api/v1/rates/USD/TND/high-low?from_date=2024-01-02&to_date=2024-01-05")
    assert resp.status_code == 200
    data = resp.json()
    assert data["high"] == 3.20
    assert data["high_date"] == "2024-01-05"
    assert data["low"] == 3.08
    assert data["low_date"] == "2024-01-04"
