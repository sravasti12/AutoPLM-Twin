import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api import app, get_service
from app.oidc_auth import IdentityUnavailable, OIDCConfig, OIDCValidator
from app.security_store import POLICY, SecurityStore, identity_key, require_secure_database

ISSUER = "https://unit-tenant.auth0.com/"
AUDIENCE = "https://autoplm.example/api"
CLIENT = "streamlit-test-client"


@pytest.fixture(scope="module")
def signing_keys():
    return [rsa.generate_private_key(public_exponent=65537, key_size=2048) for _ in range(2)]


@pytest.fixture
def oidc(monkeypatch, service, signing_keys):
    for key, value in {
        "AUTOPLM_ENVIRONMENT": "production",
        "AUTOPLM_OIDC_ISSUER": ISSUER,
        "AUTOPLM_OIDC_AUDIENCE": AUDIENCE,
        "AUTOPLM_OIDC_CLIENT_ID": CLIENT,
    }.items():
        monkeypatch.setenv(key, value)
    config = OIDCConfig.from_environment()
    validator = OIDCValidator(config)
    documents = {
        "keys": [
            {
                **json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(signing_keys[0].public_key())),
                "kid": "key-one",
                "alg": "RS256",
                "use": "sig",
            }
        ]
    }
    fetches = []

    def fetch(url):
        fetches.append(url)
        if url.endswith("openid-configuration"):
            return {"issuer": ISSUER, "jwks_uri": ISSUER + ".well-known/jwks.json"}
        assert url == ISSUER + ".well-known/jwks.json"
        return documents

    monkeypatch.setattr("app.oidc_auth.fetch_document", fetch)
    monkeypatch.setattr(service.db, "command", lambda *args, **kwargs: {"ok": 1})

    def options(**kwargs):
        from pymongo import ReadPreference

        assert kwargs["read_preference"] == ReadPreference.PRIMARY
        assert kwargs["write_concern"].document == {"w": "majority"}
        return service.db

    monkeypatch.setattr(service.db, "with_options", options)
    store = SecurityStore(service.repo)
    monkeypatch.setattr(store.db, "command", lambda *args, **kwargs: {"ok": 1})
    store.initialize()
    for module in ("app.api", "app.review_auth", "app.execution_security"):
        monkeypatch.setattr(module + ".get_validator", lambda: validator)
        monkeypatch.setattr(module + ".get_security_store", lambda: store)
    app.dependency_overrides[get_service] = lambda: service

    def mint(_key=0, _kid="key-one", **updates):
        claims = {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "sub": "auth0|reviewer",
            "azp": CLIENT,
            "iat": int(time.time()),
            "exp": int(time.time()) + 300,
            "scope": "openid autoplm:access",
        }
        claims.update(updates)
        return jwt.encode(claims, signing_keys[_key], algorithm="RS256", headers={"kid": _kid})

    try:
        with TestClient(app) as client:
            yield client, store, validator, mint, documents, fetches
    finally:
        app.dependency_overrides.clear()


def bearer(token):
    return {"Authorization": "Bearer " + token}


@pytest.mark.parametrize(
    "mutation",
    [
        {"_key": 1},
        {"iss": "https://wrong.example/"},
        {"aud": "wrong"},
        {"aud": CLIENT},
        {"exp": 1},
        {"iat": int(time.time()) + 7200},
        {"scope": "openid"},
        {"azp": "wrong-client"},
        {"nonce": "id-token"},
        {"exp": True},
        {"exp": int(time.time()) + 7200},
        {"sub": "client@clients"},
    ],
)
def test_invalid_access_tokens_are_401(oidc, mutation):
    client, _, _, mint, _, _ = oidc
    response = client.get("/jobs", headers=bearer(mint(**mutation)))
    assert response.status_code == 401


def test_missing_and_malformed_tokens(oidc):
    client, _, _, _, _, _ = oidc
    assert client.get("/jobs").status_code == 401
    for token in (
        "invalid",
        "x" * 16385,
        jwt.encode({"sub": "spoof"}, "test-key-that-is-at-least-thirty-two-characters", algorithm="HS256"),
    ):
        assert client.get("/jobs", headers=bearer(token)).status_code == 401


def test_claim_roles_email_and_wrong_issuer_grants_do_not_authorize(oidc):
    client, store, _, mint, _, _ = oidc
    token = mint(roles=["engineering_reviewer"], email="approved@example.com")
    store.set_reviewer("https://other.example/", "auth0|reviewer", True, "test-operator", "wrong issuer")
    assert client.get("/jobs", headers=bearer(token)).status_code == 403
    assert client.get("/review/me", headers=bearer(token)).json() == {
        "subject": "auth0|reviewer",
        "roles": ["investigation_reader"],
    }


def test_reviewer_promotion_uses_verified_subject_and_revocation_is_fresh(oidc, service, generated):
    client, store, _, mint, _, _ = oidc
    store.set_reviewer(ISSUER, "auth0|reviewer", True, "test-operator", "approved reviewer")
    token = mint()
    job = service.migrate(generated[0])["_id"]
    response = client.post(
        f"/jobs/{job}/promote", headers=bearer(token), json={"approve": True, "actor": "forged"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["approved_by"] == "auth0|reviewer"
    event = service.db.audit_events.find_one({"job_id": job, "action": "promotion_authorized"})
    assert event["details"]["actor"] == "auth0|reviewer"
    store.set_reviewer(ISSUER, "auth0|reviewer", False, "test-operator", "revoke immediately")
    assert client.get("/jobs", headers=bearer(token)).status_code == 403
    grant = store.db.reviewer_grants.find_one({"_id": identity_key(ISSUER, "auth0|reviewer")})
    assert len(grant["history"]) == 2


def test_unknown_kid_refresh_is_bounded_and_rotation_works(oidc, signing_keys):
    _, _, validator, mint, documents, fetches = oidc
    for _ in range(5):
        with pytest.raises(jwt.InvalidTokenError):
            validator.validate(mint(_kid="new-key", _key=1))
    assert len(fetches) == 2  # startup discovery + JWKS, no per-token fetch
    documents["keys"].append(
        {
            **json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(signing_keys[1].public_key())),
            "kid": "new-key",
            "alg": "RS256",
        }
    )
    validator.attempted_at = float("-inf")
    assert validator.validate(mint(_kid="new-key", _key=1))["sub"] == "auth0|reviewer"
    assert len(fetches) == 3


def test_expired_jwks_cache_does_not_fail_open(oidc, monkeypatch):
    _, _, validator, mint, _, _ = oidc
    validator.loaded_at = validator.attempted_at = float("-inf")
    monkeypatch.setattr(
        "app.oidc_auth.fetch_document", lambda url: (_ for _ in ()).throw(IdentityUnavailable())
    )
    with pytest.raises(IdentityUnavailable):
        validator.validate(mint())


@pytest.mark.parametrize("keys", [[], [{"kty": "RSA", "kid": "broken"}], [{"kty": "oct", "kid": "x"}]])
def test_malformed_jwks_never_replaces_trusted_cache(oidc, keys):
    _, _, validator, _, document, _ = oidc
    previous = validator.keys.copy()
    document["keys"] = keys
    with pytest.raises(IdentityUnavailable):
        validator._refresh()
    assert validator.keys == previous


def test_incomplete_security_policy_blocks_startup(oidc):
    _, store, _, _, _, _ = oidc
    store.db.security_policy.update_one({"_id": "v1"}, {"$set": {"slots": 999}})
    with pytest.raises(RuntimeError, match="Non-local startup blocked"):
        with TestClient(app):
            pass


def test_security_logs_do_not_include_tokens_claims_or_headers(oidc, caplog):
    client, _, _, _, _, _ = oidc
    secret = "never-log-this-credential"
    assert client.get("/jobs", headers=bearer(secret)).status_code == 401
    assert "invalid_access_token" in caplog.text
    assert secret not in caplog.text and "Authorization" not in caplog.text


def test_llm_daily_budget_is_shared_and_crashed_locks_do_not_expire(oidc):
    _, store, _, _, _, _ = oidc
    for _ in range(POLICY["llm_day"]):
        store.quota("reviewer", "llm_day")
    with pytest.raises(HTTPException) as exhausted:
        SecurityStore(store.repo).quota("reviewer", "llm_day")
    assert exhausted.value.status_code == 429
    store.db.security_locks.update_many(
        {"_id": {"$in": ["execution:0", "execution:1"]}},
        {
            "$set": {"owner": "crashed-worker"},
        },
    )
    with pytest.raises(HTTPException):
        with store.lock():
            pass


def test_no_network_locations_from_token_headers(oidc, signing_keys):
    _, _, validator, _, _, fetches = oidc
    token = jwt.encode(
        {"sub": "x"},
        signing_keys[0],
        algorithm="RS256",
        headers={"kid": "key-one", "jku": "https://attacker.example/keys"},
    )
    with pytest.raises(jwt.InvalidTokenError):
        validator.validate(token)
    assert len(fetches) == 2


def test_shared_quota_is_atomic_across_store_instances(oidc):
    _, first, _, _, _, _ = oidc
    other = SecurityStore(first.repo)

    def attempt(index):
        try:
            (first if index % 2 else other).quota("same-reviewer", "llm_minute")
            return 200
        except HTTPException as exc:
            assert exc.headers["Retry-After"]
            return exc.status_code

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(attempt, range(5)))
    assert sorted(results) == [200, 429, 429, 429, 429]


def test_shared_concurrency_and_conflicting_decision_locks(oidc):
    _, store, _, _, _, _ = oidc
    other = SecurityStore(store.repo)
    with store.lock(), other.lock():
        with pytest.raises(HTTPException) as error:
            with other.lock():
                pass
        assert error.value.status_code == 429
    with store.lock("/jobs/job/promote"):
        with pytest.raises(HTTPException):
            with other.lock("/jobs/job/promote"):
                pass
    assert store.db.security_locks.count_documents({"owner": {"$ne": None}}) == 0


def test_execution_limits_and_large_body(oidc):
    client, store, _, mint, _, _ = oidc
    store.set_reviewer(ISSUER, "auth0|reviewer", True, "operator", "test")
    headers = bearer(mint())
    assert client.post("/datasets/generate", headers=headers, json={"fleets": 11}).status_code == 422
    assert client.post("/datasets/generate", headers=headers, json={"fleets": 1}).status_code == 200
    response = client.post(
        "/jobs/unknown/investigations",
        headers=headers,
        json={
            "variant_id": "unknown",
            "request": "Inspect",
            "mode": "llm",
        },
    )
    assert response.status_code == 403
    response = client.post("/datasets/generate", content=b"x" * 2_000_001)
    assert response.status_code == 413
    for _ in range(POLICY["executions"] - 1):
        assert client.post("/datasets/generate", headers=headers, json={"fleets": 1}).status_code == 200
    response = client.post("/datasets/generate", headers=headers, json={"fleets": 1})
    assert response.status_code == 429 and response.headers["Retry-After"]


def test_public_snapshots_do_not_need_grants_or_database(oidc):
    client, _, _, _, _, _ = oidc
    with patch("app.review_auth.get_security_store", side_effect=AssertionError("private DB accessed")):
        assert client.get("/public/samples").status_code == 200
        assert client.get("/public/samples/synthetic-equivalent").status_code == 200


def test_installed_streamlit_builds_api_audience_and_pkce_authorization_url(monkeypatch):
    from streamlit.runtime.secrets import AttrDict
    from streamlit.web.server.starlette import starlette_auth_routes as routes

    config = AttrDict(
        {
            "redirect_uri": "https://demo.streamlit.app/oauth2callback",
            "cookie_secret": "x" * 64,
            "expose_tokens": ["access"],
            "auth0": {
                "client_id": CLIENT,
                "client_secret": "test-only",
                "server_metadata_url": ISSUER + "discovery",
                "authorize_params": {"audience": AUDIENCE},
                "client_kwargs": {
                    "scope": "openid profile email autoplm:access",
                    "code_challenge_method": "S256",
                },
            },
        }
    )
    monkeypatch.setattr(routes, "get_secrets_auth_section", lambda: config)
    client, redirect = routes._create_oauth_client("auth0")

    async def metadata():
        return {"authorization_endpoint": ISSUER + "authorize", "code_challenge_methods_supported": ["S256"]}

    monkeypatch.setattr(client, "load_server_metadata", metadata)
    result = asyncio.run(client.create_authorization_url(redirect, code_verifier="a" * 64))
    params = parse_qs(urlsplit(result["url"]).query)
    assert params["audience"] == [AUDIENCE]
    assert params["response_type"] == ["code"]
    assert params["code_challenge_method"] == ["S256"]
    assert "autoplm:access" in params["scope"][0]
    assert params["state"] and params["nonce"]


@pytest.mark.parametrize(
    "uri",
    [
        "mongodb://user:password@localhost",
        "mongodb+srv://cluster.example/",
        "mongodb+srv://user:password@cluster.example/?ssl=false",
        "mongodb+srv://user:password@cluster.example/?tlsInsecure=TRUE",
        "mongodb+srv://user:password@cluster.example/?tlsAllowInvalidCertificates=true",
        "mongodb+srv://user:password@cluster.example/?w=0",
    ],
)
def test_insecure_database_configuration_is_rejected(monkeypatch, uri):
    monkeypatch.setenv("MONGODB_DATABASE", "security_test")
    with pytest.raises(ValueError):
        require_secure_database(uri)
