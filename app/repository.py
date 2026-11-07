"""MongoDB repositories. Append-only events and manifest-based atomic publication."""

import hashlib
import json
import os
from datetime import datetime, timezone
from uuid import uuid4

from bson import ObjectId
from pymongo import ASCENDING, MongoClient

COLLECTIONS = {
    "hardware": "ecu_hardware",
    "software": "ecu_software",
    "platform": "vehicle_platforms",
    "variant": "vehicle_variants",
    "bom": "engineering_boms",
    "change": "engineering_changes",
}


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


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

    @classmethod
    def connect(cls):
        client = MongoClient(
            os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
            serverSelectionTimeoutMS=3000,
            tz_aware=True,
        )
        client.admin.command("ping")
        return cls(client[os.getenv("MONGODB_DATABASE", "autoplm_twin")])

    def audit(self, job_id: str, action: str, details: dict):
        self.db.audit_events.insert_one(
            {
                "_id": str(uuid4()),
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
        return [r["source"] for r in self.db.source_records.find({"job_id": job_id}).sort("key", 1)]

    def approved_records(self, job_id: str) -> list[dict]:
        # Partial copies cannot be consumed until a single-document manifest is committed.
        if self.job(job_id)["status"] != "approved":
            raise ValueError("Job has no committed engineering manifest")
        return [
            doc["record"] for name in COLLECTIONS.values() for doc in self.db[name].find({"job_id": job_id})
        ]


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
