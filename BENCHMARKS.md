# Reproducible synthetic benchmark

Run `python -m app.cli benchmark --fleets 2 --seed 42 --output benchmarks/results.json`. Rebuild examples, all seven scenario traces, runtime outage trace, environment lock and benchmark using `python scripts/build_evidence.py`.

The checked-in [raw results](benchmarks/results.json) are executed measurements, not illustrative numbers. Evaluation uses two legacy schemas, 26 source records per schema, four variants per schema, one clean dataset and ten separately injected single-defect datasets. Each of three modes receives identical faults. This yields 66 case evaluations (22 unique input/fault combinations across the modes). Faults are injected after transformation to isolate engineering defect detection from mapping quality. The exported `data/synthetic/corrupted_revision.json` separately demonstrates a corrupted legacy input; its label lives only in `data/ground_truth/`.

## Measured correctness

| Mode, for each schema | Mapping accuracy | Migration correctness before injection | Defect recall | Precision | False positive rate |
|---|---:|---:|---:|---:|---:|
| Dictionary baseline, schema validation | 100% | 100% | 0/10 | Undefined (no positive predictions) | 0/1 |
| Offline LangGraph agent, schema validation | 100% | 100% | 0/10 | Undefined (no positive predictions) | 0/1 |
| Offline agent + engineering rules + twins | 100% | 100% | 10/10 | 10/10 | 0/1 |

All injected faults deliberately remain schema-valid. Thus the first two modes have zero engineering-defect recall by design, not because their transformation is incorrect. The offline graph uses the same dictionary as the baseline; **no LLM benefit has been measured**. A paid/live model is not required to reproduce these numbers. Optional `--mapper llm` uses the configured structured provider; unresolved mappings stop scoring rather than silently falling back.

## Attribution

Per source schema:

- Engineering rules without source reconciliation detect 8/10 fault cases.
- Engineering rules with independent source reconciliation detect 10/10.
- Twin structural/semantic comparison detects 9/10. Duplicate identities collapse in snapshots; the separate duplicate rule detects them.
- Fictional behavioral simulation exposes 5/10. Wrong version labels, unit errors and BOM relationship changes do not acquire invented physical effects.
- Incremental twin detections beyond the complete rule-plus-reconciliation engine: **0/10**. The twins add inspectable configuration and behavioral evidence, not additional recall in this corpus.
- Zero agent retries and zero job review rate occurred in the clean dictionary-mapping experiment. These do not estimate live model uncertainty or human workload.

Each case stores source/mode/fault label, rule identifiers, intrinsic rule identifiers, twin discrepancy count, failed simulated variants and measured elapsed time. Precision/recall use **case-level** positives, not individual finding-level labels. The false-positive denominator is only one clean case per schema. This small corpus cannot support a robust statistical generalization.

`mean_verification_seconds` is the mean across clean+ten fault cases. All modes run schema, rule, twin and behavior diagnostics for attribution, even when only schema output determines their decision. Therefore these timings are end-to-end diagnostic runtimes and **must not be used to claim a speed advantage between modes**. Consult the JSON for exact host-dependent measurements. There is no measured database or LLM latency in this benchmark.

Mapping accuracy compares every expected source field's target and transformation with separately held mapping truth. Record correctness compares full normalized dictionaries before faults. Ground-truth mappings and fault labels are never passed into agent prompts. The generator and offline mapper share a versioned synthetic schema dictionary; the migration service's source adapters independently encode the source contracts and conversions. This remains an offline regression benchmark, not a blind semantic-mapping research study. The full test suite separately injects defects into the transformation implementation and source-row bindings; those regression tests are outside the ten-fault benchmark corpus.
