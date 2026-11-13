"""Offline Atlas payload checks, not a substitute for authenticated Atlas acceptance."""

import ast
import json
from pathlib import Path
from typing import Any

import pytest

from app.repository import COLLECTIONS, Repository

ROOT = Path(__file__).resolve().parents[2]
ENTITIES = set(COLLECTIONS.values())
MUTABLE = ENTITIES | {
    "source_records", "staging_records", "schema_mappings", "twin_snapshots",
    "migration_jobs", "repair_proposals", "investigation_reports",
}
INDEXED = MUTABLE | {"validation_results", "simulation_runs", "audit_events"}
SECURITY = {"reviewer_grants", "security_policy", "security_quotas", "security_locks"}


def permissions(role: str) -> dict[str, set[str]]:
    payload = json.loads((ROOT / "config" / "atlas" / f"{role}-role.json").read_text())
    assert set(payload) == {"roleName", "inheritedRoles", "actions"}
    assert payload["roleName"] == f"autoplm_{role}"
    assert payload["inheritedRoles"] == []
    result: dict[str, set[str]] = {}
    actions = set()
    for entry in payload["actions"]:
        assert set(entry) == {"action", "resources"}
        action = entry["action"]
        assert action in {"FIND", "INSERT", "UPDATE", "CREATE_INDEX", "LIST_INDEXES"}
        assert action not in actions
        actions.add(action)
        resources = set()
        for resource in entry["resources"]:
            assert set(resource) == {"cluster", "db", "collection"}
            assert resource["cluster"] is False and resource["db"] == "autoplm_twin"
            collection = resource["collection"]
            assert collection in INDEXED | SECURITY  # No wildcard, unknown namespace or system collection.
            assert collection not in resources
            resources.add(collection)
            result.setdefault(collection, set()).add(action)
    return result


@pytest.mark.parametrize("role", ["runtime", "operator"])
def test_atlas_role_payload_is_scoped_and_has_no_inherited_privileges(role: str) -> None:
    permissions(role)


def test_runtime_privileges_are_exact_and_security_history_is_protected() -> None:
    expected = {name: {"FIND", "INSERT", "UPDATE", "CREATE_INDEX"} for name in MUTABLE}
    expected.update({
        "validation_results": {"INSERT", "CREATE_INDEX"},
        "simulation_runs": {"FIND", "INSERT", "CREATE_INDEX"},
        "audit_events": {"FIND", "INSERT", "CREATE_INDEX"},
        "reviewer_grants": {"FIND", "LIST_INDEXES"},
        "security_policy": {"FIND"},
        "security_quotas": {"FIND", "INSERT", "UPDATE", "LIST_INDEXES"},
        "security_locks": {"FIND", "INSERT", "UPDATE"},
    })
    assert permissions("runtime") == expected


def test_operator_can_provision_without_engineering_data_writes_or_audit_edits() -> None:
    expected = {name: {"CREATE_INDEX"} for name in INDEXED}
    expected["audit_events"].add("INSERT")
    expected.update({name: {"FIND", "INSERT", "UPDATE"} for name in SECURITY})
    expected["security_policy"].discard("UPDATE")
    for name in ("reviewer_grants", "security_quotas"):
        expected[name] |= {"CREATE_INDEX", "LIST_INDEXES"}
    assert permissions("operator") == expected


def test_both_roles_cover_actual_repository_index_creation() -> None:
    created: set[str] = set()

    class Collection:
        def __init__(self, name: str):
            self.name = name

        def create_index(self, *args: Any, **kwargs: Any) -> None:
            created.add(self.name)

    class Database:
        def __getitem__(self, name: str) -> Collection:
            return Collection(name)

        def __getattr__(self, name: str) -> Collection:
            return self[name]

    Repository(Database())  # No MongoDB connection; execute the real constructor.
    assert created == INDEXED
    for role in ("runtime", "operator"):
        granted = permissions(role)
        assert all("CREATE_INDEX" in granted[name] for name in created)


def test_runtime_payload_covers_current_direct_database_operations() -> None:
    granted = permissions("runtime")
    reads = {"find", "find_one", "count_documents"}
    writes = {"insert_one", "update_one", "find_one_and_update", "create_index", "index_information"}
    seen = set()
    for filename in ("repository.py", "service.py", "security_store.py", "api.py", "investigation_review.py"):
        tree = ast.parse((ROOT / "app" / filename).read_text(encoding="utf-8"))
        # Provisioning methods are intentionally not runtime operations.
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in {
                "initialize", "set_reviewer",
            }:
                node.body = []
        for call in ast.walk(tree):
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
                continue
            target = call.func.value
            names: set[str] = set()
            if isinstance(target, ast.Attribute):
                if isinstance(target.value, ast.Attribute) and target.value.attr == "db":
                    names = {target.attr}
                elif target.attr == "collection" and isinstance(target.value, ast.Name):
                    names = {"investigation_reports"}
            elif isinstance(target, ast.Subscript):
                # Published entities use self.db[COLLECTIONS[...]] / self.db[collection].
                if isinstance(target.value, ast.Attribute) and target.value.attr == "db":
                    names = ENTITIES
            if not names:
                continue
            method = call.func.attr
            assert method in reads | writes, (filename, call.lineno, method)
            needed = set()
            if method in reads or method == "find_one_and_update":
                needed.add("FIND")
            if method in {"update_one", "find_one_and_update"}:
                needed.add("UPDATE")
            if method == "insert_one" or any(
                keyword.arg == "upsert" and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is True for keyword in call.keywords
            ):
                needed.add("INSERT")
            if method == "create_index":
                needed.add("CREATE_INDEX")
            if method == "index_information":
                needed.add("LIST_INDEXES")
            for name in names:
                assert needed <= granted[name], (filename, call.lineno, name, needed)
                seen.add(name)
    assert seen == INDEXED | SECURITY
