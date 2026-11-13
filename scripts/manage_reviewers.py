"""Trusted-host provisioning; never an HTTP role-management endpoint. No secrets on argv."""

import argparse
import os

from pymongo import MongoClient

from app.oidc_auth import OIDCConfig
from app.repository import Repository
from app.security_store import SecurityStore, require_secure_database


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("initialize", "grant", "revoke", "recover-lock"))
    parser.add_argument("--subject")
    parser.add_argument("--operator", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--lock-id")
    parser.add_argument("--owner")
    parser.add_argument("--confirm-workers-stopped", action="store_true")
    args = parser.parse_args()
    config = OIDCConfig.from_environment()
    # Separate privileged identity from the API runtime connection.
    uri = os.environ.get("AUTOPLM_PROVISIONING_MONGODB_URI")
    database = os.environ.get("MONGODB_DATABASE")
    if not uri or not database:
        parser.error("Protected provisioning URI and explicit database are required")
    require_secure_database(uri)
    if not args.operator.strip() or not args.reason.strip():
        parser.error("Nonempty operator and reason are required")
    client: MongoClient
    with MongoClient(
        uri, serverSelectionTimeoutMS=3000, tz_aware=True, maxPoolSize=5, w="majority"
    ) as client:
        store = SecurityStore(Repository(client[database]))
        if args.action == "initialize":
            store.initialize()
            store.repo.audit(
                "authorization",
                "security_initialized",
                {
                    "operator": args.operator,
                    "reason": args.reason,
                },
            )
        elif args.action in ("grant", "revoke"):
            if not args.subject:
                parser.error("Subject is required")
            store.set_reviewer(
                config.issuer, args.subject, args.action == "grant", args.operator, args.reason
            )
        else:
            if not args.confirm_workers_stopped or not args.lock_id or not args.owner:
                parser.error("Verified stopped workers, lock ID and exact owner are required")
            event = {"operator": args.operator, "reason": args.reason, "owner": args.owner}
            result = store.db.security_locks.update_one(
                {"_id": args.lock_id, "owner": args.owner},
                {"$set": {"owner": None}, "$push": {"recovery": event}},
            )
            if result.modified_count != 1:
                parser.error("Lock owner changed or lock does not exist")
            store.repo.audit("authorization", "security_lock_recovered", event)
    print("Security operation completed; no credentials displayed.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit(
            "Security operation failed. Inspect protected operator diagnostics; no secrets displayed."
        ) from None
