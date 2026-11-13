"""Hosted OIDC controls. UI identity hints never replace backend authorization."""

import os
from urllib.parse import urlsplit

import streamlit as st

from app.oidc_auth import OIDCConfig


def clear_private_state() -> None:
    for key in list(st.session_state):
        if key != "workspace":
            del st.session_state[key]
    st.session_state["workspace"] = "Public Demonstration"


def validate_login_settings(auth: dict, backend: str) -> None:
    config = OIDCConfig.from_environment()
    callback = urlsplit(auth.get("redirect_uri", ""))
    target = urlsplit(backend)
    provider = auth.get("auth0", {})
    if (
        callback.scheme != "https"
        or not callback.hostname
        or callback.path != "/oauth2callback"
        or callback.username
        or callback.password
        or callback.query
        or callback.fragment
        or target.scheme != "https"
        or not target.hostname
        or target.username
        or target.password
        or target.query
        or target.fragment
        or len(auth.get("cookie_secret", "")) < 32
        or auth.get("expose_tokens") != ["access"]
        or provider.get("client_id") != config.client_id
        or not provider.get("client_secret")
        or provider.get("server_metadata_url") != config.issuer + ".well-known/openid-configuration"
        or provider.get("authorize_params", {}).get("audience") != config.audience
        or "autoplm:access" not in provider.get("client_kwargs", {}).get("scope", "").split()
        or provider.get("client_kwargs", {}).get("code_challenge_method") != "S256"
    ):
        raise ValueError("Hosted reviewer login configuration is incomplete")


def reviewer_credential(backend: str) -> str:
    if os.getenv("AUTOPLM_ENVIRONMENT", "local") == "local":
        return st.sidebar.text_input(
            "Engineering reviewer credential (local only)", type="password", key="reviewer_credential"
        )
    try:
        auth = st.secrets["auth"].to_dict()
        validate_login_settings(auth, backend)
    except (KeyError, ValueError, FileNotFoundError, TypeError, AttributeError):
        st.sidebar.caption("Reviewer login is not configured. Public browsing remains available.")
        return ""
    if st.user.is_logged_in:
        if st.sidebar.button("Sign out / switch account"):
            clear_private_state()
            st.logout()
            return ""
        # Never substitute st.user tokens['id'] or accept profile roles as authorization.
        access = st.user.tokens.get("access", "")
        if not isinstance(access, str) or not access:
            st.sidebar.warning("No API access token is available. Sign out and sign in again.")
            return ""
        return access
    if st.sidebar.button("Engineering reviewer sign in"):
        clear_private_state()
        st.login("auth0")
    return ""
