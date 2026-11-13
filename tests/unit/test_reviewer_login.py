from types import SimpleNamespace
from unittest.mock import patch

import pytest
from streamlit.runtime.secrets import AttrDict
from streamlit.testing.v1 import AppTest

from dashboard.reviewer_login import configured_backend_url, validate_login_settings
from tests.unit.test_oidc_auth import AUDIENCE, CLIENT, ISSUER
from tests.unit.test_oidc_auth import oidc as oidc_fixture
from tests.unit.test_oidc_auth import signing_keys as keys_fixture

oidc = oidc_fixture
signing_keys = keys_fixture


def settings():
    return {
        "redirect_uri": "https://demo.streamlit.app/oauth2callback",
        "cookie_secret": "test-cookie-key-" * 5,
        "expose_tokens": ["access"],
        "auth0": {
            "client_id": CLIENT,
            "client_secret": "test-only",
            "server_metadata_url": ISSUER + ".well-known/openid-configuration",
            "authorize_params": {"audience": AUDIENCE},
            "client_kwargs": {
                "scope": "openid profile email autoplm:access",
                "code_challenge_method": "S256",
            },
        },
    }


def start():
    from pathlib import Path

    return AppTest.from_file(Path("dashboard/streamlit_app.py").resolve(), default_timeout=20).run()


@pytest.mark.parametrize(
    "field,value",
    [
        ("expose_tokens", ["id"]),
        ("cookie_secret", "short"),
        ("redirect_uri", "http://insecure.example/oauth2callback"),
    ],
)
def test_invalid_login_configuration_fails_closed(oidc, field, value):
    config = settings()
    config[field] = value
    with pytest.raises(ValueError):
        validate_login_settings(config, "https://api.example")


def test_public_browsing_and_optional_hosted_login(oidc, monkeypatch):
    monkeypatch.setenv("AUTOPLM_API_URL", "https://api.example")
    user = SimpleNamespace(is_logged_in=False, tokens={})
    with (
        patch("streamlit.secrets", {"auth": AttrDict(settings())}),
        patch("streamlit.user", user),
        patch("streamlit.login") as login,
        patch("httpx.request", side_effect=AssertionError("Anonymous browsing contacted backend")),
    ):
        view = start()
        assert not view.exception
        assert view.sidebar.radio[0].value == "Public Demonstration"
        next(b for b in view.sidebar.button if b.label == "Engineering reviewer sign in").click().run()
        login.assert_called_once_with("auth0")


def test_access_forwarding_logout_expiry_and_account_switch_clear_private_state(oidc, monkeypatch):
    client, store, _, mint, _, _ = oidc
    monkeypatch.setenv("AUTOPLM_API_URL", "https://api.example")
    store.set_reviewer(ISSUER, "auth0|reviewer", True, "operator", "test")
    access = mint()
    user = SimpleNamespace(is_logged_in=True, tokens={"access": access, "id": "ID-TOKEN-NEVER-FORWARD"})
    sent = []

    def request(method, url, **kwargs):
        kwargs.pop("timeout", None)
        sent.append(kwargs.get("headers", {}).get("Authorization"))
        return client.request(method, url, **kwargs)

    with (
        patch("streamlit.secrets", {"auth": AttrDict(settings())}),
        patch("streamlit.user", user),
        patch("streamlit.logout", side_effect=lambda: setattr(user, "is_logged_in", False)) as logout,
        patch("httpx.request", side_effect=request),
    ):
        view = start()
        assert not view.exception
        assert "Investigation Workspace" in view.sidebar.radio[0].options
        assert sent and all(value == f"Bearer {access}" for value in sent)
        view.session_state["private_record_cache"] = "private-test-record"
        user.tokens["access"] = mint(sub="auth0|different-account")
        view.run()
        assert "Investigation Workspace" not in view.sidebar.radio[0].options
        assert "private_record_cache" not in view.session_state
        user.tokens["access"] = access
        view.run()
        view.session_state["private_record_cache"] = "private-test-record"
        user.tokens["access"] = mint(exp=1)
        view.run()
        assert "Investigation Workspace" not in view.sidebar.radio[0].options
        assert "private_record_cache" not in view.session_state
        assert any("expired" in item.value for item in view.sidebar.warning)
        user.tokens["access"] = access
        view.run()
        view.session_state["private_record_cache"] = "private-test-record"
        next(b for b in view.sidebar.button if b.label == "Sign out / switch account").click().run()
        logout.assert_called_once()
        assert not view.exception and "private_record_cache" not in view.session_state
        assert view.sidebar.radio[0].options == ["Public Demonstration", "Reviewer Access"]
        assert "ID-TOKEN-NEVER-FORWARD" not in " ".join(sent)


def test_backend_cloud_secret_takes_precedence_over_environment(monkeypatch):
    monkeypatch.setenv("AUTOPLM_API_URL", "http://localhost:8010")
    with patch("streamlit.secrets", {"AUTOPLM_API_URL": "https://api.example/"}):
        assert configured_backend_url() == "https://api.example"


def test_backend_missing_secret_uses_environment_then_local_fallback(monkeypatch):
    with patch("streamlit.secrets", {}):
        monkeypatch.setenv("AUTOPLM_API_URL", "http://127.0.0.1:8010")
        assert configured_backend_url() == "http://127.0.0.1:8010"
        monkeypatch.delenv("AUTOPLM_API_URL")
        assert configured_backend_url() == "http://localhost:8000"


@pytest.mark.parametrize("url", [
    "", "ftp://api.example", "https:///missing", "http://remote.example",
    "https://user:secret@api.example", "https://api.example/?token=secret",
    "https://api.example/#secret", "https://api.example:bad", 123,
])
def test_invalid_backend_secret_is_rejected(url):
    with patch("streamlit.secrets", {"AUTOPLM_API_URL": url}):
        with pytest.raises(ValueError):
            configured_backend_url()


def test_hosted_auth_configuration_is_independent_of_environment(monkeypatch):
    # Hosted auth is authoritative; never mutate process environment to run shared validation.
    for key in ("ISSUER", "AUDIENCE", "CLIENT_ID"):
        monkeypatch.delenv("AUTOPLM_OIDC_" + key, raising=False)
    validate_login_settings(settings(), "https://api.example")
    for key in ("ISSUER", "AUDIENCE", "CLIENT_ID"):
        monkeypatch.setenv("AUTOPLM_OIDC_" + key, "conflicting-environment-value")
    validate_login_settings(settings(), "https://api.example")


@pytest.mark.parametrize("field,value", [
    ("client_id", ""), ("client_id", "x" * 121), ("client_secret", ""),
    ("server_metadata_url", "http://tenant.example/.well-known/openid-configuration"),
    ("server_metadata_url", "https://tenant.example:8443/.well-known/openid-configuration"),
    ("server_metadata_url", "https://user:secret@tenant.example/.well-known/openid-configuration"),
    ("server_metadata_url", "https://tenant.example/nested/.well-known/openid-configuration"),
    ("server_metadata_url", "https://tenant.example/incorrect-metadata"),
])
def test_hosted_provider_validation_rejects_missing_or_invalid_fields(field, value):
    config = settings()
    config["auth0"][field] = value
    with pytest.raises(ValueError):
        validate_login_settings(config, "https://api.example")


@pytest.mark.parametrize("section,field,value", [
    ("authorize_params", "audience", ""),
    ("authorize_params", "audience", "http://api.example"),
    ("authorize_params", "audience", ISSUER + "userinfo"),
    ("client_kwargs", "scope", "openid profile email"),
    ("client_kwargs", "code_challenge_method", "plain"),
])
def test_hosted_audience_scope_and_pkce_requirements_remain_enforced(section, field, value):
    config = settings()
    config["auth0"][section][field] = value
    with pytest.raises(ValueError):
        validate_login_settings(config, "https://api.example")


def test_cloud_secret_url_and_auth_enable_public_ui_without_backend_calls(oidc, monkeypatch):
    monkeypatch.delenv("AUTOPLM_API_URL", raising=False)
    for key in ("ISSUER", "AUDIENCE", "CLIENT_ID"):
        monkeypatch.delenv("AUTOPLM_OIDC_" + key, raising=False)
    with (
        patch("streamlit.secrets", {
            "AUTOPLM_API_URL": "https://api.example", "auth": AttrDict(settings()),
        }),
        patch("streamlit.user", SimpleNamespace(is_logged_in=False, tokens={})),
        patch("httpx.request", side_effect=AssertionError("Anonymous UI contacted backend")),
    ):
        view = start()
        assert not view.exception
        assert any(b.label == "Engineering reviewer sign in" for b in view.sidebar.button)


def test_invalid_backend_secret_keeps_public_ui_and_disables_reviewer_login(oidc):
    with (
        patch("streamlit.secrets", {"AUTOPLM_API_URL": "https://user:secret@api.example"}),
        patch("httpx.request", side_effect=AssertionError("Invalid configuration contacted backend")),
    ):
        view = start()
        assert not view.exception
        assert view.sidebar.radio[0].value == "Public Demonstration"
        assert any("Backend URL configuration is invalid" in item.value for item in view.sidebar.warning)
        assert "secret@" not in str(view.sidebar.warning)
