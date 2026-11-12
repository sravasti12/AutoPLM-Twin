import hashlib
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.api import app
from app.review_auth import ReviewPrincipal


@pytest.fixture
def identity_client(monkeypatch):
    registry = {
        hashlib.sha256(b"identity-test-secret").hexdigest(): {
            "subject": "engineer-123",
            "roles": ["engineering_reviewer"],
        },
        hashlib.sha256(b"reader-test-secret").hexdigest(): {
            "subject": "reader-456",
            "roles": ["investigation_reader"],
        },
    }
    monkeypatch.setenv("AUTOPLM_REVIEW_CREDENTIALS", json.dumps(registry))
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize(
    "token,subject,role",
    [
        ("identity-test-secret", "engineer-123", "engineering_reviewer"),
        ("reader-test-secret", "reader-456", "investigation_reader"),
    ],
)
def test_authenticated_identity_matches_registered_principal(identity_client, token, subject, role):
    with patch("app.repository.Repository.connect") as connect:
        response = identity_client.get("/review/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == {"subject": subject, "roles": [role]}
    assert ReviewPrincipal.model_validate(response.json()).subject == subject
    assert response.headers["Cache-Control"] == "no-store"
    connect.assert_not_called()


@pytest.mark.parametrize(
    "headers", [{}, {"Authorization": "Bearer invalid"}, {"Authorization": "Basic identity-test-secret"}]
)
def test_missing_or_invalid_identity_credentials(identity_client, headers):
    response = identity_client.get("/review/me", headers=headers)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize("configuration", [None, "{}", "invalid-json"])
def test_identity_disabled_credentials(identity_client, monkeypatch, configuration):
    if configuration is None:
        monkeypatch.delenv("AUTOPLM_REVIEW_CREDENTIALS", raising=False)
    else:
        monkeypatch.setenv("AUTOPLM_REVIEW_CREDENTIALS", configuration)
    response = identity_client.get("/review/me", headers={"Authorization": "Bearer identity-test-secret"})
    assert response.status_code == 503


def test_identity_response_contains_no_credentials_or_registry(identity_client):
    response = identity_client.get("/review/me", headers={"Authorization": "Bearer identity-test-secret"})
    assert set(response.json()) == {"subject", "roles"}
    for value in (
        "identity-test-secret",
        "reader-test-secret",
        "reader-456",
        "AUTOPLM_REVIEW_CREDENTIALS",
        hashlib.sha256(b"identity-test-secret").hexdigest(),
        hashlib.sha256(b"reader-test-secret").hexdigest(),
    ):
        assert value not in response.text


def test_identity_cannot_be_overridden(identity_client):
    response = identity_client.request(
        "GET",
        "/review/me?subject=attacker&roles=administrator",
        headers={"Authorization": "Bearer identity-test-secret"},
        json={"subject": "attacker", "roles": ["administrator"]},
    )
    assert response.status_code == 200
    assert response.json() == {"subject": "engineer-123", "roles": ["engineering_reviewer"]}
    assert identity_client.post("/review/me", json={"subject": "attacker"}).status_code == 405


def test_administrator_role_is_not_invented(identity_client, monkeypatch):
    monkeypatch.setenv(
        "AUTOPLM_REVIEW_CREDENTIALS",
        json.dumps(
            {
                hashlib.sha256(b"identity-test-secret").hexdigest(): {
                    "subject": "admin-user",
                    "roles": ["administrator"],
                }
            }
        ),
    )
    response = identity_client.get("/review/me", headers={"Authorization": "Bearer identity-test-secret"})
    assert response.status_code == 503
    assert "admin-user" not in response.text
