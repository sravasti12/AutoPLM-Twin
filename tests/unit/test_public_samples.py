import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from pydantic import ValidationError
from streamlit.testing.v1 import AppTest

from app.api import app, get_service
from app.public_samples import SampleArtifact, artifact_hash, load_catalog, load_sample
from scripts.build_public_samples import build_samples

PRIVATE_ROUTES = [
    (
        next(iter(route.methods)),
        route.path.replace("{job_id}", "private-job")
        .replace("{proposal_id}", "private-proposal")
        .replace("{investigation_id}", "private-report"),
    )
    for route in app.routes
    if isinstance(route, APIRoute)
    and route.path not in ("/health", "/ready", "/review/me")
    and not route.path.startswith("/public/")
]


@pytest.fixture
def disconnected_client():
    def forbidden_database():
        raise AssertionError("Public or unauthorized request reached private service")

    app.dependency_overrides[get_service] = forbidden_database
    try:
        with patch(
            "app.repository.Repository.connect", side_effect=AssertionError("MongoDB called")
        ) as connect:
            with TestClient(app) as client:
                yield client
            connect.assert_not_called()
    finally:
        app.dependency_overrides.clear()


def test_public_catalog_and_all_samples_without_database(disconnected_client, monkeypatch):
    monkeypatch.delenv("AUTOPLM_REVIEW_CREDENTIALS", raising=False)
    response = disconnected_client.get("/public/samples")
    assert response.status_code == 200
    for entry in response.json()["samples"]:
        response = disconnected_client.get(f"/public/samples/{entry['sample_id']}")
        assert response.status_code == 200
        artifact = SampleArtifact.model_validate(response.json())
        assert artifact.artifact_sha256 == artifact_hash(artifact.sample.model_dump(mode="json"))
        assert artifact.sample.synthetic
        assert artifact.sample.investigation.evidence
        assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("identifier", ["unknown", "1159cf031e93874f8a12c0a1"])
def test_unknown_or_historical_job_cannot_be_looked_up(disconnected_client, identifier):
    assert disconnected_client.get(f"/public/samples/{identifier}").status_code == 404


@pytest.mark.parametrize("identifier", ["../private.json", "/etc/passwd", "synthetic-equivalent.json"])
def test_loader_never_resolves_arbitrary_paths(identifier):
    with pytest.raises(KeyError):
        load_sample(identifier)


@pytest.mark.parametrize("method,path", PRIVATE_ROUTES)
@pytest.mark.parametrize("token,status", [(None, 401), ("invalid", 401), ("reader-token", 403)])
def test_every_private_route_denies_public_and_reader_before_database(
    disconnected_client,
    credentials,
    method,
    path,
    token,
    status,
):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    # Forged identity and approval fields must not grant authorization, even with malformed input.
    response = disconnected_client.request(method, path, headers=headers, json={"actor": "forged-user"})
    assert response.status_code == status, (method, path, response.text)


@pytest.mark.parametrize("path", ["/public/samples", "/public/samples/synthetic-equivalent"])
def test_public_routes_have_no_mutation_methods(disconnected_client, path):
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        assert disconnected_client.request(method, path, json={"approve": True}).status_code == 405


def test_projection_has_no_private_fields_or_incident_identifiers():
    forbidden = {"audit", "audit_events", "actor", "approved_by", "result", "provider_payload", "credentials"}

    def inspect(value):
        if isinstance(value, dict):
            assert not forbidden.intersection(value)
            for child in value.values():
                inspect(child)
        elif isinstance(value, list):
            for child in value:
                inspect(child)

    for entry in load_catalog().samples:
        sample = load_sample(entry.sample_id)
        inspect(sample.model_dump(mode="json"))
        text = sample.model_dump_json()
        for secret in ("forged-user", "1159cf031e93874f8a12c0a1", "Bearer ", "mongodb://", "mongodb+srv://"):
            assert secret not in text
        document = sample.model_dump(mode="json")
        document["sample"]["investigation"]["credentials"] = "never-publish"
        with pytest.raises(ValidationError):
            SampleArtifact.model_validate(document)


def test_samples_reproduce_and_contain_actual_twin_and_validation_results(tmp_path):
    build_samples(tmp_path)
    for name in ("catalog.json", "synthetic-equivalent.json", "synthetic-hardware-revision-drift.json"):
        assert json.loads((tmp_path / name).read_text("utf-8")) == json.loads(
            (Path("app/public_data") / name).read_text("utf-8")
        )
    clean = load_sample("synthetic-equivalent").sample
    drift = load_sample("synthetic-hardware-revision-drift").sample
    assert clean.migration.validation_passed and not clean.twin.differences
    assert clean.twin.source_fingerprint == clean.twin.target_fingerprint
    assert not drift.migration.validation_passed and drift.investigation.findings
    assert any(d.path == "/nodes/F0000-brake/hardware/hardware_revision" for d in drift.twin.differences)


def test_corrupted_artifact_fails_closed_without_database(tmp_path, monkeypatch, disconnected_client):
    from app import public_samples

    directory = tmp_path / "public_data"
    build_samples(directory)
    sample_file = directory / "synthetic-equivalent.json"
    document = json.loads(sample_file.read_text("utf-8"))
    document["sample"]["migration"]["records"] += 1
    sample_file.write_text(json.dumps(document), "utf-8")
    monkeypatch.setattr(public_samples, "files", lambda package: tmp_path)
    assert disconnected_client.get("/public/samples/synthetic-equivalent").status_code == 503


def test_public_dashboard_needs_no_backend_and_has_no_engineering_controls():
    with patch("httpx.request", side_effect=AssertionError("Public UI contacted API")):
        view = AppTest.from_file(Path("dashboard/streamlit_app.py").resolve(), default_timeout=20).run()
        assert not view.exception
        assert view.sidebar.radio[0].options == ["Public Demonstration", "Reviewer Access"]
        assert not view.button and not view.get("file_uploader")
        view.selectbox[0].select("synthetic-hardware-revision-drift").run()
        assert not view.exception
        assert "hardware_revision" in " ".join(item.value for item in view.json)


def test_production_public_ui_does_not_offer_local_credentials(monkeypatch):
    monkeypatch.setenv("AUTOPLM_ENVIRONMENT", "production")
    with patch("httpx.request", side_effect=AssertionError("Public UI contacted API")):
        view = AppTest.from_file(Path("dashboard/streamlit_app.py").resolve(), default_timeout=20).run()
    assert not view.exception and not view.text_input
    assert view.sidebar.radio[0].value == "Public Demonstration"
