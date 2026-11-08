# AutoPLM Twin implementation progress

All engineering data and behavior in this project are synthetic.
## Latest verification update — 2026-11-08

The following results supersede older environment-blocker statements elsewhere in this document. Historical phase reports remain preserved as records of earlier verification.

### Confirmed results

- **Last complete unit-suite run:** 212 passed locally in 27.80 seconds at the Phase 2 checkpoint. This is historical evidence; the complete suite was not rerun for Phase 3A or 3B.
- **Phase 3B focused verification:** 39 new mechanical tests passed in 0.39 seconds; the final relevant regression run passed 224 tests in 6.21 seconds. Scoped Ruff and nine-module Mypy passed.
- **Phase 3A focused verification:** 87 passed in 1.01 seconds across graph, engineering/twin and migration tests, including 31 new graph cases. Scoped Ruff and two-module Mypy passed.
- **Latest MongoDB integration tests:** 6 passed locally in 4.16 seconds using real MongoDB and isolated test databases.
- **Focused migration tests:** 14 passed in 0.98 seconds; Ruff passed for `tests/unit/test_migration.py`.
- **Docker:** MongoDB service confirmed healthy through Docker Compose.
- **GitHub Actions:** Latest workflow reported successful after changing the CI runner from `ubuntu-24.04` to `ubuntu-22.04`.
- **Git:** Phase 3B changes are uncommitted; exact files are listed in its delivery section below. No commit or push was performed. Earlier clean-tree and delivery statements describe their historical checkpoints.

### Resolved blocker

The MongoDB 8.0 container previously failed to start in GitHub Actions because of a reported incompatibility with Linux kernels 6.19 and newer.

Changing the workflow runner to Ubuntu 22.04 resolved the observed CI failure in the latest run. This is an environment compatibility fix, not a modification to the application's engineering verification logic.

### Remaining verification work

- Live LLM provider calls have not yet been verified end-to-end.
- Phase 2 configuration-twin validation is complete. Broader simulation, remediation, dashboard and benchmark completeness reviews remain outside this phase; inspect existing coverage before any further development.
- Existing benchmark results remain historical evidence; no new benchmark execution is claimed.
- Production readiness, hardware validation, and vendor PLM integration are not claimed.

### Delivery policy

Continue development in small, explicitly approved tasks. Preserve completed functionality, use focused tests, and avoid unnecessary full-repository changes.

Documentation is part of the definition of done. After each meaningful checkpoint, synchronize README.md's public capabilities, architecture/workflow, safety behavior, technology purposes, setup and verified results with this tracker's detailed tasks, exact changed files, test evidence, bugs, limitations, remaining work, next step and Git status. Clearly distinguish implemented, tested, partial, planned and unverified work. Preserve historical information without presenting it as current verification; keep README.md capability-focused rather than adding a development diary. Review both documents at phase completion, and do not commit or push without explicit approval.

## Active delivery workflow

The user now requires phased delivery: finish and verify each phase, update README.md, then ask for explicit approval before starting the next phase. This supersedes the original autonomous phase progression. Existing code is retained as the baseline; approval checkpoints track subsequent review and development rather than claiming the code has not been built.

Current checkpoint: Phase 2 remains complete. Phase 3 Engineering Change Impact Intelligence includes completed/focused-tested Phase 3A Typed Engineering Dependency Graph and Phase 3B Mechanical Product Modelling. Proposals, impact workflows and UI/AI extensions remain pending separately approved tasks. Earlier build-phase numbering and verification counts remain historical.

## Phase 3B — Mechanical Product Modelling

**Status: Implemented and focused-tested (2026-11-08). Broader Phase 3 remains in progress.**

### Implementation and decisions

- Added typed `MechanicalPart` and `Assembly` records to the existing discriminated entity union and mapping/service/repository registries. Assemblies and subassemblies share one catalog type, with roles established by explicit BOM edges. Existing generated fixtures were not changed.
- Added `Bom.domain="mechanical"` and explicit `Variant.mechanical_bom_ids` applicability. Mechanical BOM roots/parents must resolve to assembly records; children may be mechanical parts, assemblies or existing ECU hardware. No applicability is inferred for unselected variants.
- Extended the Phase 3A builder rather than creating another graph engine. Mechanical nodes are explicit; legacy implicit assembly nodes remain BOM-scoped. Existing `configures` edges represent explicit variant/BOM selection with variant context; containment edges retain originating BOM, edge pointer, parent, child, quantity and revision. Mechanical change references retain the non-propagating `affects` annotation policy.
- Kept mechanical checks and product-structure extraction in `app/mechanical.py`. The common verifier dispatches mechanical checks alongside unchanged electronic compatibility checks. Detected missing/wrong-type roots/parents/children, catalog revision mismatch, duplicate edges/selections, empty/disconnected/cyclic structures, incorrect quantity roll-ups, lifecycle/effectivity errors and mechanical change approval/revision inconsistencies.
- Mechanical revisions are opaque, nonblank identifiers. Only equality with catalog/change expectations is evaluated; mechanical-only changes do not inherit the electronic alphabetic revision ordering convention. Shared component definitions under different parents are valid DAG relationships; weighted leaf quantities include every path. Duplicate same-parent/same-child edges remain invalid.
- Twins with explicit mechanical selections add version 1.1 `product_structure` containing selected BOMs, components/assemblies, relevant change records and graph provenance. Unresolved records remain unassessed placeholders; comparison uses precise component paths. Legacy snapshots remain version 1.0 with unchanged fingerprints. Empty new fields and the electronic domain default are omitted by serialization; four fingerprints captured before implementation are checked exactly.
- Mixed optional BOM/variant fields initially reached mapping review because the mapper attempted absent fields on legacy rows. The fix is constrained to missing canonical identity fields with declared optional defaults. Present values are retained; missing required fields, aliases and conversions still fail closed. Focused tests cover both default handling and retained checks.
- Registered `mechanical_parts` and `assemblies` with the existing publication reader/index mechanism and allowed the new kinds through the existing upload path. Pipeline version 1.4 prevents reuse of earlier verification results. No new API endpoint, what-if persistence, autonomous approval or promotion bypass was introduced.

### Actual verification

All commands used the existing `.venv` Python interpreter:

| Check | Command arguments after `python` | Result |
|---|---|---|
| New mechanical tests | `-m pytest tests/unit/test_mechanical.py -q --basetemp=.pytest_tmp/mechanical -p no:cacheprovider --tb=short` | **39 passed in 0.39 seconds** |
| Relevant regressions | `-m pytest tests/unit/test_mechanical.py tests/unit/test_dependencies.py tests/unit/test_engineering.py tests/unit/test_migration.py tests/unit/test_domain_mapping.py tests/unit/test_source_adapters.py tests/unit/test_mapping_workflow.py tests/unit/test_persistence_api.py tests/unit/test_traceability.py -q --basetemp=.pytest_tmp/mechanical-regressions -p no:cacheprovider --tb=short` | **224 passed in 6.21 seconds** |
| Scoped Ruff | `-m ruff check app/models.py app/mapping.py app/repository.py app/service.py app/impact_models.py app/mechanical.py app/dependencies.py app/verification.py app/twin.py tests/unit/test_mechanical.py` | Passed |
| Scoped Mypy | `-m mypy app/models.py app/mapping.py app/repository.py app/service.py app/impact_models.py app/mechanical.py app/dependencies.py app/verification.py app/twin.py` | Passed on **nine source modules** |

New tests cover model schemas, nonfinite/invalid mass and quantities, assembly/subassembly structure, reference/revision defects, cycles/duplicates, variant selection, shared-part roll-ups, graph provenance and reverse discovery, missing-node placeholders, deterministic mechanical snapshots, precise revision differences, mechanical change references, mixed-product source/restoration/promotion safeguards and four unchanged legacy fingerprints. The initial mixed-upload failure was diagnosed and fixed as described above; no test was disabled. Scoped formatting/type-annotation issues were corrected. Full-suite, real MongoDB integration, dashboard, benchmark and live LLM runs were not performed for this task; prior counts remain historical.

### Exact files changed

- Created: `app/mechanical.py`, `tests/unit/test_mechanical.py`.
- Modified: `app/models.py`, `app/mapping.py`, `app/impact_models.py`, `app/dependencies.py`, `app/verification.py`, `app/twin.py`, `app/repository.py`, `app/service.py`, `README.md`, `PROJECT_PROGRESS.md`.
- Registry changes in mapping/upload/publication are necessary to carry the new records through existing migration safeguards. Existing source adapters work through the extended Dataset model without modification. Existing tests/fixtures, API, UI, CI and dependencies were not changed. No commit or push was performed.

### Limits and remaining work

- This is declared product-structure integrity, not CAD/physics or a mechanical compatibility solver. There are no inferred geometry, fit, mounting, material, strength, load or safety rules. Optional mass is metadata only; mass roll-up is not implemented.
- Repeated component definitions across parents are supported; distinct occurrence identities and placement/effectivity ranges are not. The existing fixed verification as-of date remains 2025-06-01; graph traversal itself is not effectivity-filtered.
- Mechanical migration/promotion was tested with mongomock. Real MongoDB integration of the new collection kinds is unverified in this task. No user-facing mechanical UI or dedicated impact API exists.
- What-if proposals, automatic changes/approvals and Agentic AI are not implemented. Existing source-restoration review remains unchanged and must not be described as general engineering change authorization.
- Recommended next small task, subject to approval: design the isolated what-if assessment contract over the mixed mechanical/electronic graph, including baseline hashes, constrained edits and explicit rule/twin differences, before persistence or UI work. Do not start that work automatically.

## Phase 3A — Typed Engineering Dependency Graph

**Status: Implemented and tested (2026-11-08). The broader Phase 3 remains in progress.**

### Implemented contract and builder

- Added frozen Pydantic contracts for the six existing engineering entity kinds, BOM-scoped derived assembly nodes, typed relationships, provenance, resolution diagnostics and potential-impact paths. Unknown nodes preserve unresolved identities without pretending to resolve them.
- Added a pure NetworkX MultiDiGraph builder over existing normalized records. Parallel relationship types and variant-specific software bindings retain distinct deterministic edge keys.
- Provenance identifies the originating record/kind, normalized-record JSON pointer, and applicable variant, platform or BOM context. BOM edges retain parent/child, quantity and revision evidence. No source records are modified.
- Relationship types: `bom_root`, `contains`, `based_on`, `installs`, `runs`, `configures`, `requires`, `released_under`, `declares_compatible`, `applicable_to`, `allows_platform`, `communicates_with` and `affects`.
- Explicit references are distinguished from derived assembly nodes, configuration shortcuts and reverse representations of network pairs. Assembly identities are scoped to their BOM to avoid accidental merging across BOMs.
- Detected dangling/wrong-type references, duplicate record identities, repeated ambiguous bindings/BOM occurrences/network pairs, assembly/record identity collisions, unrooted BOM context and structural dependency cycles. Ambiguous identities never select an arbitrary duplicate record.
- Added deterministic reverse BFS with depth/result bounds, truncation reporting and a shortest explanatory edge path per node/variant context. Variant context prevents a software binding from propagating through another variant's installation of the same ECU. Cycles terminate through visited-state tracking.

### Architectural decisions and limitations

- Propagating edges use **dependent -> dependency** direction. Reverse traversal reports potentially exposed dependents, not proven failures, compatibility or approval. Every edge's engineering assessment remains `unassessed`; resolved means only that a reference has a supported, unambiguous target.
- Compatibility declarations, platform applicability/allowlists, communication and change annotations remain traceable but do not automatically propagate structural impact. The stored network pair is represented in both directions without inventing signal-flow behavior.
- Feature/function names are not first-class typed record references and are explicitly reported as unassessed. Unsupported entity schemas/fields are diagnosed rather than silently treated as supported records. Invalid/ambiguous links are retained but excluded from propagation.
- Graph serialization, insertion and traversal are deterministic for reordered input records. Provenance retains original list indices, so reordering relationship lists may legitimately change their evidence pointers. Topology is frozen after construction; this is not a persisted or signed graph snapshot.
- No variant-to-BOM applicability, physical compatibility or effectivity-filtered impact is inferred. The existing verifier remains authoritative for engineering rules; this graph does not replace it. No migration gate, twin implementation or fingerprint algorithm was modified.
- Mechanical parts, isolated what-if proposals, graph persistence, impact-report services, API/UI integration and agentic changes are **not implemented in Phase 3A**. No complete impact-intelligence workflow is claimed.

### Verification

| Command using the existing `.venv` Python | Actual result |
|---|---|
| `-m pytest tests/unit/test_dependencies.py -q --basetemp=.pytest_tmp/graph -p no:cacheprovider --tb=short` | Initial graph implementation: 28 passed in 0.22 seconds |
| `-m pytest tests/unit/test_dependencies.py tests/unit/test_engineering.py tests/unit/test_migration.py -q --basetemp=.pytest_tmp/graph-regression -p no:cacheprovider --tb=short` | Final combined run: **87 passed in 1.01 seconds**, including all 31 graph cases |
| `-m ruff check app/impact_models.py app/dependencies.py tests/unit/test_dependencies.py` | Passed |
| `-m mypy app/impact_models.py app/dependencies.py` | Passed on two modules |

Focused coverage includes entity/edge types, parallel relationships, provenance, explicit/derived distinctions, dangling and ambiguous references, software/BOM cycles, deterministic paths, variant-context isolation, traversal bounds, unassessed semantics, BOM scoping and unchanged twin fingerprints/source inputs. Existing engineering/twin and migration tests passed in the same run. Initial formatting/type-annotation findings in the new modules were corrected; no functional test failure was suppressed. The full unit suite, MongoDB integration, benchmarks, UI and live LLM checks were not rerun for this pure internal graph task.

### Exact files and next task

- Created: `app/impact_models.py`, `app/dependencies.py`, `tests/unit/test_dependencies.py`.
- Modified: `PROJECT_PROGRESS.md` only among existing files. Existing models, fixtures, verification, service, twin, persistence, API, dashboard, dependencies and CI remain unchanged.
- README.md is unchanged because no new application-facing workflow has been completed. Its earlier suggested simulation direction is superseded by the approved Phase 3 direction recorded here; public impact capability documentation should accompany an integrated capability.
- Recommended next small task, subject to approval: review/design explicit mechanical-part and variant-to-BOM applicability contracts against this graph, without yet implementing proposals or UI. Mechanical extensions and all other Phase 3 steps remain pending.
- No commit, push or subsequent task was started.

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

**Status: Completed (2026-11-08). Implementation and local verification are complete, as confirmed by the user. Publication requires separate approval.**

This section follows the current Digital Twin Validation task name; the older synthetic-data Phase 2 delivery below remains a separate historical checkpoint.

### Completed
- Constructed source and target configuration twins containing platform/variant data, ECU hardware/software, topology, related BOM/change data and initial states.
- Identified an ECU-ordering sensitivity in digital twin fingerprint generation.
- Added a regression test for semantically equivalent ECU configurations.
- Canonicalized installed ECU ordering without modifying source records.
- Confirmed that equivalent ECU configurations generate identical fingerprints.
- Matched ECU nodes by identifier for recursive comparison; ignored the derived fingerprint when reporting configuration differences.
- Verified precise hardware revision difference reporting at `/nodes/<ECU_ID>/hardware/hardware_revision`. Corrected misplaced ordering assertions in the engineering tests; the focused engineering run passed 38 tests in 0.14 seconds at that checkpoint.
- Existing regressions also verify precise software version differences, added/removed ECU node evidence and fail-closed handling of missing software configuration. Their test names are recorded below; no additional focused test count is inferred from the earlier 38-test checkpoint.
- Confirmed duplicate engineering identities are reported before ID-based lookups collapse records. Earlier focused regression checks covered both duplicate orderings, migration rejection and fresh promotion validation; no production safety-gate fix was needed.
- Added three migration-safety regression tests using the existing generated datasets and service fixture:
  - `test_incompatible_software_blocks_approval_even_when_source_and_target_twins_match`: revision-incompatible brake software produces `HW_SW_REVISION` findings and rejection even with equal source/target twins.
  - `test_genuine_twin_difference_independently_blocks_promotion`: compatible target-only version drift produces actual `/nodes/<ECU_ID>/software/version` differences and fails validation. A test-scoped override omits reference reconciliation while retaining real engineering rules and real twin construction/comparison, proving twin differences independently block promotion.
  - `test_compatible_software_version_change_with_updated_source_expectation_is_approved`: a compatible release supplied in the source before ingestion passes engineering checks, exact source/target comparison and promotion. Captured source records are not modified.
- Added `assert_fresh_validation_blocks_cached_approval`, used by both rejection tests: even a forged cached `verified` status, cached passing result and matching staging digest cannot bypass fresh validation. No software records are published.
- Preserved all production validation/promotion gates and public interfaces; this migration-safety task required test changes only.

### Regression coverage

In addition to the three migration-safety tests named above, the completed phase includes these existing checks in `tests/unit/test_engineering.py`:

- `test_twin_equality_and_semantics`: identical configurations compare equal and changed software content is detected.
- `test_twin_equivalent_when_installed_ecu_order_changes`: equivalent ECU ordering preserves fingerprint and comparison equality.
- `test_twin_reports_precise_hardware_revision_difference` and `test_twin_reports_precise_software_version_difference`: exact ECU-level paths and before/after values.
- `test_twin_reports_removed_ecu` and `test_twin_reports_added_ecu`: whole-node differences with the absent side represented by `None`.
- `test_missing_software_configuration_is_rejected`: missing installed software produces `COMPATIBILITY_UNKNOWN`.
- `test_duplicate_identity_is_reported_even_when_lookup_shadows_a_record`: duplicate findings survive both conflicting-record orderings.

Existing migration checks for tampered staging, duplicate engineering identities, approval/manifests and source preservation remain in place. The latest complete unit run below includes these tests; no separate new run is claimed here.

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
- Phase 2 closure documentation: **only `README.md` and `PROJECT_PROGRESS.md`** changed in this request. README now has a dedicated Digital Twin Validation section, completed status, ECU presence/difference semantics and an explicit fresh-promotion gate in the architecture. Production code, tests and saved reports were untouched. The migration regression implementation belongs to the preceding task; its test file is unchanged in the current working tree. No commit or push was performed.

### Engineering decisions

- Canonicalize installed-ECU ordering, not every list or every graph-equivalent representation. Fingerprints summarize snapshots; comparison examines actual content instead of treating the hash itself as engineering evidence.
- Report added/removed nodes at the ECU identifier path, with the absent side `None`. Presence detection does not approve the added ECU's engineering compatibility.
- Keep engineering findings and twin differences independent: either prevents validation success. Duplicate safety remains enforced by the deterministic verifier before lookups collapse identities.
- Preserve exact source expectations. The compatible-release regression updates the expected source before ingestion; it does not mutate captured provenance or introduce an approval policy for target drift.
- Preserve digest checks, human authorization, fresh promotion validation and publication manifests. The twin-only regression isolates reference reconciliation in the test only; production gates remain unchanged.

### Next phase and remaining work

- **Recommended next phase: Phase 3 — Deterministic Behavioral Simulation Validation** under the current delivery numbering. This is a proposed next scope, distinct from the older schema-mapping Phase 3 checkpoint below; it has not started.
- First small task, subject to approval: inspect the existing SimPy model and scenario tests, identify actual gaps, and propose focused coverage without recreating completed simulation work.
- Candidate follow-up tasks: verify modeled ECU initialization/state transitions, deterministic event ordering and repeatable traces; inspect interface-failure and runtime sensor-outage coverage; document signal/timing assumptions and confirm simulation cannot bypass engineering approval. Implement only approved gaps.
- A migration-level missing-required-ECU regression remains optional future hardening after checking existing coverage, not an outstanding prerequisite for the completed Phase 2.
- No new phase, commit or push is authorized by this documentation update. Broader simulation acceptance, live integrations and production readiness remain outside this phase's completion claim.

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
