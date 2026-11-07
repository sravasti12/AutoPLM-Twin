import copy

import pytest

from app.data import FAULTS, inject
from app.twin import SCENARIOS, build_twin, compare_twins, scenario_records, simulate
from app.verification import verify


def test_clean_engineering(generated):
    assert verify(generated[1].documents()) == []


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
