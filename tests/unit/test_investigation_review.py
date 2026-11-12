import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest
from pymongo.errors import AutoReconnect

from app.investigation_review import InvestigationReviews, ReviewInput
from app.investigation_service import BaselineError
from app.review_auth import ReviewPrincipal
from tests.unit.test_investigation_api import approved_job as job_fixture
from tests.unit.test_investigation_api import client as client_fixture

approved_job = job_fixture
client = client_fixture


@pytest.fixture
def credentials(monkeypatch):
    tokens = {
        "reviewer-token": {"subject": "engineer-123", "roles": ["engineering_reviewer"]},
        "reader-token": {"subject": "reader-456", "roles": ["investigation_reader"]},
    }
    monkeypatch.setenv(
        "AUTOPLM_REVIEW_CREDENTIALS",
        json.dumps(
            {hashlib.sha256(token.encode()).hexdigest(): principal for token, principal in tokens.items()}
        ),
    )
    return {"Authorization": "Bearer reviewer-token"}


@pytest.fixture
def stored(client, approved_job, credentials):
    response = client.post(
        f"/jobs/{approved_job}/investigation-reports",
        headers=credentials,
        json={
            "request": "Inspect F0000-brake",
            "variant_id": "F0000-standard",
            "component_id": "F0000-brake",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def engineering_snapshot(db):
    return {
        name: list(db[name].find().sort("_id", 1))
        for name in db.list_collection_names()
        if name not in ("investigation_reports", "audit_events")
    }


def test_report_persistence_queue_and_retrieval(client, service, stored, credentials):
    identifier = stored["investigation_id"]
    response = client.get(f"/investigation-reports/{identifier}", headers=credentials)
    assert response.status_code == 200 and response.json() == stored
    queue = client.get("/investigation-reports", headers=credentials).json()
    assert [item["investigation_id"] for item in queue["items"]] == [identifier]
    assert stored["review_status"] == "pending"
    assert stored["investigation"]["baseline"]["fingerprint"]
    assert stored["investigation"]["baseline"]["source_provenance"]
    assert stored["investigation"]["report"]["evidence"]
    assert service.db.investigation_reports.count_documents({"_id": identifier}) == 1


@pytest.mark.parametrize("decision,status", [("ACCEPT", "accepted"), ("REJECT", "rejected")])
def test_decisions_audit_and_engineering_immutability(client, service, stored, credentials, decision, status):
    identifier = stored["investigation_id"]
    before = engineering_snapshot(service.db)
    response = client.post(
        f"/investigation-reports/{identifier}/decisions",
        headers=credentials,
        json={"decision": decision, "comments": "Evidence reviewed for further consideration"},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    row = result["decisions"][0]
    assert row["reviewer"] == "engineer-123" and row["decision"] == decision
    assert row["baseline_fingerprint"] == stored["investigation"]["baseline"]["fingerprint"]
    assert row["report_digest"] == stored["report_digest"]
    assert result["audit_mirrored"]
    audit = service.db.audit_events.find_one({"_id": row["audit_event_id"]})
    assert audit["details"]["investigation_id"] == identifier
    assert audit["details"]["comments"] == row["comments"]
    report = client.get(f"/investigation-reports/{identifier}", headers=credentials).json()
    assert report["review_status"] == status
    assert report["investigation"] == stored["investigation"]
    assert engineering_snapshot(service.db) == before
    assert client.get(f"/investigation-reports?review_status={status}", headers=credentials).json()["items"]
    assert client.get("/investigation-reports", headers=credentials).json()["items"] == []
    history = client.get(f"/investigation-reports/{identifier}/decisions", headers=credentials).json()
    assert history == result


@pytest.mark.parametrize(
    "headers,status",
    [({}, 401), ({"Authorization": "Bearer invalid"}, 401), ({"Authorization": "Bearer reader-token"}, 403)],
)
def test_authentication_and_authorization(client, stored, credentials, headers, status):
    response = client.post(
        f"/investigation-reports/{stored['investigation_id']}/decisions",
        headers=headers,
        json={"decision": "ACCEPT", "comments": "Reviewed"},
    )
    assert response.status_code == status


@pytest.mark.parametrize(
    "configuration",
    [
        None,
        "{}",
        "invalid-json",
        "[]",
        json.dumps({"0" * 64: {"subject": "", "roles": ["engineering_reviewer"]}}),
    ],
)
def test_disabled_or_invalid_authorization_fails_closed(client, monkeypatch, configuration):
    if configuration is None:
        monkeypatch.delenv("AUTOPLM_REVIEW_CREDENTIALS", raising=False)
    else:
        monkeypatch.setenv("AUTOPLM_REVIEW_CREDENTIALS", configuration)
    response = client.get("/investigation-reports", headers={"Authorization": "Bearer any-token"})
    assert response.status_code == 503


@pytest.mark.parametrize(
    "body",
    [
        {"decision": "ACCEPT"},
        {"decision": "ACCEPT", "comments": " "},
        {"decision": "APPROVE", "comments": "Reviewed"},
        {"decision": "ACCEPT", "comments": "Reviewed", "reviewer": "spoofed-name"},
    ],
)
def test_decision_validation(client, stored, credentials, body):
    response = client.post(
        f"/investigation-reports/{stored['investigation_id']}/decisions", headers=credentials, json=body
    )
    assert response.status_code == 422


def test_duplicate_decisions_cannot_overwrite(client, stored, credentials):
    url = f"/investigation-reports/{stored['investigation_id']}/decisions"
    first = client.post(url, headers=credentials, json={"decision": "ACCEPT", "comments": "First review"})
    for choice in ("ACCEPT", "REJECT"):
        second = client.post(url, headers=credentials, json={"decision": choice, "comments": "Overwrite"})
        assert second.status_code == 409
    assert client.get(url, headers=credentials).json() == first.json()


def test_conflicting_concurrent_decisions(service, stored):
    reviews = InvestigationReviews(service.repo)
    principal = ReviewPrincipal(subject="authorized-test", roles=("engineering_reviewer",))

    def submit(choice):
        try:
            reviews.decide(
                stored["investigation_id"], ReviewInput(decision=choice, comments="Review"), principal
            )
            return 200
        except BaselineError as exc:
            return exc.status

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, ["ACCEPT", "REJECT"]))
    assert sorted(results) == [200, 409]
    assert len(reviews.history(stored["investigation_id"]).decisions) == 1


def test_audit_mirror_failure_preserves_atomic_history(client, service, stored, credentials):
    with patch.object(service.repo, "audit", side_effect=AutoReconnect("temporary database issue")):
        response = client.post(
            f"/investigation-reports/{stored['investigation_id']}/decisions",
            headers=credentials,
            json={"decision": "REJECT", "comments": "Reviewed"},
        )
    assert response.status_code == 200
    assert not response.json()["audit_mirrored"]
    history = InvestigationReviews(service.repo).history(stored["investigation_id"])
    assert len(history.decisions) == 1 and not history.audit_mirrored


def test_report_tampering_is_not_reviewable(client, service, stored, credentials):
    service.db.investigation_reports.update_one(
        {"_id": stored["investigation_id"]}, {"$set": {"investigation.report.request": "tampered"}}
    )
    response = client.post(
        f"/investigation-reports/{stored['investigation_id']}/decisions",
        headers=credentials,
        json={"decision": "ACCEPT", "comments": "Review"},
    )
    assert response.status_code == 409


def test_no_history_edit_delete_and_pagination_validation(client, stored, credentials):
    url = f"/investigation-reports/{stored['investigation_id']}/decisions"
    assert client.delete(url, headers=credentials).status_code == 405
    assert client.put(url, headers=credentials, json={}).status_code == 405
    assert client.get("/investigation-reports?limit=0", headers=credentials).status_code == 422
    assert client.get("/investigation-reports?review_status=approved", headers=credentials).status_code == 422
    assert client.get("/investigation-reports/missing", headers=credentials).status_code == 404


def test_creation_does_not_change_engineering_records(client, service, approved_job, credentials):
    before = engineering_snapshot(service.db)
    response = client.post(
        f"/jobs/{approved_job}/investigation-reports",
        headers=credentials,
        json={"request": "Inspect", "variant_id": "F0000-standard"},
    )
    assert response.status_code == 201
    assert engineering_snapshot(service.db) == before


def test_reader_can_read_but_not_decide(client, stored):
    headers = {"Authorization": "Bearer reader-token"}
    assert (
        client.get(f"/investigation-reports/{stored['investigation_id']}", headers=headers).status_code == 200
    )
