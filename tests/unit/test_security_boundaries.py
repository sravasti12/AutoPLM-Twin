"""Local authorization boundaries; no provider or application database calls."""
from unittest.mock import patch

import pytest

from tests.unit.test_investigation_api import client as client_fixture
from tests.unit.test_investigation_review import credentials as credentials_fixture

client = client_fixture
credentials = credentials_fixture

ACTIONS = [
    ("/jobs/job/repairs", {}, "propose_repair"),
    ("/repairs/proposal/decision", {"approve": False, "actor": "forged-user"}, "decide_repair"),
    ("/jobs/job/mappings/decision", {"plan": {}, "approve": False, "actor": "forged-user"}, "decide_mapping"),
]


@pytest.mark.parametrize("path,body,method", ACTIONS)
@pytest.mark.parametrize("token,status", [(None, 401), ("wrong", 401), ("reader-token", 403)])
def test_sensitive_actions_fail_before_service_execution(
    client, service, credentials, path, body, method, token, status,
):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    with patch.object(service, method) as operation:
        response = client.post(path, json=body, headers=headers)
    assert response.status_code == status
    operation.assert_not_called()


@pytest.mark.parametrize("path,body,method", ACTIONS)
def test_sensitive_actions_use_authenticated_subject(client, service, credentials, path, body, method):
    with patch.object(service, method, return_value={"status": "test"}) as operation:
        response = client.post(path, json=body, headers=credentials)
    assert response.status_code == 200
    args, kwargs = operation.call_args
    assert "engineer-123" in (*args, *kwargs.values())
    assert "forged-user" not in (*args, *kwargs.values())


@pytest.mark.parametrize("environment", ["production", "staging", "unexpected", ""])
def test_static_credentials_are_rejected_outside_explicit_local_mode(
    client, credentials, monkeypatch, environment,
):
    monkeypatch.setenv("AUTOPLM_ENVIRONMENT", environment)
    response = client.get("/review/me", headers=credentials)
    assert response.status_code == 503
    assert response.json()["detail"] == "Production identity provider is not configured"


def test_authenticated_repair_persists_server_identity(client, service, generated, credentials):
    job = service.migrate(generated[0])["_id"]
    response = client.post(f"/jobs/{job}/repairs", headers=credentials)
    assert response.status_code == 200, response.text
    proposal = response.json()
    assert proposal["proposed_by"] == "engineer-123"
    response = client.post(
        f"/repairs/{proposal['_id']}/decision",
        json={"approve": False, "actor": "forged-user"}, headers=credentials,
    )
    assert response.status_code == 200, response.text
    assert service.db.repair_proposals.find_one({"_id": proposal["_id"]})["reviewer"] == "engineer-123"


@pytest.mark.parametrize("environment", ["production", "staging"])
def test_non_local_startup_fails_closed(monkeypatch, environment):
    from fastapi.testclient import TestClient

    from app.api import app

    monkeypatch.setenv("AUTOPLM_ENVIRONMENT", environment)
    with pytest.raises(RuntimeError, match="Non-local startup blocked"):
        with TestClient(app):
            pass


@pytest.mark.parametrize(
    "error,status", [(KeyError("private-secret"), 404), (ValueError("private-secret"), 409)]
)
def test_domain_errors_do_not_expose_internal_messages(client, service, error, status):
    with patch.object(service.repo, "job", side_effect=error):
        response = client.get("/jobs/missing")
    assert response.status_code == status
    assert "private-secret" not in response.text
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"


@pytest.mark.parametrize("token,status", [("reviewer-token", "approved"), ("reader-token", "verified")])
def test_dashboard_promotion_forwards_credential_and_uses_backend_identity(
    client, service, generated, credentials, token, status,
):
    from pathlib import Path

    from streamlit.testing.v1 import AppTest

    job_id = service.migrate(generated[0])["_id"]

    def request(method, url, **kwargs):
        kwargs.pop("timeout", None)
        return client.request(method, url.replace("http://localhost:8000", ""), **kwargs)

    with patch("httpx.request", side_effect=request):
        view = AppTest.from_file(Path("dashboard/streamlit_app.py").resolve(), default_timeout=20).run()
        view.sidebar.radio[0].set_value("Agent Review Queue").run()
        credential_input = next(
            item for item in view.text_input if item.label == "Reviewer bearer credential"
        )
        credential_input.set_value(token).run()
        next(item for item in view.button if item.label == "Approve engineering promotion").click().run()
    assert not view.exception
    job = service.repo.job(job_id)
    assert job["status"] == status
    if status == "approved":
        assert job["approved_by"] == "engineer-123"
    else:
        assert view.error
