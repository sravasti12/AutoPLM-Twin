"""Presentation-only investigation/review console. All durable operations use FastAPI."""

from urllib.parse import quote, urlsplit

import httpx
import streamlit as st
from pydantic import BaseModel, ValidationError

from app.investigation_review import ReviewHistory, ReviewQueue, StoredInvestigation
from app.models import Dataset
from app.review_auth import ReviewPrincipal


def api_request(base: str, token: str, method: str, path: str, **kwargs):
    try:
        response = httpx.request(
            method,
            base.rstrip("/") + path,
            headers={"Authorization": f"Bearer {token}"},
            timeout=180,
            follow_redirects=False,
            **kwargs,
        )
        if response.status_code >= 300:
            messages = {
                401: "Authentication failed. Check the bearer credential.",
                403: "The backend denied this action: reviewer authorization is required.",
                404: "The requested baseline or report was not found.",
                409: "The backend reported an integrity or review conflict. Refresh the report.",
                422: "The backend rejected the submitted fields or context.",
                503: "The backend or its authorization/database configuration is unavailable.",
            }
            st.error(messages.get(response.status_code, "The backend could not complete this request."))
            return None
        return response.json()
    except (httpx.HTTPError, ValueError):
        # Never render exception/request/header/provider text, which may contain credentials.
        st.error(
            "Backend request did not complete. Check saved reports before resubmitting an investigation."
        )
        return None


def validated(model: type[BaseModel], payload):
    if payload is None:
        return None
    try:
        return model.model_validate(payload)
    except (ValidationError, TypeError):
        st.error("The backend returned an unexpected response format.")
        return None


def display_report(stored: StoredInvestigation) -> None:
    report = stored.investigation.report
    baseline = stored.investigation.baseline
    st.subheader("Investigation report")
    st.code(stored.investigation_id, language=None)
    columns = st.columns(3)
    columns[0].metric("Investigation status", report.status)
    columns[1].metric("Human review status", stored.review_status)
    columns[2].metric("Reasoning status", report.reasoning_status)
    st.write(
        {
            "Request": report.request,
            "Created by": stored.created_by,
            "Created at": stored.created_at.isoformat(),
        }
    )
    with st.expander("Extracted intent and identified engineering records", expanded=True):
        st.json(
            {
                "extracted_intent": report.extracted.model_dump(),
                "identified_components": report.identified_components,
                "identified_variants": report.identified_variants,
            }
        )
    with st.expander("Baseline fingerprints, digests and source provenance"):
        st.json(
            {
                "baseline": baseline.model_dump(),
                "baseline_fingerprints": report.baseline_fingerprints,
                "baseline_digest": report.baseline_digest,
                "report_digest": stored.report_digest,
            }
        )
    with st.expander("Investigation plan and tool execution history"):
        st.json(
            {
                "plan": [p.model_dump() for p in report.plan],
                "steps": report.executed_steps,
                "tools_invoked": [c.model_dump() for c in report.tools_invoked],
            }
        )
    st.markdown("### Retrieved evidence")
    st.caption(
        "Record facts and deterministic tool results are distinct from potential exposure and unknowns."
    )
    if not report.evidence:
        st.info("No tool evidence was retrieved. Inspect missing evidence before making a decision.")
    for evidence in report.evidence:
        with st.expander(
            f"{evidence.evidence_id} · {evidence.call.tool} · {evidence.classification} · {evidence.status}"
        ):
            st.json(evidence.model_dump())
    with st.expander("Deterministic engineering findings", expanded=bool(report.validation_findings)):
        if report.validation_findings:
            st.json(report.validation_findings)
        else:
            st.info(
                "No validation findings were reported. "
                "This does not establish safety or complete verification."
            )
    with st.expander("Potential exposure, affected entities and dependency paths"):
        st.caption("Dependency exposure is not confirmed incompatibility or approval.")
        st.json({"affected_entities": report.affected_entities, "dependency_paths": report.dependency_paths})
    with st.expander("Missing evidence and uncertainties", expanded=bool(report.missing_evidence)):
        st.json({"missing_evidence": report.missing_evidence, "uncertainties": report.uncertainties})
    with st.expander("Recommendations and evidence-cited LLM reasoning"):
        st.json({"recommendations": report.recommendations, "reasoning_status": report.reasoning_status})
        if report.reasoning and report.reasoning_status == "validated":
            st.caption(
                "Validated citations support these statements; LLM synthesis is not independent verification."
            )
            st.json([conclusion.model_dump() for conclusion in report.reasoning])
        else:
            st.info("No validated LLM reasoning is available for this report.")


def render_investigation_workspace(base: str) -> None:
    st.subheader("Engineering Investigation Workspace")
    st.warning(
        "ACCEPT means further engineering consideration only. This workspace cannot approve migrations, "
        "modify engineering records, apply proposals, publish, release or deploy changes."
    )
    try:
        parsed = urlsplit(base)
        valid_url = (
            parsed.scheme in ("http", "https")
            and parsed.hostname
            and not parsed.username
            and not parsed.password
        )
    except ValueError:
        valid_url = False
    if not valid_url:
        st.error("Set a valid Backend URL without embedded credentials.")
        return
    token = st.text_input("Review bearer credential", type="password", key="investigation_bearer")
    st.caption(
        "Use an existing server-provisioned credential. "
        "It stays in this session and is never included in reports."
    )
    if not token:
        st.info("Enter a bearer credential to authenticate and load investigations.")
        return
    principal = validated(ReviewPrincipal, api_request(base, token, "GET", "/review/me"))
    if principal is None:
        return
    with st.container(border=True):
        st.write({"Authenticated subject": principal.subject, "Roles": list(principal.roles)})
        st.caption("Identity and permissions come from the backend, not a reviewer-name field.")
    scope = (base.rstrip("/"), principal.subject)
    if st.session_state.get("investigation_scope") != scope:
        st.session_state["investigation_scope"] = scope
        st.session_state.pop("investigation_selected", None)
    notice = st.session_state.pop("investigation_notice", None)
    if notice:
        st.success(notice)

    console, explorer = st.tabs(["Investigation console", "Saved reports and human review"])
    with console:
        jobs = api_request(base, token, "GET", "/jobs")
        if jobs is not None and not isinstance(jobs, list):
            st.error("The backend returned an unexpected jobs response.")
            jobs = None
        approved = [j for j in jobs or [] if j.get("status") == "approved"]
        if not approved:
            st.info("No approved baselines are available. Investigation requires an approved publication.")
        else:
            job_id = st.selectbox(
                "Approved baseline", [j["_id"] for j in approved], key="investigation_baseline"
            )
            selected_job = next(j for j in approved if j["_id"] == job_id)
            st.write(
                {"Selected approved job": job_id, "Publication digest": selected_job.get("approved_digest")}
            )
            records = api_request(base, token, "GET", f"/jobs/{quote(job_id, safe='')}/approved")
            dataset = validated(Dataset, {"records": records}) if records is not None else None
            if dataset is not None:
                variants = [r.id for r in dataset.records if r.kind == "variant"]
                if not variants:
                    st.info("This approved publication contains no available vehicle variant.")
                else:
                    with st.form("investigation_submit"):
                        variant = st.selectbox("Investigation vehicle variant", variants)
                        component = st.selectbox(
                            "Optional component (backend checks variant applicability)",
                            [None] + [r.id for r in dataset.records if r.kind != "variant"],
                            format_func=lambda value: value or "No component restriction",
                        )
                        request_text = st.text_area(
                            "Engineering investigation request", height=120, max_chars=10000
                        )
                        mode = st.selectbox("Investigation mode", ["offline", "llm"])
                        st.caption(
                            "LLM mode requires provider configuration on the backend; "
                            "no model availability is assumed."
                        )
                        submit = st.form_submit_button("Run and save investigation", type="primary")
                    if submit:
                        if not request_text.strip():
                            st.warning("Enter an engineering investigation request.")
                        else:
                            request = {
                                "request": request_text,
                                "variant_id": variant,
                                "component_id": component,
                                "mode": mode,
                            }
                            with st.spinner("Investigating through the authoritative backend…"):
                                stored = validated(
                                    StoredInvestigation,
                                    api_request(
                                        base,
                                        token,
                                        "POST",
                                        f"/jobs/{quote(job_id, safe='')}/investigation-reports",
                                        json=request,
                                    ),
                                )
                            if stored is not None:
                                st.session_state["investigation_selected"] = stored.investigation_id
                                st.success(
                                        "Investigation saved. "
                                        "Open 'Saved reports and human review' to inspect it."
                                )

    with explorer:
        st.markdown("### Persistent report queue")
        status = st.selectbox("Review status filter", ["pending", "accepted", "rejected", "all"])
        offset = st.number_input("Report offset", min_value=0, max_value=100000, step=50)
        queue = validated(
            ReviewQueue,
            api_request(
                base,
                token,
                "GET",
                "/investigation-reports",
                params={"review_status": status, "limit": 50, "offset": offset},
            ),
        )
        if queue is not None:
            if queue.items:
                st.dataframe(
                    [
                        {
                            "Investigation ID": item.investigation_id,
                            "Review": item.review_status,
                            "Investigation": item.investigation.report.status,
                            "Variant": item.investigation.baseline.variant_id,
                            "Created": item.created_at.isoformat(),
                        }
                        for item in queue.items
                    ],
                    hide_index=True,
                )
                selected = st.selectbox(
                    "Saved investigation", [item.investigation_id for item in queue.items]
                )
                if st.button("Open selected report"):
                    st.session_state["investigation_selected"] = selected
            else:
                st.info("No investigations match this review status.")
        manual_id = st.text_input("Retrieve report by investigation ID")
        if st.button("Retrieve persisted report") and manual_id.strip():
            st.session_state["investigation_selected"] = manual_id.strip()
        identifier = st.session_state.get("investigation_selected")
        if not identifier:
            return
        path = f"/investigation-reports/{quote(identifier, safe='')}"
        stored = validated(StoredInvestigation, api_request(base, token, "GET", path))
        if stored is None:
            return
        display_report(stored)
        st.markdown("### Persistent human decision history")
        history = validated(ReviewHistory, api_request(base, token, "GET", path + "/decisions"))
        if history is not None:
            if history.decisions:
                st.json(history.model_dump(mode="json"))
                if not history.audit_mirrored:
                    st.warning("The decision is durable, but its central audit mirror is incomplete.")
            else:
                st.info("No human decision has been recorded.")
        can_review = "engineering_reviewer" in principal.roles
        if not can_review:
            st.info("Your authenticated roles permit report access, not engineering review decisions.")
        with st.form(f"investigation_decision_{identifier}"):
            decision = st.radio("Recommendation decision", ["ACCEPT", "REJECT"], horizontal=True)
            comments = st.text_area("Mandatory review comments", max_chars=10000)
            confirmed = st.checkbox(
                "I confirm this recommendation decision does not authorize an engineering change."
            )
            decide = st.form_submit_button(
                "Submit human decision", disabled=not can_review or stored.review_status != "pending"
            )
        if decide:
            if not confirmed or not comments.strip():
                st.warning("Add review comments and explicitly confirm the recommendation-only decision.")
            else:
                result = validated(
                    ReviewHistory,
                    api_request(
                        base,
                        token,
                        "POST",
                        path + "/decisions",
                        json={"decision": decision, "comments": comments.strip()},
                    ),
                )
                if result is not None:
                    st.session_state["investigation_notice"] = (
                        "Decision persisted. Review status and history refreshed."
                    )
                    st.rerun()
