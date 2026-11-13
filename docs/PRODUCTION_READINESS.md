# Production readiness and security boundary

Phase 13B checkpoint, 2026-11-13 (retains earlier findings and incident evidence). **Not cleared for production deployment.**
This is a preparation guide, not evidence of a deployed or production-authenticated system.

## Endpoint security audit

All routes in `app/api.py` were reviewed. No separate engineering publication endpoint exists:
publication occurs through promotion. CLI/operator access is a separate trusted-host boundary.

| Routes | Current boundary | Audit identity / disposition |
|---|---|---|
| POST `/jobs/{job_id}/promote` | Authenticated `engineering_reviewer` | Principal subject; legacy body actor ignored. Existing fresh validation, digest, lock, publication and rollback gates preserved. |
| POST `/jobs/{job_id}/repairs` | Authenticated `engineering_reviewer` (Phase 12 fix) | Principal subject stored as proposed_by; provider mode is not an identity. |
| POST `/repairs/{proposal_id}/decision` | Authenticated `engineering_reviewer` (Phase 12 fix) | Principal subject replaces caller actor; staging validation remains independent. |
| POST `/jobs/{job_id}/mappings/decision` | Authenticated `engineering_reviewer` (Phase 12 fix) | Principal subject replaces caller actor; structured mapping validation unchanged. |
| GET `/review/me` | Authenticated reader or reviewer | Subject/roles only; no credential registry or token returned. |
| POST `/jobs/{job_id}/investigation-reports` | Authenticated `engineering_reviewer` | Immutable baseline association; created_by is authenticated subject. |
| GET `/investigation-reports`, GET `/investigation-reports/{id}`, GET `/investigation-reports/{id}/decisions` | Authenticated `engineering_reviewer` | Typed report/queue/history; report integrity checks preserved. |
| POST `/investigation-reports/{id}/decisions` | Authenticated `engineering_reviewer` | Atomic terminal decision and persistent history; principal subject, mandatory comments, baseline fingerprint and audit mirror. ACCEPT is recommendation acceptance only. |
| GET `/jobs`, `/jobs/{id}`, `/jobs/{id}/approved`, `/jobs/{id}/report` | Authenticated `engineering_reviewer` (Phase 13A) | Private database-backed reads; no anonymous access. Resource/tenant isolation remains future work. |
| POST `/datasets/generate`, `/jobs`, `/jobs/{id}/simulations`, `/jobs/{id}/investigations` | Authenticated `engineering_reviewer` (Phase 13A) | Anonymous and reader-only execution blocked. Production quotas and principal attribution on every execution path remain work. |
| GET `/public/samples`, `/public/samples/{sample_id}` | Public read-only packaged snapshots | Explicit typed projections; no MongoDB fallback, job lookup, execution or history export. Unknown sample IDs return 404. |
| GET `/health`, `/ready` | Public liveness / database readiness | Minimal responses; readiness failure uses a generic database error. Restrict readiness to operations network at the proxy. |

The local credential registry retains SHA-256 and constant-time comparison. Reader-only credentials
cannot access private engineering reads, execution or decisions; identity discovery remains permitted. Optional legacy actor fields are deprecated and ignored on decision APIs;
service/CLI methods still accept operator actors and must not be exposed as an authentication shortcut.

`AUTOPLM_ENVIRONMENT=local` retains the separate development credential registry. In `production` or
`staging`, startup now verifies OIDC discovery/issuer/JWKS, configured API audience/client, authenticated
verified-TLS MongoDB and initialized shared grant/quota/lock metadata. Unknown environments or incomplete
configuration block startup with a sanitized error. Non-local requests use only signed access tokens and
fresh database grants; there is no static-token fallback. This retains the interlock as concrete verification,
not a boolean opt-out. Configuration changes require a controlled restart. Actual provider/client/callback,
database privileges and hosted workflow acceptance are still prerequisites, not established by mocked tests.

API responses now send `Cache-Control: no-store` and `X-Content-Type-Options: nosniff`.
Global KeyError/ValueError responses preserve 404/409 while omitting raw exception messages.
Validation details remain available in job reports. Database and investigation/review failures retain
their existing sanitized handlers. The legacy dashboard request helper no longer displays HTTP exception text.
Phase 13B adds fixed-category sanitized security logs, durable reviewer quotas and execution locks. Full
centralized log retention/alerting, edge/anonymous flood controls and a complete request-validation/provider
message-redaction audit remain work; never log bearer headers, secret environments or raw provider payloads.

## Historical incident and disposition

Preserve job `1159cf031e93874f8a12c0a1`, its `approved_by=forged-user`, its 26 materialized records,
and original promotion authorization audit event `6bf86c49-04f7-4691-95a8-7d98841aa03e`
(`2026-11-12T20:17:38.716000+00:00`). Prior runtime investigation found an unprotected stale API
behind conflicting listeners despite a protected source endpoint. The precise reload failure was not established.
See PROJECT_PROGRESS.md for the original investigation and live acceptance evidence.

**Disposition:** retain as synthetic incident/acceptance evidence only; exclude from production baseline
selection/import. Computational source/publication integrity does not legitimize its approval. No records,
identities or audit events were changed during Phase 12. This exclusion is a documented operational rule,
not an implemented database quarantine flag or retroactive approval. Before any production import, an
accountable engineering owner must establish an independently authorized baseline and retain the incident
reference. Do not re-promote this historical job or silently repair its approved_by field.

## Public demonstration and reviewer separation - Phase 13A

Implemented: a versioned catalog plus two synthetic snapshots, public read-only API routes and a Streamlit
browser that reads the packaged artifacts directly. No HTTP request, MongoDB access or reviewer credential
is required to browse. Strict nested projection models exclude raw records/audit/provider payloads. Catalog
IDs alone resolve package resources; unknown/private job IDs are never sent to a database lookup. Snapshot
SHA-256 is checked against catalog metadata before display. Publication remains a controlled source/build
operation, not a visitor-accessible export or generation endpoint.

Rebuild with `python -m scripts.build_public_samples`. Inputs come exclusively from `app.data.generate`
(seed 42, one fleet, schema A), never application databases. Scenarios are equivalent data and explicit brake
revision Z drift. Summaries measure existing engineering rules and selected-variant twin differences, not a
persisted migration job. Offline reports retain missing-evidence/uncertainty disclosures; only allowlisted
projections are published. Public artifact hashes, source/target input hashes and original report hashes are
distinct. Evidence source_pointer refers to the hashed original report, not a public arbitrary-file endpoint.
Hashes detect drift but do not replace review/signing of a compromised release.

The historical forged job is absent from the catalog and generated inputs. No historical application/audit
records were touched. Private reviewer pages and all engineering API operations now require the reviewer role;
UI visibility is supplementary to server-side enforcement. Local bearer entry is development-only; Phase 13B adds production OIDC. The startup interlock now verifies
the concrete production security configuration before allowing non-local startup, including public routes.
Do not bypass it by selecting local mode for a free-hosted API.

Phase 13A measured verification: 64 focused public/security tests passed; 506 selected regressions passed
(including those 64); 11 isolated real MongoDB integration tests passed. Ruff on changed Python files and
Mypy on six scoped modules passed. Public UI tests run with HTTP requests forbidden; API tests reject
unauthorized access before private service/database resolution. Snapshot regeneration and hash corruption
are tested. Production OIDC, actual cloud/Atlas deployment, installed-wheel and live-browser acceptance
are not claimed. See PROJECT_PROGRESS.md for exact commands, files and results.

## Target free-hosting architecture and roadmap

Public visitors -> Streamlit Community Cloud -> packaged public samples (no backend/database needed).
Authenticated reviewers -> the same Streamlit app -> HTTPS FastAPI on Render Free -> authenticated Atlas M0.
Anonymous API consumers may read only `/public/samples` and `/public/samples/{sample_id}` plus minimal health
responses. Publicly reachable Render hosting makes authorization on every private route mandatory; hiding
Streamlit controls alone is insufficient. The previous single-host reverse-proxy layout is an alternative,
not a requirement for this three-service target.

Phase 13B application authentication is implemented and locally tested. Remaining deployment sequence:

1. Configure a real Auth0 tenant, custom API and confidential Streamlit client using the settings below.
   Verify a real authorization-code callback yields an API-audience access token; never substitute an ID token.
2. Provision authenticated TLS Atlas access with a separate trusted operator identity. Initialize shared controls,
   assign only approved reviewer subjects and verify runtime privileges. Never import the historical forged
   baseline as legitimately authorized data. Test grant/revoke and backups/restore on isolated data first.
3. Install `requirements.txt` with a supported patched Python 3.13 release on both platforms. Local checks used
   Python 3.13.3, Streamlit 1.67.0, Authlib 1.9.5, PyJWT 2.15.1 and cryptography 50.0.2; clean Linux/platform
   installation, dependency vulnerability review and capacity validation remain unverified.
4. Prepare Render's `python -m uvicorn app.api:app --host 0.0.0.0 --port $PORT --workers 1 --no-access-log`
   launch and `/health` health-check path. Managed TLS and forwarded-header trust must be verified; do not
   blindly trust arbitrary proxy headers. Keep secrets in platform settings, not command arguments or Git.
5. Set Community Cloud entry point `dashboard/streamlit_app.py` and protected secrets/callback. Validate public
   browsing without login/backend, reviewer login, private navigation, token expiry/account switching, 401/403,
   forged actor resistance, quotas/locks, persistent review history and source/twin integrity end to end.
6. Verify Render cold starts, Atlas network allowlists, runtime database permissions, TLS, load bounds, lock
   recovery, logging/alerts and backup restoration. Resource/tenant isolation and broader execution actor
   attribution remain future work. No production capacity, certification or availability guarantee is claimed.
7. Record measured hosted results, then request deployment approval. Do not use local mode, disable validation
   or introduce an unverified shared service token to make free hosting work.

Phase 13B measured verification: **546 selected unit/API/dashboard/domain regressions passed**, including
**40 new JWT/grant/security/login cases**; **12 real MongoDB integration tests passed** with shared grants,
quotas and locks. Ruff on all 23 currently changed Python files, scoped Mypy on ten modules, pip check and
example TOML parsing passed. Both Phase 13A canonical public hashes match the recorded values. Warnings
come from mongomock TTL deprecations. No real Auth0 handshake, Atlas M0 or hosted browser/deployment test
was performed. Exact commands, file inventory and limitations are recorded in PROJECT_PROGRESS.md.

## Phase 13B OIDC configuration and provisioning

### Backend environment (Render secrets/settings)

| Variable | Required value |
|---|---|
| `AUTOPLM_ENVIRONMENT` | `production` (or `staging`), never `local` on a hosted backend |
| `AUTOPLM_OIDC_ISSUER` | Exact HTTPS tenant issuer with trailing slash, e.g. `https://YOUR-TENANT.auth0.com/` |
| `AUTOPLM_OIDC_AUDIENCE` | Dedicated registered custom API identifier, e.g. `https://autoplm-api.example` |
| `AUTOPLM_OIDC_CLIENT_ID` | The permitted confidential Streamlit application client ID |
| `MONGODB_URI` | Protected authenticated Atlas SRV URI, verified TLS, no insecure TLS flags or w=0 |
| `MONGODB_DATABASE` | Explicit application database name |
| `AUTOPLM_ENABLE_LLM` | `false` initially; `true` only with separately authorized provider configuration/budgets |

FastAPI does not need the Auth0 client secret, cookie secret or Management API credentials. Do not configure
`AUTOPLM_REVIEW_CREDENTIALS` for production. JWKS/discovery URLs are derived only from the trusted issuer;
URLs supplied in tokens are rejected. RS256 is the fixed algorithm, not selected by caller claims. The API
requires iss/aud/sub/iat/exp/azp/scope, the allowed client and `autoplm:access`; lifetime is at most 3600 seconds
with five seconds clock leeway. Set Auth0's custom API access-token lifetime accordingly. ID tokens have the
application audience and are not API credentials. Profile roles, email and token role claims are ignored.

### Auth0 Free and Streamlit Community Cloud

Register a Regular Web Application and a custom API with RS256 and permission/scope `autoplm:access`.
Use hosted Universal Login and Authorization Code + PKCE. Set the application Token Endpoint Authentication
Method to Basic, matching the example client_secret_basic setting. Register the exact Streamlit callback
`https://YOUR-APP.streamlit.app/oauth2callback`, application origin and permitted logout return URL.
No paid provider Role Management, token exchange, M2M grant or enterprise connection is needed for this flow.
Free plan feature/rate/log-retention limits remain provider-controlled; verify the chosen tenant before release.
New authenticated accounts receive identity-only `investigation_reader`, with no private engineering access.

Copy `.streamlit/secrets.example.toml` into Community Cloud's protected Secrets settings, replacing every
placeholder. Its root environment values must match the backend issuer/audience/client ID and use the HTTPS
Render URL. Under `[auth]`, supply a strongly random cookie secret (at least 32 characters), exact redirect
and `expose_tokens = ["access"]`. Under `[auth.auth0]`, supply client ID, confidential client secret and exact
discovery URL. The **named provider** is intentional: `[auth.auth0.authorize_params] audience=...` is passed
to Authlib's authorization request. Put scope/PKCE/prompt in `[auth.auth0.client_kwargs]` as shown in the example.
Do not assume a top-level/default provider's arbitrary client_kwargs audience is forwarded correctly.

Installed Streamlit 1.67.0 was inspected before coding: `st.login("auth0")`, `st.user.tokens["access"]`,
state/nonce handling and PKCE are supported. A test using the installed native OAuth client verifies the
actual authorization URL has the custom audience, requested scope, code response, state, nonce and S256
challenge. This is not proof of a completed hosted handshake. Authlib/PyJWT/cryptography were added because
no login/JWT/crypto implementation was previously installed; custom cryptographic code was not introduced.

Tokens are sent only in HTTPS Authorization headers to the operator-configured backend; redirects are not
followed by request helpers. They are not rendered, logged, placed in URLs/downloads or shared app caches.
Streamlit manages its OIDC cookies; use HTTPS and keep XSRF/origin protections enabled. Clearing/replacing
identity, logout or failed/expired backend authentication removes private session state. Expired access tokens
require reauthentication; the longer Streamlit identity-cookie lifetime does not extend API access. Other
open browser sessions and copies of a bearer token are not globally revoked by local logout. Server-side
reviewer revocation affects subsequent requests, not already-running authorized operations.

### Trusted reviewer provisioning and revocation

Supply `AUTOPLM_PROVISIONING_MONGODB_URI` only to an approved operator environment, with a separate database
identity allowed to manage grants and initialize controls. Do not supply it to the API runtime or Streamlit.
The operator also sets the three OIDC settings and explicit MONGODB_DATABASE. The provisioning URI must use
authenticated verified TLS. The API runtime should read grants (and list their indexes), but must not be
allowed to modify them; engineering/quota/lock writes and audit inserts need separately scoped privileges.
Repository startup still creates engineering indexes, which must be accounted for in the MongoDB role setup.
The security store uses primary reads and majority writes; connection pools are bounded to ten per client.

Commands contain no database URI/token/secret. Operator identity is a trusted-host audit annotation, not an
API authentication mechanism. Obtain the exact verified subject from `/review/me`; email alone is not a grant.

```sh
python -m scripts.manage_reviewers initialize --operator APPROVED_OPERATOR --reason "Initialize security policy"
python -m scripts.manage_reviewers grant --subject 'auth0|VERIFIED_SUBJECT' --operator APPROVED_OPERATOR --reason "Approved engineering reviewer"
python -m scripts.manage_reviewers revoke --subject 'auth0|VERIFIED_SUBJECT' --operator APPROVED_OPERATOR --reason "Reviewer access revoked"
```

Grants are keyed by the verified issuer/subject pair and read for each authenticated request. Enabled state
and appended provisioning history update atomically. Events also use the existing append-only audit helper;
if mirroring fails, the grant/history can already be committed, so inspect the protected database before retrying.
No API lets reviewers grant themselves roles or edit/delete provisioning history. Database administrators remain
outside this boundary. Existing review decision/audit records and the historical incident are preserved.

### Shared budgets, locks and operational recovery

The initialized `security_policy` v1 must match code policy: requests 60/minute, executions 6/minute,
decisions 10/minute, LLM 1/minute and 10/day per verified identity, and two global execution slots. These are
fixed UTC-window counters using atomic MongoDB updates and TTL cleanup, shared across processes/restarts.
Unexpired counters survive process loss; changing tokens does not reset an issuer/subject's budget.
Initialization does not silently overwrite an incompatible shared policy. Policy migrations require an operator.

Production request bodies are capped at 2,000,000 bytes and ten seconds to receive. Existing execution bounds
are additionally capped at 12 investigation steps, 100 simulation ticks, ten generated fleets and 500 uploaded
records. LLM calls remain disabled unless explicitly enabled and still consume daily/minute budgets.
Existing bounded provider calls remain in place; there is no general mechanism to forcibly interrupt arbitrary
synchronous Python engineering work. Edge slow-client/flood protection, timeout/load testing and operational
alerts remain deployment work. Public packaged browsing does not consume engineering quotas.

Global locks and per-decision-resource locks are durable and deliberately **do not auto-expire**. This prevents
an old worker from continuing after an expiry while another worker acquires the same capacity. Crashes can
block availability. Stop/verify every affected worker first, inspect the held ID/owner in the approved database
console, then use the owner-conditional recovery command:

```sh
python -m scripts.manage_reviewers recover-lock --lock-id HELD_ID --owner EXACT_OWNER_UUID --confirm-workers-stopped --operator APPROVED_OPERATOR --reason "Verified stopped worker recovery"
```

Recovery appends a recovery record and mirrors an audit event; it never removes historical decisions. Do not
recover locks based solely on age. Existing terminal review decisions still use atomic compare-and-set and
retain mandatory comments/history; production resource locks add concurrent decision serialization. Promotion
and repair validation/digest/rollback checks remain unchanged. Repeated already-terminal review decisions fail
rather than overwrite history. Not every operation has request-level idempotency; on network loss inspect saved
results before retrying. 429 responses include Retry-After; contention can persist until work or recovery finishes.

Application security logs contain fixed reason categories only, not tokens, headers, claims or provider/MongoDB
exception text. Use protected centralized retention/alerting before release. Do not enable debug/header/body logs
or expose provisioning diagnostics publicly. No durable authentication-denial audit stream is claimed.

Official identity references:
[Streamlit login/token configuration](https://docs.streamlit.io/develop/api-reference/user/st.login),
[Auth0 custom APIs](https://auth0.com/docs/get-started/apis),
[Auth0 access-token validation](https://auth0.com/docs/secure/tokens/access-tokens/validate-access-tokens),
[Auth0 Free plan](https://auth0.com/pricing),
[PyJWT validation API](https://pyjwt.readthedocs.io/en/stable/api.html).

The checked-in `docker-compose.yml` is **local development only**: loopback MongoDB, no authentication.
Do not reuse its configuration or existing data volume for production. No live database configuration
was changed or inspected for secrets in this task.

### Required configuration and identity work

- Phase 13B implements a verified OIDC/OAuth2 resource-server boundary; for an organization provider (Auth0 or other
  approved provider), retain signature, issuer, audience, expiry, permitted-algorithm and key-rotation checks,
  and map administrator-managed claims to existing roles. Do not trust a free-form body or proxy identity header.
  Streamlit needs an approved login/session/token lifecycle; local bearer text entry is not production SSO.
  Auth0-compatible application support is implemented; real tenant/SSO acceptance remains unverified. Preserve review and engineering approval semantics.
- Supply secrets through a platform secret manager or protected service environment file outside the checkout,
  with owner-only permissions. Never bake API keys, local registry or MongoDB credentials into images/commands,
  URLs in logs, Git, reports or dashboards. `.env.example` contains placeholders only; the app does not
  automatically load it. Restrict outbound model-provider traffic; keep live providers disabled for acceptance.
- Use `MONGODB_URI` supplied securely with authentication, TLS verification and a database-scoped application
  identity, plus `MONGODB_DATABASE`. Private firewall rules must allow only the API and approved operators.
  Do not grant root/dbAdmin to the runtime. Repository initialization creates indexes: provision those through
  a controlled migration identity, or explicitly review the narrow createIndex privileges required at startup.
  Test permissions for CAS writes, publication rollback and insert-only audit access before release.
- Database administrators can currently edit history. Application conventions are not tamper-proof storage;
  independent immutable audit export, retention, backups and tested restore procedures remain necessary.
- CORS middleware is currently absent: no cross-origin browser allowance is configured. Server-side Streamlit
  requests do not require CORS. If a browser API is later introduced, allow only exact trusted HTTPS origins;
  never combine credentialed access with a wildcard origin. Keep Streamlit XSRF/origin protections enabled.
- Terminate trusted TLS at the proxy; configure certificate renewal and secure sessions. Forward WebSocket
  upgrades for Streamlit. Do not expose 8010, 8510 or 27017 externally. Trust forwarded headers only from the
  actual proxy address; do not use a wildcard trusted-proxy setting.

### Ordered deployment steps (blocked until prerequisites above are verified)

1. Resolve all endpoint, identity/session, logging and historical-baseline blockers above. Add negative
   authorization tests for every protected route, IdP expiry/role/issuer checks and selected-baseline policy.
   Obtain accountable security/engineering approval. Do not bypass the non-local startup interlock.
2. Provision an isolated MongoDB database with authenticated TLS, scoped users, required indexes and backups.
   Run integration tests against a separate test instance/database, never the production URI.
3. Build a pinned release using `requirements-lock.txt`, verify supply-chain/vulnerability status and run the
   recorded security/regression checks. Pin the reviewed commit and runtime; do not run reload supervisors.
4. After the implemented provider boundary passes real tenant/database acceptance and startup checks,
   supervise API and Streamlit as separate unprivileged services with protected environment injection:

   ```sh
   python -m uvicorn app.api:app --host 127.0.0.1 --port 8010 --workers 1 --proxy-headers --forwarded-allow-ips 127.0.0.1
   python -m streamlit run dashboard/streamlit_app.py --server.address 127.0.0.1 --server.port 8510 --server.headless true
   ```

   For production Streamlit, supply the trusted HTTPS API origin, not the loopback HTTP URL. Explicitly set
   the non-local environment in service configuration; startup refuses incomplete/unverified security settings.
   The HTTP loopback URL remains local-development only.
5. Configure the TLS/access proxy and Streamlit WebSocket forwarding on the isolated network. Set request
   size/time/rate limits for synchronous investigations and migrations; do not log Authorization or request bodies.
   Do not open ingress until startup/readiness, TLS, authorization and audit persistence checks pass.
6. Verify `/health` without a database and `/ready` against authenticated MongoDB; test missing-token 401,
   reader-decision 403, forged-actor resistance, authorized synthetic review, immutable baseline and persisted
   history. Confirm the serving OpenAPI advertises bearer security on decision routes and the expected build
   is listening on the expected port. Test backup restoration and restart behavior. No live Groq acceptance required.
7. Only then request explicit deployment approval. Retain rollback release/config and incident evidence;
   rollback must not remove audit history or restore an unauthenticated API.

For current **local-only** verification, stop only the positively identified AutoPLM process bound to 8010,
then restart it from this repository in the same protected environment that contains its local registry:
`python -m uvicorn app.api:app --host 127.0.0.1 --port 8010` (no reload).
Restart the dashboard on 8510 with `AUTOPLM_API_URL=http://127.0.0.1:8010`.
Do not stop the unrelated service on 8000, print credentials, or assume a new shell inherits an old server's registry.
Phase 12 source tests do not establish that these existing local processes were restarted.

Official operational references:
[FastAPI HTTPS](https://fastapi.tiangolo.com/deployment/https/),
[trusted proxies](https://fastapi.tiangolo.com/advanced/behind-a-proxy/),
[CORS](https://fastapi.tiangolo.com/tutorial/cors/),
[MongoDB security](https://www.mongodb.com/docs/manual/security/),
[MongoDB TLS](https://www.mongodb.com/docs/manual/core/tls/plan-tls-deployment/).
