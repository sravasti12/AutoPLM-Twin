import copy
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from pymongo.errors import ServerSelectionTimeoutError

from app.api import app, get_service
from app.investigation_service import (
    BaselineError,
    InvestigationInput,
    InvestigationResponse,
    InvestigationService,
)
from app.repository import digest, publication_digest
from tests.unit.test_mechanical import mechanical_records as mixed_records

mechanical_records = mixed_records


@pytest.fixture
def approved_job(service, generated):
    job = service.migrate(generated[0])["_id"]
    service.promote(job, "test-engineer")
    return job


@pytest.fixture
def client(service):
    app.dependency_overrides[get_service] = lambda: service
    try:
        with TestClient(app) as instance:
            yield instance
    finally:
        app.dependency_overrides.clear()


def payload(**updates):
    return {"request": "Investigate impact and verify", "variant_id": "F0000-standard", **updates}


def snapshot(db):
    return {name: list(db[name].find().sort("_id", 1)) for name in db.list_collection_names()}


def test_authoritative_loading_provenance_and_fingerprint(service, generated, approved_job):
    records, context = InvestigationService(service.repo).load(approved_job, InvestigationInput(**payload()))
    assert len(records) == len(generated[1].documents())
    assert {"F0000-standard", "F0000-P", "F0000-brake", "F0000-brake-sw", "F0000-BOM"} <= set(
        context.associated_record_ids
    )
    assert len(context.fingerprint) == 64
    assert len(context.source_provenance) == len(records)
    assert all(
        p["source_sha256"] == digest(row)
        for p, row in zip(context.source_provenance, service.repo.source(approved_job), strict=True)
    )
    assert context.baseline_id == f"approved:{approved_job}"


def test_endpoint_response_integration_and_read_only(client, service, approved_job):
    before = snapshot(service.db)
    response = client.post(f"/jobs/{approved_job}/investigations", json=payload(component_id="F0000-brake"))
    assert response.status_code == 200, response.text
    result = InvestigationResponse.model_validate(response.json())
    assert result.report.request == "Investigate impact and verify"
    assert result.report.human_review_status == "required"
    assert result.report.evidence and result.report.dependency_paths
    assert result.report.baseline_digest == result.baseline.baseline_digest
    assert snapshot(service.db) == before


@pytest.mark.parametrize(
    "changes,status,code",
    [
        ({"variant_id": "absent"}, 404, "variant_not_found"),
        ({"component_id": "absent"}, 404, "component_not_found"),
        ({"expected_fingerprint": "0" * 64}, 409, "fingerprint_mismatch"),
        ({"proposal_id": "session-proposal"}, 422, "proposal_store_unavailable"),
    ],
)
def test_context_errors(client, approved_job, changes, status, code):
    response = client.post(f"/jobs/{approved_job}/investigations", json=payload(**changes))
    assert response.status_code == status
    assert response.json()["detail"]["code"] == code


@pytest.mark.parametrize(
    "changes",
    [
        {"request": " "},
        {"variant_id": ""},
        {"max_steps": True},
        {"max_steps": 31},
        {"mode": "invalid"},
        {"extra": "unexpected"},
        {"expected_fingerprint": "invalid"},
    ],
)
def test_request_validation(client, approved_job, changes):
    response = client.post(f"/jobs/{approved_job}/investigations", json=payload(**changes))
    assert response.status_code == 422


def test_unknown_job_and_nonapproved(client, service, generated):
    assert client.post("/jobs/missing/investigations", json=payload()).status_code == 404
    staged = service.migrate(generated[0])["_id"]
    response = client.post(f"/jobs/{staged}/investigations", json=payload())
    assert response.status_code == 409
    assert service.repo.job(staged)["status"] == "verified"


@pytest.mark.parametrize("target", ["publication", "source", "missing_publication"])
def test_tampered_baseline_rejected(client, service, approved_job, target):
    if target == "publication":
        service.db.ecu_hardware.update_one(
            {"job_id": approved_job}, {"$set": {"record.hardware_revision": "Z"}}
        )
    elif target == "source":
        service.db.source_records.delete_one({"job_id": approved_job})
    else:
        service.db.vehicle_variants.delete_many({"job_id": approved_job})
    response = client.post(f"/jobs/{approved_job}/investigations", json=payload())
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "baseline_integrity"


def test_recomputed_manifest_cannot_hide_changed_source_expectation(client, service, approved_job):
    service.db.ecu_hardware.update_one({"job_id": approved_job}, {"$set": {"record.hardware_revision": "Z"}})
    records = service.repo.publication_records(approved_job)
    service.db.migration_jobs.update_one(
        {"_id": approved_job}, {"$set": {"approved_digest": publication_digest(records)}}
    )
    response = client.post(f"/jobs/{approved_job}/investigations", json=payload())
    assert response.status_code == 409


def test_mechanical_context_and_outside_variant(client, service, mechanical_records):
    envelope = {
        "synthetic": True,
        "source_schema": "A",
        "records": [
            {"source_id": f"mixed:{i:04}", "entity": r["kind"], "data": copy.deepcopy(r)}
            for i, r in enumerate(mechanical_records)
        ],
    }
    job = service.migrate(envelope)["_id"]
    service.promote(job, "test-engineer")
    response = client.post(f"/jobs/{job}/investigations", json=payload(component_id="M-MOUNT"))
    assert response.status_code == 200, response.text
    assert {"M-MOUNT", "M-CHASSIS", "M-FRONT", "M-BOM"} <= set(
        response.json()["baseline"]["associated_record_ids"]
    )
    outside = client.post(
        f"/jobs/{job}/investigations", json=payload(variant_id="F0000-touring", component_id="M-MOUNT")
    )
    assert outside.status_code == 409


def test_database_and_execution_errors_are_redacted(client, service, approved_job):
    with patch.object(
        service.repo, "approved_records", side_effect=ServerSelectionTimeoutError("private URI")
    ):
        response = client.post(f"/jobs/{approved_job}/investigations", json=payload())
    assert response.status_code == 503 and "private URI" not in response.text
    with patch("app.investigation_service.investigate", side_effect=RuntimeError("private credential")):
        response = client.post(f"/jobs/{approved_job}/investigations", json=payload())
    assert response.status_code == 500 and "private credential" not in response.text


def test_missing_llm_config_is_partial_without_writes(client, service, approved_job, monkeypatch):
    monkeypatch.delenv("AUTOPLM_LLM_MODEL", raising=False)
    before = snapshot(service.db)
    response = client.post(f"/jobs/{approved_job}/investigations", json=payload(mode="llm"))
    assert response.status_code == 200
    assert response.json()["report"]["status"] == "partial"
    assert snapshot(service.db) == before


def test_changed_baseline_during_execution(client, service, approved_job):
    from app.investigation import investigate

    def mutate(*args, **kwargs):
        report = investigate(*args, **kwargs)
        service.db.ecu_hardware.delete_one({"job_id": approved_job})
        return report

    with patch("app.investigation_service.investigate", side_effect=mutate):
        response = client.post(f"/jobs/{approved_job}/investigations", json=payload())
    assert response.status_code == 409


def test_inconsistent_reference_snapshot_fails_closed(service, generated, approved_job):
    records = generated[1].documents()
    next(r for r in records if r["id"] == "F0000-standard")["platform_id"] = "missing"
    with (
        patch.object(service.repo, "approved_records", return_value=records),
        patch("app.investigation_service.normalize_source", return_value=records),
    ):
        with pytest.raises(BaselineError) as error:
            InvestigationService(service.repo).load(approved_job, InvestigationInput(**payload()))
    assert error.value.code == "inconsistent_references"
