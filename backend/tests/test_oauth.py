from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import jwt
import pytest
from app.adapters.oauth import OAuthVerifier
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException


@pytest.fixture
def signer(monkeypatch):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier = OAuthVerifier("http://localhost:8080/auth/realms/family", "http://unused/certs")
    monkeypatch.setattr(
        verifier.keys,
        "get_signing_key_from_jwt",
        lambda _: SimpleNamespace(key=private.public_key()),
    )
    claims = {
        "iss": verifier.issuer,
        "aud": "family-api",
        "sub": "family-account",
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=5),
        "realm_access": {"roles": ["family-app"]},
    }
    return private, verifier, claims


def test_valid_signed_family_token(signer):
    private, verifier, claims = signer
    assert (
        verifier.verify(jwt.encode(claims, private, algorithm="RS256"))["sub"] == "family-account"
    )


@pytest.mark.parametrize(
    "change",
    [
        {"iss": "http://attacker"},
        {"aud": "another-api"},
        {"exp": datetime(2000, 1, 1, tzinfo=UTC)},
    ],
)
def test_rejects_wrong_issuer_audience_or_expiration(signer, change):
    private, verifier, claims = signer
    with pytest.raises(HTTPException) as error:
        verifier.verify(jwt.encode(claims | change, private, algorithm="RS256"))
    assert error.value.status_code == 401


def test_rejects_unsigned_token_and_account_without_role(signer):
    private, verifier, claims = signer
    with pytest.raises(HTTPException) as error:
        verifier.verify(jwt.encode(claims, "", algorithm="none"))
    assert error.value.status_code == 401
    claims["realm_access"] = {"roles": []}
    with pytest.raises(HTTPException) as error:
        verifier.verify(jwt.encode(claims, private, algorithm="RS256"))
    assert error.value.status_code == 403


@pytest.fixture
def cognito_signer(monkeypatch):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier = OAuthVerifier(
        "https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_example",
        "http://unused/certs",
        "web-client",
        provider="cognito",
        required_group="",
        required_scope="",
    )
    monkeypatch.setattr(
        verifier.keys,
        "get_signing_key_from_jwt",
        lambda _: SimpleNamespace(key=private.public_key()),
    )
    claims = {
        "iss": verifier.issuer,
        "sub": "family-account",
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=5),
        "client_id": "web-client",
        "token_use": "access",
        "username": "family@example.invalid",
    }
    return private, verifier, claims


def test_valid_cognito_access_token(cognito_signer):
    private, verifier, claims = cognito_signer
    token = jwt.encode(claims, private, algorithm="RS256")
    assert verifier.verify(token)["sub"] == "family-account"


@pytest.mark.parametrize(
    ("change", "status"),
    [
        ({"client_id": "another-client"}, 401),
    ],
)
def test_rejects_cognito_tokens_without_required_claims(cognito_signer, change, status):
    private, verifier, claims = cognito_signer
    token = jwt.encode(claims | change, private, algorithm="RS256")
    with pytest.raises(HTTPException) as error:
        verifier.verify(token)
    assert error.value.status_code == status


def test_cognito_family_token_does_not_require_a_shared_group_or_custom_scope(cognito_signer):
    private, verifier, claims = cognito_signer
    token = jwt.encode(claims, private, algorithm="RS256")
    verified = verifier.verify(token)
    assert verified["sub"] == "family-account"
    assert verified["username"] == "family@example.invalid"
