def test_gated_route_rejects_without_token(noauth_client):
    r = noauth_client.get("/api/v1/currencies")
    assert r.status_code == 401


def test_gated_route_allows_with_override(client):
    # `client` overrides get_current_user, so no token needed.
    r = client.get("/api/v1/currencies")
    assert r.status_code == 200
