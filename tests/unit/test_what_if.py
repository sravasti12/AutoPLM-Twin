import copy

import pytest
from pydantic import ValidationError

from app.what_if import EngineeringProposal, assess, baseline_digest, discard
from tests.unit.test_mechanical import mechanical_records as mixed_records

mechanical_records = mixed_records


def proposal(records, changes, **kwargs):
    return EngineeringProposal(
        proposal_id="synthetic-proposal", baseline_reference="synthetic-product",
        baseline_digest=baseline_digest(records), creator="test-engineer",
        created_at="2026-11-12T10:00:00+05:30", changes=changes, **kwargs,
    )


def replace(record):
    return {"operation": "replace", "record_id": record["id"], "record": record}


def test_mechanical_revision_with_bom_and_explainable_impact(mechanical_records):
    baseline = copy.deepcopy(mechanical_records)
    part = copy.deepcopy(next(r for r in baseline if r["id"] == "M-MOUNT"))
    bom = copy.deepcopy(next(r for r in baseline if r["id"] == "M-BOM"))
    part["revision"] = "R2"
    bom["edges"][1]["revision"] = "R2"
    p = proposal(baseline, [replace(part), replace(bom)])
    result = assess(p, baseline)
    assert result.status == "assessed"
    assert baseline == mechanical_records
    assert result.report["proposed_findings"] == []
    paths = result.report["impact"]["original"]["M-MOUNT"]["potentially_affected"]
    assert {"M-FRONT", "M-CHASSIS", "M-BOM", "F0000-standard"} <= {p["node"][1] for p in paths}
    assert any(e["provenance"]["source_field"] == "/edges/1" for p in paths for e in p["edges"])
    assert result.report["twins"]["F0000-standard"]["differences"]
    assert result.report["twins"]["F0000-touring"]["differences"] == []
    assert result == assess(p, list(reversed(baseline)))
    result.proposed_snapshot[0]["id"] = "mutated-output"
    assert baseline == mechanical_records


@pytest.mark.parametrize("incompatible", [False, True])
def test_electronic_version_and_rules(generated, incompatible):
    records = generated[1].documents()
    software = copy.deepcopy(next(r for r in records if r["kind"] == "software"))
    software["version"] = "9.1"
    if incompatible:
        software["supported_hardware_revisions"] = ["unsupported"]
    result = assess(proposal(records, [replace(software)]), records)
    assert bool(result.report["proposed_findings"]) == incompatible
    assert any(t["differences"] for t in result.report["twins"].values())
    assert records == generated[1].documents()


def test_stale_digest_and_discard(generated):
    records = generated[1].documents()
    p = proposal(records, [replace(records[0])])
    result = assess(p, records)
    dropped = discard(result)
    assert dropped.status == "discarded" and dropped.proposed_snapshot is None
    assert dropped.report == {} and result.status == "assessed"
    records[0]["id"] = "changed-baseline"
    stale = assess(p, records)
    assert stale.status == "stale" and stale.proposed_snapshot is None


def test_add_remove_and_dangling_diagnostics(mechanical_records):
    records = mechanical_records
    new = {"id": "new-part", "kind": "mechanical_part", "part_number": "SYN", "revision": "A"}
    result = assess(proposal(records, [
        {"operation": "add", "record_id": "new-part", "record": new},
        {"operation": "remove", "record_id": "M-MOUNT"},
    ]), records)
    assert result.report["proposed_findings"]
    assert result.report["diagnostics"]["proposed"]
    changes = {c["id"]: c for c in result.report["direct_changes"]}
    assert changes["new-part"]["before"] is None
    assert changes["M-MOUNT"]["after"] is None


@pytest.mark.parametrize("case", ["duplicate", "missing", "identity", "kind", "remove_payload"])
def test_invalid_operations(generated, case):
    records = generated[1].documents()
    change = replace(records[0])
    changes = [change]
    if case == "duplicate":
        changes.append(change)
    elif case == "missing":
        change["record_id"] = "absent"
    elif case == "identity":
        change["record"] = {**records[0], "id": "other"}
    elif case == "kind":
        change["record"] = {"kind": "assembly", "id": records[0]["id"],
                            "part_number": "SYN", "revision": "A"}
    else:
        change["operation"] = "remove"
    with pytest.raises(ValueError):
        assess(proposal(records, changes), records)


def test_schema_and_duplicate_baseline_rejected(generated):
    records = generated[1].documents()
    with pytest.raises(ValidationError):
        proposal(records, [{"operation": "add", "record_id": "bad", "record": {
            "kind": "mechanical_part", "id": "bad", "part_number": "SYN", "revision": ""
        }}])
    with pytest.raises(ValueError, match="unique"):
        baseline_digest(records + [records[0]])


def test_bounds_and_unknown_variant(generated):
    records = generated[1].documents()
    sw = next(r for r in records if r["kind"] == "software")
    result = assess(proposal(records, [replace(sw)]), records, max_entities=1)
    assert result.report["impact"]["original"][sw["id"]]["truncated"]
    with pytest.raises(ValueError, match="variant"):
        assess(proposal(records, [replace(sw)], variant_ids=("unknown",)), records)


def test_variant_software_assignment_is_isolated(generated):
    records = generated[1].documents()
    variant = copy.deepcopy(next(r for r in records if r["id"] == "F0000-standard"))
    sw = copy.deepcopy(next(r for r in records if r["id"] == "F0000-brake-sw"))
    hw = copy.deepcopy(next(r for r in records if r["id"] == "F0000-brake"))
    sw["id"] += "-candidate"
    sw["version"] = "2.11"
    hw["compatible_software"].append(sw["id"])
    variant["software_configuration"][hw["id"]] = sw["id"]
    result = assess(proposal(records, [replace(variant), replace(hw),
        {"operation": "add", "record_id": sw["id"], "record": sw}
    ]), records)
    assert result.report["proposed_findings"] == []
    paths = result.report["impact"]["proposed"][sw["id"]]["potentially_affected"]
    assert "F0000-standard" in {p["node"][1] for p in paths}
    assert "F0000-touring" not in {p["node"][1] for p in paths}
    assert records == generated[1].documents()


def test_hardware_revision_has_precise_difference(generated):
    records = generated[1].documents()
    hw = copy.deepcopy(next(r for r in records if r["id"] == "F0000-brake"))
    hw["hardware_revision"] = "C"
    result = assess(proposal(records, [replace(hw)]), records)
    diffs = result.report["twins"]["F0000-standard"]["differences"]
    assert any(d["path"] == "/nodes/F0000-brake/hardware/hardware_revision" for d in diffs)
    assert result.report["proposed_findings"]
