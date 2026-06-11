import pytest
from fastapi import HTTPException
from app import models
from app.services import deps, security


def test_get_current_user_valid(db_session):
    u = models.User(email="x@y.com", hashed_password="h")
    db_session.add(u)
    db_session.commit()
    token = security.create_access_token(str(u.id))
    got = deps.get_current_user(authorization=f"Bearer {token}", db=db_session)
    assert got.id == u.id


def test_get_current_user_missing_header(db_session):
    with pytest.raises(HTTPException) as e:
        deps.get_current_user(authorization=None, db=db_session)
    assert e.value.status_code == 401


def test_get_current_user_bad_token(db_session):
    with pytest.raises(HTTPException) as e:
        deps.get_current_user(authorization="Bearer garbage", db=db_session)
    assert e.value.status_code == 401


def test_get_current_user_non_numeric_sub(db_session):
    token = security.create_access_token("not-a-number")
    with pytest.raises(HTTPException) as e:
        deps.get_current_user(authorization=f"Bearer {token}", db=db_session)
    assert e.value.status_code == 401
