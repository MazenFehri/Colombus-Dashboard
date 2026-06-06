from app import models


def test_list_currencies_empty(client):
    resp = client.get("/api/v1/currencies")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_currencies_returns_seeded_data(client, db_session):
    db_session.add(models.Currency(code="USD", name="US Dollar"))
    db_session.add(models.Currency(code="EUR", name="Euro"))
    db_session.commit()

    resp = client.get("/api/v1/currencies")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    codes = {c["code"] for c in data}
    assert codes == {"USD", "EUR"}
