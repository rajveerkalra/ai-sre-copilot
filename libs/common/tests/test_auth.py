from libs.common.auth import Principal, Role, create_access_token, decode_token


def test_token_roundtrip():
    secret = "test-secret-at-least-32-characters!!"
    token = create_access_token(
        subject="alice",
        roles=[Role.OPERATOR.value],
        secret=secret,
        email="alice@example.com",
    )
    principal = decode_token(token, secret=secret)
    assert principal.sub == "alice"
    assert principal.has_role("operator")
    assert principal.has_permission("remediations:approve")
    assert not principal.has_permission("does-not-exist")


def test_admin_star_permission():
    p = Principal(sub="a", roles=["admin"])
    assert p.has_permission("anything")
