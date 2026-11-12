"""Phase 4 regression checks. MongoDB behavior here uses an explicit test double."""

import copy

import pytest
from fastapi.testclient import TestClient
from pymongo.errors import ServerSelectionTimeoutError

from app.api import app, get_service
from tests.unit.test_investigation_review import credentials as reviewer_fixture

credentials = reviewer_fixture


@pytest.mark.parametrize("mutation", ["content", "annotation", "deleted_row", "extra_row"])
def test_source_snapshot_tampering_blocks_promotion(service, generated, mutation):
    job = service.migrate(generated[0])["_id"]
    row = service.db.source_records.find_one({"job_id": job})
    if mutation == "content":
        service.db.source_records.update_one({"_id": row["_id"]}, {"$set": {"source.data.revision": "Z"}})
    elif mutation == "annotation":
        service.db.source_records.update_one({"_id": row["_id"]}, {"$set": {"source.source_id": "wrong"}})
    elif mutation == "deleted_row":
        service.db.source_records.delete_one({"_id": row["_id"]})
    else:
        del row["_id"]
        row["key"] = "unexpected"
        row["source"]["source_id"] = "unexpected"
        service.db.source_records.insert_one(row)
    with pytest.raises(ValueError):
        service.repo.source(job)
    with pytest.raises(ValueError):
        service.promote(job, "engineer")
    assert service.repo.job(job)["status"] == "verified"


@pytest.mark.parametrize("mutation", ["content", "identity", "deleted_row", "extra_row"])
def test_approved_reader_checks_publication_manifest(service, generated, mutation):
    job = service.migrate(generated[0])["_id"]
    service.promote(job, "engineer")
    row = service.db.ecu_hardware.find_one({"job_id": job})
    if mutation == "content":
        service.db.ecu_hardware.update_one({"_id": row["_id"]}, {"$set": {"record.hardware_revision": "Z"}})
    elif mutation == "identity":
        service.db.ecu_hardware.update_one({"_id": row["_id"]}, {"$set": {"id": "wrong-wrapper"}})
    elif mutation == "deleted_row":
        service.db.ecu_hardware.delete_one({"_id": row["_id"]})
    else:
        del row["_id"]
        row["id"] = row["record"]["id"] = "unexpected"
        service.db.ecu_hardware.insert_one(row)
    with pytest.raises(ValueError):
        service.repo.approved_records(job)
    with pytest.raises(ValueError):
        service.promote(job, "engineer")


@pytest.mark.parametrize("status", ["approved", "promoting", "repairing", "verifying", "mapping_review"])
def test_persisted_verification_cannot_unlock_other_operations(service, generated, status):
    job = service.migrate(generated[0])["_id"]
    service.db.migration_jobs.update_one({"_id": job}, {"$set": {"status": status}})
    with pytest.raises(ValueError):
        service.validate(job)
    assert service.repo.job(job)["status"] == status


def test_interrupted_verification_recovery(service, generated):
    job = service.migrate(generated[0])["_id"]
    service.db.migration_jobs.update_one(
        {"_id": job}, {"$set": {"status": "verifying", "verification_token": "interrupted-worker"}}
    )
    service.recover(job, "operator-confirmed-worker-stopped")
    assert "verification_token" not in service.repo.job(job)
    assert service.migrate(generated[0])["status"] == "verified"


def test_candidate_cannot_replace_staging_verification(service, generated):
    job = service.migrate(generated[0])["_id"]
    with pytest.raises(ValueError, match="Candidate records"):
        service.validate(job, generated[1].documents())
    assert service.repo.job(job)["status"] == "verified"


def test_approved_reader_also_requires_intact_source_provenance(service, generated):
    job = service.migrate(generated[0])["_id"]
    service.promote(job, "engineer")
    service.db.source_records.delete_one({"job_id": job})
    with pytest.raises(ValueError, match="incomplete"):
        service.repo.approved_records(job)


def test_incomplete_materialized_copy_never_commits(service, generated, monkeypatch):
    job = service.migrate(generated[0])["_id"]
    monkeypatch.setattr(service.repo, "publication_records", lambda job_id: [])
    with pytest.raises(ValueError, match="Published copy"):
        service.promote(job, "engineer")
    assert service.repo.job(job)["status"] == "verified"
    with pytest.raises(ValueError):
        service.repo.approved_records(job)


def test_lost_promotion_lock_cannot_commit_or_overwrite_new_status(service, generated, monkeypatch):
    job = service.migrate(generated[0])["_id"]
    collection = service.db.migration_jobs
    original = collection.update_one

    def intercept(query, update, **kwargs):
        if update.get("$set", {}).get("status") == "approved":
            original({"_id": job}, {"$set": {"status": "failed"}, "$inc": {"revision": 1}})
        return original(query, update, **kwargs)

    monkeypatch.setattr(collection, "update_one", intercept)
    with pytest.raises(ValueError, match="lock was lost"):
        service.promote(job, "engineer")
    assert service.repo.job(job)["status"] == "failed"
    with pytest.raises(ValueError):
        service.repo.approved_records(job)


@pytest.fixture
def api_client(service, credentials):
    app.dependency_overrides[get_service] = lambda: service
    try:
        with TestClient(app, headers=credentials) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("approval", ["yes", "false", 1, None])
def test_api_requires_explicit_boolean_approval(api_client, generated, approval):
    job = api_client.post("/jobs", json={"dataset": generated[0]}).json()["_id"]
    response = api_client.post(f"/jobs/{job}/promote", json={"actor": "engineer", "approve": approval})
    assert response.status_code == 422


def test_api_rejects_blank_actors_and_extra_request_fields(api_client, generated):
    job = api_client.post("/jobs", json={"dataset": generated[0]}).json()["_id"]
    assert api_client.post(f"/jobs/{job}/promote", json={"actor": "  ", "approve": True}).status_code == 422
    assert api_client.post("/datasets/generate", json={"fleets": 1, "unexpected": True}).status_code == 422


@pytest.mark.parametrize("mutation", ["synthetic_string", "source_schema", "missing_source_id", "entity"])
def test_api_validates_nested_uploads(api_client, generated, mutation):
    data = copy.deepcopy(generated[0])
    if mutation == "synthetic_string":
        data["synthetic"] = "true"
    elif mutation == "source_schema":
        data["source_schema"] = "unknown"
    elif mutation == "missing_source_id":
        del data["records"][0]["source_id"]
    else:
        data["records"][0]["entity"] = "unknown"
    assert api_client.post("/jobs", json={"dataset": data}).status_code == 422


def test_api_approved_reader_gate_and_unknown_simulations(api_client, service, generated):
    job = api_client.post("/jobs", json={"dataset": generated[0]}).json()["_id"]
    assert api_client.get(f"/jobs/{job}/approved").status_code == 409
    assert api_client.get("/jobs/unknown/approved").status_code == 404
    assert api_client.post("/jobs/unknown/simulations", json={"variant_id": "unknown"}).status_code == 404
    assert api_client.post(f"/jobs/{job}/simulations", json={"variant_id": "unknown"}).status_code == 404
    assert (
        api_client.post(f"/jobs/{job}/promote", json={"actor": "engineer", "approve": True}).status_code
        == 200
    )
    response = api_client.get(f"/jobs/{job}/approved")
    assert response.status_code == 200 and len(response.json()) == 13
    service.db.ecu_hardware.delete_one({"job_id": job})
    assert api_client.get(f"/jobs/{job}/approved").status_code == 409


def test_api_database_failure_is_503():
    def unavailable():
        raise ServerSelectionTimeoutError("private database connection information")

    app.dependency_overrides[get_service] = unavailable
    try:
        with TestClient(app) as client:
            response = client.get("/ready")
            assert response.status_code == 503
            assert "private" not in response.text
    finally:
        app.dependency_overrides.clear()
