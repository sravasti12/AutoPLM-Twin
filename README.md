# AutoPLM Twin

**Agentic Automotive PLM Migration with Digital Twin-Based Engineering Verification**

A functioning Python engineering prototype for migrating **fictional, synthetic** vehicle engineering data. A record can satisfy a database schema while assigning incompatible software to an ECU. AutoPLM Twin preserves the source, stages transformations, checks engineering constraints, compares vehicle configuration twins, and exposes explicit human approval controls.

This project has no Teamcenter, Windchill, supplier, CAN hardware or production vehicle integration. Its signal simulation is a documented behavioral prototype, not validated vehicle physics.

## Phased delivery and approval

**Current status: Phase 1 and Phase 2 are complete. Phase 3 Engineering Change Impact Intelligence is in progress; Phase 3A Typed Engineering Dependency Graph, Phase 3B Mechanical Product Modelling and Phase 3C in-memory Isolated What-if Assessment are implemented and focused-tested.**

Further implementation, commits and pushes require separate approval. Earlier publication approvals and build-review checkpoints are historical.

### Verified Phase 1 foundation

- **Engineering domain:** versioned schemas for ECU hardware/software, vehicle platforms/variants, multi-level BOMs and engineering changes; explicit lifecycle states, relationship identifiers, date validation and numeric software-version comparison.
- **Synthetic source data:** reproducible A/B legacy schemas, configurable dataset sizes, hardware/software compatibility constraints, separate canonical/mapping truth and fault labels, and preservation of surviving source identifiers in corrupted exports.
- **Mapping and transformation:** field profiling, an offline dictionary baseline, bounded LangGraph proposal/repair/review states, structured mapping validation and allowlisted transformations. Source reconciliation uses an independent adapter; no generated code is executed. Live LLM providers exist but remain unverified end-to-end.
- **Migration and persistence:** PyMongo source capture, staging, idempotent jobs, source provenance checks, record validation, audit history, controlled promotion and approved-publication integrity checks. Real MongoDB integration covers both legacy schemas, idempotency, promotion, indexes, corruption rejection and API/report reads.
- **Engineering safety and access:** deterministic BOM, compatibility, variant, dependency, interface, release and change checks; duplicate identity detection; FastAPI endpoints and JSON/CSV/HTML reports. Existing dashboard workspaces have unit coverage through Streamlit AppTest with a mocked-database backend; that does not establish a live dashboard-to-MongoDB acceptance result.

### Phase 2 Digital Twin Validation — completed

Completed and locally tested:

- Construct source and migrated configuration twins containing installed ECUs, hardware, software, topology and related engineering data.
- Canonicalize installed-ECU ordering without changing source records, so equivalent ordering produces the same fingerprint.
- Report genuine ECU differences at precise paths, including `/nodes/<ECU_ID>/hardware/hardware_revision` and `/nodes/<ECU_ID>/software/version`.
- Detect added and removed ECUs at `/nodes/<ECU_ID>`; report missing installed software as an engineering compatibility finding.
- Reject incompatible software even when source and target twins match; reject genuine twin differences independently of engineering findings.
- Revalidate before promotion, so a forged cached passing result, `verified` status and matching staging digest cannot bypass the safety gates.
- Accept a compatible software release when the expected source is updated before ingestion and all engineering/comparison checks pass. Target-only version drift remains rejected; no selective-delta approval policy is implemented.

Verification boundaries and next phase:

- Phase 2 is complete; further scenario hardening, including a migration-level missing-required-ECU regression, is optional follow-up work after checking existing coverage.
- The approved next direction is Engineering Change Impact Intelligence, beginning with the typed graph foundation documented below. Existing fictional SimPy scenarios remain a separate prototype; no new simulation capability or simulation-phase completion is claimed.
- The new service regressions use mongomock; the six real MongoDB integration checks are separate and do not cover every new scenario end-to-end. Live LLM behavior and production PLM/hardware integration remain unverified.
- Latest local evidence: **14 migration tests passed, 212 unit tests passed, 6 real MongoDB integration tests passed**, and Ruff passed on the modified migration test file. See Verification below for scope; no new benchmark or remote CI run is claimed.

The existing baseline already contains code for all eleven phases. The original build-review checkpoints below are preserved as historical context; they do not authorize new work or supersede the current focused milestone. Current implementation and verification qualifications are recorded in [PROJECT_PROGRESS.md](PROJECT_PROGRESS.md).

For each phase: inspect and implement its scope, run relevant checks, update this README with changes, actual results and blockers, then request your approval. Work on the next phase starts only after your explicit approval. This replaces the earlier autonomous execution workflow.

| Phase | Scope | Current delivery checkpoint |
|---|---|---|
| 1 | Engineering domain models | Reviewed and tested; continuation approved |
| 2 | Synthetic datasets and isolated ground truth | Completed and tested; continuation approved |
| 3 | Profiling, schema mapping and LangGraph agents | Completed and tested; awaiting approval to continue |
| 4 | MongoDB migration, provenance, staging and API | Next; awaiting approval to start |
| 5 | Deterministic engineering verification | Awaiting phased review |
| 6 | Configuration twins and behavioral simulation | Awaiting phased review |
| 7 | Agent-assisted repairs and human approval | Awaiting phased review |
| 8 | Streamlit engineering dashboard | Awaiting phased review |
| 9 | Fault injection and reproducible benchmarks | Awaiting phased review |
| 10 | Automated tests, lint, typing and CI | Awaiting phased review |
| 11 | Documentation and final acceptance report | Awaiting phased review |

### Phase 1 checkpoint: engineering domain models

- Existing implementation: `app/models.py` defines schema version 1.0 for ECU hardware, ECU software, vehicle platforms, vehicle variants, multi-level engineering BOMs and engineering changes, plus structured validation findings.
- Models preserve relationship identifiers, lifecycle/release states, revisions and dates. Software versions use semantic numeric comparison through `packaging.version.Version`; masses and BOM quantities reject nonfinite values, and quantities must be positive.
- Verification at this checkpoint: **4 tests passed** covering software-version validation and rejection of NaN/infinite hardware masses, source masses and BOM quantities. Earlier full-suite evidence remains available separately; this checkpoint did not rerun the entire suite.
- No code changes were needed for this historical checkpoint. Domain-model checks require neither MongoDB nor a live LLM. Real MongoDB integration has since passed separately; live LLM integration remains unverified.

Reproduce this checkpoint:

```powershell
python -m pytest tests/unit/test_domain_mapping.py::test_models_and_versions tests/unit/test_source_adapters.py::test_nonfinite_engineering_values_rejected -q
```

Phase 1 continuation was explicitly approved before Phase 2 began.

### Phase 2 checkpoint: synthetic datasets and isolated ground truth

- Reviewed both fictional legacy schemas, seeded reproducibility, releases 2.10.0/3.0.0, revisions B/C, four ECU functions, two suppliers, two trims per platform, multi-level BOMs and engineering changes.
- Verified configurable sizes from 1 through 1,000 fleets (13–13,000 records), unique engineering/source identities, canonical normalization and clean engineering relationships. The local random-number generator leaves global random state unchanged.
- Fixed corrupted-data exports to preserve surviving source IDs rather than renumbering them after deletions. Injected duplicates receive distinct source IDs while retaining their duplicated engineering identity. Ambiguous and non-synthetic inputs are rejected.
- Corruption now uses the independent source adapter rather than migration mapping execution. Tested all ten faults under both schemas. Input envelopes contain no fault labels; separately exported labels explicitly identify themselves as synthetic.
- Refreshed the three-fleet examples and separate canonical/mapping truth, plus a corrupted revision example derived from schema A. See the [dataset guide](data/synthetic/README.md). Architecture follows controlled templates; seed variation affects suppliers and masses.
- Verification: **32 focused Phase 2 tests passed**; **123 passed, 1 skipped** across the full regression suite. Ruff and scoped Mypy passed. CLI tests exercised both schemas in isolated temporary directories.
- Historical evidence: `benchmarks/phase2-tests.xml`, `benchmarks/test-results.xml` and `benchmarks/check-results.json`. The real MongoDB test was skipped at that checkpoint; six real MongoDB integration tests have since passed separately. Synthetic-data checks require neither a database service nor a live LLM.

Reproduce Phase 2:

```powershell
python -m pytest tests/unit/test_synthetic_data.py -q --junitxml=benchmarks/phase2-tests.xml
python scripts/check.py
python -m app.cli generate --fleets 3 --seed 42 --source A --output data/synthetic/legacy_A.json
python -m app.cli generate --fleets 3 --seed 42 --source B --output data/synthetic/legacy_B.json
python -m app.cli inject data/synthetic/legacy_A.json --fault unsupported_hardware_revision --output data/synthetic/corrupted_revision.json
```

Phase 2 continuation was explicitly approved before Phase 3 began.

### Phase 3 checkpoint: profiling, schema mapping and LangGraph agents

- Enriched profiles with gram/kilogram suffix hints and known relationship targets; detached example values so providers cannot mutate source rows through profiles.
- Tightened executable mapping validation: every source field must be accounted for, source/target assignments must be unambiguous, gram-to-kilogram conversions must match units/targets, text transformations require string inputs, and enum dictionaries must be explicit and applicable. Silent field omission and accidental numeric-to-string coercion are rejected.
- Hardened the LangGraph proposal node to schema-validate provider responses within the bounded retry loop. Malformed responses and provider exceptions reach review after at most the configured 1–5 attempts. Transient failures can recover, with earlier error evidence retained. Invalid entities and empty source sets fail before provider invocation.
- Providers receive detached profiles/errors; transformations return detached nested values. Assumptions require review, and self-reported confidence never overrides executable checks. Live prompts include the transformation contract and prior errors.
- Bumped pipeline version to 1.2 so stricter mapping checks do not reuse earlier cached job results. See the [mapping contract and state workflow](docs/MAPPING.md).
- Verification: **48 focused Phase 3 tests passed**; **171 passed, 1 skipped** in the full regression suite. Ruff and scoped Mypy passed; the agent module also passed an additional type check. Evidence is in `benchmarks/phase3-tests.xml`, `benchmarks/test-results.xml` and `benchmarks/check-results.json`.
- The live provider boundary was checked with a fake client. No live LLM call was made. Six real MongoDB integration tests have since passed separately; those results do not verify a live LLM mapping session.

Reproduce Phase 3:

```powershell
python -m pytest tests/unit/test_mapping_workflow.py -q --junitxml=benchmarks/phase3-tests.xml
python scripts/check.py
python -m mypy app/agents.py
```

The historical next-step request at this checkpoint was the MongoDB/migration/API review. Current delivery status is the Phase 2 Digital Twin Validation summary above; this historical roadmap does not authorize additional work.

## Architecture

```mermaid
flowchart TD
    A[Seeded legacy JSON A / B] --> B[Immutable source capture and profiling]
    B --> C[LangGraph mapping / bounded repair / review]
    C --> D[Allowlisted deterministic transformations]
    D --> E[MongoDB staging]
    B --> F[Independent versioned source adapter]
    E --> G[Engineering rules and reconciliation]
    F --> G
    F --> H[Source configuration twin]
    E --> I[Target configuration twin]
    H --> J[Structural and semantic comparison]
    I --> J
    I --> K[SimPy fictional ECU state machines]
    G --> L[Verification gate]
    J --> L
    L --> M[Human promotion request]
    M --> R[Staging digest and fresh validation]
    R --> S[Approved publication manifest]
    G --> N[Constrained repair proposal]
    N --> O[Candidate verification and twin reconstruction]
    O --> P[Human decision and staging revision]
    P --> G
    E --> Q[FastAPI / Streamlit / audit exports]
    K --> Q
```

The LLM proposes structured mappings and source-referenced repair actions. The system never executes generated code. LangGraph tracks attempts, errors, profiles and history; failed proposals reach a human review queue after at most three attempts. Offline mode uses a versioned dictionary through the same graph. Confidence is explicitly uncalibrated.

Independent deterministic rules verify BOM graphs, hardware/software allowlists and revisions, platform applicability, features, interfaces, dependencies, lifecycle and engineering changes. Reconciliation compares target values against a separate source adapter, so an agent cannot certify its own incorrect transformation. Unknown installed compatibility is critical.

The configuration twin includes software, hardware, network edges, related BOMs and changes. SimPy models fictional speed sensor → gateway → brake/cluster interactions and runtime sensor loss. Structural BOM errors remain engineering findings without invented physical behavior. See [engineering assumptions](ENGINEERING_ASSUMPTIONS.md).

## Digital Twin Validation

For each source vehicle variant, the migration service constructs a source twin from the independently normalized source snapshot and a target twin from staging. Each twin includes the platform, variant, installed ECU identities, hardware records/revisions, installed software/releases, network topology, related BOMs and engineering changes, plus initial ECU states. These are synthetic configuration snapshots, not live telemetry or vehicle-physics models.

Twin construction copies the variant and sorts installed ECU identifiers before building its nodes. SHA-256 over the snapshot's JSON representation with sorted dictionary keys supplies a reproducible fingerprint. Changing only installed-ECU order therefore leaves the fingerprint unchanged, without modifying the source variant. This is a defined normalization rule, not general graph-isomorphism or normalization of every list in the snapshot.

Comparison ignores the derived fingerprint and compares actual configuration content. ECU nodes are matched by identifier and examined recursively, producing source/target evidence at stable paths:

| Change | Difference path | Evidence |
|---|---|---|
| Hardware revision | `/nodes/<ECU_ID>/hardware/hardware_revision` | Original and migrated revision |
| Software version | `/nodes/<ECU_ID>/software/version` | Original and migrated version |
| Added ECU | `/nodes/<ECU_ID>` | Source is `null`; target contains the new node |
| Removed ECU | `/nodes/<ECU_ID>` | Source contains the node; target is `null` |

Detecting a new ECU does not certify its engineering compatibility. Independent rules check required ECUs, hardware/software allowlists, supported revisions, interfaces, release states and dependencies. Duplicate identities are reported before ID-based lookups can collapse records; missing software assignments produce compatibility findings.

Migration validation passes only when **both engineering findings and twin differences are empty**. Equal source and target twins cannot excuse incompatible source engineering. Conversely, genuine twin differences can reject a migration even when intrinsic engineering rules pass; unit regression coverage isolates this twin gate while leaving real twin construction/comparison active.

The software update scenarios preserve this distinction:

- **Incompatible release:** brake software requiring revision C on revision B hardware produces `HW_SW_REVISION` findings and rejection, even when source and target twins match.
- **Compatible expected release:** supplying a compatible release in the source before ingestion permits migration and promotion when all engineering checks pass and the target matches that source expectation.
- **Compatible but unexpected target drift:** changing only the staged version remains a source-preservation violation and a twin difference. No policy authorizing selected source/target deltas is implemented.

Promotion independently checks the staging digest and reruns validation with `persist=False` before publication. A cached passing result or forged `verified` status cannot authorize incompatible or divergent staging, even if the cached digest matches. Human authorization and the existing publication-manifest checks remain required. The simulation subsystem supplies separate diagnostic evidence and does not replace these gates.

Phase 2 verification is included in the **212 passing unit tests** and **14 passing migration tests** recorded below. The **6 passing real MongoDB integration tests** are a separate suite; they do not imply that every new twin regression ran against real MongoDB. See [PROJECT_PROGRESS.md](PROJECT_PROGRESS.md) for the individual regressions, exact commands and limitations.

## Typed Engineering Dependency Graph — Phase 3A

`app/impact_models.py` defines frozen Pydantic graph contracts; `app/dependencies.py` builds an in-memory NetworkX `MultiDiGraph` from existing normalized engineering records. Parallel edges preserve different relationship meanings and variant-specific bindings between the same entities. The builder does not modify input records, existing ECU twins, fingerprints or migration/promotion gates. Graph topology is frozen after construction.

**Supported nodes:** hardware, software, platform, variant, BOM and engineering change records; Phase 3B adds mechanical-part and explicit assembly records. Legacy implicit BOM assemblies remain derived nodes scoped by BOM identifier. Unknown nodes retain dangling or unsupported identities without pretending they are supported engineering records.

| Relationship types | Representation and traversal policy |
|---|---|
| `bom_root`, `contains` | BOM-to-root and assembly-to-component dependencies |
| `based_on`, `installs` | Variant-to-platform and variant-to-installed-hardware dependencies |
| `runs`, `configures` | Variant-scoped hardware/software binding, derived software shortcut, and explicit mechanical BOM selection |
| `requires`, `released_under` | Software dependencies and engineering-change release reference |
| `declares_compatible` | Declared software allowlist; does not establish compatibility or propagate structural exposure |
| `applicable_to`, `allows_platform` | Applicability/allowlist references; no automatic structural propagation |
| `communicates_with`, `affects` | Network connections and change annotations; no automatic structural propagation |

**Explicit and derived evidence.** Explicit edges correspond to references or bindings present in records. Derived structures include BOM assembly nodes, variant/software shortcuts and the reverse representation of a stored network pair. Both network directions are represented without claiming signal-flow direction. Origin labels are retained so derived evidence cannot be confused with an independently declared engineering relationship.

**Provenance.** Every node and edge identifies its originating record and kind, with a JSON pointer into that normalized record. Relationship context retains the applicable variant, platform or BOM; BOM-edge evidence includes parent, child, quantity and revision. Edge keys are deterministic hashes of the typed relationship evidence, so parallel edges retain separate provenance. These references are not persisted database snapshots or signed audit records.

**Reverse traversal and explanations.** Propagating edges use **dependent -> dependency** direction. A bounded reverse breadth-first search discovers potentially exposed dependents, returning a deterministic shortest witness per node/variant context. Each witness contains the actual typed edges and their provenance, ordered from dependent toward the changed entity—for example, brake ECU -> brake software -> gateway software. Construction and traversal remain deterministic when the input record list is reordered; original relationship-list indices remain part of the evidence.

**Variant-context isolation.** Software installation bindings carry their originating variant. Traversal retains that context instead of propagating through another variant's installation of shared hardware. A changed hardware record can still expose multiple variants that explicitly install it.

**Diagnostics and bounds.** The builder reports structural dependency cycles, dangling and wrong-type references, duplicate identities, ambiguous/repeated bindings, BOM assembly identity collisions, unrooted BOM context and unsupported schemas. Unknown feature/function relationships are explicitly unassessed. Ambiguous identities do not select an arbitrary record, and unresolved/ambiguous links do not propagate impact. Visited node/context states prevent cycle loops. Default limits are depth **20** and **1,000 result entries**, configurable as positive integers; hitting a limit sets `truncated=True`. Result entries represent node/context witnesses, not necessarily distinct record IDs. Diagnostics accompany traversal results so incomplete assessment is visible.

**Potential engineering exposure is not compatibility, safety approval or automatic change authorization.** A resolved edge means its reference is supported and unambiguous; its engineering assessment remains `unassessed`. Traversal reports `potential_only`. Connectivity does not establish that a component fits, communicates correctly or is safe. Existing deterministic verification, source-preservation checks and human promotion controls remain authoritative. Phase 3B supplies explicit variant-to-mechanical-BOM selection; absent applicability links and effectivity-filtered impact are not inferred.

Phase 3A verification passed **87 focused tests**, including **31 new graph cases** and existing engineering/twin/migration regressions; scoped Ruff and Mypy passed. This is not a new full-suite or real-MongoDB verification result. Details are in [PROJECT_PROGRESS.md](PROJECT_PROGRESS.md).

**Future work:** graph/proposal persistence, dedicated impact API/UI and Agentic AI integration are not implemented. Phase 3C provides the in-memory assessment described below; existing application APIs do not expose it.

## Mechanical Product Modelling — Phase 3B

The existing product model now supports mechanical parts and explicit assemblies/subassemblies alongside ECUs. Assemblies use the same type at each level; their parent-child roles are declared by the BOM.

| Contract | Explicit data |
|---|---|
| `MechanicalPart` (`mechanical_part`) | Identity, part number, revision, lifecycle and optional positive finite mass in kilograms |
| `Assembly` (`assembly`) | Identity, part number, revision and lifecycle |
| Mechanical BOM | `domain="mechanical"`, an explicit assembly root, parent-child edges, positive quantities, child revisions, effectivity and expected leaf quantity |
| Vehicle variant | `mechanical_bom_ids` selects the applicable BOMs; applicability reaches components through their declared assembly structure |

Mechanical BOMs resolve parents to explicit assembly records and children to assemblies, mechanical parts or existing ECU hardware. Shared component definitions may occur under different parents; quantity roll-ups multiply quantities along paths. Duplicate parent-child pairs are rejected, so repeated occurrences under one parent must use an aggregated quantity. The Phase 3A graph retains BOM-edge provenance, explicit variant selections and deterministic reverse paths from a part through subassemblies/BOMs to applicable variants. It does not guess applicability from a shared part number or vehicle layout.

Mechanical integrity checks live in `app/mechanical.py`, separately from electronic compatibility rules. They detect dangling/wrong-type references, catalog revision mismatches, duplicate edges/selections, cycles, unrooted structure, empty BOMs, incorrect quantity roll-ups, lifecycle/effectivity conflicts and inconsistent mechanical change references. Revisions are opaque catalog identifiers; no numerical or alphabetic ordering is invented for mechanical-only changes. The existing default engineering as-of date remains 2025-06-01.

For an explicitly selected mechanical BOM, `build_twin()` adds a version 1.1 `product_structure` containing components, assemblies, BOMs, related changes and typed relationship evidence. Unknown references remain visible as unassessed placeholders. Recursive comparison reports changes such as `/product_structure/components/<PART_ID>/revision`. Unselected mechanical BOMs do not leak into an ECU-only variant's snapshot.

Legacy electronic BOMs retain their implicit assembly representation. Empty mechanical selections and the default electronic BOM domain are omitted from serialization, preserving existing ECU-only snapshots and version 1.0 fingerprints. Four pre-extension fingerprint values are checked by regression tests. The existing migration path registers the two new record kinds, uses pipeline version 1.4, and retains source reconciliation, repair review, digest checks and fresh promotion validation. Missing optional canonical identity fields may use declared schema defaults; present values, aliases, conversions and required fields are not silently discarded.

**Verification:** 39 new mechanical tests passed. A relevant nine-file graph/engineering/migration/mapping/provenance regression run passed **224 tests**. Scoped Ruff passed and Mypy passed across nine changed source modules. Mixed-product migration, restoration and promotion were exercised with the existing mongomock service fixture; new collection integration against real MongoDB was not rerun. These results do not replace the historical complete-unit-suite count below.

This is structural engineering modelling, not CAD, physics or proof of mechanical fit. Mass is optional metadata; no mass roll-up, strength, material, geometry, mounting, load or safety-compatibility rules are claimed. Phase 3B introduced no new UI or automatic approval. Phase 3C adds isolated assessment below.

## Isolated What-if Assessment — Phase 3C

`app.what_if` provides typed, in-memory engineering proposals and deterministic assessment over the existing mechanical and electronic models. A proposal records its identifier, creator, timezone-aware timestamp, baseline reference and SHA-256 digest, optional job/product/variant context, evidence, and explicit add/replace/remove operations. Replacements supply complete typed records; identity and entity kind cannot change. Multiple independent record operations can be assessed together, including part/BOM revisions and variant software assignments.

`baseline_digest(records)` canonicalizes model defaults and record order. `assess(proposal, records)` checks that digest before applying edits to independent copies. Stale baselines produce a `stale` result without a candidate snapshot. Successful execution produces an `assessed` result with a proposed snapshot and report; this status means assessment execution, not engineering acceptance. `discard(result)` returns a discarded copy without candidate/report payload, leaving the baseline and previous result untouched. There is no persistent proposal lifecycle or secure deletion guarantee.

Reports include directly added/removed/modified records, original/proposed twins and precise differences, baseline/proposed engineering findings, graph diagnostics, and reverse dependency paths with relationship provenance from both configurations. Comparing both graphs retains removed relationships as evidence. Every variant is compared, even when a proposal specifies a narrower context, so shared components cannot hide exposure. Graph traversal retains Phase 3A variant-context isolation, cycle handling and bounds (default depth 20, 1,000 entities per seed per graph); reports retain truncation flags and unassessed consequences.

Intentional twin differences are assessment evidence. They do not use or weaken migration validation, which still requires exact source preservation and fresh promotion revalidation. Findings are evaluated independently with the existing rules and explicit `as_of` date (default 2025-06-01). Potential exposure is **not compatibility, physical fit, functional safety, approval or authorization**. There is no apply/publish operation; any future application requires separate human authorization.

Verification: 14 focused Phase 3C tests and 238 tests in the relevant combined regression run passed; scoped Ruff and Mypy passed. Existing mechanical regression tests retain four exact legacy ECU fingerprints. Persistence was unchanged, so no new MongoDB integration result is claimed. Dedicated API/UI, persistent proposals, authentication, 2D visualization and Agentic AI remain future work.

## Setup and launch

Use Python 3.11+; this build was executed with **Python 3.13**. Run from this directory:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e '.[dev]'
docker compose up -d mongo
python -m uvicorn app.api:app --host 127.0.0.1 --port 8000
```

In a second activated terminal:

```powershell
python -m streamlit run dashboard/app.py --server.address 127.0.0.1
```

Backend: http://127.0.0.1:8000/docs · Dashboard: http://127.0.0.1:8501

Docker Desktop must be running before Compose. A local standalone MongoDB is sufficient; Atlas and replica-set transactions are unnecessary. MongoDB is the sole application persistence backend. Unit tests use **mongomock only as a test double**, never as an application database. No SQLite is used.

Environment variables are listed in [.env.example](.env.example). Defaults work locally without an `.env`. To load a file for the API, use `python -m uvicorn app.api:app --env-file .env` (requires python-dotenv), or set variables explicitly in the shell. The application does not automatically load `.env` files.

| Variable | Purpose |
|---|---|
| `MONGODB_URI` | Defaults to `mongodb://localhost:27017` |
| `MONGODB_DATABASE` | Defaults to `autoplm_twin` |
| `AUTOPLM_API_URL` | Dashboard backend; defaults to `http://localhost:8000` |
| `OPENAI_API_KEY` | Needed only for live LLM provider |
| `AUTOPLM_LLM_MODEL` | Explicit model name required for live LLM mode |
| `AUTOPLM_LLM_BASE_URL` | Optional OpenAI-compatible service URL |
| `AUTOPLM_TEST_MONGODB_URI` | Explicit opt-in for isolated real MongoDB tests |

Select `offline` or `llm` in the migration UI/API/CLI. Live providers use LangChain structured Pydantic outputs. Mapping and repair providers have timeouts and bounded retries. Never put secrets in datasets, prompts or reports. This is a localhost, trusted-user prototype: reviewer names are audit annotations, not authenticated identities.

## Demonstration

```powershell
python -m app.cli generate --fleets 3 --source A --output data/synthetic/legacy_A.json
python -m app.cli generate --fleets 3 --source B --output data/synthetic/legacy_B.json
python -m app.cli migrate data/synthetic/legacy_A.json --mapper offline
python -m app.cli inject data/synthetic/legacy_A.json --fault unsupported_hardware_revision --output data/synthetic/corrupted_revision.json
python -m app.cli simulate --scenario valid
python -m app.cli simulate --scenario incompatible_software --output artifacts/incompatible.json
python -m app.cli simulate --scenario valid --fault-at 2 --output artifacts/sensor-loss.json
python -m app.cli benchmark --fleets 2 --seed 42 --output benchmarks/results.json
```

Generation emits legacy data and **separate** canonical records/mapping truth under `data/ground_truth/`. Truth is never supplied to the mapping graph. Dataset size is configurable, capped at 1,000 fleets. Each fleet has 13 records, two variants and four ECU functions. The seven simulation scenarios are `valid`, `incompatible_software`, `missing_ecu`, `unsupported_variant`, `missing_interface`, `broken_bom`, and `incorrect_revision`.

The dashboard has eight workspaces: overview, migration, compatibility, twin comparison, simulation, agent reviews, benchmarks and audit exports. Uploads support the versioned synthetic legacy **JSON envelope**, not arbitrary vendor exports. JSON/CSV/escaped HTML reports include findings; full JSON preserves provenance, mappings, twins, simulations, repair proposals and events.

## MongoDB and approval behavior

Collections: `source_records`, `schema_mappings`, `migration_jobs`, `staging_records`, `validation_results`, `twin_snapshots`, `simulation_runs`, `repair_proposals`, `audit_events`, and six entity collections. Indexes enforce job/source and job/entity identities. Source documents use insert-only updates. Job identifiers hash the dataset, selected provider mode and pipeline version. Retrying an identical job returns its existing result.

Only verified jobs can be explicitly promoted. Promotion revalidates and checks a staging digest, takes a compare-and-set job lock, copies records into a job namespace and commits a single job document as its publication manifest. Readers must use `Repository.approved_records`, which refuses uncommitted jobs. This supports standalone MongoDB without partial copies becoming approved. Entity collections are versioned by job; this is not a global latest-part catalog.

Repairs only restore authoritative source fields; the system does not invent new engineering designs. Offline restoration and optional LLM plans both undergo independent checks and twin comparison. Human approval is required to change staging. Approved jobs cannot be repaired. Stale candidates are rejected. Invalid source engineering data remains blocked until a separately authorized source revision is supplied.

After a process interruption, confirm no worker is still active, then run `python -m app.cli recover JOB_ID --actor YOUR_NAME` and retry the original migration. Recovery is an explicit operator action, not an automatic lock takeover. Events are append-only by application convention; database administrator access is outside this boundary.

## GitHub Actions troubleshooting

The earlier issue described below was subsequently resolved by using Ubuntu 22.04, with a successful workflow run reported. These historical failure details do not describe the current CI status; the latest local migration-safety results are recorded under Verification.

The Phase 2 run for commit `f068e31` reported **123 passed, 1 failed**: `test_real_mongodb_migration` could not ping MongoDB at `localhost:27017` (`Connection refused`). Dependency installation, Ruff and Mypy passed. See the [failed job](https://github.com/sravasti12/AutoPLM-Twin/actions/runs/42374959108/job/128410552472). The provided traceback confirms a database connectivity failure before migration logic ran; it does not establish whether the container was not ready, stopped, or its port was unavailable.

The workflow fix was pushed in commit `bfdc93c`. It waits for MongoDB health, uses Docker's assigned host port with explicit IPv4, and verifies a runner-side ping with a bounded 30-second selection timeout before pytest. It records dependencies, captures container diagnostics on failure and uploads pytest XML even after failure. The integration test remains enabled. Local configuration checks passed; a successful GitHub rerun has not been confirmed. Inspect the named readiness/test steps and the `engineering-evidence` artifact if a run still fails.

This CI investigation does not start Phase 4. The phased approval checkpoint above remains unchanged.

## Verification

```powershell
python -m pytest -q
python -m pytest tests/unit -q
python -m ruff check app dashboard tests
python -m mypy app/models.py app/mapping.py app/resolution.py app/source_adapters.py
python scripts/check.py
$env:AUTOPLM_TEST_MONGODB_URI = 'mongodb://localhost:27017'
python -m pytest tests/integration -q
```

Integration tests create and drop only random `autoplm_test_*` databases. Without explicit opt-in, the real database test skips. Streamlit AppTest exercises every workspace against a mocked-database FastAPI backend. CI uses Ubuntu 22.04; its successful run was previously reported, while the results below are local verification rather than a claim about a new remote run.

Latest verified migration-safety milestone (2026-11-08):

| Check | Result |
|---|---|
| Focused migration tests | 14 passed |
| Complete unit suite | 212 passed |
| Real MongoDB integration tests | 6 passed |
| Ruff on `tests/unit/test_migration.py` | Passed |

Regression coverage confirms that incompatible software is rejected even when source/target twins match, genuine twin differences independently prevent promotion, and stale cached approvals cannot bypass fresh validation. A compatible software release is accepted when the source expectation is updated before ingestion and all engineering checks pass. Target-only version drift remains rejected under the current exact source-preservation policy. Twin ordering normalization and precise ECU revision/version difference paths are also covered by unit tests.

Service regression tests use mongomock; real MongoDB integration is a separate suite. The unit run passed outside the sandbox after two temporary-directory permission errors in the initial run. No live LLM or new benchmark execution is claimed. [PROJECT_PROGRESS.md](PROJECT_PROGRESS.md) contains detailed commands, limitations and historical checkpoints. [BENCHMARKS.md](BENCHMARKS.md) explains measured benchmark results and attribution; `requirements-lock.txt` captures the build environment.

## Original engineering contributions and limits

The project combines independent source reconciliation, constrained agent proposals, staged approval, graph rules, configuration twin comparison and behavioral traces in one auditable migration workflow. Its deliberate separation of schema, rule, twin and behavioral detections makes the demonstration technically inspectable.

Limitations: fictional compatibility data; alphabetic single-letter hardware revisions; exact configuration comparisons; no physical bus timing or vehicle dynamics; bounded in-process jobs; no distributed worker scheduler, RBAC or tamper-proof audit storage; no production PLM connector. Source adapters are versioned and require engineering work for additional schemas. The small injected-fault benchmark does not estimate field failure rates or demonstrate LLM superiority. Live LLM and real database integration require their respective services.

Future work: authenticated reviewers, least-privilege MongoDB roles, durable background execution, broader independent datasets, richer effectivity/version ranges, per-occurrence BOM semantics, and validated vendor adapters.

See [ARCHITECTURE.md](ARCHITECTURE.md), [API documentation](docs/API.md), [file inventory](docs/FILES.md), and [ENGINEERING_ASSUMPTIONS.md](ENGINEERING_ASSUMPTIONS.md).
