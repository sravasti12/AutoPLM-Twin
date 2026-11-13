"""Startup failures remain fatal and reveal only constant stages and exception classes."""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pymongo.errors import OperationFailure, ServerSelectionTimeoutError

from app.api import app
from app.oidc_auth import IdentityUnavailable
from app.security_store import get_security_store
from tests.unit.test_oidc_auth import oidc as oidc_fixture
from tests.unit.test_oidc_auth import signing_keys as signing_keys_fixture

oidc = oidc_fixture
signing_keys = signing_keys_fixture
SECRET = "never-log-startup-credential"
GENERIC = "Non-local startup blocked: production security configuration failed validation"


def fail(exc):
    def operation(*args, **kwargs):
        raise exc
    return operation


@pytest.mark.parametrize("failure,stage,exception_class", [
    ("environment", "environment_validation", "ValueError"),
    ("config", "oidc_configuration_validation", "ValueError"),
    ("discovery", "oidc_discovery_jwks_initialization", "IdentityUnavailable"),
    ("jwks", "oidc_discovery_jwks_initialization", "IdentityUnavailable"),
    ("uri", "mongodb_secure_uri_validation", "ValueError"),
    ("connectivity", "mongodb_connectivity", "ServerSelectionTimeoutError"),
    ("repository_indexes", "mongodb_repository_indexes", "OperationFailure"),
    ("policy", "shared_security_policy_validation", "ValueError"),
    ("indexes", "security_index_lock_validation", "OperationFailure"),
    ("locks", "security_index_lock_validation", "ValueError"),
    ("quota", "startup_quota_validation", "HTTPException"),
])
def test_failed_stage_is_logged_without_secrets_and_startup_stays_blocked(
    oidc, monkeypatch, caplog, failure, stage, exception_class,
):
    _, store, _, _, documents, _ = oidc
    if failure == "environment":
        monkeypatch.setenv("AUTOPLM_ENVIRONMENT", SECRET)
    elif failure == "config":
        monkeypatch.setattr("app.api.get_validator", fail(ValueError(SECRET)))
    elif failure == "discovery":
        monkeypatch.setattr("app.oidc_auth.fetch_document", fail(IdentityUnavailable(SECRET)))
    elif failure == "jwks":
        documents["keys"] = [{"kty": "RSA", "kid": SECRET}]
    elif failure in {"uri", "connectivity", "repository_indexes"}:
        get_security_store.cache_clear()
        monkeypatch.setattr("app.api.get_security_store", get_security_store)
        monkeypatch.setenv("MONGODB_DATABASE", "autoplm_twin")
        monkeypatch.setenv("MONGODB_URI", f"mongodb://user:{SECRET}@example.invalid/?tls=true")
        if failure == "uri":
            monkeypatch.setenv("MONGODB_URI", f"mongodb://user:{SECRET}@example.invalid/?tls=false")
        elif failure == "connectivity":
            monkeypatch.setattr("app.repository.MongoClient", fail(ServerSelectionTimeoutError(SECRET)))
        else:
            mongo = MagicMock()
            mongo.__getitem__.return_value.__getitem__.return_value.create_index.side_effect = (
                OperationFailure(SECRET, 13)
            )
            monkeypatch.setattr("app.repository.MongoClient", lambda *args, **kwargs: mongo)
    elif failure == "policy":
        store.db.security_policy.update_one({"_id": "v1"}, {"$set": {"slots": SECRET}})
    elif failure == "indexes":
        monkeypatch.setattr(store.db.security_quotas, "index_information", fail(OperationFailure(SECRET, 13)))
    elif failure == "locks":
        monkeypatch.setattr(store.db.security_locks, "count_documents", lambda *args, **kwargs: 0)
    else:
        monkeypatch.setattr(store, "quota", fail(HTTPException(429, SECRET)))
    caplog.clear()
    try:
        with pytest.raises(RuntimeError) as error:
            with TestClient(app):
                pytest.fail("A failed security check must not start the application")
        assert str(error.value) == GENERIC
        records = [record for record in caplog.records
                   if getattr(record, "security_event", None) == "startup_failed"]
        assert len(records) == 1
        record = records[0]
        assert record.name == "autoplm.security"
        assert record.stage == stage and record.exception_class == exception_class
        assert f"stage={stage}" in record.getMessage()
        assert record.exc_info is None and record.stack_info is None
        assert SECRET not in caplog.text
        assert SECRET not in repr(record.__dict__)
    finally:
        get_security_store.cache_clear()


def test_valid_startup_has_no_failure_diagnostic_or_provisioning(oidc, monkeypatch, caplog):
    _, store, _, _, _, _ = oidc
    monkeypatch.setattr(store, "initialize", fail(AssertionError("Startup must not provision")))
    caplog.clear()
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
    assert not [r for r in caplog.records if getattr(r, "security_event", None) == "startup_failed"]
