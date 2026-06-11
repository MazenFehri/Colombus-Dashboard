from app import models


def test_user_row_persists(db_session):
    u = models.User(email="a@b.com", hashed_password="x", digest_enabled=False)
    db_session.add(u)
    db_session.commit()
    got = db_session.query(models.User).filter_by(email="a@b.com").one()
    assert got.id is not None
    assert got.is_active is True
    assert got.digest_enabled is False
