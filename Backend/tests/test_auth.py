def test_register_and_login_flow(noauth_client):
    r = noauth_client.post("/api/v1/auth/register",
                           json={"email": "t@e.com", "password": "secret12"})
    assert r.status_code == 201
    assert r.json()["email"] == "t@e.com"

    dup = noauth_client.post("/api/v1/auth/register",
                             json={"email": "t@e.com", "password": "secret12"})
    assert dup.status_code == 409

    ok = noauth_client.post("/api/v1/auth/login",
                            json={"email": "t@e.com", "password": "secret12"})
    assert ok.status_code == 200
    token = ok.json()["access_token"]
    assert token

    bad = noauth_client.post("/api/v1/auth/login",
                             json={"email": "t@e.com", "password": "wrong"})
    assert bad.status_code == 401

    me = noauth_client.get("/api/v1/auth/me",
                           headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["digest_enabled"] is False

    patched = noauth_client.patch("/api/v1/auth/me",
                                  headers={"Authorization": f"Bearer {token}"},
                                  json={"digest_enabled": True})
    assert patched.status_code == 200
    assert patched.json()["digest_enabled"] is True


def test_short_password_rejected(noauth_client):
    r = noauth_client.post("/api/v1/auth/register",
                           json={"email": "s@e.com", "password": "short"})
    assert r.status_code == 422


def test_long_password_rejected(noauth_client):
    r = noauth_client.post("/api/v1/auth/register",
                           json={"email": "long@e.com", "password": "x" * 100})
    assert r.status_code == 422
