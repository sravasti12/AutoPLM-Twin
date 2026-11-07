import copy

import pytest

from app.mapping import baseline, profile
from app.repository import digest
from app.resolution import RepairAction, RepairPlan
from app.verification import verify


def test_idempotency_and_source_immutability(service, generated):
    envelope = generated[0]
    original = copy.deepcopy(envelope)
    first = service.migrate(envelope)
    second = service.migrate(envelope)
    assert first["_id"] == second["_id"]
    assert first["status"] == "verified"
    assert service.db.staging_records.count_documents({}) == len(envelope["records"])
    assert envelope == original
    assert service.repo.source(first["_id"]) == envelope["records"]


def test_promotion_gate_and_manifest(service, generated):
    job = service.migrate(generated[0])
    with pytest.raises(ValueError):
        service.repo.approved_records(job["_id"])
    with pytest.raises(ValueError):
        service.promote(job["_id"], "")
    approved = service.promote(job["_id"], "engineer")
    assert approved["status"] == "approved"
    assert len(service.repo.approved_records(job["_id"])) == len(generated[0]["records"])
    with pytest.raises(ValueError):
        service.propose_repair(job["_id"])


def corrupt(service, job):
    row = service.db.staging_records.find_one({"job_id": job, "record.kind": "hardware"})
    service.db.staging_records.update_one({"_id": row["_id"]}, {"$set": {"record.hardware_revision": "Z"}})
    return row


def test_tampered_staging_cannot_promote(service, generated):
    job = service.migrate(generated[0])["_id"]
    corrupt(service, job)
    with pytest.raises(ValueError):
        service.promote(job, "engineer")


def assert_fresh_validation_blocks_cached_approval(service, job_id):
    staged_digest = digest(service.repo.records(job_id))
    service.db.migration_jobs.update_one(
        {"_id": job_id},
        {
            "$set": {
                "status": "verified",
                "staging_digest": staged_digest,
                "validation": {"passed": True, "findings": [], "twin_differences": []},
            }
        },
    )
    assert service.repo.job(job_id)["staging_digest"] == digest(service.repo.records(job_id))
    with pytest.raises(ValueError, match="failed revalidation"):
        service.promote(job_id, "engineer")
    assert service.repo.job(job_id)["status"] != "approved"
    assert service.db.ecu_software.count_documents({"job_id": job_id}) == 0


def test_incompatible_software_blocks_approval_even_when_source_and_target_twins_match(service, generated):
    envelope = copy.deepcopy(generated[0])
    software = next(
        row["data"]
        for row in envelope["records"]
        if row["entity"] == "software" and "brake" in row["data"]["capabilities"]
    )
    software["supported_hardware_revisions"] = ["C"]  # Generated brake hardware is revision B.

    job = service.migrate(envelope)
    validation = job["validation"]
    assert job["status"] == "rejected" and validation["passed"] is False
    assert {finding["rule_id"] for finding in validation["findings"]} == {"HW_SW_REVISION"}
    assert validation["twin_differences"] == []
    with pytest.raises(ValueError, match="Only verified jobs"):
        service.promote(job["_id"], "engineer")
    assert_fresh_validation_blocks_cached_approval(service, job["_id"])


def test_genuine_twin_difference_independently_blocks_promotion(service, generated, monkeypatch):
    job_id = service.migrate(generated[0])["_id"]
    staged = service.repo.records(job_id)
    brake = next(
        record for record in staged if record["kind"] == "hardware" and record["function"] == "brake"
    )
    software_id = brake["compatible_software"][0]
    software = next(record for record in staged if record["id"] == software_id)
    original_version = software["version"]
    service.db.staging_records.update_one(
        {"job_id": job_id, "record.id": software_id},
        {"$set": {"record.version": "2.11.0"}},
    )
    assert verify(service.repo.records(job_id)) == [], "The modified release is intrinsically compatible"
    validation = service.validate(job_id)
    assert validation["passed"] is False
    assert {finding["rule_id"] for finding in validation["findings"]} == {
        "RECONCILIATION_VALUE",
        "SW_VERSION_PRESERVATION",
    }
    expected_difference = {
        "path": f"/nodes/{brake['id']}/software/version",
        "source": original_version,
        "target": "2.11.0",
    }
    assert validation["twin_differences"]
    assert all(difference == expected_difference for difference in validation["twin_differences"])

    # Isolate the twin gate by omitting only reference reconciliation in this test.
    # Engineering rules, twin construction/comparison, validate() and promote() remain real.
    monkeypatch.setattr("app.service.verify", lambda records, reference: verify(records))
    twin_only_validation = service.validate(job_id)
    assert twin_only_validation["findings"] == []
    assert twin_only_validation["twin_differences"] == validation["twin_differences"]
    assert twin_only_validation["passed"] is False
    assert service.repo.job(job_id)["status"] == "rejected"
    with pytest.raises(ValueError, match="Only verified jobs"):
        service.promote(job_id, "engineer")
    assert_fresh_validation_blocks_cached_approval(service, job_id)


def test_compatible_software_version_change_with_updated_source_expectation_is_approved(service, generated):
    envelope = copy.deepcopy(generated[0])
    software = next(
        row["data"]
        for row in envelope["records"]
        if row["entity"] == "software" and "brake" in row["data"]["capabilities"]
    )
    original_version = software["SW_REL"]
    software["SW_REL"] = "2.11.0"
    assert software["SW_REL"] != original_version

    # The expected source release changes before ingestion; immutable captured source is not edited.
    job = service.migrate(envelope)
    records = service.repo.records(job["_id"])
    migrated_release = next(record for record in records if record["id"] == software["ECU_ID"])
    assert migrated_release["version"] == "2.11.0"
    assert verify(records) == []
    assert job["validation"] == {"passed": True, "findings": [], "twin_differences": []}
    assert job["status"] == "verified"
    assert service.promote(job["_id"], "engineer")["status"] == "approved"
    assert migrated_release in service.repo.approved_records(job["_id"])


def test_approved_repair_and_audit(service, generated):
    job = service.migrate(generated[0])["_id"]
    original_source = service.repo.source(job)
    corrupt(service, job)
    service.validate(job)
    proposal = service.propose_repair(job)
    assert proposal["validation"]["passed"]
    assert service.repo.job(job)["status"] == "rejected"
    assert service.decide_repair(proposal["_id"], True, "engineer")["status"] == "approved"
    assert service.repo.job(job)["status"] == "verified"
    assert service.repo.source(job) == original_source
    assert service.repo.job(job)["staging_digest"] == digest(service.repo.records(job))
    actions = [a["action"] for a in service.repo.db.audit_events.find({"job_id": job})]
    assert "repair_proposed" in actions and "repair_approved" in actions
    with pytest.raises(ValueError):
        service.decide_repair(proposal["_id"], True, "engineer")


def test_stale_repair_and_rejection(service, generated):
    job = service.migrate(generated[0])["_id"]
    proposal = service.propose_repair(job)
    corrupt(service, job)
    with pytest.raises(ValueError):
        service.decide_repair(proposal["_id"], True, "engineer")
    assert service.decide_repair(proposal["_id"], False, "engineer")["status"] == "rejected"


def test_llm_repair_reference_actions(service, generated):
    job = service.migrate(generated[0])["_id"]
    row = corrupt(service, job)
    service.validate(job)

    class FakePlanner:
        def propose(self, *args):
            return RepairPlan(
                actions=[
                    RepairAction(
                        record_id=row["record"]["id"],
                        field="hardware_revision",
                        evidence="Source revision is B; target Z violates matrix",
                    )
                ],
                requires_engineering_decision=False,
                rationale="Restore source",
            )

    proposal = service.propose_repair(job, provider=FakePlanner())
    assert proposal["agent_plan"]["provider"] == "llm"
    assert proposal["validation"]["passed"]
    assert service.repo.job(job)["status"] == "rejected"


def test_mapping_review_resolution(service, generated):
    class Broken:
        def propose(self, *args):
            raise RuntimeError()

    job = service.migrate(generated[0], provider=Broken())
    assert job["status"] == "mapping_review"
    for entity in {row["entity"] for row in generated[0]["records"]}:
        rows = [row["data"] for row in generated[0]["records"] if row["entity"] == entity]
        plan = baseline(entity, profile(rows))
        service.decide_mapping(job["_id"], plan.model_dump(), "engineer", True)
    assert service.repo.job(job["_id"])["status"] == "verified"


def test_source_duplicate_rejected(service, generated):
    envelope = copy.deepcopy(generated[0])
    envelope["records"].append(copy.deepcopy(envelope["records"][0]))
    with pytest.raises(ValueError):
        service.migrate(envelope)


def test_duplicate_engineering_identity_blocks_migration_and_promotion(service, generated):
    envelope = copy.deepcopy(generated[0])
    duplicate = copy.deepcopy(next(row for row in envelope["records"] if row["entity"] == "hardware"))
    # A distinct source ID bypasses only the source-row uniqueness check. Sorting it
    # before the original makes the released original win later ID-based lookups.
    duplicate["source_id"] = "0-conflicting-engineering-record"
    duplicate["data"]["lifecycle"] = "draft"
    envelope["records"].insert(0, duplicate)

    job = service.migrate(envelope)
    assert job["status"] == "rejected" and not job["validation"]["passed"]
    assert {finding["rule_id"] for finding in job["validation"]["findings"]} == {"IDENTITY_DUPLICATE"}
    assert not job["validation"]["twin_differences"]
    assert job["records_processed"] == len(envelope["records"])
    assert len(service.repo.records(job["_id"])) == len(envelope["records"])
    assert job["rejected_records"] == 2
    with pytest.raises(ValueError, match="Only verified jobs"):
        service.promote(job["_id"], "engineer")

    # Even a stale verified flag and matching cached digest cannot bypass the
    # independent fresh-validation gate in promote().
    service.db.migration_jobs.update_one({"_id": job["_id"]}, {"$set": {"status": "verified"}})
    assert digest(service.repo.records(job["_id"])) == job["staging_digest"]
    with pytest.raises(ValueError, match="failed revalidation"):
        service.promote(job["_id"], "engineer")
    assert service.db.ecu_hardware.count_documents({"job_id": job["_id"]}) == 0


def test_simulation_and_report_persisted(service, generated):
    job = service.migrate(generated[0])["_id"]
    result = service.run_simulation(job, "F0000-standard")
    assert result["behavior_passed"]
    report = service.report(job)
    assert report["simulations"] and report["twins"] and report["mappings"]


def test_recovery_explicit(service, generated):
    job = service.migrate(generated[0])["_id"]
    with pytest.raises(ValueError):
        service.recover(job, "engineer")
    service.db.migration_jobs.update_one({"_id": job}, {"$set": {"status": "running"}})
    service.recover(job, "engineer")
    assert service.migrate(generated[0])["status"] == "verified"
