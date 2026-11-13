# AutoPLM Twin implementation progress

All engineering data and behavior in this project are synthetic.

## Editable installation verification - Streamlit Community Cloud (2026-11-13)

**Status: local editable installation and outside-checkout import/UI verification passed. Ready for a fresh
Community Cloud dependency installation; actual hosted rebuild/result is unverified.** On resume, HEAD was
`ac86cb8` (`fix: use editable install for Streamlit deployment`) and the working tree was clean. The requested
requirements change was already present; this verification did not create a commit or push anything.

### Confirmed configuration and scope

`requirements.txt` contains exactly:

```text
-r requirements-lock.txt
-e .
```

Existing setuptools discovery includes app* and dashboard*. The tracked dashboard/__init__.py is valid;
CSS and vehicle HTML package-data rules remain intact. No changes to package discovery, imports, dependency
versions, authentication, OIDC, MongoDB security or engineering logic were necessary during this resume.
No sys.path or PYTHONPATH workaround was introduced.

### Clean installation and requested imports

- Completed the fresh isolated venv installation prepared before the usage interruption at
  `artifacts/dashboard-editable-check-2e89f757/venv` (Python 3.13.3, system site-packages disabled).
  `pip install -r requirements.txt --no-compile` consumed the unchanged locked dependencies and explicitly
  built/installed the editable project from requirements line 2. Build/runtime downloads needed approved
  network access; no dependencies or metadata in the normal development environment were changed.
- Then, from an OS temporary working directory outside the repository, ran the fresh interpreter with
  `-m pip install --no-deps --editable "C:\Users\KIIT\Desktop\AutoPLM Twin"`. This verified the actual
  checkout's editable installation independently of the working directory. Existing dependencies were retained.
- Ran an isolated (`-I`) import/asset/UI smoke script from that same external directory. Distribution
  direct_url.json reports editable=true and the actual checkout URL; all imports resolve to the intended
  checkout through the installed editable mapping, not a temporary manual search-path change.
- Explicitly imported app, dashboard, dashboard.streamlit_app and dashboard.public_workspace successfully.
  Also imported investigation_workspace, reviewer_login, vehicle and vehicle_workspace: eight checked imports.
- Dashboard theme.css and vehicle_component/index.html were accessible; both public sample artifacts loaded
  and validated. Executed the public entry point through AppTest twice, including revision-drift sample
  selection, with backend HTTP requests forbidden. Bare entry-point import emits expected Streamlit
  missing-ScriptRunContext warnings outside its runner; no import exception occurred.
- Fresh-environment `pip check`: **No broken requirements found**. Isolated verification scripts/logs remain
  under ignored artifacts; no tracked application diagnostic helper was added.

### Tests and static checks in the isolated environment

- `-m pytest tests/unit/test_dashboard.py tests/unit/test_public_samples.py tests/unit/test_vehicle.py tests/unit/test_reviewer_login.py -q --basetemp=artifacts/dashboard_editable_resume_final -p no:cacheprovider --disable-warnings`: **88 passed in 15.88s**, 91 upstream mongomock deprecation warnings. The initial fresh-environment run had 87 passes and one 15-second AppTest timeout on the first Overview render; the unchanged full selection passed on rerun after imports warmed. No timeout or production/test behavior was weakened.
- Ruff on dashboard and those four test files: **passed**.
- Scoped Mypy on streamlit_app, public_workspace, investigation_workspace, reviewer_login, vehicle and vehicle_workspace: **passed, six modules**.
- `git diff --check`: **passed**.

### Changed files and remaining Cloud verification

Only **PROJECT_PROGRESS.md** changed during this resume. requirements.txt already contained the editable
fix in the existing commit; pyproject.toml and all application/test/security files were left unchanged.

Streamlit documents that dependency-file changes trigger dependency resolution/full redeployment when the
updated GitHub revision is consumed: [Community Cloud app updates](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app).
The watched root requirements.txt change is already recorded in ac86cb8. Confirm the Cloud app builds that
revision/branch, reads this root dependency file and logs the editable installation before checking startup.
This session did not trigger a remote build or claim a successful Linux/Community Cloud deployment; a fresh
hosted dependency installation and its logs remain the final external verification. No deployment, commit,
push, historical audit edit or engineering-data change was performed.


## Streamlit Community Cloud dashboard packaging fix (2026-11-13)

**Status: packaging fix implemented and verified with a fresh isolated installation.** Initial working
tree was clean. No authentication, authorization, OIDC, MongoDB security or engineering logic was changed.

### Cause and minimum fix

- `requirements.txt` installs the project using `.`. Setuptools discovery included only `app*`, so installed
  distributions omitted dashboard even though repository-based tests/imports could see it.
- Existing `dashboard/__init__.py` is already tracked and valid; no new initializer or import workaround needed.
- `pyproject.toml` discovery now includes `app*` and `dashboard*`, including dashboard Python submodules.
- Added dashboard package data for `theme.css` and `vehicle_component/*.html`. Existing CSS/component paths
  are relative to module files and work in an installed package. Existing app/public_data JSON inclusion remains.
- Imports and application architecture are unchanged. No sys.path modification was introduced.
- Optional `benchmarks/results.json` remains repository-root-relative, with its existing empty state outside a
  checkout; it is not required to start the public dashboard. Community Cloud should launch from repository root.

### Exact files modified

- `pyproject.toml`: package discovery and dashboard asset inclusion.
- `PROJECT_PROGRESS.md`: this checkpoint and actual verification results.

### Verification

- Focused dashboard/public/vehicle/reviewer UI regressions: `-m pytest tests/unit/test_dashboard.py tests/unit/test_public_samples.py tests/unit/test_vehicle.py tests/unit/test_reviewer_login.py -q --basetemp=artifacts/dashboard_package_regression -p no:cacheprovider --disable-warnings` - **88 passed in 22.80s**, 91 upstream mongomock deprecation warnings.
- Ruff: `-m ruff check dashboard tests/unit/test_dashboard.py tests/unit/test_public_samples.py tests/unit/test_vehicle.py tests/unit/test_reviewer_login.py` - **passed**.
- Scoped Mypy: `dashboard/streamlit_app.py dashboard/public_workspace.py dashboard/investigation_workspace.py dashboard/reviewer_login.py dashboard/vehicle.py dashboard/vehicle_workspace.py` - **passed, 6 source files**.
- Fresh installation: created a new venv without system site-packages under ignored `artifacts/dashboard-package-check-7af373dc/`. Copied current app/dashboard/pyproject sources to its isolated source directory so build products do not touch the working source tree. Ran `pip install .` with existing requirements-lock.txt as constraints, using normal isolated wheel building. Initial sandbox network restrictions blocked setuptools downloads; approved elevated installation was used for the verification environment only.
- Clean installation completed successfully using `pip install .` with the existing lock as constraints. The new venv does not use system site-packages; the existing development environment was not modified.
- From the separate empty run directory, executed the fresh venv interpreter with `-I installed_smoke.py`. The source checkout/staging source were absent from sys.path. All seven checked package/module imports resolved inside the new venv site-packages; the installed Streamlit entry point was found and executed successfully through AppTest twice (default public view and revision-drift sample selection). Both dashboard assets (CSS and vehicle HTML) and both packaged public snapshots were present and validated. HTTP requests were forbidden during public UI rendering. No sys.path workaround was used.
- Fresh environment `-m pip check` - **No broken requirements found**.
- Ignored verification evidence is under `artifacts/dashboard-package-check-7af373dc/`; the installed smoke script and log are retained there. No diagnostic helper was added to tracked application code.
- `git diff --check` - **passed**; only the two listed tracked files changed.

This is local Windows/Python 3.13.3 verification, not a Streamlit Community Cloud/Linux deployment result.
No deployment, commit or push was performed. Historical audit records and public snapshot contents were untouched.


## Phase 13B - Production OIDC Authentication (2026-11-13)

**Status: application implementation and local verification completed; real hosted authentication/deployment
acceptance remains blocked on tenant, secrets and operational setup.** Preserved all existing uncommitted
Phase 13A changes. No production configuration/secret was provisioned, no historical record was changed,
and no deployment, commit, push or live Groq call was performed.

### Verified prerequisites and architecture

- Before editing, inspected installed Streamlit **1.67.0**, its `user_info.py` token proxy, auth configuration
  handling and native Starlette OAuth routes. Confirmed named `st.login("auth0")`, top-level
  `expose_tokens=["access"]`, `st.user.tokens["access"]`, state/nonce and PKCE support. Inspected Authlib's
  authorize_params handling after installation. A test using the actual installed OAuth client confirms the
  generated authorization URL includes the dedicated audience, code flow, requested scope, state, nonce and
  S256 challenge. A named provider is used so audience is forwarded as an authorization parameter.
- Checked official Auth0 custom-API and Free-plan documentation. Use hosted login/custom API access tokens,
  not paid provider Role Management or token exchange. Engineering permissions come from controlled MongoDB
  issuer/subject grants; new authenticated accounts receive identity-only investigation_reader, never engineering
  permissions. Provider quotas/features require actual tenant verification before release.
- PyJWT/Authlib/cryptography were initially absent. Installed standard Authlib 1.9.5, PyJWT 2.15.1 and
  cryptography 50.0.2 (plus cffi 2.1.1, joserfc 1.8.0, pycparser 3.12) in the project venv. Initial sandbox
  download was denied; approved elevated installation succeeded. Existing lock entries were retained and only
  these additions appended. No custom cryptographic primitives or unrelated dependency upgrades were introduced.

### Implemented authentication and authorization

- Independent FastAPI RS256 validation: fixed algorithm, trusted HTTPS issuer-derived discovery/JWKS,
  issuer/audience, required sub/iat/exp/azp/scope, allowed client, autoplm:access scope, one-hour maximum
  lifetime and five-second clock leeway. Reject malformed/invalid-signature, wrong issuer/audience, expired,
  ID-token-shaped and machine-credential tokens. Token-supplied key URLs are never fetched.
- JWKS responses are capped at 64 KiB/16 signing keys and verified RSA key sizes; cache TTL is 300 seconds,
  refresh attempts are limited to once per 30 seconds with bounded network time/no redirects. Rotation and
  unavailable/malformed provider results fail closed. Valid cached keys are not replaced by malformed data.
- Runtime grants use trusted issuer + verified subject, primary reads and majority writes. Grants are read
  on each authenticated request, so enabled-state revocation denies subsequent engineering requests without
  waiting for token expiry. Email/profile/role claims and caller actor fields cannot grant access or identity.
  Existing ReviewPrincipal and decision response schemas remain intact; audit subject comes from verified sub.
- Added a trusted-host provisioning CLI using a separate protected provisioning URI. There is no public or
  reviewer API for granting roles. Grant enabled state plus appended history update atomically, with existing
  Repository.audit mirroring. Mirror failures can occur after the authoritative grant/history commits; operators
  must inspect state before retrying. Historical investigation/promotion audit records were not modified.
- Optional hosted login forwards only access tokens over the configured HTTPS backend path. Production has
  no manual static-token entry/fallback. Logout/account switches and backend identity failures/expiry clear
  private state/navigation. The native identity cookie does not extend access-token lifetime. No automatic
  refresh-token lifecycle is implemented; reauthentication is required after expiry. Logout does not globally
  invalidate tokens held in another session; role revocation blocks subsequent protected requests.
- Local static credentials remain separate in local mode. Production/staging startup now performs concrete
  OIDC discovery/JWKS, authenticated verified-TLS MongoDB and initialized shared-security-policy/index checks;
  unknown environments/incomplete configuration remain blocked. No bypass/approval flag was added. These
  checks are not a substitute for real provider callback/permission and production deployment acceptance.

### Shared abuse controls

- Atomic durable MongoDB fixed UTC-window budgets keyed by verified issuer/subject: 60 authenticated
  requests/minute, six executions/minute, ten decisions/minute; LLM one/minute and ten/day when explicitly
  enabled. Live LLM execution defaults off. Token rotation does not reset quotas; TTL indexes clean old windows.
- Two durable global execution slots plus per-resource decision serialization coordinate processes. Locks have
  no automatic expiry to avoid overlapping old/new work. A crashed worker can block capacity: approved operators
  must verify affected workers stopped and perform owner-conditional recovery, recording history/audit.
- Production body cap 2,000,000 bytes and ten-second receive deadline; bounds of 12 investigation steps,
  100 simulation ticks, ten generated fleets and 500 uploaded records. Local workflows retain their previous
  bounds. Existing provider/tool bounds, terminal review CAS and promotion integrity/rollback gates are retained.
- 429 responses include Retry-After. Security logs contain fixed categories only, without tokens, claims,
  Authorization headers or database/provider exception text. Full centralized alerting/denial retention and
  anonymous edge flood controls are not implemented. There is no general forced interruption of synchronous
  engineering execution; production load/time/resource acceptance remains necessary.

### Exact Phase 13B files (in addition to preserved Phase 13A changes)

Created:

- `app/oidc_auth.py`
- `app/security_store.py`
- `app/execution_security.py`
- `dashboard/reviewer_login.py`
- `scripts/manage_reviewers.py`
- `tests/unit/test_oidc_auth.py`
- `tests/unit/test_reviewer_login.py`
- `.streamlit/secrets.example.toml` (empty secret fields/placeholders only)
- `requirements.txt`

Modified:

- `app/api.py` (verified startup interlock and execution/decision security dependencies)
- `app/review_auth.py` (production JWT/grant boundary; separate local registry preserved)
- `app/repository.py` (bounded connection pools and majority write acknowledgment)
- `dashboard/streamlit_app.py`
- `dashboard/investigation_workspace.py`
- `pyproject.toml` (Streamlit auth extra/minimum 1.67 and PyJWT crypto dependency)
- `requirements-lock.txt` (six auth/runtime dependencies appended)
- `.env.example`
- `tests/integration/test_mongodb.py`
- `README.md`
- `PROJECT_PROGRESS.md`
- `docs/PRODUCTION_READINESS.md`

### Actual verification

Commands use `.\.venv\Scripts\python.exe` with Python **3.13.3**. Authentication tests use ephemeral
locally generated RSA signing keys and mocked identity metadata/network; no real Auth0 authentication was run.

- Selected combined regressions: `-m pytest tests/unit/test_oidc_auth.py tests/unit/test_reviewer_login.py tests/unit/test_public_samples.py tests/unit/test_dashboard.py tests/unit/test_investigation_workspace.py tests/unit/test_security_boundaries.py tests/unit/test_investigation_api.py tests/unit/test_investigation_review.py tests/unit/test_review_identity.py tests/unit/test_promotion_authorization.py tests/unit/test_persistence_api.py tests/unit/test_api_benchmark.py tests/unit/test_mapping_workflow.py tests/unit/test_migration.py tests/unit/test_engineering.py tests/unit/test_vehicle.py tests/unit/test_dependencies.py tests/unit/test_mechanical.py tests/unit/test_what_if.py tests/unit/test_investigation.py tests/unit/test_investigation_llm.py tests/unit/test_investigation_reliability.py -q --basetemp=artifacts/phase13b_regression -p no:cacheprovider --disable-warnings` - **546 passed in 41.34s**, including **40 new OIDC/security/UI cases** and all 64 Phase 13A public tests. This is selected coverage, not the entire unit suite. 678 warnings originate from mongomock's deprecated datetime.utcnow in TTL handling; warning display was abbreviated, not converted into successes or ignored failures.
- Real MongoDB: `AUTOPLM_TEST_MONGODB_URI=mongodb://127.0.0.1:27017`, `-m pytest tests/integration/test_mongodb.py -q --basetemp=artifacts/phase13b_mongodb -p no:cacheprovider` - **12 passed in 13.27s**. Added real shared reviewer grant/revocation/audit, quotas, concurrency locks and majority-write checks. Only isolated random autoplm_test_* databases were created/dropped.
- Ruff: all **23 currently changed Python files** (Phase 13A plus 13B) - **passed**.
- Scoped Mypy: `app/api.py app/review_auth.py app/repository.py app/oidc_auth.py app/security_store.py app/execution_security.py dashboard/streamlit_app.py dashboard/investigation_workspace.py dashboard/reviewer_login.py scripts/manage_reviewers.py` - **passed, 10 source files**.
- `-m pip check` - **No broken requirements found**.
- Secrets example TOML parsing - passed; no values printed.
- Direct comparison against the two recorded Phase 13A canonical artifact hashes - **2/2 unchanged**, with each packaged artifact revalidated.
- `git diff --check` - passed on the final patch.
- During iteration, mongomock could not implement Database.with_options(write_concern=majority); the test adapter asserts primary/majority options and returns the mock database. Production enforcement was retained and separately exercised against real MongoDB. Initial Mypy annotations were corrected. No engineering authorization/validation gate was relaxed to fix tests.

### Remaining deployment blockers / next step

- Configure a real Auth0 Regular Web Application/custom API: RS256, 3600-second access-token lifetime,
  autoplm:access scope, matching client ID, Basic token-endpoint authentication, exact HTTPS callback/origin/
  logout URLs. Verify an actual hosted code exchange and API access token on the selected Free tenant.
- Supply protected Streamlit cookie/client secrets, matching issuer/audience/client values, explicit non-local
  environment and HTTPS backend URL. No real tenant/client secrets or production credentials were configured.
- Provision Atlas runtime/operator identities with verified TLS, primary security reads, grant read-only runtime
  access, scoped quota/lock/engineering writes, append-only audit rights, index permissions and network
  allowlists. Initialize shared security state and provision only approved reviewer subjects. Real Atlas M0,
  backup restoration and least-privilege acceptance remain unverified.
- Verify patched Python 3.13/Linux installs, Community Cloud/Render cold-start behavior and resource ceilings,
  actual browser login/logout/account switching/expired tokens, operational lock recovery and capacity/load.
  No claim of production readiness, live hosted login, installed-wheel or cloud/browser acceptance is made.
- Complete operational security logging/alerting, edge abuse handling, dependency vulnerability review and
  resource/tenant policy before real private engineering use. No distributed work queue or hard synchronous
  cancellation was added. Already-running authorized work is not retroactively stopped by revocation.
- Follow the exact configuration/provisioning/deployment roadmap in docs/PRODUCTION_READINESS.md; obtain
  explicit deployment approval only after prerequisites and measured acceptance pass. Do not set local mode
  or disable lifespan/security checks to bypass verification. Historical forged approval remains preserved
  and excluded from public samples/authorized production baseline import.


## Phase 13A - Public Demonstration Architecture (2026-11-13)

**Status: implemented; production authentication/deployment remain blocked pending Phase 13B.** Initial
working tree was clean. Existing Phase 12 protections and all historical records were preserved. No OIDC
provider code, deployment, live LLM call, commit or push was introduced.

### Implemented capabilities and decisions

- Added a strict nested Pydantic public projection contract and versioned catalog. Two curated snapshots
  (`synthetic-equivalent`, `synthetic-hardware-revision-drift`, each version 1.0.0) contain recorded engineering
  check summaries, selected-variant twin fingerprints/differences, offline investigation reports, allowlisted
  evidence/record facts, findings, missing evidence, uncertainties and recommendations.
- Generator inputs are fresh `app.data.generate(1, seed=42, source="A")` data only (13 canonical records),
  with an explicit brake hardware revision Z modification for the drift scenario. Existing deterministic
  verification/twin/investigation functions compute results. The migration summaries describe those checks
  and selected-variant comparison, not a newly persisted migration job or publication. No fabricated approval
  or benchmark is represented. Offline investigations can remain partial and disclose missing evidence.
- Catalog schema 1.0, projection public-allowlist-v1, source/target input hashes, original report hash and
  canonical public-payload SHA-256 preserve reproducibility/provenance. Evidence source_pointer refers to
  the original offline report, not a public raw-report/file endpoint. Hashes detect drift, not malicious
  replacement of an entire trusted release; artifact review remains necessary.
- `GET /public/samples` and `GET /public/samples/{sample_id}` read package resources only. Unknown sample
  or historical job IDs return 404. No arbitrary identifier/path becomes a database or filesystem lookup.
  Extra projection fields and artifact/hash mismatches are rejected; detail corruption returns sanitized 503.
- No raw MongoDB records, audit exports, credentials, registry contents or internal provider payloads are
  exposed. Only explicit synthetic record facts are retained. The historical forged job/identity/audit event
  is absent from the catalog and never used to generate samples. No application database history was changed.
- All private job/report/approved-record reads and dataset/migration/simulation/investigation execution now
  require `authorized_reviewer`. Persisted investigation report creation, queue, retrieval and history also
  require this role; reader-only accounts retain identity discovery but receive 403 on engineering routes.
  Existing promotion, repair/mapping and ACCEPT/REJECT service safeguards remain unchanged.
- Streamlit defaults to a public snapshot browser without backend calls or login. Reviewer-only navigation
  appears after backend-authenticated reviewer authorization. The backend URL is operator-configured rather
  than visitor-editable. Local bearer entry is labelled development-only and hidden outside local mode.
  Credentials are forwarded on private calls/exports; redirects are not followed on the generic request path.
  Removing/changing reviewer identity clears private session state and restores safe navigation.
- Investigation Workspace checks the reviewer role independently, including standalone rendering. Existing
  UI/HTTP fixtures were adapted to authenticate valid workflows and reject reader access. The shared local
  test credential fixture was moved to tests/conftest.py and reused rather than bypassing authorization.
- Production startup interlock and local credential restriction are unchanged. Public Streamlit browsing can
  use packaged assets without launching the API; this does not authorize a non-local API launch.

### Exact files created or modified

Created:

- `app/public_samples.py`
- `app/public_data/catalog.json`
- `app/public_data/synthetic-equivalent.json`
- `app/public_data/synthetic-hardware-revision-drift.json`
- `dashboard/public_workspace.py`
- `scripts/build_public_samples.py`
- `tests/unit/test_public_samples.py`

Modified:

- `app/api.py`
- `dashboard/streamlit_app.py`
- `dashboard/investigation_workspace.py`
- `pyproject.toml` (include JSON snapshots as app package data; no dependency changes)
- `tests/conftest.py`
- `tests/integration/test_mongodb.py`
- `tests/unit/test_dashboard.py`
- `tests/unit/test_investigation_api.py`
- `tests/unit/test_investigation_review.py`
- `tests/unit/test_investigation_workspace.py`
- `tests/unit/test_security_boundaries.py`
- `README.md`
- `PROJECT_PROGRESS.md`
- `docs/PRODUCTION_READINESS.md`

### Verification

Commands use `.\.venv\Scripts\python.exe`; no live provider calls were made.

- Focused: `-m pytest tests/unit/test_public_samples.py -q --basetemp=artifacts/phase13a_public_tests -p no:cacheprovider` - **64 passed in 16.76s**. Coverage includes every private route with missing/invalid/reader credentials before database resolution, public method restrictions, no-MongoDB/no-registry operation, path/unknown IDs, nested field allowlists, incident exclusion, hashes, deterministic regeneration, corruption failure and public Streamlit browsing with no HTTP requests.
- Combined selected regressions: `-m pytest tests/unit/test_public_samples.py tests/unit/test_dashboard.py tests/unit/test_investigation_workspace.py tests/unit/test_security_boundaries.py tests/unit/test_investigation_api.py tests/unit/test_investigation_review.py tests/unit/test_review_identity.py tests/unit/test_promotion_authorization.py tests/unit/test_persistence_api.py tests/unit/test_api_benchmark.py tests/unit/test_mapping_workflow.py tests/unit/test_migration.py tests/unit/test_engineering.py tests/unit/test_vehicle.py tests/unit/test_dependencies.py tests/unit/test_mechanical.py tests/unit/test_what_if.py tests/unit/test_investigation.py tests/unit/test_investigation_llm.py tests/unit/test_investigation_reliability.py -q --basetemp=artifacts/phase13a_regression_final -p no:cacheprovider` - **506 passed in 39.16s** (selected regressions, not the complete unit suite).
- Real MongoDB: `AUTOPLM_TEST_MONGODB_URI=mongodb://127.0.0.1:27017`, `-m pytest tests/integration/test_mongodb.py -q --basetemp=artifacts/phase13a_mongodb -p no:cacheprovider` - **11 passed in 13.84s**. Only random `autoplm_test_*` databases were created/dropped; no application history was edited.
- Ruff on all 14 changed Python modules/tests - **passed**.
- Scoped Mypy: `app/api.py app/public_samples.py dashboard/streamlit_app.py dashboard/public_workspace.py dashboard/investigation_workspace.py scripts/build_public_samples.py` - **passed, 6 source files**.
- Initial focused run had two test setup errors from a missing temporary-directory parent and two relative AppTest path failures. Corrected test paths/temp location; focused run above passed. The initial combined run had 505 passes and one obsolete reader-access expectation; updated that expectation to the approved reviewer-only policy before final verification. No engineering gate was weakened.

### Limitations and Phase 13B

- No production OIDC, token expiry/JWKS handling, verified issuer/subject role provisioning or SSO session
  lifecycle exists yet. Do not deploy the API in local mode or remove the startup block to fit free hosting.
- Public samples are two frozen offline projections, not live jobs, complete raw investigation reports,
  executed publication or proof of physical fit/safety. Public selection cannot generate/repair/simulate/decide.
  Raw original reports are intentionally not published; their hashes/pointers support offline reproduction.
- Production quotas/rate limits/concurrency budgets, resource/tenant authorization, full execution actor
  attribution, durable denial logs and complete logging/redaction controls remain work.
- Community Cloud, Render Free and Atlas M0 configuration, clean Linux install/wheel/browser acceptance,
  startup/cold-start behavior, TLS/database permissions/backups and production reviewer acceptance remain
  unverified. Existing services were not restarted and no live browser/cloud verification is claimed.
- Next step: implement Phase 13B verified OIDC access-token validation and controlled reviewer grants with
  independent server-side enforcement, then abuse controls and free-hosting verification. Update both public
  documentation and this tracker with actual results; deployment still requires explicit approval.


## Phase 12 - Production Readiness & Security Hardening (2026-11-13)

**Status: focused security hardening implemented; production readiness remains blocked.** Started from clean
`main` at `95db5b3`, matching `origin/main` (zero commits ahead/behind). No pre-existing uncommitted files
were present or overwritten. No deployment, live Groq call, commit or push was performed.

### Audit, changes and engineering decisions

- Inspected every API route and existing principal/review/service/repository boundaries. The full endpoint
  matrix is in [docs/PRODUCTION_READINESS.md](docs/PRODUCTION_READINESS.md).
- Fixed unauthenticated repair proposals, repair decisions and mapping decisions. All now require the existing
  `authorized_reviewer` dependency. Server-derived principal subject is passed into existing service methods;
  legacy actor fields remain optional/deprecated for client compatibility and cannot override audit identity.
  The repair proposal no longer uses the provider mode as proposed_by.
- Promotion and persisted investigation report/review gates were already authenticated. Preserved their role
  semantics, strict validation, terminal decision history, source/staging digests, lock/publication/rollback
  behavior and engineering safeguards. No service, repository, fingerprint or engineering-rule code changed.
- Updated the existing Agent Review Queue to use a password-type credential, backend `/review/me` identity
  and bearer forwarding for mapping, repair and promotion. Caller-entered reviewer name removed. Reader
  promotion remains denied by the backend; the UI displays an error instead of losing it during a rerun.
- Added no-store/nosniff response headers, generic 404/409 domain errors and sanitized legacy dashboard
  request errors. Status codes and validation reports remain available; this is not a complete logging audit.
- Added an explicit local-only environment boundary: default `AUTOPLM_ENVIRONMENT=local` preserves local
  workflows; any other value blocks API startup and static-credential authentication. This deliberately blocks
  production launch until a genuine provider integration is implemented and verified. No replacement auth
  mechanism or production-ready authentication claim was introduced.
- Reviewed environment settings, local MongoDB Compose, CORS absence, private service topology, TLS/proxy,
  readiness and error handling. Added ignored local environment/temp patterns; no credential values added.

### Historical incident disposition

Original job `1159cf031e93874f8a12c0a1`, approved_by `forged-user`, 26 records and audit event
`6bf86c49-04f7-4691-95a8-7d98841aa03e` remain historical evidence. Prior runtime findings below are
preserved, including the uncertainty about reload failure. No application database record or historical
identity was edited. Disposition is synthetic incident/local acceptance evidence only, excluded from production
baseline import/use pending an independently authorized baseline. This is a documented operational restriction,
not an implemented quarantine flag. Phase 12 tests use mock or isolated random integration databases.

### Exact files changed

- `app/api.py`: reviewer dependencies/actor enforcement, startup interlock, safe errors and response headers.
- `app/review_auth.py`: reject local static credentials outside local mode; hashing/comparison unchanged.
- `dashboard/streamlit_app.py`: authenticated decision controls/requests and sanitized error handling.
- `tests/unit/test_security_boundaries.py` (new): 23 focused security/dashboard regression cases.
- `.env.example`: documented local-only environment setting; no populated registry or secret.
- `.gitignore`: ignore local `.env.*` files (retain example) and Phase 12 temporary test directories.
- `docs/PRODUCTION_READINESS.md` (new): route audit, incident disposition, deployment architecture,
  provider choices, MongoDB controls, production blockers and ordered deployment/restart instructions.
- `README.md`: Phase 12 capability/limitations, corrected legacy actor/RBAC descriptions and guide link.
- `PROJECT_PROGRESS.md`: this implementation/verification checkpoint; previous history retained.

### Tests and verification

Commands use `.\.venv\Scripts\python.exe`; no live provider was invoked.
New coverage: missing/invalid/reader credentials on all three newly protected routes, forged actor ignored,
server identity persisted on repair propose/reject, production/staging startup refusal, static credentials
rejected outside local mode, sanitized exceptions/headers, and reviewer/reader dashboard promotion behavior.
The first broader run exposed an error-display problem on reader denial; fixed before the final run.

- Focused security tests: `-m pytest tests/unit/test_security_boundaries.py -q --basetemp=.pytest_phase12/focused_final -p no:cacheprovider` - **23 passed in 9.71s**.
- Final combined regression: `-m pytest tests/unit/test_security_boundaries.py tests/unit/test_promotion_authorization.py tests/unit/test_review_identity.py tests/unit/test_investigation_review.py tests/unit/test_persistence_api.py tests/unit/test_dashboard.py tests/unit/test_mapping_workflow.py tests/unit/test_investigation_api.py tests/unit/test_investigation_workspace.py tests/unit/test_migration.py -q --basetemp=.pytest_phase12/regression_final -p no:cacheprovider` - **207 passed in 48.57s** (selected tests, not the complete unit suite).
- Real MongoDB: `AUTOPLM_TEST_MONGODB_URI=mongodb://127.0.0.1:27017`, `-m pytest tests/integration/test_mongodb.py -q --basetemp=.pytest_phase12/integration -p no:cacheprovider` - **11 passed in 17.19s**. Tests create/drop only random `autoplm_test_*` databases; existing application evidence untouched.
- Ruff: `-m ruff check app/api.py app/review_auth.py dashboard/streamlit_app.py tests/unit/test_security_boundaries.py` - **passed**.
- Scoped Mypy: `-m mypy app/api.py app/review_auth.py dashboard/streamlit_app.py` - **passed, 3 source files**.
- `git diff --check` - passed on the final patch.

### Remaining blockers and next step

Production identity/SSO and token lifecycle are unimplemented. Public prototype job/data/report/execution
routes still need authenticated, resource-scoped access and request budgets before external exposure.
Local Compose has no database authentication and is not production configuration. Production MongoDB
TLS/least privilege/index provisioning, independent audit retention, backup/restore, TLS/session/proxy,
logging/redaction/rate controls, dependency vulnerability review and supervised startup remain unverified.
Local services on 8010/8510 were not restarted or browser-tested with these edits; new UI verification uses
AppTest with FastAPI and a mocked repository. The prior live local acceptance results remain historical,
not a fresh Phase 12 live-browser claim. No deployment artifacts were applied or historical data rewritten.

Next recommended grouped change: choose the organization identity provider and implement/verify its
resource-server/session integration, then close the remaining public-route policy gaps before permitting a
non-local launch. Follow the production guide's ordered verification checklist; request deployment approval
only once those blockers are resolved. Do not change local mode to bypass the interlock.


## Local acceptance and promotion security verification (2026-11-13)

**Status: Selected security tests and the live local offline investigation/review workflow passed. Deployment was not performed.** Preserved all pre-existing uncommitted work. No application authorization, engineering, API or persistence logic was changed in this task; the protected endpoint source was already correct.

### Incident cause and runtime correction

- Confirmed job `1159cf031e93874f8a12c0a1` was approved with `approved_by=forged-user`, 26 materialized records, and original `promotion_authorized` audit event `6bf86c49-04f7-4691-95a8-7d98841aa03e` at `2026-11-12T20:17:38.716000+00:00`. Read but did not delete, rewrite or repair that event/identity.
- The serving `/openapi.json` on 8000 identified AutoPLM but advertised no promotion security requirement, contrary to the source dependency. Two native Uvicorn supervisor/worker trees were present, alongside Docker/WSL listeners on the default development ports. This was stale unprotected runtime code being reached, not a demonstrated bypass of the current `authorized_reviewer` dependency. Why the old reload supervisors failed to refresh is not independently established.
- Stopped the native AutoPLM API trees and started one isolated loopback API at `http://127.0.0.1:8010`, without reload. The actual served application object was inspected before serving: module path `C:\Users\KIIT\Desktop\AutoPLM Twin\app\api.py`, promotion parameters include `principal`, and dependencies include `authorized_reviewer` and `get_service`. Live OpenAPI exposes HTTPBearer for promotion. Port 8000 then identified the unrelated Equipment Reliability Prediction API; its containers were preserved.
- Preserved the matching original backend environment and original owner-protected token; did not regenerate/expose it or print a registry. A temporary memory-only reader credential was provisioned for acceptance and revoked afterward. Local Streamlit is available on `http://127.0.0.1:8510`, explicitly targeting 8010. No deployment or public binding was introduced.
- Actual live authorization results: correct reviewer identity 200; incorrect credential 401; unauthenticated `{"approve":true,"actor":"forged-user"}` against the existing job 401; reader promotion 403. No authenticated promotion was reissued against the existing job. New-promotion actor/audit identity was proved in isolated regression databases instead.

### Existing baseline and actual Streamlit workflow

- Existing publication/source integrity, schema/reference checks and selected twin fingerprint passed using the Phase 4B loader. All 26 records remain unchanged; selected F0000-standard fingerprint is `7fe9acfe2ef1e46c4bca359dbc6077adfab01822a1f28b7561badd9da1ed568d`. Usable for local synthetic acceptance, with the original unauthorized approval clearly retained as an incident; it is not retroactively a legitimate engineering approval.
- Streamlit AppTest exercised the real entry point against live local FastAPI/MongoDB, not mocked HTTP: authenticated identity, selected the existing approved baseline/variant/component, submitted real offline investigation reports, inspected retrieved evidence/provenance and missing conditions, and submitted explicit confirmed recommendation decisions.
- ACCEPT report: `7a42d001-8637-49a8-90fd-cd19c6fb32a8` — persisted accepted, six evidence entries, three missing conditions, one decision with the authenticated reviewer and successful audit mirror.
- REJECT report: `03ae4e52-0be0-4d20-a43b-819eb2b64cbb` — persisted rejected, six evidence entries, three missing conditions, one decision with the authenticated reviewer and successful audit mirror.
- Reader decision submissions returned 403 on both reports; terminal decision controls were disabled after refresh. Temporary reader removal was verified by 401 afterward. Original job document, all approved records and every original audit document were compared unchanged. Only the two authorized acceptance reports, their decisions and appended audit mirrors were added to application data; no new application dataset or repeated promotion was performed.
- Secret-free evidence is retained in ignored `artifacts/local-acceptance-evidence.json`, with a small runtime outcome log. Removed obsolete `.pytest_tmp/reviewer_auth_runtime.py` and `artifacts/local_acceptance_controller.py` after completion; active local services continue running with the inspected application in memory. Useful source test fixtures and persisted evidence were preserved.

### Tests and static checks

Commands used `.\.venv\Scripts\python.exe`:

| Check | Command arguments after Python | Actual result |
|---|---|---|
| Selected regression suite | `-m pytest tests/unit/test_promotion_authorization.py tests/unit/test_persistence_api.py tests/unit/test_api_benchmark.py tests/unit/test_migration.py tests/unit/test_additional_gates.py tests/unit/test_review_identity.py tests/unit/test_investigation_review.py tests/unit/test_investigation_workspace.py tests/unit/test_dashboard.py tests/unit/test_vehicle.py tests/unit/test_investigation_api.py -q --basetemp=.pytest_tmp/local-security-acceptance -p no:cacheprovider --tb=short` | **163 passed in 54.68 seconds** |
| Real MongoDB integration | `-m pytest tests/integration/test_mongodb.py -q --basetemp=.pytest_tmp/local-security-mongodb -p no:cacheprovider --tb=short`, explicit `AUTOPLM_TEST_MONGODB_URI=mongodb://127.0.0.1:27017` | **11 passed in 20.32 seconds** |
| Strengthened real actor/audit assertions | `-m pytest tests/integration/test_mongodb.py -k real_api_promotion_and_reports -q --basetemp=.pytest_tmp/local-authenticated-audit -p no:cacheprovider --tb=short` | **1 passed, 10 deselected in 2.32 seconds** |
| Ruff | `-m ruff check app/api.py app/review_auth.py dashboard/investigation_workspace.py dashboard/streamlit_app.py tests/unit/test_promotion_authorization.py tests/unit/test_persistence_api.py tests/unit/test_api_benchmark.py tests/unit/test_review_identity.py tests/unit/test_investigation_review.py tests/unit/test_investigation_workspace.py tests/unit/test_dashboard.py tests/integration/test_mongodb.py` | **Passed**, including the strengthened test recheck |
| Scoped Mypy | `-m mypy app/api.py app/review_auth.py dashboard/investigation_workspace.py dashboard/streamlit_app.py` | **Success, four source files** |

- Added exact unauthenticated forged-user wire-request regression, asserting 401, unchanged job, no publication and no authorization audit event. Strengthened existing real MongoDB API promotion regression: forged body actor is ignored, and both `approved_by` and audit actor equal the authenticated test subject. Real integration fixture datasets exist only in random isolated `autoplm_test_*` databases and are cleaned by existing fixtures, separate from application data.
- No full unit suite, browser pixel/keyboard acceptance, live Groq/model request, deployment, commit or push. Live workflow was executed through Streamlit widgets/AppTest; no claim of manually observed browser behavior is made.

### Exact changed files and deployment prerequisites

- Modified in this task: `tests/unit/test_promotion_authorization.py`, `tests/integration/test_mongodb.py`, `README.md`, `PROJECT_PROGRESS.md`. No production code changed. Pre-existing uncommitted API/UI/identity work remains intact.
- Retained ignored evidence JSON/logs; removed only the two obsolete helper scripts created for diagnosis/acceptance. No historical audit deletion or identity rewrite occurred. No token/credential hash/complete registry was exposed.
- Use the isolated 8010/8510 origins; old 8000/8501 ports also belong to another local project and must not be treated as authoritative AutoPLM endpoints. Restart from a single supervised launch path with explicit environment and verify negative authorization after restart; do not rely solely on source/reload state.
- Deployment prerequisites: production identity and secret lifecycle, authorization for remaining legacy mutation routes, documented disposition/quarantine of historically unauthenticated baselines, TLS/session controls, single non-reloading process supervision/configuration validation, and MongoDB least privilege/backups/network/readiness policy. The static local credential registry, temporary token storage and local acceptance servers are not production deployment infrastructure.

## Focused promotion authorization hardening (2026-11-13)

**Status: Implemented and verified.** Preserved all pre-existing uncommitted identity/workspace/documentation changes. No new phase or deployment work was started.

- Before: `POST /jobs/{job_id}/promote` accepted unauthenticated requests and passed caller-supplied `Decision.actor` to the promotion service. After: it requires existing `authorized_reviewer`, and passes only `ReviewPrincipal.subject` as the audit/approval actor. Missing/invalid credentials are 401, reader-only credentials 403 and disabled registry 503.
- `Decision` is shared with repair approval, so it remains unchanged. Added promotion-specific `PromotionDecision`: strict `approve`, optional deprecated validated `actor` ignored for compatibility. New callers can omit actor; forged actor strings cannot change audit identity or `approved_by`.
- `app/service.py` was not modified. Existing explicit approval, verified status, staging digest, fresh verification, concurrency lock/revision checks, publication manifests, audit and rollback/idempotence behavior are preserved. ACCEPT of an investigation recommendation remains separate from explicit promotion.
- Added 13 focused cases for unauthenticated/invalid/reader denial, service non-invocation on denial, authenticated promotion with and without forged actor, authoritative audit/approved-by identity, idempotence, unverified states, tampered staging despite matching cached digest, explicit false approval, missing job and disabled registry. Existing API tests now provision real test bearer credentials so they still exercise body validation/publication gates rather than stopping at 401.

### Actual verification

Commands used `.\.venv\Scripts\python.exe`:

| Check | Command arguments after Python | Actual result |
|---|---|---|
| Focused and relevant unit/API regressions | `-m pytest tests/unit/test_promotion_authorization.py tests/unit/test_persistence_api.py tests/unit/test_api_benchmark.py tests/unit/test_migration.py tests/unit/test_additional_gates.py tests/unit/test_review_identity.py tests/unit/test_investigation_review.py -q --basetemp=.pytest_tmp/promotion-authorization -p no:cacheprovider --tb=short` | **107 passed in 14.58 seconds** |
| Relevant real MongoDB API case | `-m pytest tests/integration/test_mongodb.py -k real_api_promotion_and_reports -q --basetemp=.pytest_tmp/promotion-auth-mongodb -p no:cacheprovider --tb=short` with explicit `AUTOPLM_TEST_MONGODB_URI=mongodb://127.0.0.1:27017` | **1 passed, 10 deselected in 3.22 seconds** |
| Ruff | `-m ruff check app/api.py tests/unit/test_promotion_authorization.py tests/unit/test_persistence_api.py tests/unit/test_api_benchmark.py tests/integration/test_mongodb.py` | **Passed** |
| Scoped Mypy | `-m mypy app/api.py app/review_auth.py` | **Success, two source files** |

Real MongoDB verification used the existing isolated random test database fixture, not application data. No full unit suite, live Groq, browser, deployment or benchmark experiment was run; existing benchmark calculations ran only as their unit regression test.

### Exact files changed and remaining limitations

- Created: `tests/unit/test_promotion_authorization.py`.
- Modified: `app/api.py`, `tests/unit/test_persistence_api.py`, `tests/unit/test_api_benchmark.py`, `tests/integration/test_mongodb.py`, `README.md`, `PROJECT_PROGRESS.md`.
- Authentication implementation, role definitions, promotion service and unrelated backend/UI logic were unchanged. No credentials were exposed or hardcoded into application code. No dependencies, commit or push.
- API promotion now requires an authorized bearer credential. The existing legacy dashboard promotion button still sends only actor/approval; it will correctly receive 401 until separately integrated with authenticated identity. That UI change was not included in this endpoint-focused task.
- Authentication remains a local static registry with no SSO/MFA/expiry/per-job scope. Other legacy mapping/repair approval APIs and trusted in-process service/CLI callers remain outside this specific HTTP-boundary hardening. No production-ready or system-wide authorization claim is made.

## Phase 4E — Investigation Workspace Integration (2026-11-12)

**Status: Implemented and verified with mocked-HTTP Streamlit tests and relevant UI/API regressions. Live browser/deployment acceptance remains unverified.** Reused the already implemented `/review/me`; it was not modified in this task. Initial working tree contained the preceding identity-endpoint changes, which were preserved.

### Architecture discovered and implementation

- Confirmed active entry point `dashboard/streamlit_app.py`; `dashboard/app.py` no longer exists. Existing Streamlit light theme, sidebar navigation, HTTP backend and vehicle workspace were retained. No additional API gap was found after identity discovery became available.
- Added `dashboard/investigation_workspace.py` and one navigation item. New workspace has an Investigation console and Saved reports/human review tab. All durable operations use existing FastAPI routes, with existing Pydantic response models; no backend engine, repository, auth mechanism or persistence was recreated in Streamlit.
- Password-masked bearer input is session-scoped. Requests attach Authorization headers, do not follow redirects, and never render exception/header/provider body text. Identity and roles come only from `/review/me`; no arbitrary reviewer field or registry access exists. Identity is fetched each rerun and report IDs are scoped to backend/subject. UI role hints do not replace backend decision authorization.
- Approved baseline selection uses `/jobs` filtered to approved status and `/jobs/{id}/approved`. Available variants/components come from the actual publication. Natural-language request, selected context and existing offline/LLM mode are submitted to `/jobs/{id}/investigation-reports`; provider credentials/settings remain backend-only. No live model availability is assumed. Submission has a loading spinner and explicit success/error states.
- Persisted reports are retrieved by ID or queue selection. Queue uses existing status/limit/offset contract; pending is the default. Every display/decision cycle reads persisted report/history rather than locally assigning review outcomes.
- Explorer renders request/intent, statuses, identified components/variants, tools/history, evidence IDs/classifications/record data, dependency paths/affected entities, deterministic findings, baseline fingerprint/digests/source provenance, missing evidence/uncertainties, recommendations and validated reasoning citations. Findings, potential exposure and LLM synthesis have distinct labels and safety explanations.
- ACCEPT/REJECT requires nonblank comments and explicit checkbox confirmation before any decision POST. Decision bodies contain only `decision` and `comments`. Backend denial/conflict/error remains authoritative. Successful submission reruns and reads actual report/queue/history; terminal reports disable submission and audit-mirror incompleteness is shown.
- All review actions retain recommendation-only semantics. No control for automatic migration approval, engineering modification, proposal application, publication, release or deployment was added. Existing legacy migration review UI remains unchanged and separate.

### Actual verification

Commands used `.\.venv\Scripts\python.exe`:

| Check | Command arguments after Python | Actual result |
|---|---|---|
| Relevant UI/API regression | `-m pytest tests/unit/test_investigation_workspace.py tests/unit/test_dashboard.py tests/unit/test_vehicle.py tests/unit/test_review_identity.py tests/unit/test_investigation_review.py tests/unit/test_investigation_api.py -q --basetemp=.pytest_tmp/investigation-ui-regression -p no:cacheprovider --tb=short` | **86 passed in 44.94 seconds** |
| Added reasoning-rendering/transport-redaction checks | `-m pytest tests/unit/test_investigation_workspace.py -k 'validated_reasoning or transport_failure' -q --basetemp=.pytest_tmp/investigation-ui-safety -p no:cacheprovider --tb=short` | **2 passed, 11 deselected in 7.10 seconds** |
| Ruff | `-m ruff check dashboard/investigation_workspace.py dashboard/streamlit_app.py tests/unit/test_investigation_workspace.py tests/unit/test_dashboard.py` | **Passed**, including after supplemental tests |
| Scoped Mypy | `-m mypy dashboard/investigation_workspace.py dashboard/streamlit_app.py` | **Success, two source modules** |

- Added 13 UI cases overall: approved-baseline filtering, authenticated subject/role, password masking, submission/persistent retrieval, actual evidence/missing conditions, manual report lookup, ACCEPT/REJECT/history/status refresh, confirmation/comments gate, reader-disabled decisions and backend 403, invalid credential handling, sanitized backend failure, empty queue/baselines, actual validated citation rendering, and transport exception credential redaction. ACCEPT/REJECT are parameterized cases. No combined 13-case timing is claimed beyond the recorded runs.
- HTTP transport is mocked to FastAPI TestClient backed by existing mongomock/service fixtures. Report setup and requests use actual existing offline models/engine; the validated-reasoning test uses a mocked summarizer with real citation validation. Tests do not contact external services or live providers. Existing ten-workspace navigation and nine vehicle tests passed, along with 56 identity/review/investigation API cases.
- Initial focused run had 10 passes and one test assertion mismatch: password type is a protobuf enum, not the string `password`. Corrected the assertion to use `PASSWORD`; the actual password input was already configured correctly. Corrected initial line lengths and request-mode typing; no feature/test was removed or disabled.
- No full unit suite, real MongoDB, live LLM/Groq evaluation, live browser, OTA Verifier test or benchmark was run. Prior real MongoDB results remain historical. Backend behavior was not modified.

### Exact files changed in Phase 4E

- Created: `dashboard/investigation_workspace.py`, `tests/unit/test_investigation_workspace.py`.
- Modified: `dashboard/streamlit_app.py`, `tests/unit/test_dashboard.py`, `README.md`, `PROJECT_PROGRESS.md`.
- The prior uncommitted identity prerequisite (`app/api.py`, `tests/unit/test_review_identity.py`, earlier documentation additions) remains present and unchanged by this task. `ARCHITECTURE.md` was not modified: this integrates the existing Streamlit→FastAPI→investigation/review design without changing its runtime architecture.
- No dependency, backend API, persistence/auth, engineering logic, fingerprint, migration safeguard, OTA Verifier or CI changes. No commit or push performed.

### Manual acceptance and remaining limitations

1. Start existing MongoDB/FastAPI and `python -m streamlit run dashboard/streamlit_app.py --server.address 127.0.0.1`. Configure the existing server review registry securely; use an already provisioned reviewer credential.
2. Prepare an approved synthetic job through the existing workflow. Open Investigation Workspace, authenticate, confirm backend subject/roles, select the approved job/variant and submit an offline request.
3. Open Saved reports and human review, inspect the persisted report/evidence/fingerprints/missing conditions, retrieve it again by ID and confirm it appears in the pending queue.
4. Add explicit ACCEPT/REJECT, comments and confirmation; verify persisted terminal status/history and unchanged engineering data. With an existing reader credential, verify decisions are disabled; invalid/revoked credentials or backend denial must remain failures.

These manual steps were documented, not executed. Real browser layout, keyboard/focus, remote TLS/session behavior and a live frontend/backend/MongoDB deployment remain unverified. Credential authentication retains the existing local static-registry limitations; older trusted-user APIs are not retroactively secured. UI credentials must use HTTPS for remote backends; no secret is stored in reports by the client.

The existing `/jobs` API returns at most 200 recent jobs, so the picker is limited to approved jobs in that response; report queue pages show up to 50 full reports with offset paging. Large-baseline UI performance is unverified. The HTTP timeout is 180 seconds; after a timeout, check saved reports before retrying because the backend may still finish. Persisted proposal IDs remain unsupported by the existing backend and no replacement store was invented. Next recommended task, only with approval, is manual browser acceptance; no further work started.

## Phase 4E prerequisite — Authenticated identity endpoint (2026-11-12)

**Status: Implemented and verified.** The existing authentication safely supports identity retrieval; no replacement authentication mechanism was needed. Starting working tree was clean. This resolves the identity-discovery API gap found during Phase 4E inspection; the Streamlit integration itself has not started in this task.

- Added read-only `GET /review/me`, with existing `ReviewPrincipal` response schema: `subject` and JSON-array `roles`. Returns only the principal resolved by existing `authenticated_review_user()` bearer authentication. Sets `Cache-Control: no-store`; does not initialize MongoDB, write audit/history or invoke an investigation.
- Retained existing 401 missing/invalid credential and 503 disabled/malformed credential configuration behavior. Query/body identity values cannot override the server-assigned principal; no override parameters or additional roles were introduced. The current model supports `engineering_reviewer` and `investigation_reader`, not an administrator role. Unsupported administrator configuration continues to fail closed under existing validation.
- Added 11 focused API cases covering both supported authenticated roles, missing/invalid/wrong-scheme credentials, absent/disabled/malformed configuration, exact response fields/no token/hash/other-registry-entry disclosure, attempted identity/role overrides, no database access and unsupported administrator configuration.
- Actual verification using `.\.venv\Scripts\python.exe`: `-m pytest tests/unit/test_review_identity.py tests/unit/test_investigation_review.py tests/unit/test_investigation_api.py -q --basetemp=.pytest_tmp/review-identity -p no:cacheprovider --tb=short` — **56 passed in 22.81 seconds** (11 identity cases plus 45 existing review/investigation API regressions). `-m ruff check app/api.py tests/unit/test_review_identity.py` — **passed**. `-m mypy app/api.py app/review_auth.py` — **success, two source files**.
- Exact files: created `tests/unit/test_review_identity.py`; modified `app/api.py`, `README.md`, `PROJECT_PROGRESS.md`. `app/review_auth.py` was inspected/type-checked but not modified. Review decision contracts/roles, ACCEPT/REJECT semantics, audit history, investigation execution, baseline integrity, persistence and dependencies were unchanged.
- No live LLM/external API calls, real MongoDB tests, full unit suite, commit or push. Existing authentication is still a local static-credential boundary, not production SSO/MFA or per-job authorization. Phase 4E UI integration remains a separately scoped next task; no dashboard work performed.

## Focused investigation identification fix (2026-11-12)

- Fixed report identification omitting successful component/variant lookups when extraction supplied no identifiers. Successful lookup evidence now contributes only when its complete record matches the authoritative `tools.by_id` entry, its ID matches the tool argument and variant lookups return actual variants. Final classification uses the canonical record kind. Failed/unknown/mismatched records do not add identities; existing extracted identifiers and valid impact identities remain supported.
- Changed in this task: `app/investigation.py`, `tests/unit/test_investigation.py`, `PROJECT_PROGRESS.md`. Preserved all preceding uncommitted reliability changes. README was not changed in this task because this corrects an existing reporting capability rather than introducing a public feature.
- Added ten regression cases covering successful component/variant lookup with empty extraction (including validated synthesis), generic component lookup of an actual variant, missing and failed existing-record lookups, mismatched kind/ID/content/tool binding, and retained extracted identifiers.
- Final verification using `.\.venv\Scripts\python.exe`: `-m pytest tests/unit/test_investigation.py tests/unit/test_investigation_llm.py tests/unit/test_investigation_reliability.py -q --basetemp=.pytest_tmp/identified-lookup-final -p no:cacheprovider --tb=short` — **97 passed in 9.36 seconds**. `-m ruff check app/investigation.py tests/unit/test_investigation.py` — **passed**. `-m mypy app/investigation.py` — **success, one source file**.
- No LLM prompt/provider, evaluation, API, fingerprint, migration or persistence contract changes. No live Groq test, external API call, commit or push. Live verification remains outside this focused fix; no new live result is claimed.

## Phase 4D reliability hardening (2026-11-12)

**Status: Focused hardening implemented and locally verified. No new phase or architecture was introduced. Live Groq functionality remains unverified.** Starting working tree was clean. Inspected the five requested investigation/evaluation/test files and the installed ChatOpenAI structured-output signature. Only boolean environment/file-presence metadata was checked: model, key, endpoint and live opt-in were absent; no local `.env` file was present. No secrets were printed and no live provider test/evaluation was executed.

### Root causes found

- Deduplication compared complete serialized argument dictionaries, including bounds irrelevant to lookup results. Equivalent impact/provenance operations and already-retrieved twin fingerprints were not recognized as redundant. Missing identifiers and transient tool failures were reduced to exception classes, so later distinct calls against the same unavailable entity were not suppressed.
- Planner context had the argument schema but no explicit tool-purpose contract or attempted-outcome/unresolved-target summary. Completion checks counted attempted tool names, including failed calls, and did not explicitly surface requested targets lacking successful evidence.
- Empty decisions already routed directly to finalization. They were **not** demonstrated to cause extra planning loops; preserved that route and added explicit tests. Incomplete planner output could default an absent `calls` field to an empty list; the LLM wrapper now rejects that malformed case while accepting explicit `calls=[]`.
- Installed ChatOpenAI defaults to `json_schema`; the existing adapter did not explicitly choose a method for compatible endpoints. Provider/model structured-output support can differ. No Groq model/configuration or live error trace was available to establish a model-specific cause. Local diagnostics only exposed exception class, and synthesis asked the model to invent pointer strings without a supplied list of valid candidates. Strict rejection of nonexistent citations was correct behavior and remains intact.
- Evaluation used empty-set subset checks for missing targets, defaulted most understanding/incompatibility checks to true, counted failed calls as obtained tools, marked absent reasoning and absent aggregate traceability true, and conflated permissible extra retrieval with unnecessary calls. Tool names alone could pass despite the wrong entity, and citation IDs were checked without verifying their associated content.

### Implementation

- Internal graph state now retains attempted calls/status/outcome/evidence IDs and definitive unavailable entities. Semantic signatures ignore lookup-irrelevant bounds, alias equivalent impact/provenance calls and valid variant/component lookups, and suppress fingerprint reads after successful twin construction. Existing evidence objects/IDs remain the authoritative executed-call record.
- Added a specific missing-identifier outcome with stable code/entity/nonretryable metadata. It blocks subsequent queued and planned tools for that entity, including a missing comparison operand. Other tool failures remain distinct; transient timeout/connection failures do not poison entity availability. Identical calls are still suppressed rather than automatically retried.
- Planning receives purpose descriptions, extracted needs, attempt outcomes, unresolved/unavailable targets and budget. Offline planning uses the same semantic suppression rules so a filtered duplicate cannot hide later useful work. Empty or fully suppressed plans terminate gracefully. Unsuccessfully investigated targets remain missing evidence; requested-tool completion uses successful results and equivalent evidence capabilities.
- Added configurable structured-output protocol, defaulting to `function_calling` for compatible/Groq endpoints and `json_schema` otherwise. Supports explicit `json_mode` without changing provider transport, dependencies or public request models. Structured envelopes are parsed without reporting raw provider messages; malformed/incomplete output remains partial.
- Sanitized diagnostics retain stage, exception class, safe HTTP status, allowlisted provider codes and Pydantic error types, without inputs, validation messages, generated text, credentials or authorization headers. Synthesis receives actual candidate citations validated against existing results; returned citations still pass the unchanged strict validator. No grounding or incompatibility requirement was weakened.
- Corrected all six evaluation cases. Required and optional tools differ; successful results must address the expected entity; impact checks require actual expected exposure. Missing-target success requires explicit safe abstention and missing evidence. Redundant calls and irrelevant calls have separate counters; missing/inapplicable metrics are null. Missing reasoning is not grounded. Aggregated paths/findings must match cited tool-result content. The evaluation remains a narrow synthetic contract suite, not model accuracy measurement.

### Actual verification

All commands used `.\.venv\Scripts\python.exe`:

| Check | Command arguments after Python | Actual result |
|---|---|---|
| Existing investigation/synthesis checkpoint | `-m pytest tests/unit/test_investigation.py tests/unit/test_investigation_llm.py -q --basetemp=.pytest_tmp/reliability -p no:cacheprovider --tb=short` | **68 passed in 9.60 seconds** |
| Initial added reliability cases | `-m pytest tests/unit/test_investigation_reliability.py -q --basetemp=.pytest_tmp/reliability-new -p no:cacheprovider --tb=short` | **15 passed in 8.89 seconds**; four additional target/metric/malformed-response cases were subsequently included below |
| Final regression checkpoint | `-m pytest tests/unit/test_investigation_reliability.py tests/unit/test_investigation.py tests/unit/test_investigation_llm.py tests/unit/test_investigation_api.py tests/unit/test_investigation_review.py tests/unit/test_migration.py tests/unit/test_engineering.py tests/unit/test_mechanical.py tests/unit/test_dependencies.py tests/unit/test_what_if.py tests/unit/test_persistence_api.py tests/unit/test_traceability.py -q --basetemp=.pytest_tmp/reliability-final -p no:cacheprovider --tb=short` | **303 passed in 21.08 seconds**, including **19 new reliability cases** |
| Final variant-alias type-validation adjustment | `-m pytest tests/unit/test_investigation_reliability.py -k semantic_aliases -q --basetemp=.pytest_tmp/reliability-alias -p no:cacheprovider --tb=short` | **1 passed, 18 deselected in 3.27 seconds**; no new combined regression count claimed |
| Ruff | `-m ruff check app/investigation.py app/investigation_evaluation.py tests/unit/test_investigation_reliability.py tests/unit/test_investigation.py tests/unit/test_investigation_llm.py` | **Passed** |
| Scoped Mypy | `-m mypy app/investigation.py app/investigation_evaluation.py` | **Success, two source modules** |

- An intermediate broader checkpoint passed 299 tests in 19.54 seconds; further target-aware metric/unresolved-target cases justified the final 303-test run. Initial line-length/type-annotation issues were corrected. No test was deleted/disabled and strict citation rejection regressions passed.
- Corrected offline evaluation was executed after the final metric changes: **6/6 passed, 0 redundant calls, 0 irrelevant calls, 0 reasoning cases evaluated**. Grounding is null for all offline cases. Missing-target `required_tools_obtained` is null and `abstention_correct=true`. This establishes neither live LLM accuracy nor a live grounding/hallucination rate.
- Tests exercise definitive misses across different tools, lookup-bound variation, impact/provenance equivalence, twin/fingerprint deduplication, explicit empty plans, successful stopping, transient versus missing outcomes, verification/fingerprint/impact selection, raw structured parse failures, sanitized provider diagnostics, real citation candidates, invalid/misclassified citations, incorrect targets, forged trace content, wrong-type alias validation and metric non-vacuity.
- Selected regressions cover authoritative baseline loading, immutable report serialization/digests, authenticated atomic review, source reconciliation/promotion, mechanical rules, what-if isolation and exact legacy twin fingerprints. No full unit suite, MongoDB integration, browser, OTA Verifier check, or live Groq test/evaluation was run for this focused task. Existing live test was inspected and left unchanged; no live run was attempted because configuration was absent.

### Exact files changed and Git status

- Created: `tests/unit/test_investigation_reliability.py`.
- Modified: `app/investigation.py`, `app/investigation_evaluation.py`, `tests/unit/test_investigation.py`, `tests/unit/test_investigation_llm.py`, `README.md`, `PROJECT_PROGRESS.md`.
- Existing SDK mocks were adapted to explicit structured-output keyword arguments and valid typed replies; no engineering assertion was weakened. OTA Verifier, engineering/migration rules, twin fingerprint/serialization contracts, API contracts, baseline immutability, review authorization/decisions, persistence contracts, dependencies and CI were unchanged. No commit or push performed.

### Remaining limitations

- Groq model-specific protocol support, response quality and live reliability remain unverified. Configuration is absent, so the authorized once-after-tests live smoke condition was not met. No live evaluation success is claimed.
- Semantic suppression covers known equivalent operations, not every mathematically derivable result; distinct traversal bounds may change evidence and remain distinct. There is no automatic transient-tool retry or new global wall-clock/cancellation mechanism. Existing request timeouts and execution budgets remain.
- Citation candidates are bounded suggestions, not a relaxed allowlist or proof of complete engineering reasoning. Unavailable/unsupported synthesis still produces partial reports. Offline parser remains conservative; live model tool-selection quality is not measured by the six-case contract suite.
- No major architectural change was required and no next phase/task was started. Future live verification must remain opt-in and preserve current evidence and human-review boundaries.


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
