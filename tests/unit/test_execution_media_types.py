"""Production media-type checks exercise real routes with signed, locally generated tokens."""

import json
import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from tests.unit.test_oidc_auth import ISSUER, bearer
from tests.unit.test_oidc_auth import oidc as oidc_fixture
from tests.unit.test_oidc_auth import signing_keys as keys_fixture

oidc = oidc_fixture
signing_keys = keys_fixture
MEDIA_TYPES = (
    "application/json",
    "Application/JSON",
    "application/vendor+json",
    "Application/Vendor+JSON; charset=UTF-8",
)


@pytest.fixture
def reviewer_api(oidc, monkeypatch):
    client, store, _, mint, _, _ = oidc
    monkeypatch.setenv("AUTOPLM_ENABLE_LLM", "false")
    # Freeze only the quota module's clock so a UTC window boundary cannot make tests flaky.
    now = int(time.time())
    monkeypatch.setattr("app.security_store.time", SimpleNamespace(time=lambda: now))
    store.set_reviewer(ISSUER, "auth0|reviewer", True, "test-operator", "media-type regression")
    return client, bearer(mint()), store


def post(client, headers, path, media_type, body):
    return client.post(path, headers={**headers, "Content-Type": media_type}, content=json.dumps(body))


@pytest.mark.parametrize("media_type", MEDIA_TYPES)
@pytest.mark.parametrize("operation", ["migration", "investigation"])
def test_llm_disabled_for_every_supported_json_type(reviewer_api, service, generated, media_type, operation):
    client, headers, _ = reviewer_api
    with patch.object(service, "migrate") as migrate, patch("app.api.InvestigationService") as investigation:
        investigation.return_value.run.side_effect = AssertionError("Disabled LLM reached handler")
        if operation == "migration":
            response = post(client, headers, "/jobs", media_type, {"dataset": generated[0], "mapper": "llm"})
        else:
            response = post(
                client,
                headers,
                "/jobs/job/investigations",
                media_type,
                {
                    "request": "Inspect F0000-brake",
                    "variant_id": "F0000-standard",
                    "mode": "llm",
                },
            )
        assert response.status_code == 403
        migrate.assert_not_called()
        investigation.assert_not_called()


@pytest.mark.parametrize("media_type", MEDIA_TYPES)
@pytest.mark.parametrize("bound", ["fleets", "ticks", "max_steps", "records"])
def test_production_bounds_for_every_json_type(reviewer_api, service, generated, media_type, bound):
    client, headers, _ = reviewer_api
    requests = {
        "fleets": ("/datasets/generate", {"fleets": 11}),
        "ticks": ("/jobs/job/simulations", {"variant_id": "F0000-standard", "ticks": 101}),
        "max_steps": (
            "/jobs/job/investigations",
            {
                "request": "Inspect",
                "variant_id": "F0000-standard",
                "max_steps": 13,
            },
        ),
        "records": ("/jobs", {"dataset": {**generated[0], "records": generated[0]["records"][:1] * 501}}),
    }
    with (
        patch("app.api.generate") as generate,
        patch.object(service, "migrate") as migrate,
        patch.object(service, "run_simulation") as simulate,
        patch("app.api.InvestigationService") as investigate,
    ):
        path, body = requests[bound]
        response = post(client, headers, path, media_type, body)
        assert response.status_code == 422
        for handler in (generate, migrate, simulate, investigate):
            handler.assert_not_called()


@pytest.mark.parametrize("media_type", MEDIA_TYPES)
def test_valid_body_is_preserved_for_downstream_handler(reviewer_api, generated, media_type):
    client, headers, _ = reviewer_api
    response = post(
        client, headers, "/datasets/generate", media_type, {"fleets": 1, "seed": 42, "source": "A"}
    )
    assert response.status_code == 200, response.text
    assert response.json() == generated[0]


@pytest.mark.parametrize("media_type", MEDIA_TYPES)
@pytest.mark.parametrize("budget", ["executions", "llm"])
def test_shared_execution_and_llm_quotas_for_every_json_type(
    reviewer_api,
    service,
    generated,
    monkeypatch,
    media_type,
    budget,
):
    client, headers, _ = reviewer_api
    monkeypatch.setenv("AUTOPLM_ENABLE_LLM", "true")
    count = 1 if budget == "llm" else 6
    body = {"dataset": generated[0], "mapper": "llm" if budget == "llm" else "offline"}
    with patch.object(service, "migrate", return_value={"status": "mocked"}) as migrate:
        for _ in range(count):
            assert post(client, headers, "/jobs", media_type, body).status_code == 200
        response = post(client, headers, "/jobs", media_type, body)
        assert response.status_code == 429 and int(response.headers["Retry-After"]) > 0
        assert migrate.call_count == count


@pytest.mark.parametrize("media_type", [None, *MEDIA_TYPES])
def test_empty_body_repairs_preserve_query_and_authenticated_actor(reviewer_api, service, media_type):
    client, headers, _ = reviewer_api
    headers = {**headers, **({"Content-Type": media_type} if media_type else {})}
    with patch.object(service, "propose_repair", return_value={"status": "mocked"}) as repair:
        response = client.post("/jobs/job/repairs?mapper=offline", headers=headers, content=b"")
        assert response.status_code == 200
        repair.assert_called_once_with("job", actor="auth0|reviewer", provider=None)
    with patch.object(service, "propose_repair") as repair:
        response = client.post("/jobs/job/repairs?mapper=llm", headers=headers, content=b"")
        assert response.status_code == 403
        repair.assert_not_called()


@pytest.mark.parametrize("media_type", MEDIA_TYPES)
def test_malformed_json_never_reaches_execution(reviewer_api, service, media_type):
    client, headers, _ = reviewer_api
    with patch.object(service, "propose_repair") as repair:
        response = client.post(
            "/jobs/job/repairs", headers={**headers, "Content-Type": media_type}, content=b"{"
        )
        assert response.status_code == 422
        repair.assert_not_called()


@pytest.mark.parametrize("media_type", MEDIA_TYPES)
@pytest.mark.parametrize("authenticated,status", [(False, 401), (True, 403)])
def test_media_type_never_bypasses_reviewer_authorization(oidc, media_type, authenticated, status):
    client, _, _, mint, _, _ = oidc
    headers = bearer(mint(sub="auth0|non-reviewer")) if authenticated else {}
    with patch("app.api.generate") as generate:
        response = post(client, headers, "/datasets/generate", media_type, {"fleets": 1})
        assert response.status_code == status
        generate.assert_not_called()
