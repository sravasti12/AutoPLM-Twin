import copy
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, StrictBool
from pymongo.errors import DuplicateKeyError

from app.agents import LLMMapper, mapping_graph
from app.mapping import MODELS, MappingPlan, transform, validate_plan
from app.models import Finding
from app.repository import COLLECTIONS, Repository, digest, public, publication_digest
from app.source_adapters import normalize_source
from app.twin import build_twin, compare_twins, scenario_records, simulate
from app.verification import verify

PIPELINE_VERSION = "1.4"


class SourceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str = Field(min_length=1)
    entity: Literal[
        "hardware", "software", "platform", "variant", "bom", "change", "mechanical_part", "assembly"
    ]
    data: dict


class Upload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    synthetic: StrictBool
    source_schema: Literal["A", "B"]
    records: list[SourceRecord] = Field(min_length=1, max_length=50000)


def reference_records(source: list[dict], schema: str) -> list[dict]:
    return normalize_source(source, schema)


class MigrationService:
    def __init__(self, repository: Repository):
        self.repo = repository
        self.db = repository.db

    def recover(self, job_id: str, actor: str) -> dict:
        """Operator-only recovery after confirming no worker is active; never automatic takeover."""
        job = self.repo.job(job_id)
        if not actor.strip() or job["status"] not in [
            "running",
            "verifying",
            "promoting",
            "repairing",
            "failed",
        ]:
            raise ValueError("Recovery requires an actor and interrupted/uncommitted job")
        self.repo.audit(job_id, "operator_recovery", {"actor": actor, "previous_status": job["status"]})
        updated = self.db.migration_jobs.update_one(
            {"_id": job_id, "status": job["status"], "revision": job["revision"]},
            {
                "$set": {"status": "failed"},
                "$inc": {"revision": 1},
                "$unset": {"verification_token": "", "promotion_token": ""},
            },
        )
        if not updated.modified_count:
            raise ValueError("Concurrent job change during recovery")
        return public(self.repo.job(job_id))

    def decide_mapping(self, job_id: str, proposed: dict, actor: str, approve: bool) -> dict:
        job = self.repo.job(job_id)
        if job["status"] != "mapping_review" or not actor.strip():
            raise ValueError("Mapping review requires an awaiting job and human reviewer")
        plan = MappingPlan.model_validate(proposed)
        rows = [r["data"] for r in self.repo.source(job_id) if r["entity"] == plan.entity]
        if not rows:
            raise ValueError("Mapping entity is absent from source")
        self.repo.audit(job_id, "mapping_decision", {"actor": actor, "approve": approve, "plan": proposed})
        if not approve:
            return public(job)
        # Human evidence must resolve unsupported assumptions before execution.
        errors = validate_plan(plan, rows)
        if errors:
            raise ValueError(f"Mapping still fails validation: {errors}")
        self.db.schema_mappings.update_one(
            {"job_id": job_id, "key": plan.entity},
            {
                "$set": {
                    "state.plan": plan.model_dump(),
                    "state.status": "validated",
                    "state.errors": [],
                    "reviewer": actor,
                }
            },
        )
        states = list(self.db.schema_mappings.find({"job_id": job_id}))
        if any(s["state"]["status"] != "validated" for s in states):
            return public(self.repo.job(job_id))
        lock = self.db.migration_jobs.update_one(
            {"_id": job_id, "status": "mapping_review"}, {"$set": {"status": "running"}}
        )
        if not lock.modified_count:
            raise ValueError("Concurrent mapping decision")
        plans = {s["key"]: MappingPlan.model_validate(s["state"]["plan"]) for s in states}
        source = self.repo.source(job_id)
        try:
            for row in source:
                record = (
                    MODELS[row["entity"]]
                    .model_validate(transform(row["data"], plans[row["entity"]]))
                    .model_dump(mode="json")
                )
                self.db.staging_records.update_one(
                    {"job_id": job_id, "key": row["source_id"]},
                    {
                        "$set": {
                            "record": record,
                            "source_id": row["source_id"],
                            "schema_version": "1.0",
                            "status": "pending",
                        }
                    },
                    upsert=True,
                )
            self.db.migration_jobs.update_one({"_id": job_id}, {"$set": {"records_processed": len(source)}})
            self.validate(job_id)
        except Exception:
            self.db.migration_jobs.update_one({"_id": job_id}, {"$set": {"status": "failed"}})
            raise
        return public(self.repo.job(job_id))

    def migrate(self, payload: dict, mapper: str = "offline", provider=None) -> dict:
        upload = Upload.model_validate(payload)
        if not upload.synthetic or upload.source_schema not in ["A", "B"]:
            raise ValueError("Only explicitly synthetic, versioned A/B source adapters are supported")
        if mapper not in ["offline", "llm"]:
            raise ValueError("Unknown mapper")
        source = [row.model_dump() for row in upload.records]
        if len({row["source_id"] for row in source}) != len(source):
            raise ValueError("Duplicate source identifiers")
        if any(row["entity"] not in COLLECTIONS for row in source):
            raise ValueError("Unknown entity")
        job_id = digest({"payload": payload, "mapper": mapper, "pipeline_version": PIPELINE_VERSION})[:24]
        previous = self.db.migration_jobs.find_one({"_id": job_id})
        if previous and previous["status"] not in ["failed"]:
            return public(previous)
        if previous:
            lock = self.db.migration_jobs.update_one(
                {"_id": job_id, "status": "failed"}, {"$set": {"status": "running", "error": None}}
            )
            if not lock.modified_count:
                return public(self.repo.job(job_id))
        else:
            try:
                self.db.migration_jobs.insert_one(
                    {
                        "_id": job_id,
                        "status": "running",
                        "mapper": mapper,
                        "pipeline_version": PIPELINE_VERSION,
                        "created_at": datetime.now(timezone.utc),
                        "revision": 0,
                        "source_schema": upload.source_schema,
                        "source_count": len(source),
                        "source_digest": digest(sorted(source, key=lambda row: row["source_id"])),
                    }
                )
            except DuplicateKeyError:
                return public(self.repo.job(job_id))
        try:
            self.repo.audit(job_id, "migration_started", {"records": len(source), "mapper": mapper})
            for row in source:
                self.db.source_records.update_one(
                    {"job_id": job_id, "key": row["source_id"]},
                    {"$setOnInsert": {"source": row, "sha256": digest(row)}},
                    upsert=True,
                )
            provider = provider or (LLMMapper() if mapper == "llm" else None)
            graph = mapping_graph(provider)
            plans = {}
            review = False
            retries = 0
            for entity in sorted({row["entity"] for row in source}):
                rows = [row["data"] for row in source if row["entity"] == entity]
                state = graph.invoke({"entity": entity, "records": rows})
                retries += state["attempts"] - 1
                self.db.schema_mappings.update_one(
                    {"job_id": job_id, "key": entity}, {"$set": {"state": state}}, upsert=True
                )
                if state["status"] != "validated":
                    review = True
                else:
                    plans[entity] = MappingPlan.model_validate(state["plan"])
            if review:
                self.db.migration_jobs.update_one(
                    {"_id": job_id},
                    {"$set": {"status": "mapping_review", "agent_retries": retries, "records_processed": 0}},
                )
                self.repo.audit(job_id, "mapping_review_required", {})
                return public(self.repo.job(job_id))
            # Batches limit memory on the write side; source envelope is bounded by Upload.
            for start in range(0, len(source), 250):
                for row in source[start : start + 250]:
                    record = (
                        MODELS[row["entity"]]
                        .model_validate(transform(row["data"], plans[row["entity"]]))
                        .model_dump(mode="json")
                    )
                    self.db.staging_records.update_one(
                        {"job_id": job_id, "key": row["source_id"]},
                        {
                            "$set": {
                                "record": record,
                                "source_id": row["source_id"],
                                "schema_version": "1.0",
                                "status": "pending",
                            }
                        },
                        upsert=True,
                    )
            self.db.migration_jobs.update_one(
                {"_id": job_id}, {"$set": {"agent_retries": retries, "records_processed": len(source)}}
            )
            self.validate(job_id)
        except Exception as exc:
            self.db.migration_jobs.update_one(
                {"_id": job_id}, {"$set": {"status": "failed", "error": type(exc).__name__}}
            )
            self.repo.audit(job_id, "migration_failed", {"error_type": type(exc).__name__})
            raise
        return public(self.repo.job(job_id))

    def validate(self, job_id: str, records: list[dict] | None = None, persist: bool = True) -> dict:
        if not persist:
            return self._validate(job_id, records, persist=False)
        if records is not None:
            raise ValueError("Candidate records may only be verified without persisting staging status")
        job = self.repo.job(job_id)
        if job["status"] not in ["running", "staged", "verified", "rejected"]:
            raise ValueError("Job is locked, approved, or not ready for verification")
        token = str(uuid4())
        lock = self.db.migration_jobs.update_one(
            {"_id": job_id, "status": job["status"], "revision": job["revision"]},
            {"$set": {"status": "verifying", "verification_token": token}},
        )
        if not lock.modified_count:
            raise ValueError("Concurrent job change")
        try:
            return self._validate(job_id, records, persist=True, verification_token=token)
        except Exception as exc:
            self.db.migration_jobs.update_one(
                {"_id": job_id, "status": "verifying", "verification_token": token},
                {
                    "$set": {"status": "failed", "error": type(exc).__name__},
                    "$unset": {"verification_token": ""},
                },
            )
            raise

    def _validate(
        self,
        job_id: str,
        records: list[dict] | None = None,
        persist: bool = True,
        verification_token: str | None = None,
    ) -> dict:
        source_rows = self.repo.source(job_id)
        source = reference_records(source_rows, self.repo.job(job_id)["source_schema"])
        target = records if records is not None else self.repo.records(job_id)
        findings = [finding.model_dump() for finding in verify(target, source)]
        expected_by_source = {
            row["source_id"]: record for row, record in zip(source_rows, source, strict=True)
        }
        if records is None:
            bindings = [
                (row["key"], row.get("source_id"), row["record"])
                for row in self.db.staging_records.find({"job_id": job_id}).sort("key", 1)
            ]
        else:
            # Candidate snapshots preserve source-row ordering; repairs may not reassign identities.
            bindings = [
                (row["source_id"], row["source_id"], record) for row, record in zip(source_rows, target)
            ]
        for key, declared_source, actual in bindings:
            expected = expected_by_source.get(key)
            if (
                expected is None
                or declared_source != key
                or (actual.get("id"), actual.get("kind")) != (expected["id"], expected["kind"])
            ):
                evidence = {
                    "source_id": key,
                    "declared_source_id": declared_source,
                    "expected_id": expected["id"] if expected else None,
                    "actual_id": actual.get("id"),
                }
                findings.append(
                    Finding(
                        finding_id=digest(["RECONCILIATION_PROVENANCE", evidence])[:16],
                        rule_id="RECONCILIATION_PROVENANCE",
                        affected_records=sorted(
                            {
                                actual.get("id", "<missing>"),
                                expected["id"] if expected else "<unknown-source>",
                            }
                        ),
                        severity="critical",
                        evidence=evidence,
                        expected="Source-row identity and entity preserved in its staging row",
                        actual=str(evidence),
                        remediation="Restore the original source-to-target row binding.",
                    ).model_dump()
                )
        discrepancies = []
        snapshots = []
        for variant in (r for r in source if r["kind"] == "variant"):
            before = build_twin(source, variant["id"])
            try:
                after = build_twin(target, variant["id"])
                differences = compare_twins(before, after)
            except ValueError:
                after, differences = None, [{"path": "/variant", "source": variant["id"], "target": None}]
            discrepancies.extend(differences)
            snapshots.append(
                {"key": variant["id"], "source": before, "target": after, "differences": differences}
            )
        result = {
            "findings": findings,
            "twin_differences": discrepancies,
            "passed": not findings and not discrepancies,
        }
        if persist:
            job = self.repo.job(job_id)
            if job["status"] in ["approved", "promoting", "repairing"]:
                raise ValueError("Cannot replace validation of a locked or approved job")
            self.db.validation_results.insert_one({"job_id": job_id, "revision": job["revision"], **result})
            for snapshot in snapshots:
                self.db.twin_snapshots.update_one(
                    {"job_id": job_id, "key": snapshot["key"]}, {"$set": snapshot}, upsert=True
                )
            affected = {identifier for finding in findings for identifier in finding["affected_records"]}
            for row in self.db.staging_records.find({"job_id": job_id}):
                status = "rejected" if row["record"]["id"] in affected else "verified"
                self.db.staging_records.update_one({"_id": row["_id"]}, {"$set": {"status": status}})
            committed = self.db.migration_jobs.update_one(
                {"_id": job_id, "status": "verifying", "verification_token": verification_token},
                {
                    "$set": {
                        "status": "verified" if result["passed"] else "rejected",
                        "validation": result,
                        "staging_digest": digest(target),
                        "verified_records": len(target) - sum(r["id"] in affected for r in target),
                        "rejected_records": sum(r["id"] in affected for r in target),
                    },
                    "$unset": {"verification_token": ""},
                },
            )
            if not committed.modified_count:
                raise ValueError("Verification lock was lost; result was not committed")
            self.repo.audit(
                job_id,
                "verification_completed",
                {"findings": len(findings), "twin_differences": len(discrepancies)},
            )
        return result

    def promote(self, job_id: str, actor: str) -> dict:
        if not actor.strip():
            raise ValueError("Human approver is required")
        job = self.repo.job(job_id)
        if job["status"] == "approved":
            self.repo.approved_records(job_id)
            return public(job)
        if job["status"] != "verified":
            raise ValueError("Only verified jobs can be promoted")
        records = self.repo.records(job_id)
        if digest(records) != job["staging_digest"] or not self.validate(job_id, persist=False)["passed"]:
            raise ValueError("Staging changed or failed revalidation")
        token = str(uuid4())
        lock = self.db.migration_jobs.update_one(
            {"_id": job_id, "status": "verified", "revision": job["revision"]},
            {"$set": {"status": "promoting", "promotion_token": token}},
        )
        if not lock.modified_count:
            raise ValueError("Concurrent job change")
        try:
            for record in records:
                self.db[COLLECTIONS[record["kind"]]].update_one(
                    {"job_id": job_id, "id": record["id"]}, {"$set": {"record": record}}, upsert=True
                )
            copied = self.repo.publication_records(job_id)
            if len(copied) != len(records) or publication_digest(copied) != publication_digest(records):
                raise ValueError("Published copy does not match verified staging")
            self.repo.audit(job_id, "promotion_authorized", {"actor": actor, "digest": digest(records)})
            committed = self.db.migration_jobs.update_one(
                {"_id": job_id, "status": "promoting", "promotion_token": token, "revision": job["revision"]},
                {
                    "$set": {
                        "status": "approved",
                        "approved_by": actor,
                        "approved_count": len(records),
                        "approved_digest": publication_digest(records),
                    },
                    "$unset": {"promotion_token": ""},
                },
            )
            if not committed.modified_count:
                raise ValueError("Promotion lock was lost; publication was not committed")
        except Exception:
            self.db.migration_jobs.update_one(
                {"_id": job_id, "status": "promoting", "promotion_token": token},
                {"$set": {"status": "verified"}, "$unset": {"promotion_token": ""}},
            )
            raise
        return public(self.repo.job(job_id))

    def propose_repair(self, job_id: str, actor: str = "offline-source-restoration", provider=None) -> dict:
        job = self.repo.job(job_id)
        if job["status"] not in ["rejected", "verified"]:
            raise ValueError("Repair requires an unapproved staged job")
        before = self.repo.records(job_id)
        from app.resolution import propose

        source = reference_records(self.repo.source(job_id), job["source_schema"])
        before_validation = self.validate(job_id, persist=False)
        after, agent_plan = propose(before, source, before_validation, provider)
        validation = self.validate(job_id, after, persist=False)
        proposal = {
            "_id": str(uuid4()),
            "job_id": job_id,
            "status": "pending",
            "proposed_by": actor,
            "strategy": "restore_authoritative_source",
            "before": before,
            "after": after,
            "before_digest": digest(before),
            "job_revision": job["revision"],
            "before_validation": before_validation,
            "agent_plan": agent_plan,
            "validation": validation,
            "constraints": "Versioned source adapter, independent rules, source/target twin equality",
        }
        self.db.repair_proposals.insert_one(copy.deepcopy(proposal))
        self.repo.audit(job_id, "repair_proposed", {"proposal_id": proposal["_id"], "validation": validation})
        return public(proposal)

    def decide_repair(self, proposal_id: str, approve: bool, actor: str) -> dict:
        if not actor.strip():
            raise ValueError("Human reviewer required")
        proposal = self.db.repair_proposals.find_one({"_id": proposal_id})
        if proposal is None:
            raise KeyError("Unknown repair proposal")
        if proposal["status"] != "pending":
            raise ValueError("Proposal has already been decided")
        job_id = proposal["job_id"]
        if approve and proposal.get("agent_plan", {}).get("blocked"):
            raise ValueError("Unresolved engineering decision requires a new proposal")
        if not approve:
            self.db.repair_proposals.update_one(
                {"_id": proposal_id, "status": "pending"}, {"$set": {"status": "rejected", "reviewer": actor}}
            )
            self.repo.audit(job_id, "repair_rejected", {"proposal_id": proposal_id, "actor": actor})
            return public(self.db.repair_proposals.find_one({"_id": proposal_id}))
        if digest(self.repo.records(job_id)) != proposal["before_digest"]:
            raise ValueError("Stale repair proposal")
        if not self.validate(job_id, proposal["after"], persist=False)["passed"]:
            raise ValueError("Candidate repair fails deterministic checks")
        lock = self.db.migration_jobs.update_one(
            {
                "_id": job_id,
                "revision": proposal["job_revision"],
                "status": {"$in": ["verified", "rejected"]},
            },
            {"$set": {"status": "repairing"}, "$inc": {"revision": 1}},
        )
        if not lock.modified_count:
            raise ValueError("Concurrent change or approved job")
        source = self.repo.source(job_id)
        try:
            # Source identity and row count are preserved; no silent deletion or invented rows.
            for row, record in zip(source, proposal["after"], strict=True):
                self.db.staging_records.update_one(
                    {"job_id": job_id, "key": row["source_id"]},
                    {"$set": {"record": record, "source_id": row["source_id"], "status": "pending"}},
                )
            self.db.migration_jobs.update_one({"_id": job_id}, {"$set": {"status": "staged"}})
            self.validate(job_id)
            self.db.repair_proposals.update_one(
                {"_id": proposal_id}, {"$set": {"status": "approved", "reviewer": actor}}
            )
            self.repo.audit(job_id, "repair_approved", {"actor": actor, "proposal_id": proposal_id})
        except Exception:
            self.db.migration_jobs.update_one({"_id": job_id}, {"$set": {"status": "failed"}})
            raise
        return public(self.db.repair_proposals.find_one({"_id": proposal_id}))

    def run_simulation(
        self,
        job_id: str,
        variant_id: str,
        scenario: str = "valid",
        ticks: int = 5,
        fault_at: int | None = None,
    ) -> dict:
        self.repo.job(job_id)
        staged = self.repo.records(job_id)
        if not any(r["kind"] == "variant" and r["id"] == variant_id for r in staged):
            raise KeyError("Unknown vehicle variant")
        records = scenario_records(staged, variant_id, scenario)
        twin = build_twin(records, variant_id)
        result = simulate(twin, ticks, fault_at)
        result.update(
            {
                "_id": str(uuid4()),
                "job_id": job_id,
                "variant_id": variant_id,
                "scenario": scenario,
                "engineering_findings": [f.model_dump() for f in verify(records)],
            }
        )
        self.db.simulation_runs.insert_one(copy.deepcopy(result))
        self.repo.audit(job_id, "simulation_completed", {"run_id": result["_id"], "scenario": scenario})
        return public(result)

    def report(self, job_id: str) -> dict:
        return public(
            {
                "job": self.repo.job(job_id),
                "source": self.repo.source(job_id),
                "staging": list(self.db.staging_records.find({"job_id": job_id})),
                "mappings": list(self.db.schema_mappings.find({"job_id": job_id})),
                "twins": list(self.db.twin_snapshots.find({"job_id": job_id})),
                "simulations": list(self.db.simulation_runs.find({"job_id": job_id})),
                "repairs": list(self.db.repair_proposals.find({"job_id": job_id})),
                "audit": list(self.db.audit_events.find({"job_id": job_id})),
            }
        )
