from unittest.mock import patch

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from app.data import generate
from app.investigation_review import InvestigationReviews
from app.investigation_service import InvestigationInput
from app.review_auth import ReviewPrincipal
from tests.unit.test_investigation_api import approved_job as job_fixture
from tests.unit.test_investigation_api import client as client_fixture
from tests.unit.test_investigation_review import credentials as credential_fixture

approved_job = job_fixture
client = client_fixture
credentials = credential_fixture

SCRIPT = """
from dashboard.investigation_workspace import render_investigation_workspace
render_investigation_workspace("http://localhost:8000")
"""


def widget(view, kind, label):
    return next(item for item in getattr(view, kind) if item.label == label)


@pytest.fixture
def console(client, service, approved_job, credentials):
    seed = InvestigationReviews(service.repo).create(
        approved_job,
        InvestigationInput(request="Investigate impact and verify F0000-brake", variant_id="F0000-standard"),
        ReviewPrincipal(subject="engineer-123", roles=("engineering_reviewer",)),
    )
    calls, failures = [], {}

    def request(method, url, **kwargs):
        path = url.replace("http://localhost:8000", "")
        calls.append((method, path, kwargs.get("json")))
        if failures.get((method, path)):
            return httpx.Response(
                failures[(method, path)], json={"detail": "private error"}, request=httpx.Request(method, url)
            )
        kwargs.pop("timeout", None)
        return client.request(method, path, **kwargs)

    def start(token="reviewer-token"):
        view = AppTest.from_string(SCRIPT, default_timeout=30).run()
        widget(view, "text_input", "Review bearer credential").set_value(token).run()
        assert not view.exception
        return view

    with patch("httpx.request", side_effect=request):
        yield start, calls, failures, seed


def open_report(view):
    widget(view, "button", "Open selected report").click().run()
    assert not view.exception
    return view


def test_identity_and_approved_baseline_selection(console, service, approved_job):
    start, calls, _, _ = console
    staged = service.migrate(generate(1, seed=43)[0])["_id"]
    view = start()
    baseline = widget(view, "selectbox", "Approved baseline")
    assert approved_job in baseline.options and staged not in baseline.options
    text = " ".join(item.value for item in view.json)
    assert "engineer-123" in text and "engineering_reviewer" in text
    assert any(path == "/review/me" for _, path, _ in calls)
    password = widget(view, "text_input", "Review bearer credential").proto
    assert password.type == password.PASSWORD


def test_submit_and_retrieve_persistent_report(console, service, approved_job):
    start, calls, _, _ = console
    view = start()
    widget(view, "text_area", "Engineering investigation request").set_value("Verify F0000-brake")
    widget(view, "selectbox", "Optional component (backend checks variant applicability)").select(
        "F0000-brake"
    )
    widget(view, "button", "Run and save investigation").click().run()
    assert not view.exception
    submissions = [(path, body) for method, path, body in calls if method == "POST"]
    assert submissions == [
        (
            f"/jobs/{approved_job}/investigation-reports",
            {
                "request": "Verify F0000-brake",
                "variant_id": "F0000-standard",
                "component_id": "F0000-brake",
                "mode": "offline",
            },
        )
    ]
    assert service.db.investigation_reports.count_documents({}) == 2
    identifier = view.session_state["investigation_selected"]
    assert any(path == f"/investigation-reports/{identifier}" for _, path, _ in calls)
    assert any("Investigation saved" in item.value for item in view.success)


def test_report_evidence_missing_conditions_and_history(console):
    start, _, _, seed = console
    view = open_report(start())
    rendered = " ".join(item.value for item in view.json)
    for field in (
        "identified_components",
        "baseline_digest",
        "source_provenance",
        "tools_invoked",
        "E001",
        "record_fact",
        "potential_exposure",
        "dependency_paths",
        "missing_evidence",
        "uncertainties",
        "recommendations",
    ):
        assert field in rendered
    assert seed.investigation.report.missing_evidence
    assert seed.investigation.report.missing_evidence[0] in rendered
    assert any("No human decision" in item.value for item in view.info)


def test_manual_report_retrieval(console):
    start, calls, _, seed = console
    view = start()
    widget(view, "text_input", "Retrieve report by investigation ID").set_value(seed.investigation_id)
    widget(view, "button", "Retrieve persisted report").click().run()
    assert not view.exception
    assert any(path == f"/investigation-reports/{seed.investigation_id}" for _, path, _ in calls)


@pytest.mark.parametrize("decision,status", [("ACCEPT", "accepted"), ("REJECT", "rejected")])
def test_decision_submission_and_persistent_history(console, service, decision, status):
    start, calls, _, seed = console
    view = open_report(start())
    widget(view, "radio", "Recommendation decision").set_value(decision)
    widget(view, "text_area", "Mandatory review comments").set_value("Reviewed for consideration only")
    widget(
        view, "checkbox", "I confirm this recommendation decision does not authorize an engineering change."
    ).check()
    widget(view, "button", "Submit human decision").click().run()
    assert not view.exception
    body = next(body for method, path, body in calls if method == "POST" and path.endswith("/decisions"))
    assert body == {"decision": decision, "comments": "Reviewed for consideration only"}
    stored = InvestigationReviews(service.repo).get(seed.investigation_id)
    assert stored.review_status == status
    assert stored.decisions[0].reviewer == "engineer-123"
    rendered = " ".join(item.value for item in view.json)
    assert '"audit_mirrored": true' in rendered and decision in rendered
    assert widget(view, "button", "Submit human decision").disabled
    assert any(item.value == status for item in view.metric)


def test_confirmation_and_comments_required(console):
    start, calls, _, _ = console
    view = open_report(start())
    widget(view, "button", "Submit human decision").click().run()
    assert not any(method == "POST" and path.endswith("/decisions") for method, path, _ in calls)
    assert any("explicitly confirm" in item.value for item in view.warning)


def test_reader_role_and_backend_denial(console):
    start, _, failures, seed = console
    reader = start("reader-token")
    assert any("Engineering reviewer authorization" in item.value for item in reader.error)
    assert not reader.tabs
    view = open_report(start())
    failures[("POST", f"/investigation-reports/{seed.investigation_id}/decisions")] = 403
    widget(view, "text_area", "Mandatory review comments").set_value("Reviewed")
    widget(
        view, "checkbox", "I confirm this recommendation decision does not authorize an engineering change."
    ).check()
    widget(view, "button", "Submit human decision").click().run()
    assert any("backend denied" in item.value for item in view.error)
    assert not view.exception


def test_unauthenticated_identity_stops_workspace(console):
    start, calls, _, _ = console
    view = start("invalid-token")
    assert any("Authentication failed" in item.value for item in view.error)
    assert not any(path == "/jobs" for _, path, _ in calls)


def test_backend_failure_is_sanitized(console):
    start, _, failures, _ = console
    failures[("GET", "/investigation-reports")] = 503
    view = start()
    assert any("unavailable" in item.value for item in view.error)
    assert "private error" not in " ".join(item.value for item in view.error)


def test_empty_approved_baselines_and_pending_queue(console, service):
    start, _, _, _ = console
    service.db.migration_jobs.update_many({}, {"$set": {"status": "verified"}})
    service.db.investigation_reports.delete_many({})
    view = start()
    assert any("No approved baselines" in item.value for item in view.info)
    assert any("No investigations match" in item.value for item in view.info)


def test_validated_reasoning_is_rendered_with_citations(console, service, approved_job):
    from app.investigation import OfflineInvestigator

    def summarize(self, context):
        return {"citations": [context["citation_candidates"][0]]}

    with patch.object(OfflineInvestigator, "summarize", summarize, create=True):
        stored = InvestigationReviews(service.repo).create(
            approved_job,
            InvestigationInput(request="Inspect F0000-brake", variant_id="F0000-standard"),
            ReviewPrincipal(subject="engineer-123", roles=("engineering_reviewer",)),
        )
    start, _, _, _ = console
    view = start()
    widget(view, "text_input", "Retrieve report by investigation ID").set_value(stored.investigation_id)
    widget(view, "button", "Retrieve persisted report").click().run()
    assert not view.exception
    rendered = " ".join(item.value for item in view.json)
    assert '"reasoning_status": "validated"' in rendered
    assert '"pointer": "/record"' in rendered
    assert '"evidence_id": "E001"' in rendered
    assert any("not independent verification" in item.value for item in view.caption)


def test_transport_failure_does_not_display_credential_text():
    view = AppTest.from_string(SCRIPT, default_timeout=30).run()
    with patch("httpx.request", side_effect=httpx.ConnectError("Authorization: Bearer private-test-secret")):
        widget(view, "text_input", "Review bearer credential").set_value("private-test-secret").run()
    assert not view.exception
    assert any("request did not complete" in item.value for item in view.error)
    assert "private-test-secret" not in " ".join(item.value for item in view.error)
