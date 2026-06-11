from unittest.mock import patch


def test_email_news_sends_to_current_user(client):
    # `client` fixture's test user is test@fixture.com
    with patch("app.routers.news.email_service.send_email") as send, \
         patch("app.routers.news.digest_builder.build_digest_html",
               return_value=("Subj", "<b>body</b>")):
        r = client.post("/api/v1/news/email", json={"date": "2026-06-11"})
    assert r.status_code == 200
    assert r.json() == {"sent": True, "to": "test@fixture.com"}
    send.assert_called_once_with("test@fixture.com", "Subj", "<b>body</b>")


def test_email_news_returns_502_on_smtp_failure(client):
    from app.services.email_service import EmailError
    with patch("app.routers.news.email_service.send_email", side_effect=EmailError("nope")), \
         patch("app.routers.news.digest_builder.build_digest_html",
               return_value=("S", "<b>b</b>")):
        r = client.post("/api/v1/news/email", json={})
    assert r.status_code == 502
