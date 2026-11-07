# Architecture and engineering decisions

The diagram and launch instructions are in README.md. Modules are intentionally grouped by responsibility rather than creating dozens of empty packages.

| Module | Responsibility |
|---|---|
| `app/models.py` | Pydantic schema v1.0: hardware, software, platform, variant, BOM and engineering change |
| `app/data.py` | Seeded A/B legacy generator and pure-copy fault injection |
| `app/mapping.py` | Profiles, dictionary baseline, allowlisted transformations and executable plan validation |
| `app/source_adapters.py` | Independently implemented A/B source contracts and decimal unit conversion for reconciliation |
| `app/agents.py` | LangGraph nodes, structured live/offline providers, bounded repair loop, review state |
| `app/repository.py` | PyMongo indexes, source/staging retrieval, publication-manifest readers and audit insertion |
| `app/service.py` | Idempotent migration orchestration, reconciliation, promotion, decisions, simulations and reports |
| `app/verification.py` | Independent deterministic engineering rule engine and machine-readable findings |
| `app/twin.py` | Source/target snapshots, recursive comparison, scenarios and SimPy state machines |
| `app/resolution.py` | Offline restoration / structured LLM source-referenced repair planning |
| `app/benchmark.py` | Paired experiment execution, case labels and measured scoring |
| `app/api.py` | FastAPI routes and JSON/CSV/HTML exports |
| `app/cli.py` | Dataset generation, offline simulation, migration, recovery and benchmark commands |
| `dashboard/app.py` | Eight Streamlit workspaces, Plotly architecture and review controls |

## Boundaries

No LLM controls database writes or executes code. The transformation registry contains only identity, gram-to-kilogram conversion, string trim/lowercase and explicit enum substitution. Extra fields and invalid transformations fail Pydantic validation. Full source rows are checked, not merely sampled profile values. Missing evidence, unsupported assumptions and target ambiguity force review. Unknown fields do not silently disappear.

Source normalization uses the independent dictionary adapter. The mapping agent does not receive ground-truth files. A live LLM therefore proposes semantics while deterministic source adapters provide a separately implemented reconciliation oracle for the two supported synthetic sources. This intentionally limits automatic generalization: a new source requires a reviewed adapter before trustworthy reconciliation is possible.

The source adapters do not import the generator alias dictionary, baseline mapper or transformation registry. Handwritten source fixtures and deliberately broken migration conversions exercise this separation. The domain schema is shared for canonical defaults. Reconciliation also checks each staging row's source annotation and expected target identity: swapping complete records cannot pass merely because the record set and twins remain unchanged. Nonfinite engineering quantities are rejected. Pipeline version 1.1 introduced independent adapters; version 1.2 adds stricter mapping completeness, unit/type contracts and bounded response parsing. Each version creates fresh job identities rather than reusing earlier verification results.

## State transitions

`running → mapping_review | verified | rejected | failed`

`mapping_review → human mapping decisions → running → verified | rejected`

`verified → promoting → approved`

`verified | rejected → pending repair → human decision → repairing → verified | rejected`

Uncommitted interrupted jobs require explicit operator recovery to `failed`, then replay. Source records are retained; staging upserts replay deterministically. A job's provider identity includes its mode, not a hash of live provider configuration. Retries reuse the persisted result; changing a live model alone does not create a new job.

Promotion does not require multi-document transactions. Compare-and-set on the job serializes promotion and repair. Copies in entity collections are invisible to the approved reader until the manifest commits. Reattempts refresh uncommitted copies. Database administrators must not bypass this reader contract. Audit authorization is inserted before the publication manifest; a crash may record authorization without a completed publication. The job status remains authoritative.

## Trust and operational limits

This is a synchronous local prototype. No endpoints provide arbitrary staging writes. Direct database mutation, distributed malicious clients, database-enforced append-only policies and worker leases are outside the application boundary. Recovery must only be used when a worker is confirmed stopped. Audit events contain actor annotations, source digests and structured evidence, without claiming cryptographic nonrepudiation.

The verifier uses a fixed as-of date (2025-06-01 by default) for reproducible effectivity decisions. Dates must be deliberately parameterized for future engineering data. Hardware revision progression currently uses single uppercase alphabetic revisions; software versions use `packaging.version.Version`, never floating-point comparison.
