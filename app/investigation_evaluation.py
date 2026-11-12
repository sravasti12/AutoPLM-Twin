"""Reproducible synthetic contract evaluation; no model-accuracy claim."""

import argparse
import copy
import json
import os
from typing import Literal

from app.data import generate
from app.investigation import EvidenceCitation, EvidenceSummary, grounded_conclusions, investigate


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
            {"variant", "fingerprint"},
            {"variant", "fingerprint"},
            False,
        ),
        (
            "impact_followup",
            "Investigate impact F0000-brake",
            {"component", "impact", "relationships"},
            {"component", "impact", "relationships"},
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
        invoked = {call.tool for call in report.tools_invoked}
        unexpected = sum(call.tool not in allowed for call in report.tools_invoked)
        grounded = True
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
        ids = {e.evidence_id for e in report.evidence}
        traceable = all(
            item["evidence_id"] in ids for item in report.dependency_paths + report.validation_findings
        )
        understood = name != "record_lookup" or "F0000-brake" in report.identified_components
        incompatible_detected = name != "incompatible_configuration" or any(
            finding["rule_id"] == "HW_SW_REVISION" for finding in report.validation_findings
        )
        missing_handled = not missing or bool(report.missing_evidence)
        result = {
            "case": name,
            "request_understood": understood,
            "tools": [c.tool for c in report.tools_invoked],
            "required_tools_obtained": required <= invoked,
            "unnecessary_tool_calls": unexpected,
            "traceable": traceable,
            "grounded": grounded,
            "missing_evidence_handled": missing_handled,
            "within_bounds": len(report.evidence) <= 8,
            "baseline_unchanged": baseline == original,
            "incompatible_detected": incompatible_detected,
            "status": report.status,
            "reasoning_status": report.reasoning_status,
        }
        result["passed"] = (
            all(
                result[k]
                for k in (
                    "request_understood",
                    "required_tools_obtained",
                    "traceable",
                    "grounded",
                    "missing_evidence_handled",
                    "within_bounds",
                    "baseline_unchanged",
                    "incompatible_detected",
                )
            )
            and unexpected == 0
            and (mode != "llm" or not report.evidence or report.reasoning_status == "validated")
        )
        results.append(result)
    return {
        "mode": "mocked" if provider else mode,
        "seed": 42,
        "cases": results,
        "passed": sum(r["passed"] for r in results),
        "total": len(results),
        "unnecessary_tool_calls": sum(r["unnecessary_tool_calls"] for r in results),
        "unsupported_conclusion_cases": sum(not r["grounded"] for r in results),
        "note": "Synthetic contract checks, not measured LLM accuracy or automotive safety validation",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Opt-in configured-provider evaluation")
    arguments = parser.parse_args()
    result = evaluate_investigations(mode="llm" if arguments.live else "offline")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] == result["total"] else 1)
