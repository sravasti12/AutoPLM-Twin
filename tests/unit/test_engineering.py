import copy

import pytest

from app.data import FAULTS, inject
from app.twin import SCENARIOS, build_twin, compare_twins, scenario_records, simulate
from app.verification import verify


def test_clean_engineering(generated):
    assert verify(generated[1].documents()) == []


@pytest.mark.parametrize("duplicate_first", [True, False])
def test_duplicate_identity_is_reported_even_when_lookup_shadows_a_record(generated, duplicate_first):
    original = generated[1].documents()
    records = copy.deepcopy(original)
    duplicate = copy.deepcopy(next(r for r in records if r["kind"] == "hardware"))
    duplicate["lifecycle"] = "draft"
    records.insert(0 if duplicate_first else len(records), duplicate)

    findings = verify(records, original)
    identity = [finding for finding in findings if finding.rule_id == "IDENTITY_DUPLICATE"]
    assert len(identity) == 1
    assert identity[0].affected_records == [duplicate["id"]]
    assert identity[0].expected == "1" and identity[0].actual == "2"
    assert identity[0].severity == "error" and identity[0].verification_status == "failed"
    if duplicate_first:
        # The released original wins the ID lookup, masking the draft's lifecycle issue.
        # The independent duplicate finding must still survive that collapse.
        assert {finding.rule_id for finding in findings} == {"IDENTITY_DUPLICATE"}


@pytest.mark.parametrize("fault", FAULTS)
def test_detect_each_fault(generated, fault):
    original = generated[1].documents()
    target, label = inject(original, fault)
    assert verify(target, original), label
    assert original == generated[1].documents(), "Fault injection mutated source"


@pytest.mark.parametrize(
    "fault",
    [
        "unsupported_hardware_revision",
        "missing_bom_component",
        "broken_relationship",
        "invalid_vehicle_variant",
        "duplicate_record",
        "incorrect_lifecycle",
        "missing_dependency",
        "invalid_interface",
    ],
)
def test_rules_independent_of_source(generated, fault):
    target, _ = inject(generated[1].documents(), fault)
    assert verify(target)


@pytest.mark.parametrize(
    "mutation,rule",
    [
        ("cycle", "BOM_CYCLE"),
        ("duplicate", "BOM_DUPLICATE_EDGE"),
        ("quantity", "SCHEMA_INVALID"),
        ("rollup", "BOM_ROLLUP"),
        ("revision", "BOM_REVISION"),
    ],
)
def test_bom_rules(generated, mutation, rule):
    records = generated[1].documents()
    bom = next(r for r in records if r["kind"] == "bom")
    if mutation == "cycle":
        edge = bom["edges"][0]
        bom["edges"].append({**edge, "parent": edge["child"], "child": edge["parent"]})
    elif mutation == "duplicate":
        bom["edges"].append(copy.deepcopy(bom["edges"][0]))
    elif mutation == "quantity":
        bom["edges"][0]["quantity"] = -1
    elif mutation == "rollup":
        bom["expected_leaf_quantity"] = 100
    else:
        bom["edges"][1]["revision"] = "Z"
    assert rule in {f.rule_id for f in verify(records)}


def test_twin_equality_and_semantics(generated):
    records = generated[1].documents()
    variant = next(r["id"] for r in records if r["kind"] == "variant")
    before = build_twin(records, variant)
    assert not compare_twins(before, build_twin(records, variant))
    target, _ = inject(records, "incorrect_software_version")
    assert compare_twins(before, build_twin(target, variant))

def test_twin_equivalent_when_installed_ecu_order_changes(generated):
    records = generated[1].documents()
    variant_id = next(r["id"] for r in records if r["kind"] == "variant")

    original = build_twin(records, variant_id)

    reordered = copy.deepcopy(records)
    variant = next(r for r in reordered if r["id"] == variant_id)
    variant["installed_ecus"].reverse()

    equivalent = build_twin(reordered, variant_id)

    assert original["fingerprint"] == equivalent["fingerprint"]
    assert compare_twins(original, equivalent) == []


def test_twin_reports_precise_hardware_revision_difference(generated):
    records = generated[1].documents()
    variant_id = next(r["id"] for r in records if r["kind"] == "variant")

    original = build_twin(records, variant_id)

    modified_records = copy.deepcopy(records)
    brake = next(
        r
        for r in modified_records
        if r["kind"] == "hardware"
        and r["function"] == "brake"
        and r["id"] in original["variant"]["installed_ecus"]
    )

    original_revision = brake["hardware_revision"]
    brake["hardware_revision"] = "Z"

    modified = build_twin(modified_records, variant_id)
    differences = compare_twins(original, modified)

    assert {
        "path": f"/nodes/{brake['id']}/hardware/hardware_revision",
        "source": original_revision,
        "target": "Z",
    } in differences

@pytest.mark.parametrize("scenario", SCENARIOS)
def test_simulation_scenarios(generated, scenario):
    original = generated[1].documents()
    variant = next(r["id"] for r in original if r["kind"] == "variant")
    target = scenario_records(original, variant, scenario)
    twin = build_twin(target, variant)
    result = simulate(twin)
    assert result == simulate(twin)
    if scenario == "valid":
        assert result["behavior_passed"]
        assert not verify(target)
    elif scenario == "broken_bom":
        assert result["behavior_passed"], "BOM topology must not invent physical signal behavior"
        assert verify(target)
    else:
        assert not result["behavior_passed"]
        assert verify(target)


def test_runtime_sensor_fault(generated):
    records = generated[1].documents()
    variant = next(r["id"] for r in records if r["kind"] == "variant")
    result = simulate(build_twin(records, variant), fault_at=2)
    assert result["states"]["brake"] == "DEGRADED"
    assert result["states"]["speed_sensor"] == "FAILED"


def test_unknown_compatibility_fails_closed(generated):
    records = generated[1].documents()
    next(r for r in records if r["kind"] == "hardware")["compatible_software"] = []
    assert any(f.severity == "critical" for f in verify(records))
