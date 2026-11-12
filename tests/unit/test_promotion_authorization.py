from unittest.mock import patch

import pytest

from app.repository import digest
from tests.unit.test_investigation_api import client as client_fixture
from tests.unit.test_investigation_review import credentials as reviewer_fixture

client = client_fixture
credentials = reviewer_fixture


@pytest.fixture
def verified_job(service, generated):
    return service.migrate(generated[0])["_id"]


def test_reported_forged_user_wire_request_is_rejected_without_authentication(client, service, verified_job):
    before = service.repo.job(verified_job)
    response = client.post(
        f"/jobs/{verified_job}/promote",
        content='{"approve":true,"actor":"forged-user"}',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 401
    assert service.repo.job(verified_job) == before
    assert service.repo.publication_records(verified_job) == []
    assert (
        service.db.audit_events.count_documents({"job_id": verified_job, "action": "promotion_authorized"})
        == 0
    )


@pytest.mark.parametrize(
    "headers,status",
    [
        ({}, 401),
        ({"Authorization": "Bearer invalid-token"}, 401),
        ({"Authorization": "Bearer reader-token"}, 403),
    ],
)
def test_promotion_requires_authorized_reviewer(client, service, verified_job, credentials, headers, status):
    with patch.object(service, "promote") as promote:
        response = client.post(
            f"/jobs/{verified_job}/promote",
            headers=headers,
            json={"actor": "forged-engineer", "approve": True},
        )
    assert response.status_code == status
    promote.assert_not_called()
    assert service.repo.job(verified_job)["status"] == "verified"


@pytest.mark.parametrize("body", [{"approve": True}, {"approve": True, "actor": "forged-engineer"}])
def test_promotion_uses_authenticated_subject_and_preserves_idempotence(
    client, service, generated, verified_job, credentials, body
):
    response = client.post(f"/jobs/{verified_job}/promote", headers=credentials, json=body)
    assert response.status_code == 200, response.text
    assert response.json()["approved_by"] == "engineer-123"
    assert len(service.repo.approved_records(verified_job)) == len(generated[1].documents())
    events = list(service.db.audit_events.find({"job_id": verified_job, "action": "promotion_authorized"}))
    assert len(events) == 1 and events[0]["details"]["actor"] == "engineer-123"
    again = client.post(f"/jobs/{verified_job}/promote", headers=credentials, json={"approve": True})
    assert again.status_code == 200 and again.json()["approved_by"] == "engineer-123"
    assert (
        service.db.audit_events.count_documents({"job_id": verified_job, "action": "promotion_authorized"})
        == 1
    )


@pytest.mark.parametrize("status", ["staged", "rejected", "running", "verifying"])
def test_authorized_reviewer_cannot_promote_unverified_jobs(
    client, service, verified_job, credentials, status
):
    service.db.migration_jobs.update_one({"_id": verified_job}, {"$set": {"status": status}})
    response = client.post(f"/jobs/{verified_job}/promote", headers=credentials, json={"approve": True})
    assert response.status_code == 409
    assert service.repo.job(verified_job)["status"] == status
    assert service.repo.publication_records(verified_job) == []


def test_authorization_does_not_bypass_fresh_validation(client, service, verified_job, credentials):
    service.db.staging_records.update_one(
        {"job_id": verified_job, "record.id": "F0000-brake"}, {"$set": {"record.hardware_revision": "Z"}}
    )
    service.db.migration_jobs.update_one(
        {"_id": verified_job}, {"$set": {"staging_digest": digest(service.repo.records(verified_job))}}
    )
    response = client.post(f"/jobs/{verified_job}/promote", headers=credentials, json={"approve": True})
    assert response.status_code == 409
    assert service.repo.publication_records(verified_job) == []


def test_explicit_approval_still_required(client, service, verified_job, credentials):
    response = client.post(f"/jobs/{verified_job}/promote", headers=credentials, json={"approve": False})
    assert response.status_code == 409
    assert service.repo.job(verified_job)["status"] == "verified"


def test_missing_job_cannot_be_promoted(client, credentials):
    response = client.post("/jobs/unknown-job/promote", headers=credentials, json={"approve": True})
    assert response.status_code == 404


def test_promotion_fails_closed_when_registry_disabled(client, verified_job, credentials, monkeypatch):
    monkeypatch.delenv("AUTOPLM_REVIEW_CREDENTIALS", raising=False)
    response = client.post(f"/jobs/{verified_job}/promote", headers=credentials, json={"approve": True})
    assert response.status_code == 503
