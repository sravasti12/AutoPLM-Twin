from unittest.mock import patch

import pytest
from openai import BadRequestError

from app.investigation import (
    Decision,
    EngineeringTools,
    InvestigationRequest,
    LLMInvestigator,
    OfflineInvestigator,
    ToolCall,
    investigate,
    redundant_call,
)
from app.investigation_evaluation import evaluate_investigations, score_investigation
from tests.unit.test_investigation_llm import configuration as llm_configuration

configuration = llm_configuration


class MissingPlanner:
    def __init__(self):
        self.contexts = []

    def extract(self, request, catalog):
        return InvestigationRequest(components=["MISSING"])

    def decide(self, context):
        self.contexts.append(context)
        return Decision(
            calls=[
                ToolCall(tool="component", entity_id="MISSING", max_depth=1),
                ToolCall(tool="relationships", entity_id="MISSING"),
                ToolCall(tool="impact", entity_id="MISSING"),
            ],
            rationale="Resolve missing entity",
        )


def test_definitive_missing_blocks_other_tools_and_preserves_evidence(generated):
    provider = MissingPlanner()
    report = investigate("Inspect MISSING", generated[1].documents(), provider=provider)
    assert len(report.evidence) == 1
    assert report.evidence[0].evidence_id == "E001"
    assert report.evidence[0].result["code"] == "identifier_not_found"
    assert report.evidence[0].result["retryable"] is False
    assert provider.contexts[-1]["unavailable_entities"] == ["MISSING"]
    assert provider.contexts[-1]["attempted_calls"][0]["evidence_id"] == "E001"
    assert len(provider.contexts) == 2 and report.status == "partial"


def test_irrelevant_bounds_cannot_repeat_lookup(generated):
    class Varying(OfflineInvestigator):
        def decide(self, context):
            return Decision(
                calls=[
                    ToolCall(
                        tool="component", entity_id="F0000-brake", max_depth=1 + len(context["evidence"])
                    )
                ],
                rationale="Lookup",
            )

    report = investigate("Inspect F0000-brake", generated[1].documents(), provider=Varying())
    assert len(report.evidence) == 1


def test_semantic_aliases_and_twin_fingerprint_batch(generated):
    class Batch(OfflineInvestigator):
        def decide(self, context):
            return Decision(
                calls=[
                    ToolCall(tool="impact", entity_id="F0000-brake"),
                    ToolCall(tool="provenance", entity_id="F0000-brake"),
                    ToolCall(tool="twin", entity_id="F0000-standard"),
                    ToolCall(tool="fingerprint", entity_id="F0000-standard"),
                ],
                rationale="Related requests",
            )

    report = investigate(
        "Impact twin fingerprint F0000-brake F0000-standard", generated[1].documents(), provider=Batch()
    )
    assert [c.tool for c in report.tools_invoked] == ["impact", "twin"]
    assert report.dependency_paths and report.baseline_fingerprints
    lookup = investigate("Inspect F0000-brake", generated[1].documents())
    assert not redundant_call(
        ToolCall(tool="variant", entity_id="F0000-brake"),
        lookup.evidence,
        {r["id"]: r["kind"] for r in generated[1].documents()},
    )


def test_empty_decision_is_one_plan_then_stop(generated):
    class Stop(OfflineInvestigator):
        def __init__(self):
            self.count = 0

        def decide(self, context):
            self.count += 1
            return Decision(calls=[], rationale="No safe action")

    provider = Stop()
    report = investigate("Inspect unavailable", generated[1].documents(), provider=provider)
    assert provider.count == 1 and not report.evidence
    assert report.status == "partial"


def test_successful_evidence_then_stop_is_not_a_limit(generated):
    class Once(OfflineInvestigator):
        def decide(self, context):
            return Decision(
                calls=[] if context["evidence"] else [ToolCall(tool="verify")],
                rationale="Evidence sufficient" if context["evidence"] else "Check rules",
            )

    report = investigate("verify", generated[1].documents(), provider=Once())
    assert report.status == "complete" and len(report.plan) == 2


def test_transient_tool_error_does_not_mark_entity_missing(generated):
    original = EngineeringTools.invoke

    def flaky(self, call):
        if call.tool == "component":
            raise TimeoutError("private headers")
        return original(self, call)

    class Followup(OfflineInvestigator):
        def decide(self, context):
            return Decision(
                calls=[
                    ToolCall(tool="component", entity_id="F0000-brake"),
                    ToolCall(tool="relationships", entity_id="F0000-brake"),
                ],
                rationale="Follow up",
            )

    with patch.object(EngineeringTools, "invoke", flaky):
        report = investigate("Inspect F0000-brake", generated[1].documents(), provider=Followup())
    assert len(report.evidence) == 2 and report.evidence[1].status == "ok"
    assert report.evidence[0].result["retryable"] is True
    assert "private headers" not in report.model_dump_json()


@pytest.mark.parametrize(
    "query,required",
    [
        ("verify configuration", "verify"),
        ("fingerprint F0000-standard", "fingerprint"),
        ("impact F0000-brake", "impact"),
    ],
)
def test_intent_tools_selected(generated, query, required):
    report = investigate(query, generated[1].documents())
    assert required in [e.call.tool for e in report.evidence if e.status == "ok"]


def test_compatible_structured_method_and_raw_parse_failure(configuration, monkeypatch):
    monkeypatch.setenv("AUTOPLM_LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("AUTOPLM_LLM_BASE_URL", "https://api.groq.com/openai/v1")
    with patch("langchain_openai.ChatOpenAI") as factory:
        factory.return_value.with_structured_output.return_value.invoke.return_value = {
            "raw": "private provider body",
            "parsed": None,
            "parsing_error": ValueError("secret"),
        }
        provider = LLMInvestigator()
        report = investigate("inspect", [], provider=provider)
        assert factory.return_value.with_structured_output.call_args.kwargs["method"] == "function_calling"
    assert "StructuredResponseError" in report.model_dump_json()
    assert (
        "private provider body" not in report.model_dump_json() and "secret" not in report.model_dump_json()
    )


def test_synthesis_gets_actual_citation_candidates(generated):
    class Citing(OfflineInvestigator):
        def summarize(self, context):
            assert context["citation_candidates"][0]["pointer"] == "/record"
            return {"citations": [context["citation_candidates"][0]]}

    report = investigate("Inspect F0000-brake", generated[1].documents(), provider=Citing())
    assert report.reasoning_status == "validated"


def test_safe_provider_diagnostics(generated):
    import httpx

    class Invalid(OfflineInvestigator):
        def decide(self, context):
            raise BadRequestError(
                "secret-provider-message",
                response=httpx.Response(400, request=httpx.Request("POST", "https://mock.invalid")),
                body={"code": "tool_use_failed", "failed_generation": "private body"},
            )

    report = investigate("inspect", generated[1].documents(), provider=Invalid())
    serialized = report.model_dump_json()
    assert "http_status=400" in serialized and "tool_use_failed" in serialized
    assert "secret-provider-message" not in serialized and "private body" not in serialized


def test_metrics_no_vacuous_grounding_or_required_tools():
    result = evaluate_investigations()
    missing = next(c for c in result["cases"] if c["case"] == "missing_target")
    assert missing["required_tools_obtained"] is None and missing["abstention_correct"] is True
    assert all(c["grounded"] is None for c in result["cases"])
    assert result["reasoning_cases_evaluated"] == 0


def test_metrics_reject_empty_verification_and_fake_trace(generated):
    records = generated[1].documents()
    report = investigate("Inspect unidentified", records)
    score = score_investigation("verification", report, records, {"verify"}, {"verify"})
    assert not score["passed"] and not score["request_understood"]
    report = investigate("verify", records)
    report.validation_findings = [{"evidence_id": "E001", "rule_id": "fabricated"}]
    assert score_investigation("verification", report, records, {"verify"}, {"verify"})["traceable"] is False


def test_metrics_use_successful_tools_and_count_real_redundancy(generated):
    records = generated[1].documents()
    report = investigate("impact F0000-brake", records)
    score = score_investigation(
        "impact_followup", report, records, {"impact"}, {"component", "impact", "relationships"}
    )
    assert score["passed"] and score["redundant_tool_calls"] == 0
    report.evidence.append(report.evidence[0].model_copy(deep=True))
    score = score_investigation(
        "impact_followup", report, records, {"impact"}, {"component", "impact", "relationships"}
    )
    assert score["redundant_tool_calls"] == 1 and not score["passed"]
    report = investigate("verify", records)
    report.evidence[0].status = "error"
    assert not score_investigation("verification", report, records, {"verify"}, {"verify"})[
        "required_tools_obtained"
    ]


def test_required_tool_for_wrong_target_is_not_success(generated):
    records = generated[1].documents()
    report = investigate("impact F0000-gateway", records)
    report.extracted.components = ["F0000-brake"]
    result = score_investigation(
        "impact_followup", report, records, {"impact"}, {"component", "impact", "relationships"}
    )
    assert not result["required_tools_obtained"] and not result["passed"]


def test_missing_planning_calls_is_invalid_even_with_pydantic_defaults(configuration):
    with patch("langchain_openai.ChatOpenAI") as factory:
        factory.return_value.with_structured_output.return_value.invoke.return_value = {
            "raw": None,
            "parsed": Decision(rationale="Incomplete response"),
            "parsing_error": None,
        }
        provider = LLMInvestigator()
        with pytest.raises(ValueError):
            provider.decide({})


def test_uninvestigated_targets_remain_missing(generated):
    class Partial(OfflineInvestigator):
        def extract(self, request, catalog):
            return InvestigationRequest(components=["F0000-brake", "F0000-gateway"])

        def decide(self, context):
            assert "unresolved_targets" in context
            return Decision(
                calls=[] if context["evidence"] else [ToolCall(tool="component", entity_id="F0000-brake")],
                rationale="Stop",
            )

    report = investigate("Inspect F0000-brake F0000-gateway", generated[1].documents(), provider=Partial())
    assert report.status == "partial"
    assert any("F0000-gateway" in item for item in report.missing_evidence)


def test_impact_metric_requires_actual_expected_exposure(generated):
    records = generated[1].documents()
    report = investigate("impact F0000-brake", records)
    for evidence in report.evidence:
        evidence.result.pop("potentially_affected", None)
    result = score_investigation(
        "impact_followup", report, records, {"impact"}, {"component", "impact", "relationships"}
    )
    assert result["expected_impact_obtained"] is False and result["passed"] is False
