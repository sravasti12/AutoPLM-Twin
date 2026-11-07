import copy

import pytest
from packaging.version import Version
from pydantic import ValidationError

from app.agents import mapping_graph
from app.data import generate
from app.mapping import MappingPlan, baseline, profile, transform, validate_plan
from app.models import Dataset


def test_seed_and_scale():
    assert generate(2, 123) == generate(2, 123)
    assert generate(2, 123) != generate(2, 124)
    assert len(generate(2)[1].records) == 2 * len(generate(1)[1].records)
    with pytest.raises(ValueError):
        generate(0)


def test_models_and_versions(generated):
    records = generated[1].documents()
    assert Version("2.10.0") > Version("2.9.0")
    sw = next(r for r in records if r["kind"] == "software")
    sw["version"] = "bad version"
    with pytest.raises(ValidationError):
        Dataset(records=records)


@pytest.mark.parametrize("source", ["A", "B"])
def test_mapping_roundtrip(source):
    envelope, target, truth = generate(2, source=source)
    output = []
    for row in envelope["records"]:
        fields = profile([row["data"]])
        assert "ground_truth" not in fields
        plan = baseline(row["entity"], fields)
        assert not validate_plan(plan, [row["data"]])
        output.append(transform(row["data"], plan))
        assert all(truth[row["entity"]][f.source]["target"] == f.target for f in plan.fields)
    assert output == target.documents()


def test_ambiguity_and_unknown_fields(generated):
    row = next(r for r in generated[0]["records"] if r["entity"] == "hardware")
    plan = baseline("hardware", profile([row["data"]]))
    plan.fields.append(copy.deepcopy(plan.fields[0]))
    assert any("Ambiguous" in error for error in validate_plan(plan, [row["data"]]))
    plan.fields[0].target = "invented"
    assert any("Unknown target" in error for error in validate_plan(plan, [row["data"]]))


def test_allowlist_blocks_code():
    with pytest.raises(ValidationError):
        MappingPlan(
            entity="hardware", fields=[{"source": "a", "target": "id", "evidence": "x", "transform": "eval"}]
        )


def test_agent_retries_and_review(generated):
    class Broken:
        def propose(self, *args):
            raise RuntimeError("synthetic provider failure")

    row = generated[0]["records"][0]
    result = mapping_graph(Broken(), 2).invoke({"entity": row["entity"], "records": [row["data"]]})
    assert result["status"] == "review"
    assert result["attempts"] == len(result["history"]) == 2


def test_successful_agent(generated):
    row = generated[0]["records"][0]
    result = mapping_graph().invoke({"entity": row["entity"], "records": [row["data"]]})
    assert result["status"] == "validated"
    assert result["attempts"] == 1


def test_assumptions_require_review(generated):
    row = generated[0]["records"][0]
    plan = baseline(row["entity"], profile([row["data"]]))
    plan.assumptions = ["guess unit"]
    assert validate_plan(plan, [row["data"]])
