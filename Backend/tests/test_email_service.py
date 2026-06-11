from unittest.mock import MagicMock, patch
from app.services import email_service


def test_send_email_uses_smtp(monkeypatch):
    monkeypatch.setattr(email_service.settings, "smtp_user", "me@gmail.com")
    monkeypatch.setattr(email_service.settings, "smtp_password", "app-pw")
    fake = MagicMock()
    with patch("app.services.email_service.smtplib.SMTP") as smtp_cls:
        smtp_cls.return_value.__enter__.return_value = fake
        email_service.send_email("to@x.com", "Subject", "<b>hi</b>")
    fake.starttls.assert_called_once()
    fake.login.assert_called_once_with("me@gmail.com", "app-pw")
    fake.send_message.assert_called_once()


def test_send_email_raises_when_unconfigured(monkeypatch):
    monkeypatch.setattr(email_service.settings, "smtp_user", "")
    monkeypatch.setattr(email_service.settings, "smtp_password", "")
    try:
        email_service.send_email("to@x.com", "S", "<b>h</b>")
        assert False, "expected EmailError"
    except email_service.EmailError:
        pass
