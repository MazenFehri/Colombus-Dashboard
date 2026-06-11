import pytest
from app.services import security


def test_password_hash_roundtrip():
    h = security.hash_password("hunter2pass")
    assert h != "hunter2pass"
    assert security.verify_password("hunter2pass", h) is True
    assert security.verify_password("wrong", h) is False


def test_token_roundtrip():
    token = security.create_access_token("user-42")
    payload = security.decode_token(token)
    assert payload["sub"] == "user-42"


def test_decode_invalid_token_raises():
    with pytest.raises(Exception):
        security.decode_token("not.a.real.token")
