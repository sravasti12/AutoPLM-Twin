"""Reproducible case-level evaluation; truth is consulted only for scoring."""

import statistics
import time
from datetime import datetime, timezone

from app.agents import mapping_graph
from app.data import FAULTS, generate, inject
from app.mapping import MODELS, baseline, profile, transform
from app.twin import build_twin, compare_twins, simulate
from app.verification import verify


def score(labels: list[bool], predictions: list[bool]) -> dict:
    if len(labels) != len(predictions):
        raise ValueError("Label/prediction length mismatch")
    tp = sum(label and prediction for label, prediction in zip(labels, predictions))
    fp = sum(not label and prediction for label, prediction in zip(labels, predictions))
    fn = sum(label and not prediction for label, prediction in zip(labels, predictions))
    tn = sum(not label and not prediction for label, prediction in zip(labels, predictions))
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "false_positive_rate": fp / (fp + tn) if fp + tn else None,
    }


def run_benchmark(fleets: int = 2, seed: int = 42, provider=None) -> dict:
    cases = []
    runs = []
    for source in ["A", "B"]:
        envelope, truth_data, mapping_truth = generate(fleets, seed, source)
        originals = truth_data.documents()
        proposals = {}
        retries = 0
        review = False
        for entity in sorted({row["entity"] for row in envelope["records"]}):
            rows = [row["data"] for row in envelope["records"] if row["entity"] == entity]
            state = mapping_graph(provider).invoke({"entity": entity, "records": rows})
            retries += state["attempts"] - 1
            review |= state["status"] != "validated"
            proposals[entity] = state
        for mode in ["baseline", "agent_schema_only", "agent_engineering_twin"]:
            transformed = []
            correct_fields = 0
            total_fields = sum(len(mapping_truth[row["entity"]]) for row in envelope["records"])
            for row in envelope["records"]:
                if mode == "baseline":
                    plan = baseline(row["entity"], profile([row["data"]]))
                else:
                    from app.mapping import MappingPlan

                    state = proposals[row["entity"]]
                    if state["status"] != "validated":
                        continue
                    plan = MappingPlan.model_validate(state["plan"])
                for field in plan.fields:
                    expected = mapping_truth[row["entity"]].get(field.source, {})
                    correct_fields += expected == {"target": field.target, "transform": field.transform}
                transformed.append(
                    MODELS[row["entity"]].model_validate(transform(row["data"], plan)).model_dump(mode="json")
                )
            if len(transformed) != len(originals):
                raise ValueError(
                    "Benchmark mapping requires human review; resolve mappings before fault scoring"
                )
            predictions, labels, timings = [], [], []
            twin_detected = rule_detected = behavior_detected = schema_detected = 0
            intrinsic_detected = incremental_twin_detected = 0
            for fault in ["clean", *FAULTS]:
                target, label = (transformed, None) if fault == "clean" else inject(transformed, fault)
                start = time.perf_counter()
                schema_errors = []
                for record in target:
                    try:
                        MODELS[record["kind"]].model_validate(record)
                    except (ValueError, KeyError) as exc:
                        schema_errors.append(type(exc).__name__)
                rule_findings = verify(target, originals)
                intrinsic_findings = verify(target)
                twin_differences, behavior_failures = [], []
                for variant in (r for r in originals if r["kind"] == "variant"):
                    before = build_twin(originals, variant["id"])
                    try:
                        after = build_twin(target, variant["id"])
                        twin_differences.extend(compare_twins(before, after))
                        if not simulate(after)["behavior_passed"]:
                            behavior_failures.append(variant["id"])
                    except ValueError:
                        twin_differences.append({"path": "/variant", "target": None})
                elapsed = time.perf_counter() - start
                labels.append(fault != "clean")
                detected = bool(schema_errors)
                if mode == "agent_engineering_twin":
                    detected |= bool(rule_findings or twin_differences or behavior_failures)
                predictions.append(detected)
                timings.append(elapsed)
                schema_detected += bool(schema_errors) and fault != "clean"
                rule_detected += bool(rule_findings) and fault != "clean"
                twin_detected += bool(twin_differences) and fault != "clean"
                behavior_detected += bool(behavior_failures) and fault != "clean"
                intrinsic_detected += bool(intrinsic_findings) and fault != "clean"
                incremental_twin_detected += bool(twin_differences) and not rule_findings and fault != "clean"
                cases.append(
                    {
                        "source": source,
                        "mode": mode,
                        "fault": fault,
                        "label": label,
                        "detected": detected,
                        "schema_errors": schema_errors,
                        "rule_ids": sorted({f.rule_id for f in rule_findings}),
                        "intrinsic_rule_ids": sorted({f.rule_id for f in intrinsic_findings}),
                        "twin_discrepancies": len(twin_differences),
                        "behavior_failed_variants": behavior_failures,
                        "elapsed_seconds": elapsed,
                    }
                )
            runs.append(
                {
                    "source": source,
                    "mode": mode,
                    **score(labels, predictions),
                    "mapping_accuracy": correct_fields / total_fields if total_fields else None,
                    "migration_success_rate": len(transformed) / len(originals),
                    "migration_correctness": sum(a == b for a, b in zip(transformed, originals))
                    / len(originals),
                    "human_review_rate": float(review) if mode != "baseline" else 0,
                    "agent_retries": retries if mode != "baseline" else 0,
                    "mean_verification_seconds": statistics.mean(timings),
                    "schema_detection_rate": schema_detected / len(FAULTS),
                    "rule_detection_rate": rule_detected / len(FAULTS),
                    "intrinsic_rule_detection_rate": intrinsic_detected / len(FAULTS),
                    "incremental_twin_detection_rate": incremental_twin_detected / len(FAULTS),
                    "twin_discrepancy_detection_rate": twin_detected / len(FAULTS),
                    "behavior_detection_rate": behavior_detected / len(FAULTS),
                }
            )
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "fleets": fleets,
        "provider": "offline_dictionary" if provider is None else type(provider).__name__,
        "unit_of_evaluation": "one clean or one single-fault dataset; not individual findings",
        "notes": [
            "Offline agent and baseline share the same dictionary; no LLM improvement is claimed.",
            "All modes use identical post-transformation faults; diagnostics are recorded for every mode.",
            "End-to-end runtime includes diagnostic rules, twin comparison and simulation in every mode.",
            "Reconciliation is part of the rule engine; its detections are not credited to behavior.",
            "Small synthetic benchmark is a correctness demonstration, not an industry performance estimate.",
        ],
        "runs": runs,
        "cases": cases,
    }
