import copy

import pytest

from app.mapping import baseline, profile
from app.repository import digest
from app.resolution import RepairAction, RepairPlan


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
