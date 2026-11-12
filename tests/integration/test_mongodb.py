"""Real MongoDB only, with an isolated random database. No production DB variables used."""

import os
from uuid import uuid4

import pytest
from pymongo import MongoClient

from app.repository import Repository
from app.service import MigrationService

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("decision", ["ACCEPT", "REJECT"])
def test_real_persistent_investigation_review(mongodb_service, generated, monkeypatch, decision):
    import hashlib
    import json

    from fastapi.testclient import TestClient

    from app.api import app, get_service

    service = mongodb_service
    job = service.migrate(generated[0])["_id"]
    service.promote(job, "integration-setup")
    before = {
        name: list(service.db[name].find().sort("_id", 1))
        for name in service.db.list_collection_names()
        if name not in ("audit_events", "investigation_reports")
    }
    monkeypatch.setenv(
        "AUTOPLM_REVIEW_CREDENTIALS",
        json.dumps(
            {
                hashlib.sha256(b"integration-only-token").hexdigest(): {
                    "subject": "integration-reviewer",
                    "roles": ["engineering_reviewer"],
                }
            }
        ),
    )
    headers = {"Authorization": "Bearer integration-only-token"}
    app.dependency_overrides[get_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.post(
                f"/jobs/{job}/investigation-reports",
                headers=headers,
                json={"request": "Inspect F0000-brake", "variant_id": "F0000-standard"},
            )
            assert response.status_code == 201, response.text
            stored = response.json()
            identifier = stored["investigation_id"]
            # Reconstruct repository/service to prove retrieval is not process-local storage.
            app.dependency_overrides[get_service] = lambda: MigrationService(Repository(service.db))
            assert client.get(f"/investigation-reports/{identifier}", headers=headers).json() == stored
            reviewed = client.post(
                f"/investigation-reports/{identifier}/decisions",
                headers=headers,
                json={"decision": decision, "comments": "Reviewed for consideration only"},
            )
            assert reviewed.status_code == 200, reviewed.text
            assert reviewed.json()["audit_mirrored"]
            assert (
                client.get(f"/investigation-reports/{identifier}/decisions", headers=headers).json()
                == reviewed.json()
            )
            assert (
                client.post(
                    f"/investigation-reports/{identifier}/decisions",
                    headers=headers,
                    json={"decision": decision, "comments": "Duplicate"},
                ).status_code
                == 409
            )
            after = {
                name: list(service.db[name].find().sort("_id", 1))
                for name in service.db.list_collection_names()
                if name not in ("audit_events", "investigation_reports")
            }
            assert before == after
    finally:
        app.dependency_overrides.clear()


def test_real_concurrent_review_is_atomic(mongodb_service, generated):
    from concurrent.futures import ThreadPoolExecutor

    from app.investigation_review import InvestigationReviews, ReviewInput
    from app.investigation_service import BaselineError, InvestigationInput
    from app.review_auth import ReviewPrincipal

    service = mongodb_service
    job = service.migrate(generated[0])["_id"]
    service.promote(job, "integration-setup")
    principal = ReviewPrincipal(subject="reviewer", roles=("engineering_reviewer",))
    reviews = InvestigationReviews(service.repo)
    stored = reviews.create(
        job, InvestigationInput(request="Inspect", variant_id="F0000-standard"), principal
    )

    def decide(choice):
        try:
            reviews.decide(
                stored.investigation_id, ReviewInput(decision=choice, comments="Evidence reviewed"), principal
            )
            return 200
        except BaselineError as exc:
            return exc.status

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(decide, ["ACCEPT", "REJECT"]))
    assert sorted(results) == [200, 409]
    history = reviews.history(stored.investigation_id)
    assert len(history.decisions) == 1 and history.audit_mirrored


@pytest.mark.parametrize("schema", ["A", "B"])
def test_real_read_only_investigation(mongodb_service, schema):
    from fastapi.testclient import TestClient

    from app.api import app, get_service
    from app.data import generate

    service = mongodb_service
    job = service.migrate(generate(1, source=schema)[0])["_id"]
    service.promote(job, "integration-test")
    before = {
        name: list(service.db[name].find().sort("_id", 1)) for name in service.db.list_collection_names()
    }
    app.dependency_overrides[get_service] = lambda: service
    try:
        with TestClient(app) as client:
            response = client.post(
                f"/jobs/{job}/investigations",
                json={
                    "request": "Investigate impact and verify",
                    "variant_id": "F0000-standard",
                    "component_id": "F0000-brake",
                },
            )
        assert response.status_code == 200, response.text
        assert response.json()["report"]["evidence"]
        assert len(response.json()["baseline"]["fingerprint"]) == 64
        after = {
            name: list(service.db[name].find().sort("_id", 1)) for name in service.db.list_collection_names()
        }
        assert before == after
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def mongodb_service():
    uri = os.getenv("AUTOPLM_TEST_MONGODB_URI")
    if not uri:
        pytest.skip("Set AUTOPLM_TEST_MONGODB_URI explicitly to run real MongoDB integration")
    client = MongoClient(uri, serverSelectionTimeoutMS=3000)
    name = f"autoplm_test_{uuid4().hex}"
    try:
        client.admin.command("ping")
        service = MigrationService(Repository(client[name]))
        yield service
    finally:
        if client.topology_description.has_known_servers:
            assert name.startswith("autoplm_test_")
            client.drop_database(name)
        client.close()


@pytest.mark.parametrize("schema", ["A", "B"])
def test_real_mongodb_migration(mongodb_service, schema):
    from app.data import generate

    envelope, _, _ = generate(2, source=schema)
    service = mongodb_service
    first = service.migrate(envelope)
    assert first["status"] == "verified"
    assert service.migrate(envelope)["_id"] == first["_id"]
    assert service.promote(first["_id"], "integration-test")["status"] == "approved"
    assert len(service.repo.approved_records(first["_id"])) == len(envelope["records"])


def test_real_source_and_publication_integrity(mongodb_service, generated):
    service = mongodb_service
    job = service.migrate(generated[0])["_id"]
    service.promote(job, "integration-test")
    service.db.ecu_hardware.delete_one({"job_id": job})
    with pytest.raises(ValueError):
        service.repo.approved_records(job)
    service.db.source_records.delete_one({"job_id": job})
    with pytest.raises(ValueError):
        service.repo.source(job)


def test_real_unique_indexes(mongodb_service, generated):
    from pymongo.errors import DuplicateKeyError

    service = mongodb_service
    job = service.migrate(generated[0])["_id"]
    original = service.db.source_records.find_one({"job_id": job})
    del original["_id"]
    with pytest.raises(DuplicateKeyError):
        service.db.source_records.insert_one(original)


def test_real_rejected_source_cannot_be_promoted(mongodb_service, generated):
    from app.data import corrupt_legacy

    service = mongodb_service
    corrupted, _ = corrupt_legacy(generated[0], "unsupported_hardware_revision")
    job = service.migrate(corrupted)
    assert job["status"] == "rejected"
    with pytest.raises(ValueError):
        service.promote(job["_id"], "integration-test")
    proposal = service.propose_repair(job["_id"])
    assert not proposal["validation"]["passed"], "Invalid source data must not become valid by restoration"
    with pytest.raises(ValueError):
        service.decide_repair(proposal["_id"], True, "integration-test")


def test_real_api_promotion_and_reports(mongodb_service, generated):
    from fastapi.testclient import TestClient

    from app.api import app, get_service

    app.dependency_overrides[get_service] = lambda: mongodb_service
    try:
        with TestClient(app) as client:
            assert client.get("/ready").status_code == 200
            response = client.post("/jobs", json={"dataset": generated[0]})
            assert response.status_code == 200
            job = response.json()["_id"]
            assert client.get(f"/jobs/{job}/approved").status_code == 409
            assert (
                client.post(
                    f"/jobs/{job}/promote", json={"actor": "integration-test", "approve": True}
                ).status_code
                == 200
            )
            assert len(client.get(f"/jobs/{job}/approved").json()) == 13
            for format in ["json", "csv", "html"]:
                assert client.get(f"/jobs/{job}/report", params={"format": format}).status_code == 200
    finally:
        app.dependency_overrides.clear()
