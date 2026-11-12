# Production readiness and security boundary

Phase 12 checkpoint, 2026-11-13. **Not cleared for production deployment.**
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
| POST `/jobs/{job_id}/investigation-reports` | Authenticated reader or reviewer | Immutable baseline association; created_by is authenticated subject. |
| GET `/investigation-reports`, GET `/investigation-reports/{id}`, GET `/investigation-reports/{id}/decisions` | Authenticated reader or reviewer | Typed report/queue/history; report integrity checks preserved. |
| POST `/investigation-reports/{id}/decisions` | Authenticated `engineering_reviewer` | Atomic terminal decision and persistent history; principal subject, mandatory comments, baseline fingerprint and audit mirror. ACCEPT is recommendation acceptance only. |
| GET `/jobs`, `/jobs/{id}`, `/jobs/{id}/approved`, `/jobs/{id}/report` | Public prototype reads | **Production blocker:** engineering records and audit exports lack authenticated access and resource-level isolation. Never expose this API publicly. |
| POST `/datasets/generate`, `/jobs`, `/jobs/{id}/simulations`, `/jobs/{id}/investigations` | Public prototype execution | **Production blocker:** compute/storage/provider-cost abuse; no principal attribution on all execution paths. Add authentication, permissions, request budgets and operational limits before release. |
| GET `/health`, `/ready` | Public liveness / database readiness | Minimal responses; readiness failure uses a generic database error. Restrict readiness to operations network at the proxy. |

The local credential registry retains SHA-256 and constant-time comparison. Reader-only credentials
cannot decide or promote. Optional legacy actor fields are deprecated and ignored on decision APIs;
service/CLI methods still accept operator actors and must not be exposed as an authentication shortcut.

`AUTOPLM_ENVIRONMENT` defaults to `local` for existing development commands. Any other value blocks
API startup. Authentication also rejects local static credentials when this setting is not `local`.
This is a fail-closed release interlock, **not** production authentication or automatic environment detection.
Never set `local` on an external deployment to work around it. Existing running processes must be
restarted to load source changes; do not assume source edits protect an already-running worker.

API responses now send `Cache-Control: no-store` and `X-Content-Type-Options: nosniff`.
Global KeyError/ValueError responses preserve 404/409 while omitting raw exception messages.
Validation details remain available in job reports. Database and investigation/review failures retain
their existing sanitized handlers. The legacy dashboard request helper no longer displays HTTP exception text.
There is no comprehensive structured/security logging, durable authentication-denial log, rate limiter,
or complete request-validation/provider-message redaction audit yet; those remain release blockers.

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

## Simplest deployment architecture

Use one supervised Linux host initially: TLS reverse proxy -> Streamlit on private/loopback 8510 ->
FastAPI on private/loopback 8010 -> a separate authenticated private MongoDB service (preferably managed).
Keep the API off the public proxy until every public execution/read route has an authorization policy.
A single API worker matches the current synchronous bounded job model; this is not a distributed task queue.
Only expose HTTPS 443 to engineers through an approved access gateway. Keep admin/backup access separate.

The checked-in `docker-compose.yml` is **local development only**: loopback MongoDB, no authentication.
Do not reuse its configuration or existing data volume for production. No live database configuration
was changed or inspected for secrets in this task.

### Required configuration and identity work

- Implement a verified OIDC/OAuth2 resource-server integration (organization Entra ID, Keycloak or other
  approved provider). Validate signature, issuer, audience, expiry and permitted algorithms, handle key rotation,
  and map administrator-managed claims to existing roles. Do not trust a free-form body or proxy identity header.
  Streamlit needs an approved login/session/token lifecycle; local bearer text entry is not production SSO.
  These are provider options, not implemented integrations. Preserve review and engineering approval semantics.
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
4. Once the real provider is implemented and the startup interlock is deliberately updated with tests,
   supervise API and Streamlit as separate unprivileged services with protected environment injection:

   ```sh
   python -m uvicorn app.api:app --host 127.0.0.1 --port 8010 --workers 1 --proxy-headers --forwarded-allow-ips 127.0.0.1
   python -m streamlit run dashboard/streamlit_app.py --server.address 127.0.0.1 --server.port 8510 --server.headless true
   ```

   Supply `AUTOPLM_API_URL=http://127.0.0.1:8010` to Streamlit. Explicitly set the non-local environment
   in the service configuration; **current code intentionally refuses that API launch**.
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
