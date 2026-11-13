"""Provisioning failures are diagnosable without disclosing secret-bearing exceptions."""

import copy
from typing import Any
from unittest.mock import patch

import mongomock
import pytest
from fastapi import HTTPException
from pymongo.errors import OperationFailure, ServerSelectionTimeoutError

from app.repository import Repository
from app.security_store import POLICY, SecurityStore
from scripts.manage_reviewers import failure_diagnostic, run


@pytest.mark.parametrize("exc,category,code", [
    (OperationFailure("secret connection detail", 13), "permission_denied", "13"),
    (OperationFailure("secret connection detail", 18), "database_authentication", "18"),
    (OperationFailure("secret connection detail", 85), "database", "85"),
    (ServerSelectionTimeoutError("secret connection detail"), "database_connectivity_or_operation", "none"),
    (HTTPException(429, "secret connection detail"), "quota_exhausted", "429"),
    (ValueError("secret connection detail"), "configuration_or_security_metadata", "none"),
])
def test_diagnostics_never_echo_exception_messages_or_details(exc, category, code) -> None:
    text = failure_diagnostic(exc)
    assert f"category={category}" in text and f"code={code}" in text
    assert "secret connection detail" not in text



def test_initialize_does_not_require_oidc_configuration(monkeypatch) -> None:
    monkeypatch.setenv(
        "AUTOPLM_PROVISIONING_MONGODB_URI",
        "mongodb+srv://operator:fake-password@cluster0.example.mongodb.net/",
    )
    monkeypatch.setenv("MONGODB_DATABASE", "autoplm_twin")

    for name in (
        "AUTOPLM_OIDC_ISSUER",
        "AUTOPLM_OIDC_AUDIENCE",
        "AUTOPLM_OIDC_CLIENT_ID",
    ):
        monkeypatch.delenv(name, raising=False)

    with (
        patch(
            "sys.argv",
            [
                "manage_reviewers",
                "initialize",
                "--operator",
                "test",
                "--reason",
                "test initialization",
            ],
        ),
        patch("scripts.manage_reviewers.MongoClient") as client,
        patch("scripts.manage_reviewers.SecurityStore") as store_class,
        patch(
            "scripts.manage_reviewers.OIDCConfig.from_environment",
            side_effect=AssertionError("Initialization must not load OIDC"),
        ) as oidc,
    ):
        run()

    client.assert_called_once()
    store_class.return_value.initialize.assert_called_once()
    store_class.return_value.repo.audit.assert_called_once()
    oidc.assert_not_called()



def test_cli_redacts_permission_failure_and_keeps_nonzero_exit() -> None:
    with patch("scripts.manage_reviewers.main", side_effect=OperationFailure("secret connection detail", 13)):
        with pytest.raises(SystemExit) as error:
            run()
    assert "permission_denied" in str(error.value)
    assert "secret connection detail" not in str(error.value)


def test_initialize_requires_no_policy_update_and_preserves_existing_state() -> None:
    db: Any = mongomock.MongoClient().autoplm_twin
    with patch.object(db, "with_options", return_value=db):
        store = SecurityStore(Repository(db))
    with patch.object(
        db.security_policy, "update_one", side_effect=AssertionError("Policy update forbidden")
    ):
        store.initialize()
        db.security_locks.update_one({"_id": "execution:0"}, {"$set": {"owner": "existing-worker"}})
        policy = copy.deepcopy(db.security_policy.find_one({"_id": "v1"}))
        store.initialize()
    assert db.security_policy.find_one({"_id": "v1"}) == policy == {"_id": "v1", **POLICY}
    assert db.security_locks.find_one({"_id": "execution:0"})["owner"] == "existing-worker"


def test_initialize_does_not_overwrite_incompatible_policy() -> None:
    db: Any = mongomock.MongoClient().autoplm_twin
    original = {"_id": "v1", **POLICY, "slots": 999}
    db.security_policy.insert_one(copy.deepcopy(original))
    with patch.object(db, "with_options", return_value=db):
        store = SecurityStore(Repository(db))
    with pytest.raises(ValueError, match="policy is not provisioned or differs"):
        store.initialize()
    assert db.security_policy.find_one({"_id": "v1"}) == original
