"""Reproducible synthetic contract evaluation; no model-accuracy claim."""

import argparse
import copy
import json
import os
from typing import Literal

from app.data import generate
from app.investigation import (
    EvidenceCitation,
    EvidenceSummary,
    InvestigationReport,
    ToolEvidence,
    grounded_conclusions,
    investigate,
    redundant_call,
)


def score_investigation(
    name: str,
    report: InvestigationReport,
    records: list[dict],
    required: set,
    allowed: set,
    *,
    require_reasoning=False,
) -> dict:
    successful = [e for e in report.evidence if e.status == "ok"]
    expected_target = {
        "record_lookup": "F0000-brake",
        "fingerprint": "F0000-standard",
        "impact_followup": "F0000-brake",
    }.get(name)
    obtained = {
        e.call.tool for e in successful if expected_target is None or e.call.entity_id == expected_target
    }
    if "twin" in obtained:
        obtained.add("fingerprint")
    if "provenance" in obtained:
        obtained.add("impact")
    kinds = {r["id"]: r["kind"] for r in records}
    previous: list[ToolEvidence] = []
    unavailable: set[str] = set()
    redundant = 0
    for evidence in report.evidence:
        if (
            redundant_call(evidence.call, previous, kinds)
            or evidence.call.entity_id in unavailable
            or evidence.call.other_variant in unavailable
        ):
            redundant += 1
        if evidence.result.get("code") == "identifier_not_found":
            unavailable.add(evidence.result["entity_id"])
        previous.append(evidence)
    irrelevant = sum(e.call.tool not in allowed for e in report.evidence)
    if name in ("record_lookup", "impact_followup"):
        understood = "F0000-brake" in report.extracted.components
        if name == "impact_followup":
            understood = understood and bool({"impact", "provenance"} & set(report.extracted.needs))
    elif name == "fingerprint":
        understood = "F0000-standard" in report.extracted.variants and bool(
            {"fingerprint", "twin"} & set(report.extracted.needs)
        )
    elif name in ("verification", "incompatible_configuration"):
        understood = "verify" in report.extracted.needs
    else:
        understood = not report.extracted.components and not report.extracted.variants
    abstained = (
        (understood and not report.evidence and report.status == "partial" and bool(report.missing_evidence))
        if name == "missing_target"
        else None
    )
    required_obtained = required <= obtained if required else None
    impact_found = None
    if name == "impact_followup":
        impact_found = any(
            e.call.tool in ("impact", "provenance")
            and e.call.entity_id == expected_target
            and any(
                p["node"] == ["record", "F0000-standard"] for p in e.result.get("potentially_affected", [])
            )
            for e in successful
        )
    grounded = None
    if report.reasoning:
        citations = [
            EvidenceCitation.model_validate(c.model_dump(exclude={"statement"})) for c in report.reasoning
        ]
        try:
            grounded = (
                grounded_conclusions(EvidenceSummary(citations=citations), report.evidence)
                == report.reasoning
            )
        except (ValueError, KeyError, IndexError, TypeError):
            grounded = False
    aggregates = report.dependency_paths + report.validation_findings
    by_id = {e.evidence_id: e for e in successful}

    def contains(data, target):
        if data == target:
            return True
        if isinstance(data, dict):
            return any(contains(v, target) for v in data.values())
        if isinstance(data, list):
            return any(contains(v, target) for v in data)
        return False

    traceable = (
        all(
            item.get("evidence_id") in by_id
            and contains(
                by_id[item["evidence_id"]].result, {k: v for k, v in item.items() if k != "evidence_id"}
            )
            for item in aggregates
        )
        if aggregates
        else None
    )
    incompatible = (
        any(f["rule_id"] == "HW_SW_REVISION" for f in report.validation_findings)
        if name == "incompatible_configuration"
        else None
    )
    missing_handled = (
        abstained
        if name == "missing_target"
        else (bool(report.missing_evidence) if report.status in ("partial", "limit_reached") else None)
    )
    passed = (
        understood
        and (abstained is True if name == "missing_target" else required_obtained is True)
        and not redundant
        and not irrelevant
        and traceable is not False
        and grounded is not False
        and incompatible is not False
        and impact_found is not False
        and len(report.evidence) <= 8
        and (
            not require_reasoning
            or not successful
            or (grounded is True and report.reasoning_status == "validated")
        )
    )
    return {
        "case": name,
        "request_understood": understood,
        "tools": [e.call.tool for e in report.evidence],
        "required_tools": sorted(required),
        "optional_tools": sorted(allowed - required),
        "required_tools_obtained": required_obtained,
        "abstention_correct": abstained,
        "redundant_tool_calls": redundant,
        "irrelevant_tool_calls": irrelevant,
        "unnecessary_tool_calls": redundant,
        "traceable": traceable,
        "grounded": grounded,
        "reasoning_evaluated": grounded is not None,
        "missing_evidence_handled": missing_handled,
        "within_bounds": len(report.evidence) <= 8,
        "incompatible_detected": incompatible,
        "expected_impact_obtained": impact_found,
        "status": report.status,
        "reasoning_status": report.reasoning_status,
        "passed": bool(passed),
    }


def evaluate_investigations(*, mode: Literal["offline", "llm"] = "offline", provider=None) -> dict:
    if mode not in ("offline", "llm"):
        raise ValueError("Unsupported evaluation mode")
    if mode == "llm" and os.getenv("AUTOPLM_RUN_LIVE_INVESTIGATION") != "1":
        raise ValueError("Live evaluation requires explicit AUTOPLM_RUN_LIVE_INVESTIGATION=1")
    records = generate(1, seed=42)[1].documents()
    cases = [
        ("record_lookup", "Inspect F0000-brake", {"component"}, {"component"}, False),
        ("verification", "Verify engineering configuration", {"verify"}, {"verify"}, False),
        (
            "fingerprint",
            "Inspect fingerprint F0000-standard",
            {"fingerprint"},
            {"variant", "component", "fingerprint", "twin"},
            False,
        ),
        (
            "impact_followup",
            "Investigate impact F0000-brake",
            {"impact"},
            {"component", "impact", "relationships", "provenance"},
            True,
        ),
        ("missing_target", "Inspect an unidentified component", set(), set(), True),
        ("incompatible_configuration", "Verify engineering configuration", {"verify"}, {"verify"}, False),
    ]
    results = []
    for name, query, required, allowed, missing in cases:
        baseline = copy.deepcopy(records)
        if name == "incompatible_configuration":
            next(r for r in baseline if r["id"] == "F0000-brake-sw")["supported_hardware_revisions"] = [
                "UNKNOWN"
            ]
        original = copy.deepcopy(baseline)
        report = investigate(query, baseline, mode=mode, provider=provider, max_steps=8)
        result = score_investigation(
            name, report, original, required, allowed, require_reasoning=mode == "llm"
        )
        result["baseline_unchanged"] = baseline == original
        result["passed"] = result["passed"] and result["baseline_unchanged"]
        results.append(result)
    return {
        "mode": "mocked" if provider else mode,
        "seed": 42,
        "cases": results,
        "passed": sum(r["passed"] for r in results),
        "total": len(results),
        "unnecessary_tool_calls": sum(r["unnecessary_tool_calls"] for r in results),
        "irrelevant_tool_calls": sum(r["irrelevant_tool_calls"] for r in results),
        "reasoning_cases_evaluated": sum(r["reasoning_evaluated"] for r in results),
        "unsupported_conclusion_cases": sum(
            r["grounded"] is False or r["reasoning_status"] == "rejected" for r in results
        ),
        "note": "Synthetic contract checks, not measured LLM accuracy or automotive safety validation; "
        "null means not applicable or not evaluated, not success",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Opt-in configured-provider evaluation")
    arguments = parser.parse_args()
    result = evaluate_investigations(mode="llm" if arguments.live else "offline")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] == result["total"] else 1)
