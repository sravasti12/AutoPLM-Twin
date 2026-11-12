# AutoPLM Twin implementation progress

All engineering data and behavior in this project are synthetic.

## Phase 4D — LLM Integration and Grounded Agentic Reasoning (2026-11-12)

**Status: Implementation verified offline/with mocked providers; live-provider acceptance remains pending. Do not treat this as verified live LLM functionality.** The current session had no configured `OPENAI_API_KEY`, `AUTOPLM_LLM_MODEL`, endpoint override or live opt-in. Only boolean configuration-presence metadata was inspected; no credential values were printed. Starting working tree was clean.

### Implemented architecture and decisions

- Extended the existing Phase 4A LangGraph; did not create a second orchestrator or duplicate engineering tools. Existing extraction/planning/tool/review/finalization routes remain, with a final bounded synthesis node when the provider supports it. Offline and older mocked providers retain their behavior and output shape.
- Reused the existing `ChatOpenAI` integration. Supported transport selectors are `AUTOPLM_LLM_PROVIDER=openai` (default) and `openai_compatible` (requires existing base URL). Existing model/key/base-URL environment configuration remains. Added bounded timeout (default 45 seconds, range 1–120), SDK retries (default 1, range 0–2), and output-token cap (default 2,048, range 128–8,192). No additional provider SDK/dependency was added.
- Planner context now includes actual tool schema, remaining budget and explicit proposal availability. Calls still use the existing typed allowlist/argument validation, duplicate suppression, bounded traversal and conditional follow-up. No arbitrary Python/database/write/approval/publication tool is available.
- Added structured `EvidenceCitation`, `EvidenceSummary` and `GroundedConclusion` models. LLM synthesis selects evidence IDs, JSON pointers and categories; server validation checks actual retrieved values and allowed semantic scopes. Rendered statements are exact cited deterministic data, not unrestricted LLM engineering prose. Exposure cannot be relabelled as a deterministic incompatibility finding. Empty/malformed summaries, nonexistent IDs/pointers and unsupported classifications become explicit partial/rejected reasoning without invented conclusions.
- Categories distinguish retrieved record facts, potential exposure, deterministic findings, actual configuration differences and unknown evidence. `reasoning_status` records validated/unavailable/rejected synthesis; `validated` only means citation checks passed, not engineering approval or completeness. Original tool evidence/findings, recommendation-only human-review semantics and all safety gates remain unchanged.
- Added optional summary forwarding in Phase 4B's existing context-provider adapter, preserving authoritative baseline/source rechecks. Legacy/offline serialization omits unused new fields so existing stored snapshots/report digests remain stable. Added a test that a nonempty grounded report persists, retrieves and accepts recommendation review through Phase 4C without changing baseline records.
- Failure handling redacts exception messages to classes for missing configuration, provider outage, timeout/rate limit, malformed extraction/planning/synthesis and invalid tool plans. SDK retries remain bounded. Explicitly choosing offline mode after failure is supported; no hidden automatic fallback or fabricated live results. There is no total wall-time kill switch for CPU tools.

### Reproducible evaluation

- Created `app/investigation_evaluation.py`, using `generate(1, seed=42)` and six declared cases: lookup, verification, variant fingerprint, impact/product-structure follow-up, missing target and revision-incompatible software.
- Case checks cover expected tools/request targeting, unnecessary calls, evidence-ID traceability, validated synthesis where present, missing-evidence handling, execution bounds, deterministic incompatibility detection and unchanged baseline. This is a small synthetic contract suite, not an LLM accuracy benchmark.
- Executed `-m app.investigation_evaluation`: **6/6 offline cases passed**, **0 unnecessary tool calls**, **0 unsupported conclusion cases emitted**. All offline cases have `reasoning_status=not_requested`; the zero count does not measure an LLM hallucination rate. Mocked synthesis tests separately verify rejection of unsupported claims.
- Added `tests/live/test_investigation_live.py`: skipped unless `AUTOPLM_RUN_LIVE_INVESTIGATION=1`; opting in also requires configured model/key. CLI `--live` uses the same explicit flag. No live provider call occurred. Normal CI requires neither credentials nor network for these tests.

### Actual verification

Commands used `.\.venv\Scripts\python.exe`:

| Check | Command arguments after Python | Actual result |
|---|---|---|
| New focused provider/synthesis checks and opt-in smoke | `-m pytest tests/unit/test_investigation_llm.py tests/live/test_investigation_live.py -q --basetemp=.pytest_tmp/llm-investigation -p no:cacheprovider --tb=short` | **34 passed, 1 skipped in 8.52 seconds** |
| Relevant regression checkpoint | `-m pytest tests/unit/test_investigation_llm.py tests/unit/test_investigation_review.py tests/unit/test_investigation_api.py tests/unit/test_investigation.py tests/unit/test_what_if.py tests/unit/test_migration.py tests/unit/test_engineering.py tests/unit/test_mechanical.py tests/unit/test_dependencies.py tests/unit/test_persistence_api.py tests/unit/test_traceability.py tests/unit/test_api_benchmark.py tests/live/test_investigation_live.py -q --basetemp=.pytest_tmp/llm-regression -p no:cacheprovider --tb=short` | **285 passed, 1 skipped in 19.65 seconds** |
| Two added classification/persistence bindings | `-m pytest tests/unit/test_investigation_llm.py -k 'real_exposure or survives_persistence' -q --basetemp=.pytest_tmp/llm-review-binding -p no:cacheprovider --tb=short` | **2 passed, 34 deselected in 5.42 seconds** |
| Real MongoDB regressions | `-m pytest tests/integration/test_mongodb.py -q --basetemp=.pytest_tmp/llm-mongodb -p no:cacheprovider --tb=short` with explicit `AUTOPLM_TEST_MONGODB_URI=mongodb://127.0.0.1:27017` | **11 passed in 16.48 seconds** |
| Ruff | `-m ruff check app/investigation.py app/investigation_service.py app/investigation_evaluation.py tests/unit/test_investigation_llm.py tests/live/test_investigation_live.py` | **Passed**, including after the two added tests |
| Scoped Mypy | `-m mypy app/investigation.py app/investigation_service.py app/investigation_evaluation.py` | **Success, three source modules** |

- The 36 new unit cases were verified across the 34-case focused/regression checkpoints and two additional targeted cases; no combined 36-case timing is claimed. Initial lint line-length and evaluation mode typing issues were corrected. No failing test was removed or disabled. The live skip is intentional and separately documented.
- Actual mocked SDK route: natural-language braking exposure → structured entity extraction → component retrieval → impact → BOM relationship follow-up selected from impact paths → verification → citation synthesis. It produced exact recorded revision evidence and potential-exposure evidence, with the baseline unchanged.
- Tests cover provider configuration/compatible endpoint settings, malformed output, dynamic routing, invalid/unauthorized tools, duplicate suppression, budgets, outage/timeout/rate-limit failure classes, unknown citations, exposure misclassification, exact deterministic findings, explicit offline recovery, authoritative summary forwarding and review persistence/digests.
- Existing regressions retain exact legacy ECU fingerprints, migration/promotion safeguards, authoritative loading, isolated what-if execution and authenticated/atomic human review. Real MongoDB tests are regression checks, not live LLM execution. No complete unit suite, dashboard/browser or live-provider performance/accuracy run was performed.

### Exact files changed and Git status

- Created: `app/investigation_evaluation.py`, `tests/unit/test_investigation_llm.py`, `tests/live/test_investigation_live.py`.
- Modified: `app/investigation.py`, `app/investigation_service.py`, `README.md`, `PROJECT_PROGRESS.md`.
- Existing tools, engineering calculations, review authorization/audit, API contracts, repository, migration, UI, dependencies and CI were unchanged. No commit or push performed.

### Limitations and next recommended step

- Live functionality is wired but unverified: no configured model/key was available. No measured LLM accuracy, latency, provider reliability or vendor compatibility is claimed. Configured endpoints/models must support the client's structured-output protocol and settings.
- Final synthesis deliberately uses constrained citations and server-rendered facts. It does not provide unrestricted narrative engineering reasoning, invent physical-fit rules or turn the absence of findings into safety approval. Planner rationale remains unverified planning text, not authoritative engineering evidence.
- Provider timeouts/retries bound individual requests; extraction and synthesis are additional provider calls beyond planning. There is no hard whole-investigation wall-time deadline, context-size truncation policy or CPU-tool cancellation. Large-context/output limits remain provider-dependent and unbenchmarked.
- Fallback is explicit offline selection, not automatic recovery to offline results. Malformed structured responses produce partial reports rather than a new repair loop. The six-case evaluation is intentionally narrow; real-model evaluation and broader adversarial coverage remain future work.
- Next recommended approved task: provision a model/key securely and run the opt-in live smoke and synthetic live evaluation, inspect grounding/tool selection and document actual outcomes before claiming live acceptance or building the complete Streamlit investigation/review interface. No next task started.


## Phase 4C — Human-in-the-Loop Engineering Review (2026-11-12)

**Status: Implemented and verified with focused/unit regressions and real MongoDB. Local credential authorization only; production authentication is not claimed.** This follows the user's current Phase 4C scope of persistent review APIs, superseding earlier planning references that assumed Phase 4C would deliver a complete Streamlit interface. No UI was implemented. Starting working tree was clean.

### Implementation and architectural decisions

- Inspected existing investigation/API/repository and legacy audit/approval paths. No authenticated reviewer identity existed; legacy actor names are freely supplied annotations. Preserved those existing interfaces and added a fail-closed boundary specifically for the new review APIs.
- Added `ReviewPrincipal` and server-controlled `AUTOPLM_REVIEW_CREDENTIALS`: JSON mapping lowercase SHA-256 bearer-secret digests to subjects and allowed roles. Credential possession is checked with constant-time digest comparison. No reviewer field is accepted in decision bodies. Missing/unknown credentials return 401, a reader without reviewer role receives 403 on decisions, and disabled/malformed configuration returns 503. Registry roles/subjects are validated; malformed/empty subjects fail closed.
- New report APIs authenticate before accessing their service dependency. `engineering_reviewer` permits decisions; `investigation_reader` permits create/read/list/history only. This is static local credential authentication, not SSO/OIDC, MFA, expiry, per-job permissions or a production identity service. Existing legacy approval endpoints are not retroactively secured.
- Created `InvestigationReviews` with typed stored-report, decision, input, queue and history models. New report creation invokes existing Phase 4B authoritative loading and Phase 4A investigation, rather than accepting client-supplied report content or duplicating engineering logic. Persists exact baseline context/digest/fingerprint/provenance, request/input, evidence, execution history, findings, recommendations, uncertainties, creator and UTC time. Partial/limited investigations can be reviewed with their original evidence status preserved.
- New `investigation_reports` collection uses the existing Repository connection with an index over review status/creation time. Existing MongoDB `_id` uniqueness identifies each report. A content digest binds the input and complete response; reads reject mismatched content/history identity/baseline bindings.
- One atomic `find_one_and_update` matches pending status, the report digest and empty history; it sets accepted/rejected and appends the complete terminal decision in the same document. Exactly one concurrent decision can win. No ordinary report/decision edit, delete or reopen endpoint exists. Duplicate/conflicting decisions return 409 and preserve original history.
- Decision identity comes from authenticated principal; explicit ACCEPT/REJECT and nonblank comments are mandatory. Stored decision includes ID, investigation ID, reviewer, comments, UTC timestamp, baseline fingerprint, report digest and audit event ID. The immutable original report retains its original human-review flag; the outer review status reflects the actual review.
- Reused `Repository.audit()` and existing `audit_events` for the central decision mirror, adding an optional event ID while preserving existing callers. Atomic embedded history is the durable decision record; an audit-mirror failure leaves the decision intact and returns `audit_mirrored=false`. No unsafe cross-document rollback or reliance on MongoDB transactions was introduced. Automatic audit-mirror repair is not implemented.
- ACCEPT is recommendation acceptance for further consideration only. It does not validate/approve an engineering change, modify any approved record, promote a job or publish a what-if configuration. Historical reports stay bound to the investigated baseline; accepting a historical recommendation does not authorize its application to changed product data.

### New API contracts

- `POST /jobs/{job_id}/investigation-reports`: authenticated creation, same `InvestigationInput`, 201 `StoredInvestigation`.
- `GET /investigation-reports`: authenticated typed queue; pending default; `review_status=pending|accepted|rejected|all`; bounded `limit`/`offset`.
- `GET /investigation-reports/{id}`: authenticated immutable report retrieval.
- `GET /investigation-reports/{id}/decisions`: authenticated `ReviewHistory` including audit mirror status.
- `POST /investigation-reports/{id}/decisions`: reviewer-only `ReviewInput` (ACCEPT/REJECT plus comments), returning `ReviewHistory`.
- Original Phase 4B read-only investigation endpoint and all previous API contracts remain unchanged. New route failures sanitize execution/database messages; report integrity conflicts are 409, missing reports 404, malformed inputs 422.

### Actual verification

All commands used `.\.venv\Scripts\python.exe`:

| Check | Command arguments after Python | Actual result |
|---|---|---|
| Focused review | `-m pytest tests/unit/test_investigation_review.py -q --basetemp=.pytest_tmp/review -p no:cacheprovider --tb=short` | **22 passed in 4.87 seconds** |
| Relevant unit regressions | `-m pytest tests/unit/test_investigation_review.py tests/unit/test_investigation_api.py tests/unit/test_investigation.py tests/unit/test_what_if.py tests/unit/test_migration.py tests/unit/test_engineering.py tests/unit/test_mechanical.py tests/unit/test_dependencies.py tests/unit/test_persistence_api.py tests/unit/test_traceability.py tests/unit/test_api_benchmark.py -q --basetemp=.pytest_tmp/review-regression -p no:cacheprovider --tb=short` | **251 passed in 17.68 seconds** |
| Real MongoDB | `-m pytest tests/integration/test_mongodb.py -q --basetemp=.pytest_tmp/review-mongodb -p no:cacheprovider --tb=short` with explicit `AUTOPLM_TEST_MONGODB_URI=mongodb://127.0.0.1:27017` | **11 passed in 22.75 seconds** |
| Ruff | `-m ruff check app/review_auth.py app/investigation_review.py app/api.py app/repository.py tests/unit/test_investigation_review.py tests/integration/test_mongodb.py` | **Passed** |
| Scoped Mypy | `-m mypy app/review_auth.py app/investigation_review.py app/api.py app/repository.py` | **Success, four source modules** |

- Review tests cover durable content/queue/retrieval, accept/reject, authenticated versus caller-supplied identity, reader denial, missing/invalid authorization, missing comments/invalid decisions, duplicate and concurrent conflicting submissions, audit history/mirror failure, report tampering, unsupported edit/delete methods, pagination validation, baseline binding and unchanged engineering collections/jobs.
- Three new real MongoDB cases cover accept/reject persistence (retrieved after rebuilding the repository/service) and concurrent conflicting decisions with exactly one winner. Existing real migration, integrity and read-only investigation cases also passed. Integration uses existing random isolated `autoplm_test_*` fixtures.
- No engineering logic, fingerprint or promotion gate was modified. Full unit suite, dashboard/browser, benchmark experiment and live LLM checks were not run. Running API benchmark unit tests does not claim new benchmark measurements.

### Exact files changed and Git status

- Created: `app/review_auth.py`, `app/investigation_review.py`, `tests/unit/test_investigation_review.py`.
- Modified: `app/api.py`, `app/repository.py`, `tests/integration/test_mongodb.py`, `README.md`, `PROJECT_PROGRESS.md`.
- No new dependency, complete Streamlit review interface, engineering change publication, CI change, commit or push.

### Limitations and remaining work

- Static server-provisioned bearer registry is deliberately disabled by default. Production authentication, token expiry/rotation management, MFA, per-job authorization and protection of legacy trusted-user endpoints require a separate security scope. Use high-entropy secrets; token digests are configuration, never dataset fields.
- Decisions are terminal; corrections require a new investigation, retaining historical reports/decisions. No silent overwrites or reopen path exists. Canonical embedded history survives central audit-mirror failure, but reconciliation/repair of a missing mirror requires future operator tooling.
- Report digests are integrity checks, not signatures; database administrators can edit records. No WORM or regulatory compliance claim. Reports remain subject to MongoDB document-size limits; large-report storage/performance has not been assessed. Queue pagination is bounded but returns complete reports.
- Snapshot revalidation remains Phase 4B's observed-change check, not a distributed transaction. Reviews bind to historical baseline facts and do not reapprove current engineering state. Production/live LLM quality remains unverified.
- Next recommended approved scope: complete Streamlit investigation/review interface using these APIs, prominently showing credential boundary, evidence/uncertainties, recommendation-only acceptance and audit-mirror status. Production identity integration and mirror recovery need separate approval. No next task started.


## Phase 4B — Authoritative Baseline Loading and Read-only Investigation API (2026-11-12)

**Status: Implemented and verified with focused unit, relevant regression and real MongoDB tests.** This entry supersedes historical statements that investigation baseline/API integration is missing. Live LLM execution and Phase 4C UI remain outside this completion claim. Starting working tree was clean.

### Architecture and exact implementation

- Added `InvestigationService` as a read-only adapter, leaving repository, migration service, Phase 4A graph and engineering modules unchanged. Uses existing `approved_records`, `source` and `job` interfaces; no repository/index/collection behavior changed.
- Requires a committed approved publication. Verifies publication/source integrity, Dataset schemas, unique identities and normalized source equality before investigation. Missing/empty/unapproved publications never fall back to staging or synthetic fixtures. Selected variants and optional components must exist, with explicit component membership in the selected twin.
- Uses the existing graph to reject structural diagnostics (missing, ambiguous, unsupported references, cycles or inconsistent BOM context). Symbolic `UNASSESSED_RELATIONSHIP` diagnostics are retained for review rather than invented engineering conclusions.
- Loads the full approved job snapshot to retain cross-variant/shared dependency evidence. Selected twin context identifies platform, ECUs/software, electronic BOMs and change records, mechanical BOMs, assemblies and parts. The selected variant is context, not an access-control boundary. Source ordering preserves legacy twin list serialization; fingerprint is checked against a source-derived twin and optional caller expectation.
- Returns typed baseline context with job/baseline IDs, publication digest, normalized baseline digest, twin fingerprint, associated IDs, record/source/schema/SHA-256 provenance and diagnostics. Rechecks authoritative source/publication/context after execution to reject changes observed during investigation.
- Added `POST /jobs/{job_id}/investigations`, validated by `InvestigationInput` and `InvestigationResponse`, with natural-language request, required variant, optional component/proposal ID, optional expected fingerprint, offline/LLM mode and bounded steps. A provider adapter adds explicit context to extraction while preserving the original request. Calls the existing Phase 4A graph; no duplicate investigation engine.
- Errors: 404 missing job/variant/component; 409 unapproved/incomplete/tampered/inconsistent baseline, fingerprint or applicability conflict and observed baseline changes; 422 invalid request/unsupported persisted proposal lookup; 503 database failures; sanitized 500 unexpected execution failures. Incomplete evidence/provider failures remain HTTP 200 partial reports with human review required.
- No writes to engineering records, migration jobs, audit events, proposals or report collections. No approval, promotion or publication action. Repository/service initialization conventions are unchanged; no new indexes or persistence were introduced.
- No existing authoritative proposal store exists: optional `proposal_id` explicitly returns 422 `proposal_store_unavailable`. It never reads migration repair records as engineering change proposals. Existing isolated library what-if behavior remains intact, without claiming persisted proposal support.

### Actual verification

All commands used `.\.venv\Scripts\python.exe`:

| Check | Command arguments after Python | Actual result |
|---|---|---|
| Focused baseline/API | `-m pytest tests/unit/test_investigation_api.py -q --basetemp=.pytest_tmp/investigation-api -p no:cacheprovider --tb=short` | **23 passed in 7.44 seconds** |
| Relevant unit regressions | `-m pytest tests/unit/test_investigation_api.py tests/unit/test_investigation.py tests/unit/test_what_if.py tests/unit/test_mechanical.py tests/unit/test_dependencies.py tests/unit/test_engineering.py tests/unit/test_migration.py tests/unit/test_persistence_api.py tests/unit/test_traceability.py tests/unit/test_api_benchmark.py -q --basetemp=.pytest_tmp/authoritative-regression -p no:cacheprovider --tb=short` | **229 passed in 14.33 seconds** |
| Real MongoDB | `-m pytest tests/integration/test_mongodb.py -q --basetemp=.pytest_tmp/authoritative-mongodb -p no:cacheprovider --tb=short` with explicit `AUTOPLM_TEST_MONGODB_URI=mongodb://127.0.0.1:27017` | **8 passed in 13.08 seconds** |
| Ruff | `-m ruff check app/investigation_service.py app/api.py tests/unit/test_investigation_api.py tests/integration/test_mongodb.py` | **Passed** |
| Scoped Mypy | `-m mypy app/investigation_service.py app/api.py` | **Success, two source files** |

- Unit coverage: authoritative baseline/provenance/fingerprint loading, endpoint response validation, context injection, mechanical parts/assemblies/BOMs, missing contexts, request validation, nonapproved/tampered/missing publications, recomputed manifest versus source expectations, inconsistent references, database/execution error redaction, missing provider configuration and changes during execution.
- Read-only enforcement compares all collection documents before/after successful and missing-provider investigations. Two new real MongoDB cases (source schemas A/B) exercise promotion during setup, then investigation and full database equality checks. Real integration uses existing random isolated `autoplm_test_*` fixtures; application databases are not used.
- Relevant regressions preserve Phase 4A, what-if isolation, graph traversal, mechanical/twin fingerprints, source preservation and promotion safeguards. No full unit suite, dashboard/live browser, live LLM or benchmark execution was performed; running the API benchmark unit file does not claim a new benchmark experiment.

### Exact files changed and Git status

- Created: `app/investigation_service.py`, `tests/unit/test_investigation_api.py`.
- Modified: `app/api.py`, `tests/integration/test_mongodb.py`, `README.md`, `PROJECT_PROGRESS.md`.
- No dependencies, repository behavior, engineering modules, migration rules, dashboard or CI changed. No commit or push performed.

### Limitations and next recommended phase

- Approved jobs only. Persisted proposal IDs, durable investigation reports and authentication/authorization remain unsupported. Existing prototype APIs are for trusted local callers; no production security claim is made.
- Source/publication equality and post-execution rechecks detect observed changes, but do not supply transactional snapshot isolation or stop administrators from modifying manifests/source data. Graph integrity checks are conservative across the full job, including references outside the selected variant.
- Live LLM availability/quality remains unverified. Existing graph bounds, unknown relationship semantics and synthetic verification date/rules remain unchanged. No fit, physical safety or automatic authorization is inferred.
- Next recommended approved phase: Phase 4C Streamlit investigation interface over this endpoint, retaining baseline/provenance visibility, partial/error states and human-review boundaries. Persistent proposal/report lifecycle and authentication require separately approved scope. No further task started.


## Phase 4A — Agentic Engineering Investigation Backend (2026-11-12)

**Status: Implemented and verified with offline/mocked providers and relevant regressions. Live LLM behavior is unverified.** This checkpoint supersedes earlier statements that all agentic engineering investigation remains future work. Only Phase 4A was implemented; no investigation UI, API or persistence was added. The starting working tree was clean.

### Implementation and architecture

- Created `app/investigation.py`, separate from the existing mapping/repair agents. Reused existing LangGraph, Pydantic and provider configuration conventions without altering prior agents or adding dependencies.
- Defined typed request extraction, tool arguments, planning decisions, tool evidence and final reports, plus a typed LangGraph state. Graph nodes perform intake, planning, tool execution, evidence/uncertainty review and finalization. Conditional routes execute only selected tools, revisit planning after results and stop when no new calls remain or budgets are exhausted.
- Ten structured tools: component lookup, variant lookup, BOM/assembly relationships, reverse dependency impact, provenance paths, twin construction, two-variant comparison, explicit-proposal what-if assessment, deterministic verification and SHA-256 twin fingerprint inspection. Mechanical structure uses the existing graph/twin/verifier implementations rather than a second mechanical rules engine.
- Offline extraction supports explicit IDs and conservative function/part-number descriptions. Planning follows request intent and adds assembly/BOM relationship retrieval when impact evidence identifies them. Multiple description matches remain candidates with an ambiguity warning. Unknown identifiers cannot become confirmed record facts. Missing target context, failed tools and unexecuted requested intents remain missing evidence.
- Optional LLM extraction/planning uses `AUTOPLM_LLM_MODEL`, optional `AUTOPLM_LLM_BASE_URL`, `OPENAI_API_KEY`, temperature 0, 45-second timeout and one retry, consistent with existing provider conventions. Structured outputs are validated. Initialization/extraction/planning failures become partial reports; errors expose exception classes rather than provider messages/credentials. No live provider call was made.
- The engine suppresses duplicate tool requests, supports 1–30 tool executions/planning rounds (default 12), retains existing per-traversal depth/entity bounds and caps graph recursion accordingly. Reports distinguish `complete`, `partial` and `limit_reached`; none means engineering approval. Human review is always required.
- Reports preserve the original request, targets, plans/rationales, executed steps, invoked tools, numbered raw evidence, affected entities, provenance paths, verification findings, baseline digest/fingerprints, missing evidence, uncertainties and recommendations. Aggregated findings/paths cite actual evidence IDs. Provider planning text is planning rationale, not independently verified engineering evidence.
- Baselines and provider inputs are detached copies. Duplicate baseline identities fail closed. What-if tools accept only an explicit typed proposal and reuse stale-digest detection and isolated execution. No database writes, promotion/publication tools or autonomous approvals exist.

### Actual verification

All commands used `.\.venv\Scripts\python.exe`:

| Check | Command arguments after Python | Actual result |
|---|---|---|
| Focused investigation checkpoint | `-m pytest tests/unit/test_investigation.py -q --basetemp=.pytest_tmp/investigation-final -p no:cacheprovider --tb=short` | **27 passed in 4.72 seconds** |
| Final relevant regression, including five added investigation cases | `-m pytest tests/unit/test_investigation.py tests/unit/test_what_if.py tests/unit/test_mechanical.py tests/unit/test_dependencies.py tests/unit/test_engineering.py tests/unit/test_migration.py tests/unit/test_mapping_workflow.py tests/unit/test_domain_mapping.py tests/unit/test_source_adapters.py tests/unit/test_traceability.py -q --basetemp=.pytest_tmp/investigation-regression -p no:cacheprovider --tb=short` | **241 passed in 7.86 seconds**, including **32 investigation cases** |
| Ruff | `-m ruff check app/investigation.py tests/unit/test_investigation.py` | **Passed** |
| Scoped Mypy | `-m mypy app/investigation.py` | **Success, one source file** |

- Coverage: extraction/state, lookup-only routing, conditional mechanical follow-up, validated tools, two-variant comparison/fingerprints, provenance citations, ambiguous/missing evidence, provider and tool failures, missing credentials, mocked provider configuration, execution limits, early stop, duplicate suppression, immutable provider evidence/baseline records, what-if findings and stale proposals, and deterministic offline reports.
- Initial test collection failed because pytest reserves the parameter name `request`; renamed the test parameter. Corrected initial static line lengths and ensured LangGraph node names do not conflict with state keys. No tests were removed or disabled.
- Executed README's offline example against `generate(1)`: request `Investigate impact and verify F0000-brake` invoked `component`, `impact`, `verify`, `relationships`, with evidence IDs `E001`–`E004`. Potentially affected records include both variants and the BOM, plus two scoped implicit assemblies. Zero verification findings; `partial` status preserves unassessed graph evidence rather than implying approval.
- Existing regression tests preserve migration source reconciliation, promotion gates, Phase 3C isolation, mechanical rules, dependency traversal and exact legacy ECU fingerprints. No full unit suite, real MongoDB, live LLM, dashboard or benchmark run was performed. Persistence and UI were not modified.

### Exact files changed and Git status

- Created: `app/investigation.py`, `tests/unit/test_investigation.py`.
- Modified: `README.md`, `PROJECT_PROGRESS.md`.
- Existing production modules/tests, UI, API, persistence, CI and dependencies were unchanged. No commit or push performed.

### Limitations and remaining Phase 4 work

- Library/backend only: no investigation endpoint, job-backed baseline retrieval, durable report storage, authenticated investigator/reviewer or Phase 4C UI. Callers must provide the authoritative snapshot; its digest identifies content but does not authenticate approval or prove it remains current in an external database.
- Offline extraction is conservative keyword/identifier matching, not unrestricted language understanding. LLM planning uses bounded validated tool requests, but real-provider planning quality, availability and latency remain unverified. Large snapshots/tool outputs have not been performance-tested; bounds limit calls/traversals, not total output bytes or deterministic-tool wall time.
- Reports expose dataset-wide graph diagnostics as unresolved evidence; some may be outside a narrowly requested component. Mechanical fit/strength, real vehicle safety and unsupported relationships remain unknown. Verification keeps existing synthetic rules and default date 2025-06-01. Cross-variant comparison is descriptive; original/proposed comparisons require an explicit what-if proposal.
- Recommended next approved scope: define a read-only investigation API/service adapter with authoritative baseline loading, authentication and report lifecycle requirements before Phase 4C UI integration. No subsequent phase or dashboard work started.


## Dashboard presentation redesign (2026-11-12)

**Status: Implemented and verified with focused AppTest/static checks. Browser visual acceptance remains unverified.** Existing uncommitted Phase 3D work was preserved; no engineering-domain or backend behavior changed in this redesign.

### Changes and preserved functionality

- Added native Streamlit light-theme defaults (`#F5F7FA` main background, white secondary background, navy text and professional blue accent) and centralized dashboard CSS. Removed conflicting navy-background/light-heading inline rules and switched configuration charts to Plotly's white template. Shared styling covers text, captions, labels, inputs, primary/secondary buttons, notifications, expanders, tables, metrics, focus states and navigation. Primary-button text explicitly remains white against blue.
- Added a branded automotive engineering header, sidebar identity and readable active/hover states. Native navigation labels and all nine workspace choices remain unchanged. Material icons are used for supported buttons and the application icon.
- Reorganized the same six backend-derived overview metrics into two rows of three cards, retained the job register, and added working shortcuts to Migration, Interactive 2D Vehicle and Agent Review Queue. No synthetic metrics or engineering conclusions were added.
- Restyled the vehicle SVG with a white canvas, light structure, navy labels, blue selection outline and muted status colors. Preserved record IDs, all click/keyboard event wiring and state semantics. The iframe uses bounded scrolling and a minimum diagram width so dense diagrams do not shrink into unreadable text.
- Reorganized the vehicle workspace into a wide schematic and bordered component inspector with separate original/proposed revision cards and a colored text legend. Proposal JSON import is collapsible; selection, proposal import/selection, original/proposed views, reset, findings, record evidence and report export remain available. Responsive CSS wraps columns on narrow screens.
- All migration, compatibility, digital twin, simulation, agent review, benchmark and audit workflows retain their controls and API integration. Only presentation code/theme settings and focused UI assertions changed; no engineering rules, fingerprints, dependency analysis or what-if calculations changed. No new dependency was added.

### Actual verification

Commands used `.\.venv\Scripts\python.exe`:

| Check | Command arguments after Python | Result |
|---|---|---|
| Focused UI regression | `-m pytest tests/unit/test_dashboard.py tests/unit/test_vehicle.py -q --basetemp=.pytest_tmp/light-dashboard -p no:cacheprovider --tb=short` | **18 passed in 33.32 seconds** |
| Added overview shortcut/actual job-count assertion | `-m pytest tests/unit/test_dashboard.py -k Overview -q --basetemp=.pytest_tmp/light-navigation -p no:cacheprovider --tb=short` | **1 passed, 8 deselected in 6.82 seconds** |
| Ruff | `-m ruff check dashboard tests/unit/test_vehicle.py tests/unit/test_dashboard.py` | **Passed** |
| Scoped Mypy | `-m mypy dashboard/app.py dashboard/vehicle.py dashboard/vehicle_workspace.py` | **Success, three source files** |

The focused run exercises all nine workspaces, migration generation/start and simulation controls; vehicle tests cover actual record mapping, proposal selection, revision/impact states, original/proposed switching, reset and simulated SVG selection. The existing selected-marker assertion was updated to the new blue outline. The additional overview check verifies the real fixture job count and successful shortcut navigation. No full unit suite, engineering-only suite, MongoDB or benchmark run was needed for these presentation changes.

### Exact files changed in this redesign

- Created: `.streamlit/config.toml`, `dashboard/theme.css`.
- Modified: `dashboard/app.py`, `dashboard/vehicle.py` (SVG palette only), `dashboard/vehicle_workspace.py` (layout only), `dashboard/vehicle_component/index.html` (styling/frame sizing only), `tests/unit/test_dashboard.py`, `tests/unit/test_vehicle.py`, `README.md`, `PROJECT_PROGRESS.md`.
- Previously uncommitted Phase 3D files and edits remain present. No commit or push performed.

### Limitations and next step

- AppTest validates workflows, not rendered CSS contrast, actual browser pointer/keyboard dispatch, mobile breakpoints or screenshot appearance. Those remain unverified; no WCAG conformance or live-browser acceptance is claimed.
- CSS uses Streamlit test IDs/BaseWeb selectors and modern `:has()` support; future framework changes may require selector maintenance. Native theme defaults require launch from the project root. Wide diagrams intentionally scroll on small screens.
- Next recommended step: live-browser desktop/mobile acceptance, including notification/input contrast, sidebar active/focus states and SVG scrolling/selection. Persistent proposals, authentication, Agentic AI and other engineering features remain outside this redesign. No further task started.


## Phase 3D — Interactive 2D Digital Vehicle (2026-11-12)

**Status: Implemented and focused-tested in the existing Streamlit dashboard. Live-browser acceptance remains unverified.** This entry supersedes historical statements below that all impact UI/2D visualization remains unimplemented. Phase 1–3C domain behavior and migration safeguards were unchanged.

### Implementation and decisions

- Inspected only the dashboard/API, existing what-if and graph/twin interfaces, publication reader and relevant fixtures/tests. The starting working tree was clean. Reused Streamlit and its bundled custom-component bridge without adding dependencies or rebuilding the backend.
- Added the Interactive 2D Vehicle workspace. Approved baselines come from the existing integrity-checked `/jobs/{job_id}/approved` reader; other jobs use explicitly labelled staging records from the existing report. All API calls in this workspace are reads.
- Added a presentation adapter over actual twin membership, existing graph evidence and Phase 3C assessment reports. Component IDs, revisions, before/after variant applicability, electronic configuration, BOM relationships and explanatory paths come from records/engine output. No dependency traversal or compatibility rules were reimplemented in the UI.
- Added an SVG vehicle silhouette and labelled engineering zones, clickable record overlays and category badges based on explicit record metadata. Brakes, suspension, powertrain/battery, mechanical and electronic zones are illustrative. No missing physical component is fabricated. The custom iframe sends actual record IDs through Streamlit's component protocol; marker strings are HTML-escaped. Enter/Space and a native selector provide keyboard interaction.
- Added session-scoped import/selection of existing typed proposal JSON. Each selection runs the existing isolated engine against the current baseline, validates optional job context and rejects stale results. Original/proposed view switching and reset do not mutate engineering records. Added distinct unchanged/modified/potentially-affected/added/removed/unknown states, including retained markers for additions/removals in both views.
- Added selected-component details, revision comparison, affected-record table, findings, diagnostics, full provenance paths, unknown/truncated consequences and assessment download. Baseline engineering findings use the existing verifier. Assessments run in the Streamlit process; there is no new proposal endpoint, database collection, apply/publish action or automatic approval.
- Added `dashboard/__init__.py` to give scoped Mypy a consistent package identity; no broader packaging refactor. Corrected two line lengths and package resolution identified by initial static checks.

### Actual verification

Commands used `.\.venv\Scripts\python.exe`:

| Check | Command arguments after Python | Actual result |
|---|---|---|
| Focused vehicle/dashboard | `-m pytest tests/unit/test_vehicle.py tests/unit/test_dashboard.py -q --basetemp=.pytest_tmp/vehicle -p no:cacheprovider --tb=short` | **18 passed in 24.53 seconds** |
| Relevant regression, including final applicability/badge changes | `-m pytest tests/unit/test_vehicle.py tests/unit/test_dashboard.py tests/unit/test_what_if.py tests/unit/test_mechanical.py tests/unit/test_dependencies.py tests/unit/test_engineering.py tests/unit/test_migration.py -q --basetemp=.pytest_tmp/vehicle-regression -p no:cacheprovider --tb=short` | **158 passed in 17.66 seconds** |
| Ruff | `-m ruff check dashboard tests/unit/test_vehicle.py tests/unit/test_dashboard.py` | **Passed** |
| Scoped Mypy | `-m mypy dashboard/vehicle.py dashboard/vehicle_workspace.py` | **Success, two source files** |

- Nine new vehicle tests cover actual record/twin mapping, mechanical variant isolation, BOM provenance/electronic relationships, SVG selectable IDs and escaping, original/proposed switching, modified and potential-impact highlights, unknown references, add/remove markers, stale-result rejection, baseline immutability and the iframe selection protocol.
- Streamlit AppTest additionally loads a proposal, selects it, switches to proposed, selects a component, resets to original and handles a simulated SVG selection event. Added the ninth workspace to the existing dashboard/API TestClient checks, preserving the other eight cases.
- Existing what-if, mechanical, dependency, engineering/twin and migration regressions passed; mechanical tests retain four exact legacy fingerprints. No production engine or migration gate was changed.
- No complete unit suite, real MongoDB integration, live browser, benchmark or live LLM run was performed. No persistence was modified. Mocked-backend AppTest is not evidence of a live dashboard/MongoDB deployment or actual browser click dispatch.

### Exact files changed

- Created: `dashboard/__init__.py`, `dashboard/vehicle.py`, `dashboard/vehicle_workspace.py`, `dashboard/vehicle_component/index.html`, `tests/unit/test_vehicle.py`.
- Modified: `dashboard/app.py`, `tests/unit/test_dashboard.py`, `README.md`, `PROJECT_PROGRESS.md`.
- No dependencies, CI, API, persistence or engineering-domain modules changed. No commit or push performed.

### Limitations and next recommended work

- Native SVG markers are implemented, but browser rendering, pointer/keyboard event delivery and layout still need a live-browser acceptance check. Automated checks validate markup/protocol and simulate its Python-side event response; they do not execute iframe JavaScript in a real browser.
- Imported proposals are session-scoped, not durable/authenticated engineering records. No proposal editor, persistent list, approval or application workflow exists. Reset changes the view only; it does not discard or delete a proposal.
- Schematic zones and positions are illustrative. Explicit electronic functions/mechanical types determine badges; uncategorized records remain in the selectable overlay. No suspension/battery entity, geometry, mounting or physical compatibility is invented. Variant applicability means membership in constructed configurations, not engineering authorization.
- Small synthetic configurations are the verified scope. Large-fleet performance, filtering and dense-label usability remain unverified. Existing graph bounds and unassessed relationships remain visible through reports.
- Next recommended task: live-browser acceptance of selection, keyboard navigation and layout against representative mechanical/electronic records; then separately scope an authenticated persistent proposal lifecycle if approved. No 3D, LangGraph, Agentic AI or subsequent phase was started.


## Phase 3C — Isolated What-if Assessment (2026-11-12)

**Status: Implemented and focused-tested as an in-memory library. Broader Phase 3 remains in progress.** This checkpoint supersedes earlier statements that proposals are pending. On resume, `git status --short` was empty: Phase 3A/3B implementation was already present, but no Phase 3C module/tests or progress entry existed. No partial Phase 3C implementation was recreated.

### Implemented and architectural decisions

- Added `EngineeringProposal`, typed whole-record `RecordChange` operations and `Assessment` results in `app/what_if.py`. Captures proposal ID, creator, timezone-aware timestamp, optional job/product/variant context, baseline reference/digest and evidence. Supports add, replace and remove for existing domain entities; rejects duplicate operations, missing/existing identity conflicts, mismatched IDs, kind changes and invalid domain schemas.
- Canonical baseline digest uses existing Dataset serialization and SHA-256 digest utility, sorting records without changing meaningful list ordering. Duplicate baseline identities fail closed. Digest mismatch returns `stale` without executing changes or constructing a candidate.
- Deep-copy baseline records, revalidate proposal models, apply edits in deterministic ID order, and build original/proposed twins through existing builders. Compare all variants to retain shared-component exposure even when a narrower context is supplied. No existing fingerprint algorithm or serialization was modified.
- Reuse typed dependency graphs and reverse traversal for original and proposed configurations, preserving evidence for removed relationships, provenance, variant context, diagnostics, cycle handling and per-seed truncation flags. Direct change evidence includes before/after records; paths identify indirect assemblies, BOMs and variants.
- Run independent baseline/proposed engineering verification without source reconciliation. Intentional differences remain report evidence, never migration approval. Reports include both twin snapshots, differences, findings, diagnostics, date and explicit unassessed consequences. `assessed` describes execution, not validity or authorization.
- Pure discard returns a separate discarded result with candidate/report removed, retaining original proposal evidence. No database, migration service, source, staging or publication write is available. Existing migration gates remain unchanged.

### Actual verification

All commands used `.\.venv\Scripts\python.exe`:

- Initial Phase 3C checks: **12 passed in 0.32 seconds**. Added assignment/hardware coverage afterward.
- Combined relevant regression command: `-m pytest tests/unit/test_what_if.py tests/unit/test_mechanical.py tests/unit/test_dependencies.py tests/unit/test_engineering.py tests/unit/test_migration.py tests/unit/test_domain_mapping.py tests/unit/test_source_adapters.py tests/unit/test_mapping_workflow.py tests/unit/test_persistence_api.py tests/unit/test_traceability.py -q --basetemp=.pytest_tmp/what-if-regression -p no:cacheprovider --tb=short`: **238 passed in 17.64 seconds**.
- After replacing the union TypeAdapter with the existing Dataset validator for Mypy compatibility, final focused command: `-m pytest tests/unit/test_what_if.py -q --basetemp=.pytest_tmp/what-if-final -p no:cacheprovider --tb=short`: **14 passed in 1.03 seconds**.
- Ruff: `-m ruff check app/what_if.py tests/unit/test_what_if.py`: passed after correcting fixture naming and import spacing.
- Scoped Mypy: `-m mypy app/what_if.py`: **Success, one source file**. Earlier adapter annotations failed static checking; using the existing Dataset boundary resolved this without suppressing errors.
- Baseline immutability assertions cover mechanical multi-edits, electronic version and variant assignment, including mutation of a returned candidate; baseline records remain equal to their original fixture. Combined regressions include four exact pre-Phase-3B fingerprints and existing migration/promotion safeguards.
- Tests also cover stale digest, discard, invalid operations/schema/duplicate baseline, add/remove and dangling diagnostics, provenance paths, variant isolation, deterministic reversed input, bounds and precise hardware differences.
- No complete unit-suite, real MongoDB, dashboard, benchmark or live LLM run was performed. Persistence/collections were not modified, so MongoDB integration was not required by this task. Historical MongoDB results below remain historical.

### Exact files and Git status

- Created: `app/what_if.py`, `tests/unit/test_what_if.py`.
- Modified: `README.md`, `PROJECT_PROGRESS.md`.
- Reused the existing mechanical fixture; no previous production code or tests were changed. No commit or push performed.

### Known limitations and next step

- In-memory only: no persistent lifecycle, API, UI, authenticated creator, apply/publish action or secure erasure. Frozen models contain mutable nested payloads; returned snapshots are detached copies, not tamper-proof stored evidence. Callers must supply the authoritative current baseline when assessing; the digest does not authenticate its origin.
- Whole-record edits only; one operation per ID, no rename/kind conversion or occurrence-level patch language. Schema-invalid requests fail rather than producing partial assessments. Structurally invalid but schema-valid candidates are reported with findings/diagnostics.
- Engineering checks retain existing synthetic rules and default `as_of=2025-06-01`; no physical fit, strength, safety or invented compatibility rules. Graph paths represent potential exposure, may truncate, and are not effectivity-filtered. Existing unsupported relationships remain unassessed.
- Next recommended approved task: define an authenticated, persistent proposal lifecycle and baseline retrieval contract before exposing assessments through API/UI. The 2D schematic and Agentic AI remain unimplemented; no further task is started.

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

### Dashboard entry-point rename
- Renamed dashboard/app.py to dashboard/streamlit_app.py
  to avoid collision with the root app Python package.
- Updated active test, architecture, file inventory and launch references.
- No engineering logic changed.
