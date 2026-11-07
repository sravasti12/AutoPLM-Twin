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
