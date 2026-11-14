# Demonstration and release evidence

Verified on 2026-11-14 (Asia/Calcutta). This records measured results, not a production certification.

## What works now

- Public frontend: https://autoplm-twin.streamlit.app/ — HTTP 200, rendered synthetic public demonstration
  visually reviewed in an isolated headless Edge profile. [Screenshot](images/hosted-public-demo.png).
- Backend: https://autoplm-twin-api.onrender.com — `/health`, `/ready`, `/public/samples` and `/openapi.json`
  returned HTTP 200. The catalog contains synthetic-equivalent and synthetic-hardware-revision-drift.
- Anonymous `/jobs` and `/review/me` returned 401. A non-approving promotion request for a nonexistent
  acceptance identifier returned 401; no actual engineering record was promoted or modified. OpenAPI's
  promotion operation advertises HTTPBearer. Readiness confirms a live database response, not all privileges.
- Local complete suite: **735 passed, 1 skipped in 93.79s**. All 12 MongoDB integration tests used the existing
  local container and randomly named disposable test databases. Atlas/production records were not mutated.
- The only remaining skipped test is the opt-in live investigation provider test: no model/API key configured.
- Ruff across app/dashboard/tests/scripts, Mypy across 39 app/dashboard/scripts source files, pip check,
  workflow YAML parsing and git whitespace checks passed. Existing mongomock UTC warnings remain.

Initial full testing without the dedicated MongoDB test URI reported 723 passed/13 skipped; the final run
above includes MongoDB and supersedes that local result. All domain, migration, twin, what-if, API, security,
frontend and offline/mocked investigation tests in the repository were included. Tests do not establish
physical vehicle safety, actual OEM integration or live-model accuracy.

## Fixes completed during final verification

- Seeded raw record dictionaries now enter Dataset through model_validate, preserving the same Pydantic
  validation and canonical values while satisfying broad type checking.
- The evidence generator no longer assigns Dataset and dictionary return values to the same `_` variable.
- Existing CI Mypy coverage expands from selected modules to all app, dashboard and scripts modules.
- Removed an untracked generated Code Runner fragment with invalid indentation; no tracked user code deleted.

No dependency versions, authentication checks, MongoDB privileges, public artifacts/hashes, migration/twin
rules or historical audit records were changed. No unnecessary new product feature or phase was created.

## Exact remaining account-owner action

The live frontend displays **Reviewer login is not configured. Public browsing remains available.**
Therefore real hosted login, Auth0 code exchange, reviewer investigations and ACCEPT/REJECT acceptance
are **not claimed**. No authenticated cloud control-plane integration or account credentials were available
to this execution. Public endpoint reachability does not grant permission to inspect private cloud settings.

1. In Streamlit Community Cloud, open the existing app's Settings > Secrets and apply the full
   [.streamlit/secrets.example.toml](../.streamlit/secrets.example.toml) structure with protected real values.
   Set AUTOPLM_ENVIRONMENT=production, AUTOPLM_API_URL=https://autoplm-twin-api.onrender.com,
   redirect_uri=https://autoplm-twin.streamlit.app/oauth2callback, a random cookie_secret >=32 characters,
   expose_tokens=["access"], and the confidential Auth0 client ID/secret and trusted tenant discovery URL.
   Set authorize_params.audience to the backend's API audience; request
   `openid profile email autoplm:access`, PKCE S256 and client_secret_basic. Keep secret values out of Git/chat.
2. In Auth0, confirm the same Regular Web Application/client and custom API; exact callback above, exact
   frontend origin and logout URL https://autoplm-twin.streamlit.app/. Use RS256 and the Auth0 token profile
   with azp, not an incompatible RFC 9068 client_id-only profile. Set access lifetime <=3600 seconds.
3. Match Render's AUTOPLM_OIDC_ISSUER (HTTPS tenant root with trailing slash), AUDIENCE and CLIENT_ID to
   that Auth0 configuration. Existing protected Atlas runtime URI/database and initialized security controls
   remain required. Grant only the explicitly approved issuer/subject through the existing operator workflow.
4. After the verified release is pushed, manually deploy that revision on Render if needed: the Blueprint
   disables automatic backend deployments. No Render control-plane credential/integration was available here.
   Verify the actual deployed revision in Render, then `/health` and `/ready`; never switch to local mode.
   Community Cloud tracks the repository, but its revision/rebuild must also be checked in its dashboard.
5. Exercise the real callback, /review/me identity, authorized synthetic investigation, evidence and history,
   ACCEPT and REJECT on separate pending reports, reader denial, revocation, expiry and account switching.
   Do not reuse/re-promote the historical forged baseline or silently rewrite its actor/history.

## Security and operational limitations

- Installed Streamlit 1.67.0 signs identity/token cookies with HttpOnly/SameSite=Lax but omits Secure.
  Actual HTTP-to-HTTPS/HSTS transport policy and callback cookie flags need browser/platform acceptance;
  an explicit Secure-cookie requirement remains an upstream/platform release gate. HTTP probes did not
  observe an HSTS response header on the two checked HTTPS origins; no browser preload guarantee is claimed.
- Streamlit's own callback failure logging can include exception tracebacks; application redaction tests do
  not certify all provider/hosting log paths. Keep operational logs restricted and validate sanitized failures.
- Logout clears private application state but does not globally revoke provider sessions. No automatic
  access-token refresh is implemented; API expiry and fresh reviewer grants remain authoritative.
- Backups/restoration, immutable audit retention, Atlas least-privilege acceptance, capacity/cold starts,
  edge flood controls and monitoring remain operational gates documented in the cloud runbook.
- Live LLM behavior remains unverified; deterministic/offline recommendations and public reports are labeled
  accordingly. LLM execution stays disabled by default.

## Recruiter demonstration assessment

**Ready for a public, synthetic, read-only portfolio demonstration.** The URL and browser screenshot show
the actual dashboard. Explain the implementation and measured tests without presenting it as production
automotive approval software. **Not yet a completed hosted reviewer/live-AI demonstration:** the account-owner
configuration and acceptance above are still required. Local authorized reviewer/investigation flows are tested,
including real local MongoDB persistence, but that is not proof of the hosted Auth0 workflow.

Ignored local evidence includes artifacts/final-release-tests.xml, hosted-completion-evidence.json,
browser-completion-evidence.json and hosted-public-dashboard.png. The browser DOM probe returned false
visibility flags before the rendered screenshot was reviewed; those flags are retained with an explicit
visual-review annotation rather than being misreported as successful DOM assertions. No credential-bearing
browser profile or private engineering export is published. Git/CI release outcome is reported separately.
