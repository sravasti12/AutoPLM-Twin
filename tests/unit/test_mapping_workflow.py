"""Phase 3 acceptance: constrained proposals, complete validation and bounded graph state."""

import copy
import json

import pytest

from app.agents import LLMMapper, mapping_graph
from app.data import generate
from app.mapping import FieldMapping, MappingPlan, baseline, profile, transform, validate_plan


def hardware_rows(schema="A"):
    return [row["data"] for row in generate(2, source=schema)[0]["records"] if row["entity"] == "hardware"]


def test_profile_missing_types_units_relationships_and_detachment():
    rows = [
        {"Mass_g": 1250, "platform_id": "p", "interfaces": ["CAN"], "supplier": None},
        {"Mass_g": "1500", "platform_id": "q", "interfaces": ["LIN"]},
    ]
    summary = profile(rows)
    assert summary["Mass_g"]["types"] == ["int", "str"]
    assert summary["supplier"]["missing"] == 2
    assert summary["Mass_g"]["unit_hint"] == "grams"
    assert summary["platform_id"]["relationship_targets"] == ["platform"]
    assert profile([{"mass_kg": 1}])["mass_kg"]["unit_hint"] == "kilograms"
    summary["interfaces"]["examples"][0].append("MUTATED")
    assert rows[0]["interfaces"] == ["CAN"]


@pytest.mark.parametrize("schema", ["A", "B"])
@pytest.mark.parametrize("entity", ["hardware", "software", "platform", "variant", "bom", "change"])
def test_all_entity_graphs_validate_first_attempt(schema, entity):
    rows = [row["data"] for row in generate(2, source=schema)[0]["records"] if row["entity"] == entity]
    result = mapping_graph().invoke({"entity": entity, "records": rows})
    assert result["status"] == "validated" and result["attempts"] == 1
    assert result["history"][0]["errors"] == []
    assert set(result) == {"entity", "records", "profile", "plan", "errors", "attempts", "status", "history"}


@pytest.mark.parametrize("source", ["lifecycle", "unknown_annotation"])
def test_source_fields_cannot_disappear(source):
    rows = hardware_rows()
    if source == "unknown_annotation":
        for row in rows:
            row[source] = "unsupported source metadata"
    plan = baseline("hardware", profile(rows))
    plan.fields = [f for f in plan.fields if f.source != source]
    assert f"Unmapped source field: {source}" in validate_plan(plan, rows)


def test_ambiguous_source_reuse_rejected():
    rows = hardware_rows()
    plan = baseline("hardware", profile(rows))
    next(f for f in plan.fields if f.target == "supplier").source = "ECU_ID"
    assert "Ambiguous source reuse: ECU_ID" in validate_plan(plan, rows)


@pytest.mark.parametrize(
    "mutation",
    [
        "identity_mass",
        "unit_to_text",
        "unit_without_hint",
        "unused_enum",
        "empty_enum",
        "missing_evidence",
        "missing_required",
    ],
)
def test_unsupported_mapping_operations(mutation):
    rows = hardware_rows()
    plan = baseline("hardware", profile(rows))
    mass = next(f for f in plan.fields if f.target == "mass_kg")
    supplier = next(f for f in plan.fields if f.target == "supplier")
    if mutation == "identity_mass":
        mass.transform = "identity"
    elif mutation == "unit_to_text":
        supplier.transform = "grams_to_kg"
    elif mutation == "unit_without_hint":
        mass.source = "SupplierMass"
        for row in rows:
            row["SupplierMass"] = row.pop("Mass_g")
    elif mutation == "unused_enum":
        supplier.enum_values = {"a": "b"}
    elif mutation == "empty_enum":
        supplier.transform = "enum"
    elif mutation == "missing_evidence":
        supplier.evidence = "  "
    else:
        plan.fields = [f for f in plan.fields if f.target != "part_number"]
    assert validate_plan(plan, rows)


@pytest.mark.parametrize("operation", ["strip", "lower", "enum"])
def test_string_operations_do_not_coerce_numbers(operation):
    plan = MappingPlan(
        entity="hardware",
        fields=[
            FieldMapping(
                source="x",
                target="supplier",
                transform=operation,
                enum_values={"12": "value"} if operation == "enum" else {},
                evidence="fixture",
            )
        ],
    )
    with pytest.raises(ValueError, match="string source"):
        transform({"x": 12}, plan)


@pytest.mark.parametrize("value", [True, [], {}])
def test_unit_conversion_rejects_unsupported_types(value):
    plan = MappingPlan(
        entity="hardware",
        fields=[FieldMapping(source="Mass_g", target="mass_kg", transform="grams_to_kg", evidence="grams")],
    )
    with pytest.raises(ValueError):
        transform({"Mass_g": value}, plan)


def test_transform_returns_detached_relationship_values():
    rows = hardware_rows()
    plan = baseline("hardware", profile(rows))
    result = transform(rows[0], plan)
    result["interfaces"].append("MUTATED")
    assert "MUTATED" not in rows[0]["interfaces"]


def test_graph_repairs_with_error_feedback_and_retains_history():
    rows = hardware_rows()

    class Repairing:
        calls = 0

        def propose(self, entity, summary, errors):
            self.calls += 1
            plan = baseline(entity, summary)
            if self.calls == 1:
                plan.fields[0].target = "invented_target"
            else:
                assert any("Unknown target" in error for error in errors)
                errors.clear()  # Must not erase historical validation evidence.
                summary.clear()  # Must not erase the profile used by later validation.
            return plan

    result = mapping_graph(Repairing()).invoke({"entity": "hardware", "records": rows})
    assert result["status"] == "validated" and result["attempts"] == 2
    assert result["history"][0]["errors"]
    assert result["history"][1]["errors"] == []
    assert result["profile"]


def test_transient_failure_recovers_with_a_valid_dictionary_response():
    class Transient:
        calls = 0

        def propose(self, entity, summary, errors):
            self.calls += 1
            if self.calls == 1:
                raise TimeoutError("temporary failure")
            assert errors == ["Provider failure: TimeoutError"]
            return baseline(entity, summary).model_dump()

    result = mapping_graph(Transient()).invoke({"entity": "hardware", "records": hardware_rows()})
    assert result["status"] == "validated" and result["attempts"] == 2
    assert result["history"][0]["errors"] == ["Provider failure: TimeoutError"]


def test_invalid_record_outside_profile_examples_is_validated():
    rows = hardware_rows()
    assert len(rows) > 3
    rows[-1]["Mass_g"] = "invalid quantity beyond the first three examples"
    result = mapping_graph(max_attempts=1).invoke({"entity": "hardware", "records": rows})
    assert result["status"] == "review"
    assert result["errors"]


@pytest.mark.parametrize("response", [None, {}, {"entity": "hardware", "fields": []}, "generated code"])
def test_malformed_provider_output_reaches_review(response):
    class Malformed:
        def propose(self, *args):
            return response

    result = mapping_graph(Malformed(), 2).invoke({"entity": "hardware", "records": hardware_rows()})
    assert result["status"] == "review" and result["attempts"] == 2
    assert all(entry["errors"] for entry in result["history"])
    assert not result["plan"]


@pytest.mark.parametrize("attempts", [1, 3, 5])
def test_provider_failure_is_bounded_and_redacted(attempts):
    class Failing:
        def propose(self, *args):
            raise TimeoutError("private provider detail must not enter the audit state")

    result = mapping_graph(Failing(), attempts).invoke({"entity": "hardware", "records": hardware_rows()})
    assert result["status"] == "review"
    assert len(result["history"]) == result["attempts"] == attempts
    assert "private provider detail" not in json.dumps(result)


@pytest.mark.parametrize("attempts", [0, 6, 1.5, True])
def test_retry_configuration_rejected(attempts):
    with pytest.raises(ValueError):
        mapping_graph(max_attempts=attempts)


def test_confidence_does_not_override_executable_checks():
    class HighConfidenceGuess:
        def propose(self, entity, summary, errors):
            plan = baseline(entity, summary)
            plan.assumptions = ["unsupported guess"]
            for field in plan.fields:
                field.confidence = 1
            return plan

    result = mapping_graph(HighConfidenceGuess(), 1).invoke(
        {"entity": "hardware", "records": hardware_rows()}
    )
    assert result["status"] == "review"


def test_provider_cannot_mutate_input_records():
    rows = hardware_rows()
    original = copy.deepcopy(rows)

    class Mutating:
        def propose(self, entity, summary, errors):
            summary["interfaces"]["examples"][0].append("MUTATED")
            return baseline(entity, summary)

    result = mapping_graph(Mutating()).invoke({"entity": "hardware", "records": rows})
    assert result["status"] == "validated"
    assert rows == original
    assert "MUTATED" not in json.dumps(result["profile"])


def test_empty_inputs_and_entity_mismatch_fail_closed():
    with pytest.raises(ValueError):
        mapping_graph().invoke({"entity": "hardware", "records": []})
    with pytest.raises(ValueError):
        mapping_graph().invoke({"entity": "unknown", "records": [{}]})
    assert validate_plan(baseline("hardware", profile(hardware_rows())), [])

    class WrongEntity:
        def propose(self, entity, summary, errors):
            return baseline("variant", summary)

    result = mapping_graph(WrongEntity(), 1).invoke({"entity": "hardware", "records": hardware_rows()})
    assert result["status"] == "review" and "Entity mismatch" in result["errors"]


def test_llm_provider_prompt_and_configuration_without_network(monkeypatch):
    monkeypatch.delenv("AUTOPLM_LLM_MODEL", raising=False)
    with pytest.raises(ValueError, match="explicitly configured"):
        LLMMapper()
    monkeypatch.setenv("AUTOPLM_LLM_MODEL", "synthetic-test-model")
    monkeypatch.setenv("AUTOPLM_LLM_BASE_URL", "http://localhost:9999/v1")
    captured = {}

    class FakeChat:
        def __init__(self, **kwargs):
            captured["settings"] = kwargs

        def with_structured_output(self, schema):
            captured["schema"] = schema
            return self

        def invoke(self, messages):
            captured["messages"] = messages
            return baseline("hardware", profile(hardware_rows()))

    monkeypatch.setattr("langchain_openai.ChatOpenAI", FakeChat)
    provider = LLMMapper()
    summary = profile(hardware_rows())
    provider.propose("hardware", summary, ["previous failure"])
    assert captured["schema"] is MappingPlan
    assert captured["settings"]["model"] == "synthetic-test-model"
    assert captured["settings"]["base_url"] == "http://localhost:9999/v1"
    assert captured["settings"]["max_retries"] == 1
    payload = json.loads(captured["messages"][1][1])
    assert payload["profile"] == summary
    assert payload["validation_errors"] == ["previous failure"]
    assert set(payload["transformation_contract"]) == {"identity", "grams_to_kg", "strip", "lower", "enum"}
    assert set(payload) == {
        "entity",
        "profile",
        "target_schema",
        "validation_errors",
        "transformation_contract",
    }
