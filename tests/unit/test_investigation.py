import copy
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.investigation import (
    Decision,
    EngineeringTools,
    InvestigationRequest,
    InvestigationState,
    LLMInvestigator,
    OfflineInvestigator,
    ToolCall,
    investigate,
)
from tests.unit.test_mechanical import mechanical_records as mixed_records
from tests.unit.test_what_if import proposal, replace

mechanical_records = mixed_records


def test_extraction_and_lookup_only_routing(generated):
    records = generated[1].documents()
    spec = OfflineInvestigator().extract("Inspect F0000-brake", records)
    assert spec.components == ["F0000-brake"]
    report = investigate("Inspect F0000-brake", records)
    assert report.status == "complete"
    assert [c.tool for c in report.tools_invoked] == ["component"]
    assert report.evidence[0].result["record"]["id"] == "F0000-brake"
    assert report.human_review_status == "required"
    assert "extracted" in InvestigationState.__annotations__


def test_mechanical_multistep_followup_paths_and_traceability(mechanical_records):
    before = copy.deepcopy(mechanical_records)
    report = investigate("Investigate impact and provenance of M-MOUNT", mechanical_records)
    invoked = {(c.tool, c.entity_id) for c in report.tools_invoked}
    assert ("impact", "M-MOUNT") in invoked
    assert ("relationships", "M-FRONT") in invoked
    assert ("relationships", "M-BOM") in invoked
    assert report.dependency_paths
    evidence_ids = {e.evidence_id for e in report.evidence}
    assert all(p["evidence_id"] in evidence_ids for p in report.dependency_paths)
    assert any(e.classification == "potential_exposure" for e in report.evidence)
    assert any(p["node"] == ["record", "F0000-standard"] for p in report.dependency_paths)
    assert mechanical_records == before


@pytest.mark.parametrize("tool", ["variant", "relationships", "impact", "provenance", "twin", "fingerprint"])
def test_structured_tools(generated, tool):
    records = generated[1].documents()
    tools = EngineeringTools(records)
    result = tools.invoke(ToolCall(tool=tool, entity_id="F0000-standard"))
    assert result
    assert records == generated[1].documents()


def test_compare_and_fingerprint_report(generated):
    report = investigate(
        "Compare twin fingerprint F0000-standard and F0000-touring", generated[1].documents()
    )
    assert "compare" in [c.tool for c in report.tools_invoked]
    assert len(report.baseline_fingerprints) == 2
    comparison = next(e for e in report.evidence if e.call.tool == "compare")
    assert comparison.result["differences"]


def test_what_if_isolation_findings(mechanical_records):
    part = copy.deepcopy(next(r for r in mechanical_records if r["id"] == "M-MOUNT"))
    part["revision"] = "R2"
    p = proposal(mechanical_records, [replace(part)])
    before = copy.deepcopy(mechanical_records)
    report = investigate("Assess what-if proposal", mechanical_records, proposal=p)
    assert [c.tool for c in report.tools_invoked] == ["what_if"]
    assert report.evidence[0].result["status"] == "assessed"
    assert report.validation_findings and report.dependency_paths
    assert all(f["evidence_id"] == "E001" for f in report.validation_findings)
    assert mechanical_records == before


@pytest.mark.parametrize("query", ["Assess what-if proposal", "Inspect an unidentified part"])
def test_missing_evidence(generated, query):
    report = investigate(query, generated[1].documents())
    assert report.status == "partial"
    assert report.missing_evidence


def test_duplicate_baseline_fails_closed(generated):
    records = generated[1].documents()
    with pytest.raises(ValueError, match="unique"):
        investigate("inspect", records + [records[0]])


@pytest.mark.parametrize(
    "arguments",
    [
        {"tool": "promote"},
        {"tool": "component"},
        {"tool": "compare", "entity_id": "v"},
        {"tool": "verify", "entity_id": "x"},
        {"tool": "impact", "entity_id": "x", "max_entities": True},
    ],
)
def test_tool_argument_validation(arguments):
    with pytest.raises(ValidationError):
        ToolCall.model_validate(arguments)


class FakeProvider:
    def extract(self, request, catalog):
        catalog.clear()
        return InvestigationRequest(components=["F0000-brake"], needs=["verify"])

    def decide(self, context):
        if not context["evidence"]:
            return Decision(
                calls=[ToolCall(tool="component", entity_id="F0000-brake")], rationale="Read record"
            )
        context["evidence"][0]["result"]["record"]["hardware_revision"] = "MUTATED"
        return Decision(calls=[ToolCall(tool="verify")], rationale="Verify after retrieval")


def test_mock_provider_adapts_and_cannot_mutate_evidence(generated):
    records = generated[1].documents()
    report = investigate("check brake", records, provider=FakeProvider())
    assert [c.tool for c in report.tools_invoked] == ["component", "verify"]
    assert report.evidence[0].result["record"]["hardware_revision"] != "MUTATED"
    assert records == generated[1].documents()


@pytest.mark.parametrize("stage", ["extract", "decide"])
def test_provider_failures_redacted(generated, stage):
    class Failing(FakeProvider):
        pass

    def fail(*args):
        raise RuntimeError("secret-provider-credential")

    setattr(Failing, stage, fail)
    report = investigate("check brake", generated[1].documents(), provider=Failing())
    assert report.status == "partial"
    assert "secret-provider" not in report.model_dump_json()


def test_missing_llm_config(generated, monkeypatch):
    monkeypatch.delenv("AUTOPLM_LLM_MODEL", raising=False)
    report = investigate("inspect brake", generated[1].documents(), mode="llm")
    assert report.status == "partial"
    assert not report.evidence


def test_llm_configuration_and_structured_calls(monkeypatch):
    monkeypatch.setenv("AUTOPLM_LLM_MODEL", "mock-model")
    monkeypatch.setenv("OPENAI_API_KEY", "mock-key")
    monkeypatch.setenv("AUTOPLM_LLM_BASE_URL", "http://mock.invalid/v1")
    with patch("langchain_openai.ChatOpenAI") as constructor:
        provider = LLMInvestigator()
        provider.extract("inspect", [])
        provider.decide({})
        assert constructor.call_args.kwargs["model"] == "mock-model"
        assert constructor.call_args.kwargs["timeout"] == 45
        assert constructor.return_value.with_structured_output.call_count == 2


def test_tool_failure_is_evidence(generated):
    with patch("app.investigation.verify", side_effect=RuntimeError("private internal details")):
        report = investigate("verify", generated[1].documents())
    assert report.status == "partial"
    assert report.evidence[0].status == "error"
    assert "private internal" not in report.model_dump_json()


def test_execution_limit(generated):
    report = investigate("Impact and verify F0000-brake", generated[1].documents(), max_steps=1)
    assert report.status == "limit_reached"
    assert len(report.evidence) == 1


def test_deterministic_offline_report(mechanical_records):
    assert investigate("impact M-MOUNT", mechanical_records) == investigate(
        "impact M-MOUNT", mechanical_records
    )


def test_unknown_provider_identifier_cannot_become_confirmed(generated):
    class Unknown(FakeProvider):
        def extract(self, request, catalog):
            return InvestigationRequest(components=["INVENTED"])

        def decide(self, context):
            return Decision(calls=[ToolCall(tool="component", entity_id="INVENTED")], rationale="Lookup")

    report = investigate("inspect", generated[1].documents(), provider=Unknown())
    assert report.identified_components == []
    assert all(e.status == "error" for e in report.evidence)


def test_ambiguous_description_retains_candidates():
    from app.data import generate

    records = generate(2)[1].documents()
    report = investigate("Inspect brake", records)
    assert report.identified_components == ["F0000-brake", "F0001-brake"]
    assert report.status == "partial"
    assert any("Ambiguous" in item for item in report.missing_evidence)


def test_stale_what_if_is_unknown(mechanical_records):
    p = proposal(mechanical_records, [replace(mechanical_records[0])])
    changed = copy.deepcopy(mechanical_records)
    changed[0]["id"] = "changed"
    report = investigate("assess what-if", changed, proposal=p)
    assert report.evidence[0].result["status"] == "stale"
    assert report.status == "partial"


def test_bounds_and_no_authorization(generated):
    for limit in (True, 0, 31):
        with pytest.raises(ValueError):
            investigate("inspect", generated[1].documents(), max_steps=limit)
    with pytest.raises(ValidationError):
        ToolCall(tool="publish")


def test_planner_early_stop_marks_uninvestigated_needs(generated):
    class Stop(FakeProvider):
        def decide(self, context):
            return Decision(calls=[], rationale="Stop without evidence")

    report = investigate("inspect brake", generated[1].documents(), provider=Stop())
    assert report.status == "partial"
    assert any("verify" in item for item in report.missing_evidence)


def test_relationship_tool_retains_bom_edges(mechanical_records):
    result = EngineeringTools(mechanical_records).invoke(ToolCall(tool="relationships", entity_id="M-MOUNT"))
    assert any(e["provenance"]["record_id"] == "M-BOM" for e in result["relationships"])
