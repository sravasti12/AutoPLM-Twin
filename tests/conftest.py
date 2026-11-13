import hashlib
import json

import mongomock
import pytest

from app.data import generate
from app.repository import Repository
from app.service import MigrationService


@pytest.fixture
def generated():
    return generate(1)


@pytest.fixture
def service():
    return MigrationService(Repository(mongomock.MongoClient().autoplm_unit_test))


@pytest.fixture
def credentials(monkeypatch):
    tokens = {
        "reviewer-token": {"subject": "engineer-123", "roles": ["engineering_reviewer"]},
        "reader-token": {"subject": "reader-456", "roles": ["investigation_reader"]},
    }
    monkeypatch.setenv(
        "AUTOPLM_REVIEW_CREDENTIALS",
        json.dumps(
            {hashlib.sha256(token.encode()).hexdigest(): principal for token, principal in tokens.items()}
        ),
    )
    return {"Authorization": "Bearer reviewer-token"}
