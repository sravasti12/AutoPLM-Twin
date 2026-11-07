# AutoPLM Twin implementation progress

All engineering data and behavior in this project are synthetic.
## Latest verification update — 2026-11-08

The following results supersede older environment-blocker statements elsewhere in this document. Historical phase reports remain preserved as records of earlier verification.

### Confirmed results

- **Latest unit tests:** 212 passed locally in 27.80 seconds, superseding the earlier 200-test result.
- **Latest MongoDB integration tests:** 6 passed locally in 4.16 seconds using real MongoDB and isolated test databases.
- **Focused migration tests:** 14 passed in 0.98 seconds; Ruff passed for `tests/unit/test_migration.py`.
- **Docker:** MongoDB service confirmed healthy through Docker Compose.
- **GitHub Actions:** Latest workflow reported successful after changing the CI runner from `ubuntu-24.04` to `ubuntu-22.04`.
- **Git:** The clean-tree assessment at commit `5ff5cee` is historical. This delivery has uncommitted changes to `tests/unit/test_migration.py`, `README.md` and this progress document; no commit or push was performed.

### Resolved blocker

The MongoDB 8.0 container previously failed to start in GitHub Actions because of a reported incompatibility with Linux kernels 6.19 and newer.

Changing the workflow runner to Ubuntu 22.04 resolved the observed CI failure in the latest run. This is an environment compatibility fix, not a modification to the application's engineering verification logic.

### Remaining verification work

- Live LLM provider calls have not yet been verified end-to-end.
- Existing engineering verification, digital twin, simulation, remediation, dashboard, and benchmark modules require a current completeness review before further development.
- Existing benchmark results remain historical evidence; no new benchmark execution is claimed.
- Production readiness, hardware validation, and vendor PLM integration are not claimed.

### Delivery policy

Continue development in small, explicitly approved tasks. Preserve completed functionality, use focused tests, and avoid unnecessary full-repository changes.

Documentation is part of the definition of done. After each meaningful checkpoint, synchronize README.md's public capabilities, architecture/workflow, safety behavior, technology purposes, setup and verified results with this tracker's detailed tasks, exact changed files, test evidence, bugs, limitations, remaining work, next step and Git status. Clearly distinguish implemented, tested, partial, planned and unverified work. Preserve historical information without presenting it as current verification; keep README.md capability-focused rather than adding a development diary. Review both documents at phase completion, and do not commit or push without explicit approval.

## Active delivery workflow

The user now requires phased delivery: finish and verify each phase, update README.md, then ask for explicit approval before starting the next phase. This supersedes the original autonomous phase progression. Existing code is retained as the baseline; approval checkpoints track subsequent review and development rather than claiming the code has not been built.

Current checkpoint: the focused Phase 2 Digital Twin Validation migration-safety objectives below are implemented and locally tested. Further development requires a separately approved small task. Earlier numbered build-phase checkpoints and their test counts are preserved below as historical records, not current authorization or verification status.

## Plan
1. Define versioned domain models and seeded legacy datasets with isolated truth labels.
2. Implement profiling, constrained mappings, and bounded LangGraph review workflow.
3. Implement immutable source capture, MongoDB staging, reconciliation and gated promotion.
4. Implement independent engineering rules and source/target configuration twins.
5. Implement fictional speed/braking state machines and repeatable fault scenarios.
6. Add auditable repair proposals with explicit approval and revalidation.
7. Add FastAPI, Streamlit workspaces, exports and benchmark experiments.
8. Run unit and available integration checks; record actual results and limitations.

## Actual verification (2026-11-07)

- Python 3.13. Latest Phase 3 regression: **171 passed, 1 skipped**. The skipped check requires explicitly opted-in real MongoDB.
- Ruff: passed. Mypy: passed for models, mapping, constrained resolution and independent source adapter modules.
- Streamlit AppTest exercised all eight pages against FastAPI with a mongomock test database, including dataset generation, staged migration and simulation buttons.
- Benchmark executed: two schemas, two fleets/schema, three modes, 66 case evaluations. Mapping accuracy and pre-injection record correctness 100% in offline mode. Complete verification detected all ten injected fault types per schema. Schema-only modes detected zero deliberately schema-valid faults.
- Intrinsic rules detected 8/10, rules plus independent reconciliation 10/10, configuration twin comparison 9/10, behavior 5/10. Incremental twin detections beyond full rules: 0/10. No LLM benefit is claimed.
- Seven scenario traces and an additional runtime sensor-outage trace are saved under `benchmarks/scenarios/`.
- `benchmarks/test-results.xml`, `benchmarks/check-results.json`, `benchmarks/results.json` and `requirements-lock.txt` preserve reproducible evidence.
- Docker client exists, but the daemon pipe is unavailable. No local `mongod` executable was found. Real MongoDB integration was not run.
- Live structured LLM calls were not run; provider boundaries were tested with deterministic fake providers and exceptions. CI is defined but remote execution has not occurred.

## Historical feature acceptance matrix (2026-11-07)

"Implemented and tested" means the listed local/unit checks passed; it does not imply production or hardware validation. Integration-dependent rows explicitly retain their remaining qualification.

| Feature | Status | Evidence / remaining scope |
|---|---|---|
| Versioned domain schemas | Implemented and tested | All six entity types, dates, semantic software versions, invalid quantities/versions |
| Seeded synthetic datasets and ground truth | Implemented and tested | Sources A/B, B/C revisions, two releases, multi-level BOMs, isolated fault labels |
| Profiling and baseline schema mapping | Implemented and tested | Both sources round-trip exactly, gram conversion, enum registry, ambiguity checks |
| LangGraph workflow and bounded repair | Implemented and tested | Offline graph, fake provider failures, retry cap, history, human review |
| Live LLM mapping provider | Implemented but not integration-tested | Structured output and configurable model/endpoint; no live model call |
| Deterministic transformation registry | Implemented and tested | Allowlist, required targets, types, unknown operations and evidence requirements |
| PyMongo repositories and indexes | Implemented but not integration-tested | mongomock coverage; real service unavailable |
| Idempotent jobs, provenance and staging | Implemented and tested | Test-double round trips, unique sources, source preservation, digest gates |
| Real MongoDB migration and promotion | Blocked | Start Docker Desktop/local MongoDB and set AUTOPLM_TEST_MONGODB_URI |
| Engineering compatibility verifier | Implemented and tested | Hardware/software revision, lifecycle, interfaces, dependencies, platform support, unknown critical states |
| BOM graph verification | Implemented and tested | Cycles, missing parts, invalid edges, quantities, revision, roll-up, duplicates |
| Variant / feature / network rules | Implemented and tested | Presence, platform restrictions, dependencies, disconnected topology |
| Engineering changes and reconciliation | Implemented and tested | Approval, progression, effectivity, supersession, values, units, identities |
| Configuration twins and comparison | Implemented and tested | Source/target equality and semantic defects; duplicates handled by separate rule |
| SimPy behavioral state machines | Implemented and tested | Seven scenarios, repeatable traces, runtime sensor loss; no vehicle physics validation |
| Repair planning and human gates | Implemented and tested | Offline/fake agent actions, before/after checks, approval, rejection, stale proposals, immutable approved jobs |
| Live LLM remediation | Implemented but not integration-tested | Source-field action planner with independent candidate validation |
| FastAPI routes and report exports | Implemented and tested | TestClient with mock MongoDB; JSON/CSV/escaped HTML, job/review/simulation routes |
| Streamlit / Plotly dashboard | Implemented and tested | All eight pages in AppTest with mocked-database backend; live MongoDB path remains unverified |
| Fault injection and benchmark scoring | Implemented and tested | Ten faults, isolated labels, paired modes, confusion matrices, attribution, actual runtime |
| Automated tests / scoped typing / lint | Implemented and tested | Local commands and machine-readable reports |
| Docker Compose and CI configuration | Implemented but not integration-tested | MongoDB service and isolated real integration job defined; daemon/remote runner not exercised |
| Documentation / examples / environment template | Implemented and tested | CLI examples and synthetic evidence generated locally; real service commands await daemon |

## Decisions and limitations

The source adapter and verifier remain independent of the proposed agent mapping. Approval uses a single-document publication manifest suitable for standalone MongoDB. Materialized entity records are job-scoped snapshots. No transaction support or global part catalog is claimed.

Repairs restore source facts; invalid source engineering remains rejected. New engineering values require a separately approved source/change revision. In-process jobs require explicit interrupted-worker recovery. Application-level audit append-only behavior does not prevent database administrators from editing records. Reviewer names are not authenticated identities.

No SQLite, paid infrastructure requirement, public deployment, GitHub push, vendor connector, production readiness or real hardware validation was introduced. Remaining integration blockers are the real MongoDB service and live LLM execution. The supported synthetic portfolio scope is implemented; production vendor adapters, authentication, distributed execution and physics validation are future work, not implemented features.

## Follow-up verification improvements

- Replaced source normalization's reuse of the baseline mapper/transform function with independently implemented source adapters. The earlier implementation shared execution code despite the intended independent boundary. Handwritten fixtures cover both contracts; intentionally breaking the migration mass conversion now causes rejection for both schemas.
- Added critical source-row provenance validation. Swapped complete records and changed source annotations are detected even when record-set comparison and twin equality cannot detect them. Promotion checks current annotations, and approved restoration repairs restore them.
- Reject infinite and NaN masses/BOM quantities at the domain boundary and nonfinite source masses in the adapter.
- Bumped pipeline version to 1.1 so jobs do not reuse earlier verification results.
- Rechecked Docker outside the sandbox: the Docker Desktop Linux engine pipe remains absent. Real MongoDB integration remains blocked by the stopped daemon, independently of sandbox configuration access.
## Phase 2 — Digital Twin Validation

**Status: In progress. The focused twin-validation and migration-safety objectives are implemented and locally tested (2026-11-08); additional scenario review, broader phase acceptance and publication remain pending.**

This section follows the current Digital Twin Validation task name; the older synthetic-data Phase 2 delivery below remains a separate historical checkpoint.

### Completed
- Identified an ECU-ordering sensitivity in digital twin fingerprint generation.
- Added a regression test for semantically equivalent ECU configurations.
- Canonicalized installed ECU ordering without modifying source records.
- Confirmed that equivalent ECU configurations generate identical fingerprints.
- Verified precise hardware revision difference reporting at `/nodes/<ECU_ID>/hardware/hardware_revision`. Corrected misplaced ordering assertions in the engineering tests; the focused engineering run passed 38 tests in 0.14 seconds at that checkpoint.
- Confirmed duplicate engineering identities are reported before ID-based lookups collapse records. Earlier focused regression checks covered both duplicate orderings, migration rejection and fresh promotion validation; no production safety-gate fix was needed.
- Added three migration-safety regression tests using the existing generated datasets and service fixture:
  - `test_incompatible_software_blocks_approval_even_when_source_and_target_twins_match`: revision-incompatible brake software produces `HW_SW_REVISION` findings and rejection even with equal source/target twins.
  - `test_genuine_twin_difference_independently_blocks_promotion`: compatible target-only version drift produces actual `/nodes/<ECU_ID>/software/version` differences and fails validation. A test-scoped override omits reference reconciliation while retaining real engineering rules and real twin construction/comparison, proving twin differences independently block promotion.
  - `test_compatible_software_version_change_with_updated_source_expectation_is_approved`: a compatible release supplied in the source before ingestion passes engineering checks, exact source/target comparison and promotion. Captured source records are not modified.
- Added `assert_fresh_validation_blocks_cached_approval`, used by both rejection tests: even a forged cached `verified` status, cached passing result and matching staging digest cannot bypass fresh validation. No software records are published.
- Preserved all production validation/promotion gates and public interfaces; this migration-safety task required test changes only.

### Latest verification

Commands used the existing `.venv` Python interpreter:

| Check | Command arguments after `python` | Actual result |
|---|---|---|
| Focused migration tests | `-m pytest tests/unit/test_migration.py -q --basetemp=.pytest_tmp -p no:cacheprovider --tb=short` | 14 passed in 0.98 seconds |
| Complete unit suite | `-m pytest tests/unit -q --basetemp=.pytest_tmp/unit -p no:cacheprovider --tb=short` | 212 passed in 27.80 seconds |
| Real MongoDB integration | `-m pytest tests/integration -q --basetemp=.pytest_tmp/integration -p no:cacheprovider --tb=short` | 6 passed in 4.16 seconds; `AUTOPLM_TEST_MONGODB_URI=mongodb://127.0.0.1:27017` |
| Focused Ruff | `-m ruff check tests/unit/test_migration.py` | Passed |

The initial sandboxed unit run had 210 passes and two CLI-fixture setup errors from Windows temporary-directory permissions. The same suite was rerun outside the sandbox and all 212 tests passed. No failing test was removed or disabled. Mypy, benchmarks and GitHub Actions were not rerun for this task; their earlier results are historical. This documentation update did not rerun tests or rewrite saved test reports.

### Exact files changed

- Migration-safety implementation task: **only `tests/unit/test_migration.py`** (three tests and one shared assertion helper).
- Initial documentation follow-up: only `PROJECT_PROGRESS.md`. The subsequent documentation-maintenance checkpoint updates **`README.md` and `PROJECT_PROGRESS.md`** to synchronize the public safety guarantees, verified results and internal status under the user's new maintenance rules.
- Earlier twin/order work involved `app/twin.py` and `tests/unit/test_engineering.py`; neither was modified in the migration-safety task or either documentation follow-up.
- No tests were rerun or reports regenerated for documentation maintenance. CI, dependencies and production code were not changed in this delivery. No commit or push was performed. The next recommended task and outstanding limitations below remain unchanged.
- README status refresh: preserved its existing sections and historical checkpoints, added a public summary of verified Phase 1 foundation capabilities and completed Phase 2 validation behavior, explicitly marked remaining Phase 2 work in progress, and corrected historical database-unverified wording. This refresh changes only `README.md` and `PROJECT_PROGRESS.md`; results remain the previously executed 14 migration, 212 unit and 6 integration passes.

### Remaining
- Obtain user review of the focused validation work before any next task, commit or push.
- Recommended next small development step, subject to approval: add a migration-level missing-required-ECU regression using the existing fixture, asserting the engineering finding, failed twin validation and blocked promotion. Check existing coverage first to avoid duplication.
- Review additional twin/simulation scenarios only when explicitly requested; no broader completeness or production-readiness assessment was performed here.

### Known limitations and unverified functionality

- Migration currently requires exact source preservation. A compatible target-only software version change is still rejected; there is no implemented policy allowing selected source/target deltas. The positive regression changes the expected source before ingestion rather than weakening comparison.
- Service regression tests use mongomock. The six real MongoDB integration tests passed separately; they do not establish that every new service regression was exercised against real MongoDB.
- The twin-only isolation test overrides only the verifier's reference-reconciliation boundary. It is not evidence of a deployed configurable comparison policy.
- Live LLM calls, production PLM connectors and real automotive hardware behavior remain unverified. The twin and its behavioral model use synthetic engineering assumptions.

### Engineering impact
Avoids false-positive twin differences caused solely by installed-ECU ordering, reports genuine configuration changes precisely, and verifies that engineering findings or twin differences block migration approval despite stale cached approval data. Compatible releases remain acceptable when engineering constraints and the authoritative source expectation agree.

## Phase 2 delivery

Completed within the user's approved phase scope. Corrupted legacy exports now retain original source identifiers across deletion faults and allocate new identifiers only for injected duplicate rows. Corruption uses independently normalized clean inputs; duplicate identities/source IDs and non-synthetic inputs fail explicitly. Synthetic fault labels remain separate from agent inputs.

Added 32 tests covering both schemas, seeded random-state isolation, 1/3/1,000-fleet sizes, size limits, clean engineering consistency, revision/release/interface diversity, all ten faults per schema, source preservation and CLI exports in temporary directories. Refreshed schema A/B examples (39 records each), the matching corrupted revision example, canonical truth and labels. Added data/synthetic/README.md and updated the evidence-building script to retain the same three-fleet corruption source on regeneration.

Focused result: 32 passed. Full regression: 123 passed, 1 real-MongoDB test skipped. Ruff passed; Mypy passed on four scoped modules. Approval for Phase 3 is pending.

## Phase 3 delivery

Phase 3 was explicitly approved. Profiles now expose unit suffixes and relationship targets with detached samples. Mapping validation rejects unmapped fields, duplicate source assignments, unsupported unit operations, missing/inapplicable enum dictionaries and unsafe string coercion. All rows are validated, including values beyond the sampled examples.

Malformed structured responses now consume bounded attempts and escalate to review instead of escaping proposal validation or accepting an empty plan. Integer retry limits are restricted to 1–5. Detached provider inputs protect historical errors and source values; transformed nested values are copied. Provider exception messages remain redacted to exception class. Live prompts include a constrained transformation contract.

Added 48 focused tests, including both schemas across six entity types, failed-then-successful repairs, malformed output, timeout exhaustion, confidence/assumption gates, source/state isolation and a fake live-provider constructor/prompt boundary. Full regression: 171 passed, one real-MongoDB test skipped. Ruff and four-module scoped Mypy passed; app/agents.py additionally passed Mypy. No live LLM calls were made.

Pipeline version 1.2 separates cached jobs from the earlier mapping contract. README.md and docs/MAPPING.md record the implementation, evidence and limits. Approval for Phase 4 is pending.

The user explicitly authorized committing and pushing Phase 3 before any next phase. This delivery includes mapping/agent changes, 48 focused tests, documentation and local verification evidence. Phase 4 remains paused pending separate approval. The earlier workflow-only CI fix was already committed and pushed as bfdc93c.

## Phase 2 GitHub Actions failure investigation

The user reported the failed push for commit f068e31. Public GitHub API metadata identifies run 42374959108/job 128410552472: dependency installation, Ruff and Mypy passed; pytest failed, and benchmark/artifact steps were skipped. The full log endpoint returned HTTP 403 without repository-admin authentication; failure annotations contain only exit code 1. The exact failing traceback has been requested.

Exported the exact committed Phase 2 tree into an isolated ignored artifacts directory, preserving all uncommitted Phase 3 work. On installed Windows dependencies, its lint and type checks passed and pytest reported 123 passed, 1 real-MongoDB test skipped. This does not reproduce Linux CI or its enabled real database integration. Local diagnostic details are in artifacts/phase2-ci-diagnosis.json.

Improved CI with named steps, a MongoDB health check, a job timeout, resolved dependency output, pytest JUnit output and unconditional evidence upload. YAML parsing passed locally. No failing tests were disabled. No commit or push was performed, and Phase 4 approval remains pending.

The user subsequently supplied the traceback: 123 passed, 1 failed. The real MongoDB integration test failed on its initial ping with connection refused at localhost:27017; no migration assertions ran. The exact container readiness/lifetime/port cause is not established by that traceback. CI now uses the service's assigned host port at 127.0.0.1, adds a bounded runner-side ping before tests, and captures Docker inspect/log output on failure. A successful GitHub rerun remains unconfirmed.
