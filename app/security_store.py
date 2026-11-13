
"""Shared reviewer grants, quotas and fail-closed execution locks in MongoDB."""

import hashlib
import json
import logging
import os
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from fastapi import HTTPException
from pymongo import ReadPreference, ReturnDocument
from pymongo.errors import DuplicateKeyError
from pymongo.write_concern import WriteConcern

from app.repository import Repository

logger = logging.getLogger("autoplm.security")

POLICY = {
    "requests": 60,
    "executions": 6,
    "decisions": 10,
    "llm_minute": 1,
    "llm_day": 10,
    "slots": 2,
}


def identity_key(issuer: str, subject: str) -> str:
    return hashlib.sha256(
        json.dumps([issuer, subject], separators=(",", ":")).encode()
    ).hexdigest()


def require_secure_database(uri: str | None = None) -> None:
    uri = uri if uri is not None else os.environ.get("MONGODB_URI", "")
    parsed = urlsplit(uri)
    options = {
        k.lower(): [item.lower() for item in v]
        for k, v in parse_qs(parsed.query).items()
    }

    if (
        parsed.scheme not in ("mongodb", "mongodb+srv")
        or not parsed.username
        or not parsed.password
        or not os.environ.get("MONGODB_DATABASE")
        or (parsed.scheme == "mongodb" and options.get("tls") != ["true"])
        or any("false" in options.get(k, []) for k in ("tls", "ssl"))
        or "0" in options.get("w", [])
        or any(
            "true" in options.get(k, [])
            for k in (
                "tlsinsecure",
                "tlsallowinvalidcertificates",
                "tlsallowinvalidhostnames",
            )
        )
    ):
        raise ValueError(
            "Authenticated verified-TLS MongoDB configuration required"
        )


class SecurityStore:
    def __init__(self, repo: Repository):
        self.repo = repo
        self.db = repo.db.with_options(
            read_preference=ReadPreference.PRIMARY,
            write_concern=WriteConcern("majority"),
        )

    def initialize(self) -> None:
        """Trusted operator setup only; not an HTTP provisioning endpoint."""

        self.db.reviewer_grants.create_index(
            [("issuer", 1), ("subject", 1)],
            unique=True,
        )

        self.db.security_quotas.create_index(
            "expires_at",
            expireAfterSeconds=0,
        )

        # Insert the initial policy without requiring UPDATE permission.
        try:
            self.db.security_policy.insert_one({
                "_id": "v1",
                **POLICY,
            })
        except DuplicateKeyError:
            # Preserve an existing policy; startup() validates it below.
            pass

        for index in range(POLICY["slots"]):
            self.db.security_locks.update_one(
                {"_id": f"execution:{index}"},
                {"$setOnInsert": {"owner": None}},
                upsert=True,
            )

        self.startup()

    def startup(self) -> None:
        self.db.command("ping")

        policy = self.db.security_policy.find_one({"_id": "v1"}) or {}

        if any(policy.get(k) != value for k, value in POLICY.items()):
            raise ValueError(
                "Shared security policy is not provisioned or differs"
            )

        indexes = list(
            self.db.security_quotas.index_information().values()
        )
        grants = list(
            self.db.reviewer_grants.index_information().values()
        )

        if (
            not any(
                i.get("key") == [("expires_at", 1)]
                and i.get("expireAfterSeconds") == 0
                for i in indexes
            )
            or not any(
                i.get("key") == [("issuer", 1), ("subject", 1)]
                and i.get("unique")
                for i in grants
            )
            or self.db.security_locks.count_documents({
                "_id": {"$in": ["execution:0", "execution:1"]}
            }) != 2
        ):
            raise ValueError(
                "Shared security indexes/slots are not provisioned"
            )

        self.db.reviewer_grants.find_one(
            {"_id": "startup-read-check"}
        )
        self.quota("startup", "requests")

    def is_reviewer(self, issuer: str, subject: str) -> bool:
        grant = self.db.reviewer_grants.find_one(
            {"_id": identity_key(issuer, subject)}
        )

        return bool(
            grant
            and grant.get("issuer") == issuer
            and grant.get("subject") == subject
            and grant.get("enabled") is True
            and grant.get("role") == "engineering_reviewer"
        )

    def set_reviewer(
        self,
        issuer: str,
        subject: str,
        enabled: bool,
        operator: str,
        reason: str,
    ) -> None:
        if (
            not subject.strip()
            or subject != subject.strip()
            or len(subject) > 120
            or subject.endswith("@clients")
        ):
            raise ValueError("Invalid reviewer subject")

        if not operator.strip() or not reason.strip():
            raise ValueError("Operator and reason required")

        event_id = str(uuid4())

        event = {
            "event_id": event_id,
            "enabled": enabled,
            "operator": operator,
            "reason": reason,
            "created_at": datetime.now(timezone.utc),
        }

        self.db.reviewer_grants.update_one(
            {"_id": identity_key(issuer, subject)},
            {
                "$set": {
                    "issuer": issuer,
                    "subject": subject,
                    "role": "engineering_reviewer",
                    "enabled": enabled,
                },
                "$push": {"history": event},
            },
            upsert=True,
        )

        self.repo.audit(
            "authorization",
            "reviewer_grant_changed",
            {
                "issuer": issuer,
                "subject": subject,
                **event,
            },
            event_id=event_id,
        )

    def quota(self, identity: str, group: str) -> None:
        window = 86400 if group == "llm_day" else 60
        now = int(time.time())
        bucket = now // window
        identifier = f"{identity}:{group}:{bucket}"

        try:
            self.db.security_quotas.find_one_and_update(
                {"_id": identifier, "count": {"$lt": POLICY[group]}},
                {
                    "$inc": {"count": 1},
                    "$setOnInsert": {
                        "expires_at": (
                            datetime.fromtimestamp(
                                (bucket + 1) * window,
                                timezone.utc,
                            )
                            + timedelta(days=1)
                        )
                    },
                },
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
        except DuplicateKeyError:
            logger.warning("security_event=reviewer_quota_exceeded")
            raise HTTPException(
                429,
                "Reviewer request budget exceeded",
                headers={
                    "Retry-After": str((bucket + 1) * window - now)
                },
            ) from None

    @contextmanager
    def lock(self, resource: str | None = None):
        """No automatic expiry: a crashed worker blocks capacity until verified operator recovery."""

        owner = str(uuid4())

        identifiers = (
            ["decision:" + hashlib.sha256(resource.encode()).hexdigest()]
            if resource
            else [f"execution:{i}" for i in range(POLICY["slots"])]
        )

        acquired = None

        for identifier in identifiers:
            try:
                result = self.db.security_locks.find_one_and_update(
                    {"_id": identifier, "owner": None},
                    {"$set": {"owner": owner}},
                    upsert=True,
                    return_document=ReturnDocument.AFTER,
                )
            except DuplicateKeyError:
                continue

            if result:
                acquired = identifier
                break

        if acquired is None:
            logger.warning(
                "security_event=engineering_capacity_exceeded"
            )
            raise HTTPException(
                429,
                "Engineering execution is busy",
                headers={"Retry-After": "30"},
            )

        try:
            yield
        finally:
            self.db.security_locks.update_one(
                {"_id": acquired, "owner": owner},
                {"$set": {"owner": None}},
            )


@lru_cache(maxsize=1)
def get_security_store() -> SecurityStore:
    require_secure_database()
    return SecurityStore(Repository.connect())
