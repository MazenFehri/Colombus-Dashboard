from unittest.mock import patch
from datetime import date
from app import models
from app.services import scheduler


def test_run_digest_job_sends_only_to_opted_in(db_session):
    db_session.add_all([
        models.User(email="on@x.com", hashed_password="h", digest_enabled=True),
        models.User(email="off@x.com", hashed_password="h", digest_enabled=False),
    ])
    db_session.commit()

    with patch("app.services.scheduler.SessionLocal", return_value=db_session), \
         patch("app.services.scheduler.digest_builder.build_digest_html",
               return_value=("S", "<b>b</b>")), \
         patch("app.services.scheduler.email_service.send_email") as send:
        scheduler.run_digest_job()

    sent_to = {c.args[0] for c in send.call_args_list}
    assert sent_to == {"on@x.com"}


def test_run_digest_job_continues_past_failure(db_session):
    db_session.add_all([
        models.User(email="a@x.com", hashed_password="h", digest_enabled=True),
        models.User(email="b@x.com", hashed_password="h", digest_enabled=True),
    ])
    db_session.commit()
    from app.services.email_service import EmailError

    with patch("app.services.scheduler.SessionLocal", return_value=db_session), \
         patch("app.services.scheduler.digest_builder.build_digest_html",
               return_value=("S", "<b>b</b>")), \
         patch("app.services.scheduler.email_service.send_email",
               side_effect=[EmailError("x"), None]) as send:
        scheduler.run_digest_job()  # must not raise

    assert send.call_count == 2
