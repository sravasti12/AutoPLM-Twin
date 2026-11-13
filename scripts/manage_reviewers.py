
"""Trusted-host provisioning; never an HTTP role-management endpoint. No secrets on argv."""

import argparse
import os
from pathlib import Path

from fastapi import HTTPException
from pymongo import MongoClient
from pymongo.errors import OperationFailure, PyMongoError

from app.oidc_auth import OIDCConfig
from app.repository import Repository
from app.security_store import SecurityStore, require_secure_database


def failure_diagnostic(exc: Exception) -> str:
    """Allowlisted metadata only: never exception messages, MongoDB details or stack source."""
    category = "unexpected"
    code = "none"

    if isinstance(exc, OperationFailure):
        category = (
            "permission_denied" if exc.code == 13
            else "database_authentication" if exc.code == 18
            else "database"
        )
        code = str(exc.code) if type(exc.code) is int else "none"
    elif isinstance(exc, PyMongoError):
        category = "database_connectivity_or_operation"
    elif isinstance(exc, HTTPException):
        category = (
            "quota_exhausted" if exc.status_code == 429
            else "security_check"
        )
        code = str(exc.status_code) if type(exc.status_code) is int else "none"
    elif isinstance(exc, ValueError):
        category = "configuration_or_security_metadata"

    location = "unavailable"
    root = Path(__file__).resolve().parents[1]

    allowed = {
        "scripts/manage_reviewers.py",
        "app/oidc_auth.py",
        "app/security_store.py",
        "app/repository.py",
    }

    frame = exc.__traceback__

    while frame is not None:
        try:
            source = (
                Path(frame.tb_frame.f_code.co_filename)
                .resolve()
                .relative_to(root)
                .as_posix()
            )
        except ValueError:
            source = ""

        if source in allowed:
            location = f"{source}:{frame.tb_lineno}"

        frame = frame.tb_next

    missing = [
        name
        for name in (
            "AUTOPLM_PROVISIONING_MONGODB_URI",
            "MONGODB_DATABASE",
            "AUTOPLM_OIDC_ISSUER",
            "AUTOPLM_OIDC_AUDIENCE",
            "AUTOPLM_OIDC_CLIENT_ID",
        )
        if not os.environ.get(name)
    ]

    return (
        f"Security operation failed: category={category} code={code} "
        f"location={location} "
        f"missing_settings={','.join(missing) or 'none'}. "
        "No secrets displayed. Earlier initialization steps may have completed; "
        "do not reset existing state."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "action",
        choices=("initialize", "grant", "revoke", "recover-lock"),
    )
    parser.add_argument("--subject")
    parser.add_argument("--operator", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--lock-id")
    parser.add_argument("--owner")
    parser.add_argument(
        "--confirm-workers-stopped",
        action="store_true",
    )

    args = parser.parse_args()

    # Separate privileged identity from the API runtime connection.
    uri = os.environ.get("AUTOPLM_PROVISIONING_MONGODB_URI")
    database = os.environ.get("MONGODB_DATABASE")

    if not uri or not database:
        parser.error(
            "Protected provisioning URI and explicit database are required"
        )

    require_secure_database(uri)

    if not args.operator.strip() or not args.reason.strip():
        parser.error("Nonempty operator and reason are required")

    client: MongoClient

    with MongoClient(
        uri,
        serverSelectionTimeoutMS=3000,
        tz_aware=True,
        maxPoolSize=5,
        w="majority",
    ) as client:

        store = SecurityStore(Repository(client[database]))

        if args.action == "initialize":
            # Initial provisioning does not require Auth0 configuration.
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
            # OIDC is required when identifying reviewers.
            config = OIDCConfig.from_environment()

            if not args.subject:
                parser.error("Subject is required")

            store.set_reviewer(
                config.issuer,
                args.subject,
                args.action == "grant",
                args.operator,
                args.reason,
            )

        else:
            # Lock recovery is an operator-only operation.
            if (
                not args.confirm_workers_stopped
                or not args.lock_id
                or not args.owner
            ):
                parser.error(
                    "Verified stopped workers, lock ID and exact owner are required"
                )

            event = {
                "operator": args.operator,
                "reason": args.reason,
                "owner": args.owner,
            }

            result = store.db.security_locks.update_one(
                {"_id": args.lock_id, "owner": args.owner},
                {
                    "$set": {"owner": None},
                    "$push": {"recovery": event},
                },
            )

            if result.modified_count != 1:
                parser.error(
                    "Lock owner changed or lock does not exist"
                )

            store.repo.audit(
                "authorization",
                "security_lock_recovered",
                event,
            )

    print(
        "Security operation completed; no credentials displayed."
    )


def run() -> None:
    try:
        main()
    except Exception as exc:
        raise SystemExit(failure_diagnostic(exc)) from None


if __name__ == "__main__":
    run()
