import pytest

from app.agents import mapping_graph
from app.data import corrupt_legacy, generate
from app.mapping import FieldMapping, MappingPlan, transform
from app.resolution import RepairAction, RepairPlan, propose
from app.verification import verify


def test_multiple_releases_and_revisions():
    records = generate(4)[1].documents()
    assert {r["hardware_revision"] for r in records if r["kind"] == "hardware"} == {"B", "C"}
    assert {r["version"] for r in records if r["kind"] == "software"} == {"2.10.0", "3.0.0"}
    assert not verify(records)


def test_corrupted_input_labels_are_isolated(generated, service):
    envelope, label = corrupt_legacy(generated[0], "unsupported_hardware_revision")
    assert label["fault"] == "unsupported_hardware_revision"
    assert "fault" not in str(envelope)
    job = service.migrate(envelope)
    assert job["status"] == "rejected"
    assert generated[0] != envelope


def test_enum_units_and_unknown_transform():
    plan = MappingPlan(
        entity="hardware",
        fields=[
            FieldMapping(source="a", target="mass_kg", transform="grams_to_kg", evidence="grams header"),
            FieldMapping(
                source="b",
                target="lifecycle",
                transform="enum",
                enum_values={"REL": "released"},
                evidence="dictionary",
            ),
        ],
    )
    assert transform({"a": 1250, "b": "REL"}, plan) == {"mass_kg": 1.25, "lifecycle": "released"}
    with pytest.raises(KeyError):
        transform({"a": 1250, "b": "UNKNOWN"}, plan)


@pytest.mark.parametrize(
    "mutation,rule",
    [
        ("feature", "FEATURE_DEPENDENCY"),
        ("release", "SW_RELEASE"),
        ("change", "CHANGE_APPROVAL"),
        ("effectivity", "SW_EFFECTIVITY"),
        ("platform", "ECU_PLATFORM"),
        ("network", "NETWORK_DISCONNECTED"),
        ("progression", "CHANGE_PROGRESSION"),
        ("dependency", "SW_INSTALLED_DEPENDENCY"),
    ],
)
def test_extended_constraints(generated, mutation, rule):
    records = generated[1].documents()
    variant = next(r for r in records if r["kind"] == "variant")
    sw = next(r for r in records if r["kind"] == "software")
    hw = next(r for r in records if r["kind"] == "hardware")
    change = next(r for r in records if r["kind"] == "change")
    platform = next(r for r in records if r["kind"] == "platform")
    if mutation == "feature":
        variant["feature_dependencies"]["speed_display"] = ["absent"]
    elif mutation == "release":
        sw["release_status"] = "draft"
    elif mutation == "change":
        change["approval_status"] = "pending"
    elif mutation == "effectivity":
        sw["release_date"] = "2030-01-01"
    elif mutation == "platform":
        hw["platforms"] = []
    elif mutation == "network":
        platform["network_topology"] = [platform["network_topology"][0], platform["network_topology"][2]]
    elif mutation == "progression":
        change["old_revision"] = "Z"
    else:
        sw["dependencies"] = ["missing-dependency"]
    assert rule in {f.rule_id for f in verify(records)}


def test_repair_agent_cannot_change_identity(generated):
    records = generated[1].documents()

    class BadPlanner:
        def propose(self, *args):
            return RepairPlan(
                actions=[RepairAction(record_id=records[0]["id"], field="id", evidence="guess")],
                requires_engineering_decision=False,
                rationale="bad action",
            )

    with pytest.raises(ValueError):
        propose(records, records, {}, BadPlanner())


def test_bounded_retry_configuration():
    with pytest.raises(ValueError):
        mapping_graph(max_attempts=100)


def test_unapproved_candidate_fails_gate(service, generated):
    job = service.migrate(generated[0])["_id"]
    row = service.db.staging_records.find_one({"job_id": job, "record.kind": "hardware"})
    service.db.staging_records.update_one({"_id": row["_id"]}, {"$set": {"record.hardware_revision": "Z"}})
    service.validate(job)
    with pytest.raises(ValueError):
        service.promote(job, "engineer")


def test_partial_promotion_hidden_and_recoverable(service, generated, monkeypatch):
    job = service.migrate(generated[0])["_id"]
    collection = service.db.ecu_hardware
    original = collection.update_one

    def failure(*args, **kwargs):
        raise RuntimeError("synthetic interrupted copy")

    with monkeypatch.context() as patch:
        patch.setattr(collection, "update_one", failure)
        with pytest.raises(RuntimeError):
            service.promote(job, "engineer")
        with pytest.raises(ValueError):
            service.repo.approved_records(job)
    assert collection.update_one == original
    assert service.promote(job, "engineer")["status"] == "approved"
