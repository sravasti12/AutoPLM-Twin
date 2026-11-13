from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from app.api import app, get_service


@pytest.mark.parametrize(
    "page",
    [
        "Overview",
        "Migration Workspace",
        "ECU Compatibility Explorer",
        "Digital Twin Explorer",
        "Interactive 2D Vehicle",
        "Investigation Workspace",
        "Simulation Workspace",
        "Agent Review Queue",
        "Benchmark Dashboard",
        "Audit Reports",
    ],
)
def test_dashboard_pages_with_mock_backend(service, generated, page, credentials):
    service.migrate(generated[0])
    app.dependency_overrides[get_service] = lambda: service
    try:
        with TestClient(app) as client:

            def request(method, url, **kwargs):
                kwargs.pop("timeout", None)
                return client.request(method, url.replace("http://localhost:8000", ""), **kwargs)

            with (
                patch("httpx.request", side_effect=request),
                patch("httpx.get", side_effect=lambda url, **kwargs: request("GET", url, **kwargs)),
            ):
                view = (
    AppTest.from_file(
        Path("dashboard/streamlit_app.py").resolve(),
        default_timeout=15,
    ).run()
)
                view.sidebar.text_input[0].set_value("reviewer-token").run()
                view.sidebar.radio[0].set_value(page).run()
                assert not view.exception
                if page == "Overview":
                    assert view.metric[0].value == "1"
                    view.button[0].click().run()
                    assert not view.exception
                    assert view.sidebar.radio[0].value == "Migration Workspace"
                if page == "Migration Workspace":
                    view.button[0].click().run()
                    assert not view.exception
                    view.button[1].click().run()
                    assert not view.exception
                if page == "Simulation Workspace":
                    view.button[0].click().run()
                    assert not view.exception
    finally:
        app.dependency_overrides.clear()


def test_audit_export_errors_do_not_display_transport_secrets(service, generated, credentials):
    service.migrate(generated[0])
    app.dependency_overrides[get_service] = lambda: service
    secret = "audit-export-secret-never-display"
    try:
        with TestClient(app) as client:
            def request(method, url, **kwargs):
                kwargs.pop("timeout", None)
                return client.request(method, url.replace("http://localhost:8000", ""), **kwargs)

            with (
                patch("httpx.request", side_effect=request),
                patch("httpx.get", side_effect=httpx.TransportError(secret)),
            ):
                view = AppTest.from_file(
                    Path("dashboard/streamlit_app.py").resolve(), default_timeout=20,
                ).run()
                view.sidebar.text_input[0].set_value("reviewer-token").run()
                view.sidebar.radio[0].set_value("Audit Reports").run()
                assert not view.exception
                assert len(view.error) == 3
                assert all(secret not in item.value for item in view.error)
                assert all("export failed" in item.value.lower() for item in view.error)
    finally:
        app.dependency_overrides.clear()
