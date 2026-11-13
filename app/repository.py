"""MongoDB repositories. Append-only events and manifest-based atomic publication."""

import hashlib
import json
import os
from datetime import datetime, timezone
from uuid import uuid4

from bson import ObjectId
from pymongo import ASCENDING, MongoClient

from app.startup_diagnostics import startup_stage

COLLECTIONS = {
    "hardware": "ecu_hardware",
    "software": "ecu_software",
    "platform": "vehicle_platforms",
    "variant": "vehicle_variants",
    "bom": "engineering_boms",
    "change": "engineering_changes",
    "mechanical_part": "mechanical_parts",
    "assembly": "assemblies",
}


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def publication_digest(records: list[dict]) -> str:
    return digest(sorted(records, key=lambda record: (record["kind"], record["id"])))


class Repository:
    def __init__(self, db):
        self.db = db
        for name in ["source_records", "staging_records", "schema_mappings", "twin_snapshots"]:
            db[name].create_index([("job_id", ASCENDING), ("key", ASCENDING)], unique=True)
        for name in COLLECTIONS.values():
            db[name].create_index([("job_id", ASCENDING), ("id", ASCENDING)], unique=True)
        db.audit_events.create_index([("job_id", ASCENDING), ("created_at", ASCENDING)])
        db.migration_jobs.create_index("created_at")
        db.validation_results.create_index("job_id")
        db.simulation_runs.create_index("job_id")
        db.repair_proposals.create_index("job_id")
        db.investigation_reports.create_index([("review_status", ASCENDING), ("created_at", ASCENDING)])

    @classmethod
    def connect(cls):
        with startup_stage("mongodb_connectivity"):
            client = MongoClient(
                os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
                serverSelectionTimeoutMS=3000,
                tz_aware=True,
                maxPoolSize=10,
                w="majority",
            )
            client.admin.command("ping")
        with startup_stage("mongodb_repository_indexes"):
            return cls(client[os.getenv("MONGODB_DATABASE", "autoplm_twin")])

    def audit(self, job_id: str, action: str, details: dict, *, event_id: str | None = None):
        self.db.audit_events.insert_one(
            {
                "_id": event_id or str(uuid4()),
                "job_id": job_id,
                "action": action,
                "details": details,
                "created_at": datetime.now(timezone.utc),
            }
        )

    def job(self, job_id: str) -> dict:
        job = self.db.migration_jobs.find_one({"_id": job_id})
        if job is None:
            raise KeyError("Unknown migration job")
        return job

    def records(self, job_id: str) -> list[dict]:
        return [r["record"] for r in self.db.staging_records.find({"job_id": job_id}).sort("key", 1)]

    def source(self, job_id: str) -> list[dict]:
        rows = list(self.db.source_records.find({"job_id": job_id}).sort("key", 1))
        for row in rows:
            if row["key"] != row["source"].get("source_id") or row.get("sha256") != digest(row["source"]):
                raise ValueError("Source provenance or content digest mismatch")
        source = [row["source"] for row in rows]
        job = self.job(job_id)
        if "source_digest" in job and (
            job["source_count"] != len(source) or job["source_digest"] != digest(source)
        ):
            raise ValueError("Source snapshot is incomplete or has changed")
        return source

    def publication_records(self, job_id: str) -> list[dict]:
        records = []
        for kind, collection in COLLECTIONS.items():
            for row in self.db[collection].find({"job_id": job_id}):
                record = row["record"]
                if row["id"] != record.get("id") or record.get("kind") != kind:
                    raise ValueError("Published record identity does not match its collection")
                records.append(record)
        return records

    def approved_records(self, job_id: str) -> list[dict]:
        # Partial copies cannot be consumed until a single-document manifest is committed.
        job = self.job(job_id)
        if job["status"] != "approved":
            raise ValueError("Job has no committed engineering manifest")
        self.source(job_id)
        records = self.publication_records(job_id)
        if job.get("approved_count") != len(records) or job.get("approved_digest") != publication_digest(
            records
        ):
            raise ValueError("Approved publication is incomplete or has changed")
        return records


def public(value):
    if isinstance(value, dict):
        return {str(k): public(v) for k, v in value.items()}
    if isinstance(value, list):
        return [public(v) for v in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, ObjectId):
        return str(value)
    return value
