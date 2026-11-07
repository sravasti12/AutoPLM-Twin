# Phase 4: migration persistence and API boundaries

MongoDB remains the only application database. Unit checks explicitly use mongomock; real integration checks use PyMongo against isolated random `autoplm_test_*` databases. No transaction or replica-set requirement is introduced.

## Immutable source snapshots

Each captured row has a job namespace, original source identifier, source payload and SHA-256 digest. Insert-only upserts preserve existing source values. New jobs also store the expected source count and a digest of the complete source snapshot sorted by source identifier. Source reads check row annotations, per-row content hashes, count and whole-snapshot hash. Missing, extra, altered or misbound rows fail explicitly instead of becoming a new reference.

Idempotent job IDs hash the submitted dataset, mapper mode and pipeline version. Version 1.3 introduces source/publication manifests and operation tokens. Replaying an identical completed job returns its existing state; explicitly failed jobs may retry. Older approved jobs without the new publication manifest fail the new approved-reader contract. Re-submit the original upload to create a version 1.3 job and review/promote it; approved history is not rewritten.

## Staging and publication

Source IDs remain attached to staging records. Mapping validation, engineering verification, source reconciliation and twin comparison precede promotion. Candidate checks cannot persist a staging verification result: that result must be computed from the actual staging collection.

Persisted verification claims a compare-and-set `verifying` state with a unique token. It cannot run over an approved job, an active promotion/repair/verification, or a job awaiting mapping review. Only the matching token may commit the result. Failures leave an explicit failed state. Operator recovery includes interrupted verification and clears old tokens; it is only appropriate after confirming the worker has stopped.

Human promotion revalidates staging, checks its digest, and claims `promoting` with a token and revision. It copies records into per-job entity collections, checks the entire materialized copy against verified staging, records authorization and commits one publication manifest containing approved count, digest and reviewer. A lost token/revision cannot publish or reset another operation's state. An interrupted uncommitted copy is hidden and may be refreshed on retry.

`Repository.approved_records` and `GET /jobs/{id}/approved` require the committed job state, intact source provenance, correct entity-wrapper identities, approved count and a content digest independent of retrieval order. Missing or modified approved data is rejected. Direct queries against entity collections bypass this reader contract and must not be used as approved engineering reads.

Application-level compare-and-set checks are not distributed leases or protection against a malicious database administrator. Source hashes and publication manifests are integrity checks, not externally signed records. Audit events remain append-only by application convention.

## API validation and errors

Upload requests validate their nested envelope before migration: known source schema, known entity kind, source identifier and strict Boolean synthetic marker. Request models reject unknown top-level fields. Approval decisions require a JSON Boolean and a nonblank, trimmed reviewer name; strings such as `"yes"` are not approvals. Reviewer identities are annotations, not authenticated users.

Request schema errors return 422; invalid job states, provenance failures and integrity conflicts return 409; unknown jobs/variants return 404; database failures return 503 without exposing private driver messages. The health endpoint checks process availability; readiness pings MongoDB. Approved records, JSON reports, escaped HTML reports and CSV findings are distinct read paths.

## Real integration and CI

```powershell
docker compose up -d --wait --wait-timeout 120 mongo
$env:AUTOPLM_TEST_MONGODB_URI = 'mongodb://127.0.0.1:27017'
python -m pytest tests/integration -q --junitxml=benchmarks/phase4-integration-tests.xml
python -m pytest tests/unit/test_persistence_api.py tests/unit/test_migration.py tests/unit/test_traceability.py tests/unit/test_api_benchmark.py -q --junitxml=benchmarks/phase4-unit-tests.xml
```

Tests create and remove only fresh UUID-named test databases. They never select the application's MONGODB_DATABASE. Integration covers both source schemas, promotion/idempotency, source/publication corruption, unique indexes, rejection of invalid source engineering and FastAPI reads/exports through a real repository.

CI pins Ubuntu 24.04 and checks out source before starting Docker. It runs independent unit tests first, then starts the project's MongoDB Compose service with a bounded health wait, pings from the runner and runs real integration tests. Failure diagnostics create their output directory and capture Compose status/logs. Cleanup uses only the `autoplm-ci` Compose project. JUnit files are separate for unit and integration checks. The new CI configuration is locally checked; its remote run must be assessed separately from local integration evidence.
