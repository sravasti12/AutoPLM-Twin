import pytest


def test_swapped_complete_records_fail_reconciliation(service, generated):
    job = service.migrate(generated[0])["_id"]
    rows = list(service.db.staging_records.find({"job_id": job, "record.kind": "hardware"}))
    left, right = rows[:2]
    # The record set and twins remain identical, but each source now points at the wrong target.
    service.db.staging_records.update_one({"_id": left["_id"]}, {"$set": {"record": right["record"]}})
    service.db.staging_records.update_one({"_id": right["_id"]}, {"$set": {"record": left["record"]}})
    result = service.validate(job)
    assert not result["passed"]
    assert not result["twin_differences"]
    assert {f["rule_id"] for f in result["findings"]} == {"RECONCILIATION_PROVENANCE"}
    with pytest.raises(ValueError):
        service.promote(job, "engineer")
    repair = service.propose_repair(job)
    assert repair["validation"]["passed"]
    service.decide_repair(repair["_id"], True, "engineer")
    assert service.repo.job(job)["status"] == "verified"


def test_wrong_source_annotation_fails_closed(service, generated):
    job = service.migrate(generated[0])["_id"]
    row = service.db.staging_records.find_one({"job_id": job})
    service.db.staging_records.update_one({"_id": row["_id"]}, {"$set": {"source_id": "unrelated-source"}})
    # Metadata alone must not bypass promotion even though the record-content digest is unchanged.
    with pytest.raises(ValueError):
        service.promote(job, "engineer")
    assert any(f["rule_id"] == "RECONCILIATION_PROVENANCE" for f in service.validate(job)["findings"])
    repair = service.propose_repair(job)
    assert repair["before_validation"]["findings"]
    service.decide_repair(repair["_id"], True, "engineer")
    assert service.repo.job(job)["status"] == "verified"
