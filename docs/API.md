# API and data contract

Start `python -m uvicorn app.api:app`. OpenAPI: `/openapi.json`; interactive documentation: `/docs`. This API is intended for trusted localhost operation and has no authentication. Do not expose it publicly.

| Method | Route | Behavior |
|---|---|---|
| GET | `/health` | Process health; does not imply database connectivity |
| GET | `/ready` | MongoDB ping |
| POST | `/datasets/generate` | `{fleets: 2, seed: 42, source: "A"}` → legacy synthetic envelope |
| POST | `/jobs` | `{dataset: envelope, mapper: "offline"}` → idempotent staged job |
| GET | `/jobs` | Most recent 200 jobs |
| GET | `/jobs/{id}` | Job state, counts and current validation |
| GET | `/jobs/{id}/approved` | Approved records only after source/publication integrity checks |
| GET | `/jobs/{id}/report?format=json` | Full provenance and diagnostic evidence |
| GET | `/jobs/{id}/report?format=csv` | Machine-readable finding rows |
| GET | `/jobs/{id}/report?format=html` | Escaped readable full audit |
| POST | `/jobs/{id}/mappings/decision` | `{actor, approve, plan}`; plan must pass the same deterministic validator |
| POST | `/jobs/{id}/promote` | `{actor, approve:true}`; revalidate and commit publication manifest |
| POST | `/jobs/{id}/repairs?mapper=offline` | Auditable source-restoration candidate; `llm` enables source-field proposal planner |
| POST | `/repairs/{id}/decision` | `{actor, approve}`; stale or invalid changes cannot apply |
| POST | `/jobs/{id}/simulations` | `{variant_id, scenario, ticks:5, fault_at:null}` → persisted trace and engineering findings |

`404` means unknown identifier; `409` means invalid state, engineering decision, integrity failure or source/mapping conflict; `422` means request schema failure, including nested upload shape and non-Boolean approval values; `503` means a database operation failed. Request models reject extra fields. Approval names are trimmed and must be nonblank. Live provider configuration failures are not silently converted to successful offline migrations. Mapping provider exceptions are captured as failed attempts and reach review.

The envelope is `{synthetic:true, source_schema:"A", records:[{source_id:"A:00000000", entity:"platform", data:{...}}]}`. Valid entities: hardware, software, platform, variant, bom, change. Source identifiers are unique within a job. Up to 50,000 rows per upload; requests are synchronous. Entity fields are in the generated examples and Pydantic models. Sources A/B support their versioned aliases and the gram mass field.

Each finding includes `finding_id`, `rule_id`, `affected_records`, `severity`, `evidence`, `expected`, `actual`, `remediation`, and `verification_status`. Unknown critical compatibility uses status `unknown`. Record statuses in staging are pending/verified/rejected; relationship findings also identify their related records. Promotion is an all-job gate even if some individual records have no findings.

Repair proposals preserve complete before/after configurations, the job revision, before digest, candidate rules/twin results, planner evidence and approval status. LLM repair actions are only `restore_source_field` with a source record/field reference. Values are looked up deterministically; arbitrary generated values cannot be executed or applied.
