# AutoPLM Twin

**Agentic Automotive PLM Migration with Digital Twin-Based Engineering Verification**

A functioning Python engineering prototype for migrating **fictional, synthetic** vehicle engineering data. A record can satisfy a database schema while assigning incompatible software to an ECU. AutoPLM Twin preserves the source, stages transformations, checks engineering constraints, compares vehicle configuration twins, and exposes explicit human approval controls.

This project has no Teamcenter, Windchill, supplier, CAN hardware or production vehicle integration. Its signal simulation is a documented behavioral prototype, not validated vehicle physics.

## Phased delivery and approval

**Current status: Phase 1 foundation functionality is implemented and locally verified. Phase 2 Digital Twin Validation is in progress, with the completed validation and migration-safety capabilities listed below.**

Further implementation, commits and pushes require separate approval. Earlier publication approvals and build-review checkpoints are historical.

### Verified Phase 1 foundation

- **Engineering domain:** versioned schemas for ECU hardware/software, vehicle platforms/variants, multi-level BOMs and engineering changes; explicit lifecycle states, relationship identifiers, date validation and numeric software-version comparison.
- **Synthetic source data:** reproducible A/B legacy schemas, configurable dataset sizes, hardware/software compatibility constraints, separate canonical/mapping truth and fault labels, and preservation of surviving source identifiers in corrupted exports.
- **Mapping and transformation:** field profiling, an offline dictionary baseline, bounded LangGraph proposal/repair/review states, structured mapping validation and allowlisted transformations. Source reconciliation uses an independent adapter; no generated code is executed. Live LLM providers exist but remain unverified end-to-end.
- **Migration and persistence:** PyMongo source capture, staging, idempotent jobs, source provenance checks, record validation, audit history, controlled promotion and approved-publication integrity checks. Real MongoDB integration covers both legacy schemas, idempotency, promotion, indexes, corruption rejection and API/report reads.
- **Engineering safety and access:** deterministic BOM, compatibility, variant, dependency, interface, release and change checks; duplicate identity detection; FastAPI endpoints and JSON/CSV/HTML reports. Existing dashboard workspaces have unit coverage through Streamlit AppTest with a mocked-database backend; that does not establish a live dashboard-to-MongoDB acceptance result.

### Phase 2 Digital Twin Validation — in progress

Completed and locally tested:

- Construct source and migrated configuration twins containing installed ECUs, hardware, software, topology and related engineering data.
- Canonicalize installed-ECU ordering without changing source records, so equivalent ordering produces the same fingerprint.
- Report genuine ECU differences at precise paths, including `/nodes/<ECU_ID>/hardware/hardware_revision` and `/nodes/<ECU_ID>/software/version`.
- Reject incompatible software even when source and target twins match; reject genuine twin differences independently of engineering findings.
- Revalidate before promotion, so a forged cached passing result, `verified` status and matching staging digest cannot bypass the safety gates.
- Accept a compatible software release when the expected source is updated before ingestion and all engineering/comparison checks pass. Target-only version drift remains rejected; no selective-delta approval policy is implemented.

Remaining work and verification boundaries:

- A migration-level missing-required-ECU regression is the next recommended small task, subject to approval and a coverage check first.
- Broader twin/simulation scenario completeness and phase acceptance remain in progress. Existing fictional SimPy scenarios and historical traces are not a validated vehicle-physics model.
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
    L --> M[Human approval and atomic publication manifest]
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
