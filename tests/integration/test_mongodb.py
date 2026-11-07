"""Real MongoDB only, with an isolated random database. No production DB variables used."""

import os
from uuid import uuid4

import pytest
from pymongo import MongoClient

from app.repository import Repository
from app.service import MigrationService


@pytest.mark.integration
def test_real_mongodb_migration(generated):
    uri = os.getenv("AUTOPLM_TEST_MONGODB_URI")
    if not uri:
        pytest.skip("Set AUTOPLM_TEST_MONGODB_URI explicitly to run real MongoDB integration")
    client = MongoClient(uri, serverSelectionTimeoutMS=3000)
    client.admin.command("ping")
    name = f"autoplm_test_{uuid4().hex}"
    try:
        service = MigrationService(Repository(client[name]))
        first = service.migrate(generated[0])
        assert first["status"] == "verified"
        assert service.migrate(generated[0])["_id"] == first["_id"]
        assert service.promote(first["_id"], "integration-test")["status"] == "approved"
        assert len(service.repo.approved_records(first["_id"])) == len(generated[0]["records"])
    finally:
        assert name.startswith("autoplm_test_")
        client.drop_database(name)
        client.close()
