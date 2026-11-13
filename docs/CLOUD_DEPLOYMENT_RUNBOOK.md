# Cloud deployment runbook

Prepared from main at b804691, 2026-11-13. **Preparation only: no cloud service has been created or verified by this task.** Obtain explicit deployment approval before applying the Blueprint or publishing the frontend. Hosted acceptance and the security checklist below are release gates, not completed work.

## Architecture and repository configuration

- Public visitors: Streamlit Community Cloud reads packaged, hashed synthetic snapshots. No login, API or MongoDB is needed for public browsing.
- Reviewers: Streamlit hosted Auth0 login sends an API-audience access token over HTTPS to FastAPI on Render. FastAPI independently validates the token and checks current issuer/subject grants in Atlas.
- Atlas stores private engineering data, reports, append-only decision history, grants and shared execution controls. There is no public arbitrary-database lookup.
- `.python-version` selects Python 3.13 (latest available patch on Render); select 3.13 explicitly in Community Cloud Advanced settings too. This satisfies `pyproject.toml`'s >=3.11 and matches existing CI. No dependency versions were changed: `requirements.txt` installs the lock and `-e .`.
- `render.yaml` defines one native Python Free web service, one worker, production environment, disabled LLMs and `/health`. No Docker or local filesystem persistence is required. The actual import target is **`app.api:app`**, not bare `app.api`.

The platform supplies `PORT`; the start command expands it at runtime:

```sh
python -m pip install -r requirements.txt
python -m uvicorn app.api:app --host 0.0.0.0 --port $PORT --workers 1 --no-access-log
```

Use the repository root as the working directory. Packaged CSS, vehicle HTML and public JSON are resource-relative; the optional benchmark file is relative to the checkout. Do not store authoritative data on Render's ephemeral filesystem. `autoDeployTrigger: 'off'` disables subsequent automatic code deploys, **not initial Blueprint deployment**; also review Blueprint Auto Sync separately. `sync: false` prompts only at initial creation; add/update values manually for an existing service. Remove a stale Render `PYTHON_VERSION` override or set an explicitly reviewed full 3.13 patch version.

## Manual account setup and deployment order

All actions in this section are external/operator actions, not automated by these repository files.

1. Establish GitHub access, Streamlit Community Cloud, Render, Atlas and Auth0 accounts. Enable account MFA and restrict administrators. Select compatible nearby Render/Atlas regions and review current free-tier quotas. Record the intended Streamlit hostname before setting callbacks; do not create services until approved.
2. Create a dedicated Auth0 tenant API and confidential Regular Web Application as below. Record issuer, API audience and client ID; store the client secret only in Streamlit secrets.
3. Create a fresh Atlas M0 database with scoped runtime and separate operator/backup identities. Allow only approved operator IPs initially; initialize indexes, policy and slots, then provision approved reviewer subjects. Do not import the historically forged baseline.
4. After approval, connect the reviewed GitHub revision through Render's Blueprint flow. Enter backend values below and keep auto-deploy off. Obtain the service's **Connect > Outbound** IP ranges and allow those exact CIDRs in Atlas. Initial startup may fail closed until this is complete; restart after configuration, never select local mode as a workaround. Do not use permanent `0.0.0.0/0`. If a service cannot be created without an initial failed attempt, plan that failure explicitly; it must not be made healthy by disabling security.
5. Verify Render startup, HTTPS, `/health` and `/ready` and negative authorization tests before enabling reviewer access. No reload or additional duplicate API worker. Record the actual running revision/runtime.
6. After approval, deploy Community Cloud from `main`, entry point `dashboard/streamlit_app.py`, Python 3.13. Populate protected secrets from the exact template below. Finalize exact Auth0 callback/origin/logout entries for the assigned HTTPS hostname.
7. Complete hosted acceptance on fresh synthetic data, backup/restore rehearsal and operator recovery. Record results and obtain the accountable release/security sign-off before treating the reviewer workflow as production ready.

## Render environment reference

| Variable | Value / location |
|---|---|
| `AUTOPLM_ENVIRONMENT` | Blueprint sets `production`; never use `local` on a hosted API |
| `AUTOPLM_ENABLE_LLM` | Blueprint sets `false`; no model API keys required for this deployment |
| `MONGODB_URI` | Render protected environment: authenticated Atlas `mongodb+srv` URI, percent-encoded credentials, verified TLS, majority writes; no insecure TLS options |
| `MONGODB_DATABASE` | Explicit isolated database name, e.g. `autoplm_twin`; must match operator configuration |
| `AUTOPLM_OIDC_ISSUER` | Exact tenant HTTPS issuer, including trailing `/` |
| `AUTOPLM_OIDC_AUDIENCE` | Dedicated HTTPS-format custom API identifier, distinct from client ID and userinfo audience |
| `AUTOPLM_OIDC_CLIENT_ID` | Confidential Streamlit application client ID permitted by FastAPI |
| `PORT` | Render-managed; do not hardcode |

Do not put `AUTOPLM_REVIEW_CREDENTIALS`, `AUTOPLM_PROVISIONING_MONGODB_URI`, Auth0 client/cookie secrets or operator credentials in Render runtime. `.env.example` is a reference, not an automatically loaded file. Keep secret values out of command arguments, Git, reports and logs. Do not enable request-body/header logging. Render terminates HTTPS; verify proxy behavior without indiscriminately trusting forwarded headers. Streamlit uses server-side HTTP calls, so CORS wildcard configuration is neither necessary nor appropriate.

## Atlas initialization, collections and permissions

Create separate databases/credentials for production and testing. The local unauthenticated Compose MongoDB is not a hosted configuration. Runtime connections use verified TLS, primary security reads and majority writes. Two cached clients can each use pools of up to ten connections; measure capacity rather than assuming free-tier suitability.

### Collections and indexes

The operator constructs `Repository` then calls `SecurityStore.initialize()` through the existing CLI. Collections may be created lazily on their first write. MongoDB also supplies each collection's unique `_id` index.

| Collections | Additional required indexes |
|---|---|
| `source_records`, `staging_records`, `schema_mappings`, `twin_snapshots` | Unique `(job_id ASC, key ASC)` |
| `ecu_hardware`, `ecu_software`, `vehicle_platforms`, `vehicle_variants`, `engineering_boms`, `engineering_changes`, `mechanical_parts`, `assemblies` | Unique `(job_id ASC, id ASC)` |
| `audit_events` | `(job_id ASC, created_at ASC)` |
| `migration_jobs` | `created_at ASC` |
| `validation_results`, `simulation_runs`, `repair_proposals` | `job_id ASC` |
| `investigation_reports` | `(review_status ASC, created_at ASC)` |
| `reviewer_grants` | Unique `(issuer ASC, subject ASC)` |
| `security_quotas` | `expires_at ASC`, TTL `expireAfterSeconds=0` |
| `security_policy`, `security_locks` | `_id` only |

Initialization creates policy `_id=v1` with requests 60/minute, executions 6/minute, decisions 10/minute, LLM 1/minute and 10/day, and two global execution slots. LLM remains disabled regardless of provisioned quota. TTL removes expired quota documents, not audit history or execution locks. Request inspection retains 2 MB bodies, bounded body reads and production execution bounds. Limits are application controls, not an anonymous edge flood defense.

### Exact runtime and operator roles (2026-11-14)

Database: **`autoplm_twin`**, explicitly set as `MONGODB_DATABASE` in both environments. Version-controlled Atlas Administration API request bodies are [runtime-role.json](../config/atlas/runtime-role.json) (`autoplm_runtime`) and [operator-role.json](../config/atlas/operator-role.json) (`autoplm_operator`). They use Atlas's uppercase action names and `actions[].resources[]` objects with `cluster: false`, exact database/collection names and no inherited roles. These are **Atlas custom-role payloads**, not `mongosh db.createRole` documents or credentials. No API request has been executed.

The exact matrix below expands every resource in those files. F=`FIND`, I=`INSERT`, U=`UPDATE`, CI=`CREATE_INDEX`, LI=`LIST_INDEXES`; a dash means no privilege. CI changes index metadata, not document contents. No role has REMOVE, DROP, BYPASS, database-wide or cluster privileges, user/role administration, backup or restore rights.

| Collection(s) in `autoplm_twin` | Runtime | Operator | Actual operation / reason |
|---|---|---|---|
| `source_records`, `staging_records`, `schema_mappings`, `twin_snapshots` | F, I, U, CI | CI | Reads and upserts; source uses `$setOnInsert` but an upsert still requires U and I |
| `ecu_hardware`, `ecu_software`, `vehicle_platforms`, `vehicle_variants`, `engineering_boms`, `engineering_changes`, `mechanical_parts`, `assemblies` | F, I, U, CI | CI | Publication upserts and integrity reads; no publication deletion |
| `migration_jobs` | F, I, U, CI | CI | Insert, reads, compare-and-set updates; rollback updates status, not deletes |
| `repair_proposals` | F, I, U, CI | CI | Insert/read/update decisions |
| `investigation_reports` | F, I, U, CI | CI | Insert/read and non-upsert findOneAndUpdate decision |
| `validation_results` | I, CI | CI | Insert only; current application has no read/update operation |
| `simulation_runs` | F, I, CI | CI | Insert and report read; no update |
| `audit_events` | F, I, CI | I, CI | Audit insert, runtime report/mirror checks, constructor index; no audit update/delete for either role |
| `reviewer_grants` | F, LI | F, I, U, CI, LI | Runtime reads/index inspection; operator grant/revoke upsert and initialization index |
| `security_policy` | F | F, I, U | Runtime reads; operator `$setOnInsert` upsert during initialization |
| `security_quotas` | F, I, U, LI | F, I, U, CI, LI | findOneAndUpdate upsert; startup index inspection; operator initializes TTL index and runs startup quota write |
| `security_locks` | F, I, U | F, I, U | Runtime count/read, lock upsert/release; operator initialization upserts and exact-owner recovery update |

Source trace: `app/repository.py:34-44` (18 constructor indexes), `:58-65` (audit), `:69-113` (reads/publication); `app/service.py:172-189` (source/mapping upserts), `:335-339` (validation/twin writes), `:379-414` (publication/rollback), `:442-494` (repair decisions), `:520-534` (simulation/report); `app/investigation_review.py:69,125-139,159-191` (report collection, reads and atomic decision); `app/security_store.py:57-82,112-192` (initialization, index inspection, grant/quota/lock operations); `app/api.py:159,176` (ping/job reads); `scripts/manage_reviewers.py:36-65` (constructor, initialization, grant/revoke, audited recovery).

`find_one_and_update` needs F+U, with I when `upsert=True`; ordinary upserts require U+I even with `$setOnInsert`. Cursor sorting/paging and count_documents do not require a new action beyond FIND. `index_information()` calls listIndexes on grants and quotas, explicitly covered by LI. Every API/security-store connection constructs `Repository`, so **both identities need CI on all 18 engineering/audit collections even when indexes already exist**. Operator initialization additionally needs CI on grants/quotas (20 total). Neither code path issues explicit createCollection or listCollections, so CREATE_COLLECTION/LIST_COLLECTIONS are not added speculatively: indexing/upsert operations create their named collections implicitly. Ping and normal driver connection/session housekeeping do not justify cluster/admin management privileges.

The operator is deliberately not a runtime superset: it cannot read/write engineering documents and cannot read audit documents with this role. It can create their required indexes because its existing CLI constructs Repository. Startup inside initialize reads grants/policy/locks and consumes a quota write; these permissions cannot be omitted just because the operator does not serve HTTP. Backup/restore or general diagnostic inspection needs a separately approved identity, not an expansion of these roles.

### Manual Atlas role and user creation

These steps are **not performed by this task**. An authorized Atlas project administrator manages control-plane roles/users; `autoplm_operator` is a database provisioning role, not permission to administer Atlas accounts.

1. In the intended Atlas project open **Security / Database Access (Database & Network Access in some layouts) > Custom Roles > Add New Custom Role**. Name the roles `autoplm_runtime` and `autoplm_operator`.
2. For each JSON payload, enter each action and its exact database/collection resources from `actions`. Choose collection-scoped actions, database `autoplm_twin`, and each named collection. Do not select Apply to any database/collection, Global Actions or inherited built-in roles. The UI may display camelCase action labels; the payload's uppercase names are the Atlas API equivalents. Save both roles. If using an approved Atlas API workflow later, each file is a complete request body for `POST /api/atlas/v2/groups/{groupId}/customDBRoles/roles`; do not send it to MongoDB's database command interface.
3. Open **Database Users > Add New Database User**, select Password/SCRAM, create a distinct runtime username and strong generated password in a protected password manager, then select **Custom Roles: `autoplm_runtime`**. Remove any default `readWriteAnyDatabase`, `readWrite`, admin role or additional specific privilege. Restrict access to the intended cluster using the user cluster restriction control; custom roles themselves are project-level. Save.
4. Repeat for a different operator username/password, with **only `autoplm_operator`** and the same intended cluster restriction. Do not assign both roles to either user. Verify effective privileges, since Atlas unions all assigned roles/privileges. Free/Flex custom-role changes can take up to 30 seconds to propagate; reconnect after changes.
5. Put the runtime authenticated TLS connection only in Render's protected `MONGODB_URI`; set `MONGODB_DATABASE=autoplm_twin`. Atlas SCRAM normally authenticates against `admin`; that authentication database is distinct from the collection resource database `autoplm_twin`. Keep operator connection only in protected `AUTOPLM_PROVISIONING_MONGODB_URI` on the operator host, with the same explicit database and required OIDC settings. Neither credential belongs in Streamlit, JSON files, Git, command arguments or diagnostic output.
6. Allow only Render's exact outbound CIDRs and temporary trusted operator IPs in Atlas Network Access. Do not use permanent unrestricted ingress. With separate approval, run the existing initialize/grant commands below using the operator credential, then start the API with the runtime credential. Do not add CI on security collections to runtime to make it initialize itself.
7. On an isolated acceptance database/cluster with the same role scopes adapted and reviewed, verify runtime startup, full synthetic migration/promotion/report/review/quota/lock flows and operator initialization/grant/revoke/exact-owner audited recovery. Verify denied runtime grant/policy writes and audit update/delete, denied operator engineering reads/writes, and denied cross-database access. Use protected sessions and harmless nonexistent-ID negative requests, not modifications to historical documents. Record MongoDB Unauthorized/code 13 denials and sanitized results. This task has **not** executed those authenticated tests on Atlas or a real authorization-enabled MongoDB server; mocked/offline tests cannot prove server enforcement.

Important limitations: CI permits additional index creation on its allowed collections; it cannot be limited to particular index names without changing existing constructor behavior. INSERT permits implicit collection creation where MongoDB supports it. UPDATE is collection-level, not limited to `$setOnInsert`, particular fields, pending decisions or append-only array operations. Thus runtime source/report immutability and operator grant-history conventions still depend on the application, and operator policy/lock writes are privileged. Neither role can update/delete `audit_events`, but insert access is not cryptographic audit attestation. Protect both credentials and retain independent audit exports. Runtime permissions above are derived and offline-checked, not a substitute for the Atlas acceptance gate.

Inject `AUTOPLM_PROVISIONING_MONGODB_URI`, `MONGODB_DATABASE` and the three `AUTOPLM_OIDC_*` settings into a protected operator environment. The CLI takes no credential arguments. Run from the installed checkout:

```sh
python -m scripts.manage_reviewers initialize --operator OPERATOR_ID --reason "Initial reviewed cloud security provisioning"
python -m scripts.manage_reviewers grant --subject 'auth0|VERIFIED_SUBJECT' --operator OPERATOR_ID --reason "Approved engineering reviewer"
python -m scripts.manage_reviewers revoke --subject 'auth0|VERIFIED_SUBJECT' --operator OPERATOR_ID --reason "Reviewer access withdrawn"
```

Use the verified Auth0 subject, never email or self-declared roles. New accounts have no engineering permissions. Revocation is checked independently on subsequent API requests, even before token expiry. Verify metadata/indexes, quota writes, full engineering operations and decision history under the runtime identity; startup checks alone do not prove every permission.

### Networking, backup and restore

Allow Atlas ingress only from the selected Render service's published outbound ranges and narrowly scoped temporary operator IPs. Those Render ranges can be shared with other services; authentication/TLS remain necessary. Streamlit requires no direct Atlas access. Track platform range changes. M0 private networking is unavailable; if organizational policy requires it, free hosting cannot satisfy that requirement.

Do not assume M0 includes free automated snapshots. Current optional M0 managed backups are a **paid private-preview subscription** (daily, four retained snapshots), not part of this free-tier plan. For a free operator-managed alternative:

1. Schedule a trusted operator maintenance window; stop all API writers and provisioning changes and confirm no work is still executing. A live logical dump without consistent-point-in-time support is insufficient for cross-collection publication/audit consistency.
2. Use compatible MongoDB Database Tools with a protected, owner-only YAML config outside Git containing the connection URI/password; do not pass secrets on argv. Export the explicit application database including metadata/index definitions:
   `mongodump --config=/PROTECTED/backup.yml --db=autoplm_twin --archive=/PROTECTED/autoplm-backup.archive.gz --gzip`.
3. Encrypt the archive at rest, store off-host with access control, checksum, timestamp/revision manifest and approved retention. Review tool diagnostics privately; never publish raw exports. Back up reviewer-grant history and security state as well as engineering/audit records. Remove temporary operator network access and resume only after verifying service state.
4. Rehearse restoration with a separate destination credential/allowlisted host and isolated empty database/cluster. Use `mongorestore --config=/PROTECTED/restore.yml --archive=/PROTECTED/autoplm-backup.archive.gz --gzip --nsFrom='autoplm_twin.*' --nsTo='autoplm_restore_test.*'`. The destination config must point to the isolated target; never use `--drop` against live history.
5. Verify counts, unique/TTL indexes, source/publication/twin digests, reports, decision/grant histories and fresh negative/positive authorization. Reconcile current authoritative revocations and newer audit decisions before any recovered database is eligible for cutover. Do not reactivate revoked reviewers from an older backup. Confirm all affected workers are stopped before recovering stale locks using the CLI's exact owner match; record every recovery.

Automated scheduling, immutable offsite storage, backup freshness alerts, retention policy and a measured restore/RPO/RTO are **not implemented or verified**. If an operator-managed backup cannot meet the required recovery policy, use an approved managed option or block private deployment. Preserve the original database/export before recovery; never overwrite post-backup decisions. Recovery reconciliation requires accountable manual review, not an implemented automatic merge.

## Auth0 configuration

Create a custom API with a dedicated audience identifier, RS256 signing, `autoplm:access` permission and access-token lifetime at most 3600 seconds. Create a confidential **Regular Web Application** for Streamlit using authorization code flow with PKCE S256 and `client_secret_basic`. Use the same client ID in both applications' configuration. Verify real issued tokens contain `iss`, `aud`, `sub`, `iat`, `exp`, `azp` and `scope` and include `autoplm:access`; incompatible token dialect/settings are a release blocker, not a reason to loosen validation.

Allow exact `https://YOUR-APP.streamlit.app/oauth2callback` callback, the exact Streamlit HTTPS origin in allowed web origins, and its exact HTTPS home URL for allowed logout URLs. Do not use wildcards. Auth0 account/session behavior and actual callback/token acquisition require hosted acceptance. Free authentication does not require paid Auth0 RBAC: permissions are controlled by issuer/subject grants in Atlas, not token/profile/email roles. Review current provider quotas and registration/abuse settings before opening registration.

FastAPI fixes RS256, issuer and audience, validates expiry/allowed client/scope, bounds token lifetime, and loads trusted issuer-derived discovery/JWKS with bounded caching and refresh. Missing/invalid tokens return 401, authenticated non-reviewers 403, unavailable security configuration 503, exhausted shared quotas/slots 429 with Retry-After. Never use an ID token, local static secret or arbitrary proxy identity as an API credential.

## Streamlit configuration

Use `.streamlit/secrets.example.toml` as the exact TOML template in Community Cloud **App settings > Secrets**; do not commit a populated `secrets.toml`. Required entries are:

| TOML key | Required setting |
|---|---|
| `AUTOPLM_ENVIRONMENT` | `"production"` (also needed for a public-only hosted frontend to suppress local credential entry) |
| `AUTOPLM_API_URL` | Render HTTPS origin, no credentials/query/fragment; no localhost |
| `AUTOPLM_OIDC_ISSUER`, `AUTOPLM_OIDC_AUDIENCE`, `AUTOPLM_OIDC_CLIENT_ID` | Same exact backend values |
| `auth.redirect_uri` | Exact registered HTTPS `/oauth2callback` URL |
| `auth.cookie_secret` | Independently generated high-entropy secret, >=32 characters, stored only in protected Streamlit settings |
| `auth.expose_tokens` | `["access"]` |
| `auth.auth0.client_id` | Same permitted Streamlit client ID |
| `auth.auth0.client_secret` | Confidential web-application secret, Streamlit only |
| `auth.auth0.server_metadata_url` | Issuer + `.well-known/openid-configuration` |
| `auth.auth0.authorize_params.audience` | Dedicated FastAPI API audience |
| `auth.auth0.client_kwargs.scope` | `"openid profile email autoplm:access"` |
| `auth.auth0.client_kwargs.code_challenge_method` | `"S256"` |
| `auth.auth0.client_kwargs.token_endpoint_auth_method` | `"client_secret_basic"` |
| `auth.auth0.client_kwargs.prompt` | `"select_account"` |

Streamlit top-level secrets become environment variables. No MongoDB/operator credentials belong here. Existing Streamlit 1.67.0 integration uses only `st.user.tokens['access']` for server-to-server Authorization headers and backend `/review/me` for authoritative subject/roles. No token is displayed or intentionally logged. Expired/missing tokens require sign-out/sign-in; automatic access-token refresh is not implemented. Account switching and logout clear private UI state; logout does not revoke every other session. Database revocation remains authoritative. Rotate cookie/client secrets through protected settings and restart deliberately; expect sessions to be invalidated.

Public browsing works with login unconfigured, without reviewer credentials or reachable backend, because it reads packaged snapshots. Protected workspaces remain hidden unless `/review/me` authorizes a reviewer, and API enforcement is independent of UI visibility.

## Acceptance and troubleshooting

After deployment approval, use the assigned HTTPS URL:

```sh
curl --fail https://YOUR-SERVICE.onrender.com/health
curl --fail https://YOUR-SERVICE.onrender.com/ready
curl --fail https://YOUR-SERVICE.onrender.com/public/samples
```

`/health` is static liveness after application startup. `/ready` checks MongoDB through the service repository; neither alone proves all OIDC, lock, role or engineering permissions. Production startup still requires validated OIDC and initialized secure MongoDB, even for public API routes. Do not claim that hosted `/health` can start without them.

Verify missing token 401; valid unprovisioned account/private-route 403; approved reviewer success; revocation denied; expired/wrong-audience/forged token 401; forged actor cannot change audit identity. On fresh synthetic data verify approved baseline selection, offline investigation persistence, evidence, ACCEPT and REJECT on separate pending reports, conflicting duplicate decision rejection, persistent history, public snapshot hashes, immutable baseline and migration/twin safeguards. Never re-promote or publish historical job `1159cf031e93874f8a12c0a1` (`approved_by=forged-user`); preserve its original records/audit unchanged and exclude it from the cloud database.

| Symptom | Safe investigation |
|---|---|
| Import failure | Confirm reviewed revision, root directory, Python 3.13 and fresh `requirements.txt` install including `-e .`; run `python -m pip check` and imports. No sys.path workaround. |
| Startup blocked / 503 | Check presence (not values in logs) of required settings; exact issuer/client/audience, TLS/network/DB credentials, initialized policy/indexes/slots and runtime permissions. Never switch to local mode. |
| 401 / 403 | Confirm access-token audience/client/scope/expiry; re-login if expired. For 403 check approved issuer/subject grant, not email/role claims. Never print tokens. |
| 429 | Honor Retry-After, inspect quotas and active work. A crash-stranded lock needs stopped-worker verification and audited operator recovery, not automatic expiration. |
| 413 / 422 | Inspect body size/schema and configured execution bounds; do not remove inspection to make a request succeed. |
| Cold start / timeout | Render Free can sleep; wait for startup then inspect saved reports before retrying a timed-out investigation. Synchronous frontend timeout is 180 seconds. Do not duplicate executions blindly. |
| Public UI works, private UI fails | Public artifacts are local; verify backend readiness, login configuration and current grants separately. |

No live LLM test is required; leave LLM execution disabled. Confirm TLS/cookies, XSRF, proxy headers, sanitized logs, account switching, denied reader decisions and grant revocation in a browser. Free-tier sleep, CPU/RAM, connection/storage limits, anonymous flood protection and reliable backups need measured acceptance; there is no production availability guarantee.

## Rollback and security release checklist

Retain the reviewed Git SHA, exact effective Python patch, lock, redacted configuration inventory and artifact hashes. Disable automatic deploy/sync; restore only a reviewed release that retains all authorization/execution safeguards. Roll back code/config separately from data. A pre-security revision is not a safe rollback target. Stop writers before any restore; preserve newer audit/decision/grant history and obtain a recovery plan before database cutover. Never silently rewrite historical actors, delete evidence, clear all locks or restore revoked grants.

- [ ] Deployment explicitly approved; correct commit/runtime and locked install recorded.
- [ ] Atlas TLS/auth, least-privilege runtime, separate operator, exact network allowlists and restore rehearsal verified.
- [ ] Real Auth0 access-token/callback acceptance, scope/client validation, reviewer grant/revoke and logout verified.
- [ ] Public/private isolation, actor attribution, history, source/twin integrity and negative authorization verified.
- [ ] LLM off; execution caps/shared quotas/locks retained; edge abuse controls, monitoring and alerts reviewed.
- [ ] Backup retention/offsite encryption/restore objectives approved; current incident records preserved/excluded.
- [ ] Free-tier resource/cold-start behavior and operational support accepted; no private production-readiness claim based only on unit tests.

## Official references

- [Render Blueprint specification](https://render.com/docs/blueprint-spec), [Python version selection](https://render.com/docs/python-version), [Free service limitations](https://render.com/docs/free), [outbound IP ranges](https://render.com/docs/outbound-ip-addresses).
- [Atlas network access](https://www.mongodb.com/docs/atlas/security/ip-access-list/), [custom database roles](https://www.mongodb.com/docs/atlas/security-add-mongodb-roles/), [M0 limitations](https://www.mongodb.com/docs/atlas/reference/free-shared-limitations/).
- [Atlas custom-role action names](https://www.mongodb.com/docs/atlas/reference/custom-role-actions/), [Atlas role request schema](https://www.mongodb.com/docs/api/doc/atlas-admin-api-v2/operation/operation-creategroupcustomdbrolerole), [MongoDB privilege/action semantics](https://www.mongodb.com/docs/manual/reference/privilege-actions/).
- [M0 optional backup subscription/preview](https://www.mongodb.com/docs/atlas/backup/cloud-backup/free-cluster-backup/), [mongodump protected configuration](https://www.mongodb.com/docs/database-tools/mongodump/), [mongorestore](https://www.mongodb.com/docs/database-tools/mongorestore/).
- [Streamlit deployment](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app), [Streamlit OIDC login](https://docs.streamlit.io/develop/api-reference/user/st.login), [Auth0 API access tokens](https://auth0.com/docs/secure/tokens/access-tokens), [Auth0 plans](https://auth0.com/pricing).
