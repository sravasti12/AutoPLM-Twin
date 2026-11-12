"""Streamlit state and rendering for read-only engineering assessment."""

import json
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from app.verification import verify
from app.what_if import EngineeringProposal, assess, baseline_digest
from dashboard.vehicle import COLORS, vehicle_svg, vehicle_view

select_vehicle = components.declare_component(
    "engineering_vehicle", path=str(Path(__file__).with_name("vehicle_component"))
)


def render_vehicle(records: list[dict], job_id: str) -> None:
    st.subheader("Interactive 2D Digital Vehicle")
    st.caption("Illustrative schematic · potential engineering exposure is not safety or change approval")
    try:
        baseline_digest(records)
    except ValueError as exc:
        st.error(f"Cannot visualize ambiguous or invalid records: {exc}")
        return
    store = st.session_state.setdefault("vehicle_proposals", {})
    proposals = store.setdefault(job_id, {})
    with st.expander("Import an existing engineering proposal", expanded=False):
        raw = st.text_area("Existing Phase 3C proposal JSON", key=f"vehicle-import-{job_id}", height=160)
        load = st.button("Load proposal", key=f"vehicle-load-{job_id}", icon=":material/upload_file:")
    if load:
        try:
            proposal = EngineeringProposal.model_validate(json.loads(raw))
            if proposal.job_id is not None and proposal.job_id != job_id:
                raise ValueError("Proposal job context does not match selected job")
            proposals[proposal.proposal_id] = proposal
        except ValueError as exc:
            st.error(f"Proposal could not be loaded: {exc}")
    choice = st.selectbox("What-if proposal", ["Original configuration", *sorted(proposals)],
                          key=f"vehicle-proposal-{job_id}")
    assessment = None
    if choice != "Original configuration":
        try:
            assessment = assess(proposals[choice], records)
        except ValueError as exc:
            st.error(f"Assessment could not run: {exc}")
            return
        st.write(f"Proposal status: {assessment.status}")
        if assessment.status != "assessed":
            st.warning("Baseline changed. Load a proposal based on the current baseline.")
            return
    else:
        st.write("Proposal status: original configuration")
    mode_key = f"vehicle-mode-{job_id}"
    if st.button("Reset to original", key=f"vehicle-reset-{job_id}"):
        st.session_state[mode_key] = "Original"
    mode = st.radio("Configuration view", ["Original", "Proposed"], key=mode_key,
                    horizontal=True, disabled=assessment is None)
    proposed = mode == "Proposed" and assessment is not None
    variants = sorted({r["id"] for r in records + (assessment.proposed_snapshot or [] if assessment else [])
                       if r["kind"] == "variant"})
    if not variants:
        st.info("No vehicle variants are available.")
        return
    variant = st.selectbox("Vehicle variant", variants, key=f"vehicle-variant-{job_id}")
    view = vehicle_view(records, variant, assessment, proposed)
    if not assessment:
        view["findings"] = [f.model_dump(mode="json") for f in verify(records)]
    ids = [component["id"] for component in view["components"]]
    if not ids:
        st.info("This variant is absent in the selected configuration.")
        return
    selection_key = f"vehicle-selection-{job_id}-{variant}"
    if st.session_state.get(selection_key) not in ids:
        st.session_state[selection_key] = ids[0]
    canvas, inspector = st.columns([1.7, 1], gap="large")
    with canvas:
        st.markdown("### Vehicle configuration")
        st.caption(f"{variant} · {'Proposed' if proposed else 'Original'} configuration")
        click = select_vehicle(svg=vehicle_svg(view, st.session_state[selection_key]),
                               key=f"vehicle-svg-{job_id}-{variant}", default=None)
        st.markdown('<div class="vehicle-legend">' + ''.join(
            f'<span><i style="background:{color}"></i>{label.title()}</span>'
            for label, color in COLORS.items()) + '</div>', unsafe_allow_html=True)
    event_key = f"vehicle-click-{job_id}-{variant}"
    if isinstance(click, dict) and click.get("id") in ids and click != st.session_state.get(event_key):
        st.session_state[selection_key] = click["id"]
        st.session_state[event_key] = click
        st.rerun()
    with inspector.container(border=True):
        st.markdown("### Component inspector")
        selected = st.selectbox("Selected component (keyboard alternative)", ids, key=selection_key)
        detail = next(c for c in view["components"] if c["id"] == selected)
        st.write(f"{detail['name']} · {detail['id']} · {detail['type']} · {detail['state']}")
        revisions = st.columns(2)
        revisions[0].metric("Original revision", detail["original_revision"] or "—")
        revisions[1].metric("Proposed revision", detail["proposed_revision"] or "—")
        st.write({"Vehicle variant applicability": detail["applicability"]})
        with st.expander("Component record, BOM relationships and electronic configuration", expanded=False):
            st.json(detail)
    st.subheader("Changed and potentially affected engineering records")
    st.dataframe([{k: c[k] for k in ("id", "type", "state", "original_revision", "proposed_revision")}
                  for c in view["components"] if c["state"] != "unchanged"])
    with st.expander("Engineering findings, impact paths and unresolved questions"):
        st.caption("Reported engineering evidence · potential exposure does not authorize a change")
        st.json({"findings": view["findings"], "diagnostics": view["diagnostics"],
                 "unassessed": view["unassessed"],
                 "impact": assessment.report.get("impact", {}) if assessment else {}})
    if assessment:
        st.download_button("Download assessment report", assessment.model_dump_json(indent=2),
                           file_name=f"{choice}-assessment.json")
