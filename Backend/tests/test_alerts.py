from app.services.alert_engine import classify_risk
from app import models
from datetime import date


def seed_rates(db_session, base, quote, rates_by_date):
    for d, r in rates_by_date.items():
        db_session.add(models.ExchangeRate(
            base_currency=base, quote_currency=quote,
            rate=r, date=d, source="test"
        ))
    db_session.commit()


# --- Unit tests for alert engine ---

def test_classify_low_risk():
    level, msg = classify_risk(0.3)
    assert level == "low"
    assert "No action" in msg


def test_classify_medium_risk():
    level, msg = classify_risk(0.7)
    assert level == "medium"
    assert "Monitor" in msg


def test_classify_high_risk_by_magnitude():
    level, msg = classify_risk(1.5)
    assert level == "high"
    assert "hedging" in msg


def test_classify_high_risk_by_spike():
    level, msg = classify_risk(0.2, spike=True)
    assert level == "high"
    assert "spike" in msg.lower()


def test_classify_negative_change():
    level, _ = classify_risk(-1.2)
    assert level == "high"


# --- API tests for alerts router ---

def test_get_alert_for_pair(client, db_session):
    from unittest.mock import patch
    rates = {
        date(2024, 1, 2): 3.10,
        date(2024, 1, 3): 3.25,  # +4.8% → high
    }
    seed_rates(db_session, "USD", "TND", rates)
    with patch("app.routers.alerts._ensure_rates_cached"):
        resp = client.get("/api/v1/alerts/USD/TND?date=2024-01-03")
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "high"
    assert data["date"] == "2024-01-03"
    assert "change_pct" in data


def test_get_alert_history(client, db_session):
    from unittest.mock import patch
    rates = {date(2024, 1, i): 3.0 + i * 0.01 for i in range(2, 8)}
    seed_rates(db_session, "USD", "TND", rates)
    with patch("app.routers.alerts._ensure_rates_cached"):
        resp = client.get("/api/v1/alerts/USD/TND/history?from_date=2024-01-03&to_date=2024-01-07")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert all("risk_level" in item for item in data)
