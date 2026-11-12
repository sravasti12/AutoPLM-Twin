import copy
import json
from unittest.mock import patch

import httpx
import pytest
from openai import RateLimitError

from app.investigation import (
    Decision,
    EvidenceCitation,
    EvidenceSummary,
    InvestigationRequest,
    LLMInvestigator,
    OfflineInvestigator,
    ToolCall,
    investigate,
)
from app.investigation_evaluation import evaluate_investigations
from app.investigation_service import InvestigationInput, InvestigationService
from tests.unit.test_investigation_api import approved_job as job_fixture

approved_job = job_fixture


@pytest.fixture
def configuration(monkeypatch):
    monkeypatch.setenv("AUTOPLM_LLM_MODEL", "mocked-model")
    monkeypatch.setenv("OPENAI_API_KEY", "mocked-secret")
    for name in (
        "AUTOPLM_LLM_PROVIDER",
        "AUTOPLM_LLM_TIMEOUT",
        "AUTOPLM_LLM_RETRIES",
        "AUTOPLM_LLM_MAX_TOKENS",
        "AUTOPLM_LLM_BASE_URL",
    ):
        monkeypatch.delenv(name, raising=False)


class StructuredSDK:
    """Exercise the actual LLM wrapper without network calls."""

    def __init__(self):
        self.seen = []

    def with_structured_output(self, schema):
        owner = self

        class Adapter:
            def invoke(self, messages):
                payload = json.loads(messages[-1][1])
                owner.seen.append((schema.__name__, copy.deepcopy(payload)))
                if schema is InvestigationRequest:
                    return {"components": ["F0000-brake"], "variants": [], "needs": ["impact", "verify"]}
                if schema is Decision:
                    done = [e["call"]["tool"] for e in payload["evidence"]]
                    if "component" not in done:
                        call = {"tool": "component", "entity_id": "F0000-brake"}
                    elif "impact" not in done:
                        call = {"tool": "impact", "entity_id": "F0000-brake"}
                    elif "relationships" not in done:
                        paths = payload["evidence"][-1]["result"]["potentially_affected"]
                        bom = next(p["node"][1] for p in paths if p["node"] == ["record", "F0000-BOM"])
                        call = {"tool": "relationships", "entity_id": bom}
                    elif "verify" not in done:
                        call = {"tool": "verify"}
                    else:
                        return {"calls": [], "rationale": "Requested evidence retrieved"}
                    return {"calls": [call], "rationale": "Use retrieved evidence to choose next tool"}
                return {
                    "citations": [
                        {
                            "evidence_id": "E001",
                            "pointer": "/record/hardware_revision",
                            "category": "record_fact",
                        },
                        {
                            "evidence_id": "E002",
                            "pointer": "/potentially_affected/0",
                            "category": "potential_exposure",
                        },
                    ]
                }

        return Adapter()


def test_llm_dynamic_routing_and_grounded_synthesis(generated, configuration):
    sdk = StructuredSDK()
    records = generated[1].documents()
    with patch("langchain_openai.ChatOpenAI", return_value=sdk):
        report = investigate("Investigate the braking-system change exposure", records, mode="llm")
    assert [c.tool for c in report.tools_invoked] == ["component", "impact", "relationships", "verify"]
    assert report.reasoning_status == "validated"
    assert report.reasoning[0].statement == 'record_fact: "B"'
    assert report.reasoning[1].category == "potential_exposure"
    assert sdk.seen[-1][0] == "EvidenceSummary"
    assert records == generated[1].documents()
    assert "mocked-secret" not in report.model_dump_json()


@pytest.mark.parametrize(
    "variable,value",
    [
        ("AUTOPLM_LLM_PROVIDER", "unsupported"),
        ("AUTOPLM_LLM_PROVIDER", "openai_compatible"),
        ("AUTOPLM_LLM_TIMEOUT", "0"),
        ("AUTOPLM_LLM_TIMEOUT", "nan"),
        ("AUTOPLM_LLM_RETRIES", "3"),
        ("AUTOPLM_LLM_MAX_TOKENS", "99999"),
    ],
)
def test_invalid_provider_configuration_fails_gracefully(
    generated, configuration, monkeypatch, variable, value
):
    monkeypatch.setenv(variable, value)
    report = investigate("Inspect brake", generated[1].documents(), mode="llm")
    assert report.status == "partial" and not report.evidence


def test_compatible_endpoint_configuration(configuration, monkeypatch):
    monkeypatch.setenv("AUTOPLM_LLM_PROVIDER", "openai_compatible")
    monkeypatch.setenv("AUTOPLM_LLM_BASE_URL", "http://mock.invalid/v1")
    monkeypatch.setenv("AUTOPLM_LLM_TIMEOUT", "12")
    monkeypatch.setenv("AUTOPLM_LLM_RETRIES", "0")
    with patch("langchain_openai.ChatOpenAI") as factory:
        LLMInvestigator()
    assert factory.call_args.kwargs["base_url"] == "http://mock.invalid/v1"
    assert factory.call_args.kwargs["timeout"] == 12
    assert factory.call_args.kwargs["max_retries"] == 0


class SummarizingOffline(OfflineInvestigator):
    def summarize(self, context):
        return {"citations": [{"evidence_id": "E001", "pointer": "/record/id", "category": "record_fact"}]}


@pytest.mark.parametrize(
    "citation",
    [
        {"evidence_id": "E999", "pointer": "/record/id", "category": "record_fact"},
        {"evidence_id": "E001", "pointer": "/record/invented_revision", "category": "record_fact"},
        {"evidence_id": "E001", "pointer": "/record/id", "category": "deterministic_finding"},
        {"evidence_id": "E001", "pointer": "/potentially_affected/0", "category": "deterministic_finding"},
    ],
)
def test_unsupported_conclusions_rejected(generated, citation):
    class Unsupported(SummarizingOffline):
        def summarize(self, context):
            return {"citations": [citation]}

    report = investigate("Inspect F0000-brake", generated[1].documents(), provider=Unsupported())
    assert report.reasoning_status == "rejected"
    assert report.reasoning == [] and report.status == "partial"


@pytest.mark.parametrize("response", [None, {}, {"citations": []}, {"citations": [{"statement": "Safe"}]}])
def test_malformed_synthesis_is_explicit(generated, response):
    class Malformed(SummarizingOffline):
        def summarize(self, context):
            return response

    report = investigate("Inspect F0000-brake", generated[1].documents(), provider=Malformed())
    assert report.reasoning_status == "unavailable" and report.status == "partial"
    assert not report.reasoning


@pytest.mark.parametrize("stage", ["extract", "decide", "summarize"])
@pytest.mark.parametrize("failure", ["timeout", "rate_limit", "outage"])
def test_provider_failure_types(generated, stage, failure):
    class Failing(SummarizingOffline):
        pass

    def fail(*args):
        if failure == "rate_limit":
            raise RateLimitError(
                "private provider details",
                response=httpx.Response(429, request=httpx.Request("POST", "http://mock.invalid")),
                body={},
            )
        if failure == "timeout":
            raise TimeoutError("private provider details")
        raise ConnectionError("private provider details")

    setattr(Failing, stage, fail)
    report = investigate("Inspect F0000-brake", generated[1].documents(), provider=Failing())
    assert report.status == "partial"
    assert "private provider details" not in report.model_dump_json()
    assert not report.reasoning


@pytest.mark.parametrize(
    "call",
    [
        {"tool": "exec_python"},
        {"tool": "publish"},
        {"tool": "impact", "entity_id": "F0000-brake", "max_depth": 1000},
    ],
)
def test_malformed_plans_cannot_invoke_tools(generated, call):
    class Unsafe(OfflineInvestigator):
        def decide(self, context):
            return {"calls": [call], "rationale": "Untrusted plan"}

    report = investigate("Inspect brake", generated[1].documents(), provider=Unsafe())
    assert report.status == "partial" and not report.evidence


def test_duplicate_suppression_and_execution_bounds(generated):
    class Repeating(OfflineInvestigator):
        def decide(self, context):
            return Decision(
                calls=[ToolCall(tool="component", entity_id="F0000-brake")] * 3, rationale="Repeated request"
            )

    report = investigate("Inspect F0000-brake", generated[1].documents(), provider=Repeating())
    assert len(report.evidence) == 1
    limited = investigate("Impact verify F0000-brake", generated[1].documents(), max_steps=1)
    assert limited.status == "limit_reached" and len(limited.evidence) == 1


def test_explicit_offline_fallback_after_missing_credentials(generated, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    records = generated[1].documents()
    failed = investigate("Inspect F0000-brake", records, mode="llm")
    fallback = investigate("Inspect F0000-brake", records, mode="offline")
    assert failed.status == "partial" and not failed.evidence
    assert fallback.status == "complete" and fallback.evidence


def test_synthesis_forwarded_through_authoritative_service(service, approved_job):
    response = InvestigationService(service.repo).run(
        approved_job,
        InvestigationInput(request="Inspect F0000-brake", variant_id="F0000-standard"),
        provider=SummarizingOffline(),
    )
    assert response.report.reasoning_status == "validated"
    assert response.report.reasoning[0].evidence_id == "E001"


def test_legacy_report_serialization_stable(generated):
    report = investigate("Inspect F0000-brake", generated[1].documents())
    assert "reasoning" not in report.model_dump(mode="json")
    assert "reasoning_status" not in report.model_dump(mode="json")


def test_reproducible_evaluation_and_live_opt_in(monkeypatch):
    result = evaluate_investigations()
    assert result["passed"] == result["total"] == 6
    assert result["unnecessary_tool_calls"] == result["unsupported_conclusion_cases"] == 0
    monkeypatch.delenv("AUTOPLM_RUN_LIVE_INVESTIGATION", raising=False)
    with pytest.raises(ValueError, match="explicit"):
        evaluate_investigations(mode="llm")


def test_deterministic_incompatibility_citation(generated):
    class Findings(OfflineInvestigator):
        def summarize(self, context):
            return EvidenceSummary(
                citations=[
                    EvidenceCitation(
                        evidence_id="E001", pointer="/findings/0", category="deterministic_finding"
                    )
                ]
            )

    records = generated[1].documents()
    next(r for r in records if r["id"] == "F0000-brake-sw")["supported_hardware_revisions"] = ["UNKNOWN"]
    report = investigate("verify", records, provider=Findings())
    assert report.reasoning_status == "validated"
    assert "HW_SW_REVISION" in report.reasoning[0].statement


def test_real_exposure_cannot_be_summarized_as_a_finding(generated):
    class Misclassified(OfflineInvestigator):
        def summarize(self, context):
            return {
                "citations": [
                    {
                        "evidence_id": "E002",
                        "pointer": "/potentially_affected/0",
                        "category": "deterministic_finding",
                    }
                ]
            }

    report = investigate("Impact F0000-brake", generated[1].documents(), provider=Misclassified())
    assert report.evidence[1].result["potentially_affected"]
    assert report.reasoning_status == "rejected" and report.reasoning == []


def test_grounded_llm_report_survives_persistence_and_human_review(service, approved_job, configuration):
    from app.investigation_review import InvestigationReviews, ReviewInput
    from app.review_auth import ReviewPrincipal

    reviews = InvestigationReviews(service.repo)
    principal = ReviewPrincipal(subject="test-engineer", roles=("engineering_reviewer",))
    baseline = copy.deepcopy(service.repo.approved_records(approved_job))
    with patch("langchain_openai.ChatOpenAI", return_value=StructuredSDK()):
        stored = reviews.create(
            approved_job,
            InvestigationInput(request="Investigate brake", variant_id="F0000-standard", mode="llm"),
            principal,
        )
    assert reviews.get(stored.investigation_id) == stored
    assert stored.investigation.report.reasoning_status == "validated"
    history = reviews.decide(
        stored.investigation_id,
        ReviewInput(decision="ACCEPT", comments="Further consideration only"),
        principal,
    )
    assert history.audit_mirrored
    assert reviews.get(stored.investigation_id).investigation == stored.investigation
    assert service.repo.approved_records(approved_job) == baseline
