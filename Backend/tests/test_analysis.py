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


def _continuous_rates(start: date, n: int, base_rate: float = 3.0):
    return {start + timedelta(days=i): round(base_rate + 0.001 * i, 6) for i in range(n)}


def test_snapshot_with_as_of(client, db_session):
    start = date(2024, 1, 1)
    rates = _continuous_rates(start, 40)
    seed_rates(db_session, "USD", "TND", rates)
    as_of = start + timedelta(days=39)
    with patch("app.routers.analysis._ensure_rates_cached"):
        resp = client.get(f"/api/v1/analysis/USD/TND/snapshot?as_of={as_of.isoformat()}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["resolved_date"] == as_of.isoformat()
    assert data["rate"] is not None
    assert data["d1"] is not None
    assert data["volatility"] is not None
    assert data["risk"] in ("LOW", "MEDIUM", "HIGH")
    for key in ("resolved_date", "rate", "d1", "d7", "d30", "high", "low", "volatility", "risk"):
        assert key in data


def test_snapshot_defaults_to_live(client, db_session):
    today = date.today()
    start = today - timedelta(days=39)
    rates = _continuous_rates(start, 40)
    seed_rates(db_session, "USD", "TND", rates)
    with patch("app.routers.analysis._ensure_rates_cached"):
        resp = client.get("/api/v1/analysis/USD/TND/snapshot")
    assert resp.status_code == 200
    data = resp.json()
    assert data["resolved_date"] == today.isoformat()


def test_snapshot_holiday_resolves_prior_trading_day(client, db_session):
    seed_rates(db_session, "USD", "TND", {
        date(2024, 1, 1): 3.0,
        date(2024, 1, 2): 3.1,
        date(2024, 1, 3): 3.2,
        date(2024, 1, 8): 3.3,
    })
    with patch("app.routers.analysis._ensure_rates_cached"):
        resp = client.get("/api/v1/analysis/USD/TND/snapshot?as_of=2024-01-05")
    assert resp.status_code == 200
    data = resp.json()
    assert data["resolved_date"] == "2024-01-03"


def test_snapshot_no_data_before_as_of_returns_422(client, db_session):
    seed_rates(db_session, "USD", "TND", {date(2024, 6, 1): 3.0, date(2024, 6, 2): 3.1})
    with patch("app.routers.analysis._ensure_rates_cached"):
        resp = client.get("/api/v1/analysis/USD/TND/snapshot?as_of=2024-01-01")
    assert resp.status_code == 422


def test_snapshot_unsupported_pair(client):
    resp = client.get("/api/v1/analysis/USD/JPY/snapshot")
    assert resp.status_code == 400


def test_snapshot_endpoint_returns_signal_fields(client, db_session):
    start = date(2024, 1, 1)
    for i in range(120):
        db_session.add(models.ExchangeRate(
            base_currency="EUR", quote_currency="USD",
            rate=1.08 + i * 0.0005, date=start + timedelta(days=i), source="test",
        ))
    db_session.commit()
    as_of = (start + timedelta(days=119)).isoformat()
    resp = client.get(f"/api/v1/analysis/EUR/USD/snapshot?as_of={as_of}")
    assert resp.status_code == 200
    body = resp.json()
    assert "trend" in body and "vol_regime" in body and "momentum" in body
