import copy

import pytest
from pydantic import ValidationError

from app.data import generate
from app.mapping import TRANSFORMS
from app.models import BomEdge, Hardware
from app.source_adapters import normalize_source


@pytest.mark.parametrize("schema", ["A", "B"])
def test_adapter_contract_and_source_preservation(schema):
    envelope, target, _ = generate(3, source=schema)
    before = copy.deepcopy(envelope)
    assert normalize_source(envelope["records"], schema) == target.documents()
    assert envelope == before


@pytest.mark.parametrize(
    "schema,id_field,revision_field",
    [
        ("A", "ECU_ID", "HW_REV"),
        ("B", "ControllerCode", "HardwareLevel"),
    ],
)
def test_handwritten_contract(schema, id_field, revision_field):
    # This fixture is deliberately independent of generate()/ALIASES.
    row = {
        "source_id": "fixture-1",
        "entity": "hardware",
        "data": {
            id_field: "ecu-fixture",
            revision_field: "C",
            "part_number": "SYN-42",
            "supplier": "Fictional Supplier",
            "function": "brake",
            "interfaces": ["CAN"],
            "compatible_software": ["sw-fixture"],
            "platforms": ["p-fixture"],
            "Mass_g": 1250,
        },
    }
    record = normalize_source([row], schema)[0]
    assert record["id"] == "ecu-fixture"
    assert record["hardware_revision"] == "C"
    assert record["mass_kg"] == 1.25
    assert record["lifecycle"] == "released"
    assert record["schema_version"] == "1.0"


@pytest.mark.parametrize("schema", ["A", "B"])
def test_broken_migration_conversion_cannot_certify_itself(service, monkeypatch, schema):
    envelope, target, _ = generate(1, source=schema)
    monkeypatch.setitem(TRANSFORMS, "grams_to_kg", lambda value: float(value))
    result = service.migrate(envelope)
    assert result["status"] == "rejected"
    findings = result["validation"]["findings"]
    assert any(
        f["rule_id"] == "RECONCILIATION_VALUE" and f["evidence"].get("field") == "mass_kg" for f in findings
    )
    assert normalize_source(envelope["records"], schema) == target.documents()
    with pytest.raises(ValueError):
        service.promote(result["_id"], "engineer")


def test_collision_and_entity_mismatch_rejected(generated):
    row = copy.deepcopy(next(r for r in generated[0]["records"] if r["entity"] == "hardware"))
    row["data"]["id"] = "ambiguous"
    with pytest.raises(ValueError, match="Ambiguous"):
        normalize_source([row], "A")
    del row["data"]["id"]
    row["data"]["kind"] = "software"
    with pytest.raises(ValueError, match="disagree"):
        normalize_source([row], "A")


@pytest.mark.parametrize("value", [float("inf"), float("nan"), -float("inf")])
def test_nonfinite_engineering_values_rejected(generated, value):
    hardware = next(r for r in generated[1].documents() if r["kind"] == "hardware")
    hardware["mass_kg"] = value
    with pytest.raises(ValidationError):
        Hardware.model_validate(hardware)
    with pytest.raises(ValidationError):
        BomEdge(parent="assembly", child="part", quantity=value, revision="B")
    row = copy.deepcopy(next(r for r in generated[0]["records"] if r["entity"] == "hardware"))
    row["data"]["Mass_g"] = value
    with pytest.raises(ValueError):
        normalize_source([row], "A")
