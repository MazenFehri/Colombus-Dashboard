import smtplib
from email.message import EmailMessage
from app.config import settings


class EmailError(Exception):
    """Raised when an email cannot be sent."""


def send_email(to: str, subject: str, html: str) -> None:
    if not settings.smtp_user or not settings.smtp_password:
        raise EmailError("SMTP credentials not configured")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to
    msg.set_content("This email requires an HTML-capable client.")
    msg.add_alternative(html, subtype="html")

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
            smtp.starttls()
            smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)
    except Exception as exc:  # network, auth, etc.
        raise EmailError(str(exc)) from exc
