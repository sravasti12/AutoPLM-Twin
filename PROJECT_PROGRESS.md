# AutoPLM Twin implementation progress

All engineering data and behavior in this project are synthetic.

## Active delivery workflow

The user now requires phased delivery: finish and verify each phase, update README.md, then ask for explicit approval before starting the next phase. This supersedes the original autonomous phase progression. Existing code is retained as the baseline; approval checkpoints track subsequent review and development rather than claiming the code has not been built.

Current checkpoint: Phase 1 domain-model review recorded in README.md, with 4 focused tests passed. Awaiting explicit user approval before starting Phase 2 synthetic-data review. No Phase 2 work has started under this workflow.

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

- Python 3.13. Test run: **91 passed, 1 skipped**. The skipped check requires explicitly opted-in real MongoDB.
- Ruff: passed. Mypy: passed for models, mapping, constrained resolution and independent source adapter modules.
- Streamlit AppTest exercised all eight pages against FastAPI with a mongomock test database, including dataset generation, staged migration and simulation buttons.
- Benchmark executed: two schemas, two fleets/schema, three modes, 66 case evaluations. Mapping accuracy and pre-injection record correctness 100% in offline mode. Complete verification detected all ten injected fault types per schema. Schema-only modes detected zero deliberately schema-valid faults.
- Intrinsic rules detected 8/10, rules plus independent reconciliation 10/10, configuration twin comparison 9/10, behavior 5/10. Incremental twin detections beyond full rules: 0/10. No LLM benefit is claimed.
- Seven scenario traces and an additional runtime sensor-outage trace are saved under `benchmarks/scenarios/`.
- `benchmarks/test-results.xml`, `benchmarks/check-results.json`, `benchmarks/results.json` and `requirements-lock.txt` preserve reproducible evidence.
- Docker client exists, but the daemon pipe is unavailable. No local `mongod` executable was found. Real MongoDB integration was not run.
- Live structured LLM calls were not run; provider boundaries were tested with deterministic fake providers and exceptions. CI is defined but remote execution has not occurred.

## Feature acceptance matrix

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
