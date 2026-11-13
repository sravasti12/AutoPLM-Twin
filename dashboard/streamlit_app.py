"""Streamlit engineering console. All persisted operations go through FastAPI."""

import json
import os
from pathlib import Path

import httpx
import networkx as nx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.review_auth import ReviewPrincipal
from dashboard.investigation_workspace import api_request, validated
from dashboard.public_workspace import render_public_workspace
from dashboard.reviewer_login import reviewer_credential

st.set_page_config(page_title="AutoPLM Twin", page_icon=":material/directions_car:", layout="wide")
st.markdown(
    "<style>" + Path(__file__).with_name("theme.css").read_text(encoding="utf-8") + "</style>",
    unsafe_allow_html=True,
)
st.markdown(
    '<header class="product-header"><div class="brand-mark">AT</div><div>'
    '<div class="eyebrow">Automotive engineering intelligence</div><h1>AutoPLM Twin</h1>'
    '<p>Product data migration · Digital twin validation · Engineering change assessment</p>'
    '</div></header>', unsafe_allow_html=True,
)
st.sidebar.markdown('<div class="sidebar-brand">AutoPLM Twin</div>'
                    '<div class="eyebrow">Engineering workspace</div>', unsafe_allow_html=True)
st.sidebar.caption("Synthetic engineering environment")
base = os.getenv("AUTOPLM_API_URL", "http://localhost:8000")
credential = reviewer_credential(base)
principal = (
    validated(ReviewPrincipal, api_request(base, credential, "GET", "/review/me")) if credential else None
)
if credential and principal is None and os.getenv("AUTOPLM_ENVIRONMENT", "local") != "local":
    st.sidebar.warning("Reviewer access is unavailable or expired. Sign out and sign in again.")
reviewer = principal is not None and "engineering_reviewer" in principal.roles
scope = (base, principal.subject) if reviewer and principal is not None else None
if st.session_state.get("reviewer_scope") != scope:
    for key in list(st.session_state):
        if key not in ("reviewer_credential", "workspace"):
            del st.session_state[key]
    st.session_state["reviewer_scope"] = scope
if principal:
    st.sidebar.caption(f"Authenticated: {principal.subject} | Roles: {', '.join(principal.roles)}")
    if not reviewer:
        st.sidebar.warning("Engineering reviewer authorization is required for private workspaces.")
private_pages = [
    "Overview", "Migration Workspace", "ECU Compatibility Explorer", "Digital Twin Explorer",
    "Interactive 2D Vehicle", "Investigation Workspace", "Simulation Workspace", "Agent Review Queue",
    "Benchmark Dashboard", "Audit Reports",
]
pages = ["Public Demonstration", "Reviewer Access"] + (private_pages if reviewer else [])
if st.session_state.get("workspace") not in pages:
    st.session_state["workspace"] = "Public Demonstration"
page = st.sidebar.radio("Workspace", pages, key="workspace")



def call(method, path, **kwargs):
    try:
        kwargs.setdefault("headers", {"Authorization": f"Bearer {credential}"})
        response = httpx.request(
            method, base.rstrip("/") + path, timeout=180, follow_redirects=False, **kwargs
        )
        if response.status_code >= 300:
            st.error("Backend request rejected. Check reviewer authorization and the job validation report.")
            return None
        return response.json()
    except (httpx.HTTPError, ValueError):
        st.error("Backend request failed. Check backend availability and reviewer authorization.")
        return None


def architecture(snapshot, chart_key):
    graph = nx.Graph()
    graph.add_edges_from(snapshot["edges"])
    graph.add_nodes_from(node["id"] for node in snapshot["nodes"])
    positions = nx.spring_layout(graph, seed=42)
    figure = go.Figure()
    for left, right in graph.edges:
        figure.add_trace(
            go.Scatter(
                x=[positions[left][0], positions[right][0]],
                y=[positions[left][1], positions[right][1]],
                mode="lines",
                line={"color": "#94a3b8"},
                hoverinfo="skip",
                showlegend=False,
            )
        )
    nodes = {node["id"]: node for node in snapshot["nodes"]}
    labels, colors = [], []
    for identifier in graph:
        node = nodes.get(identifier, {})
        hw, sw = node.get("hardware"), node.get("software")
        compatible = bool(
            hw
            and sw
            and hw["hardware_revision"] in sw["supported_hardware_revisions"]
            and set(sw["required_interfaces"]).issubset(hw["interfaces"])
        )
        labels.append(
            f"{identifier}<br>HW {hw['hardware_revision'] if hw else 'MISSING'}"
            f" · SW {sw['version'] if sw else 'MISSING'}"
        )
        colors.append("#23856d" if compatible else "#c2414b")
    figure.add_trace(
        go.Scatter(
            x=[positions[n][0] for n in graph],
            y=[positions[n][1] for n in graph],
            mode="markers+text",
            text=labels,
            textposition="top center",
            marker={"size": 22, "color": colors},
            showlegend=False,
        )
    )
    figure.update_layout(
        template="plotly_white",
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        font={"color": "#172B4D"},
        height=470,
        margin={"l": 20, "r": 20, "t": 50, "b": 20},
        xaxis={"visible": False},
        yaxis={"visible": False},
    )
    st.plotly_chart(figure, width="stretch", key=chart_key)
    st.caption(
        "Node colors indicate local hardware/software compatibility. Full engineering findings appear below."
    )


if page == "Public Demonstration":
    render_public_workspace()
elif page == "Reviewer Access":
    st.subheader("Engineering reviewer access")
    st.info(
        "Public demonstration browsing requires no login. Private engineering operations require an "
        "authorized reviewer. Local credentials are development-only; "
        "production reviewers use configured hosted OIDC login."
    )
elif page == "Migration Workspace":
    st.subheader("Ingest a fictional legacy dataset")
    source = st.selectbox("Source schema", ["A", "B"])
    fleets = st.number_input("Synthetic fleets", 1, 1000, 2)
    seed = st.number_input("Seed", value=42)
    if st.button("Generate dataset"):
        st.session_state["dataset"] = call(
            "POST", "/datasets/generate", json={"source": source, "fleets": fleets, "seed": seed}
        )
    uploaded = st.file_uploader("Or upload a synthetic JSON envelope", type=["json"])
    if uploaded:
        try:
            st.session_state["dataset"] = json.load(uploaded)
        except ValueError as exc:
            st.error(str(exc))
    data = st.session_state.get("dataset")
    if data:
        if data.get("source_schema") != source:
            st.warning(
                "Selected source schema differs from uploaded envelope. The envelope controls the adapter."
            )
        st.dataframe(pd.DataFrame(data["records"]).head(50), width="stretch")
        from app.mapping import baseline, profile

        entities = sorted({row["entity"] for row in data["records"]})
        entity = st.selectbox("Inspect baseline mapping", entities)
        fields = profile([row["data"] for row in data["records"] if row["entity"] == entity])
        st.json(baseline(entity, fields).model_dump())
        mapper = st.selectbox("Mapping provider", ["offline", "llm"])
        if st.button("Start staged migration", type="primary"):
            result = call("POST", "/jobs", json={"dataset": data, "mapper": mapper})
            if result:
                st.success(f"Job {result['_id']} · {result['status']}")
                st.json(result)
elif page == "Benchmark Dashboard":
    st.subheader("Measured synthetic evaluation")
    path = Path("benchmarks/results.json")
    if path.exists():
        results = json.loads(path.read_text(encoding="utf-8"))
        st.caption(f"Provider: {results['provider']} · Seed: {results['seed']}")
        frame = pd.DataFrame(results["runs"])
        st.dataframe(frame, width="stretch")
        st.bar_chart(frame, x="mode", y="recall", color="source")
        st.json(results["notes"])
        st.download_button("Download raw experimental evidence", path.read_bytes(), "benchmark.json")
    else:
        st.info("Run python -m app.cli benchmark to generate measured results.")
elif page == "Investigation Workspace":
    from dashboard.investigation_workspace import render_investigation_workspace

    render_investigation_workspace(base, token=credential)
else:
    jobs = call("GET", "/jobs")
    if jobs is None:
        st.info("Start MongoDB and FastAPI using the commands in README.md.")
    elif page == "Overview":
        frame = pd.DataFrame(jobs)
        st.subheader("Engineering overview")
        st.caption("Current job summaries from the backend · counts reflect stored validation results")
        columns = st.columns(3)
        columns[0].metric("Migration jobs", len(jobs))
        columns[1].metric("Records processed", sum(j.get("records_processed", 0) for j in jobs))
        columns[2].metric("Verified records", sum(j.get("verified_records", 0) for j in jobs))
        columns = st.columns(3)
        columns[0].metric("Rejected records", sum(j.get("rejected_records", 0) for j in jobs))
        columns[1].metric("Review queue", sum(j["status"] in ["mapping_review", "rejected"] for j in jobs))
        columns[2].metric("Engineering findings",
                          sum(len(j.get("validation", {}).get("findings", [])) for j in jobs))
        st.subheader("Engineering workspaces")
        for column, target, description, icon in zip(
            st.columns(3),
            ["Migration Workspace", "Interactive 2D Vehicle", "Agent Review Queue"],
            ["Stage and verify synthetic product data.", "Inspect configurations and proposed changes.",
             "Review mappings, findings and human decisions."],
            [":material/sync_alt:", ":material/directions_car:", ":material/fact_check:"],
        ):
            with column.container(border=True):
                st.markdown(f"**{target}**")
                st.caption(description)
                st.button("Open workspace", key=f"open-{target}", icon=icon,
                          on_click=lambda destination=target: st.session_state.update(workspace=destination))
        st.subheader("Migration job register")
        st.dataframe(frame, width="stretch")
    elif not jobs:
        st.info("Create a migration in Migration Workspace.")
    else:
        job_id = st.selectbox("Migration job", [j["_id"] for j in jobs])
        report = call("GET", f"/jobs/{job_id}/report")
        if report:
            job = report["job"]
            st.caption(f"Status: {job['status']} · Mapper: {job['mapper']}")
            if page == "ECU Compatibility Explorer":
                hardware = [row["record"] for row in report["staging"] if row["record"]["kind"] == "hardware"]
                software = [row["record"] for row in report["staging"] if row["record"]["kind"] == "software"]
                st.subheader("Hardware and software constraints")
                st.dataframe(pd.DataFrame(hardware), width="stretch")
                st.dataframe(pd.DataFrame(software), width="stretch")
                st.subheader("Findings and evidence")
                st.json(job.get("validation", {}).get("findings", []))
            elif page == "Digital Twin Explorer":
                twins = report["twins"]
                if twins:
                    selected = st.selectbox("Vehicle variant", [t["key"] for t in twins])
                    twin = next(t for t in twins if t["key"] == selected)
                    for column, key in zip(st.columns(2), ["source", "target"]):
                        with column:
                            st.subheader(key.title())
                            if twin[key]:
                                architecture(twin[key], f"twin-{selected}-{key}")
                    st.subheader("Structural and semantic discrepancies")
                    st.json(twin["differences"])
            elif page == "Interactive 2D Vehicle":
                from dashboard.vehicle_workspace import render_vehicle

                if job["status"] == "approved":
                    records = call("GET", f"/jobs/{job_id}/approved")
                    st.caption("Baseline: integrity-checked approved publication")
                else:
                    records = [row["record"] for row in report["staging"]]
                    st.caption("Baseline: current staging snapshot; not an approved product")
                if records is not None:
                    render_vehicle(records, job_id)
            elif page == "Simulation Workspace":
                from app.twin import SCENARIOS

                variants = [
                    row["record"]["id"] for row in report["staging"] if row["record"]["kind"] == "variant"
                ]
                if variants:
                    variant = st.selectbox("Vehicle variant", variants)
                    scenario = st.selectbox("Scenario", SCENARIOS)
                    sensor_fault = st.checkbox("Inject sensor outage after tick 2")
                    if st.button("Execute simulation", type="primary"):
                        result = call(
                            "POST",
                            f"/jobs/{job_id}/simulations",
                            json={
                                "variant_id": variant,
                                "scenario": scenario,
                                "fault_at": 2 if sensor_fault else None,
                            },
                        )
                        if result:
                            st.json(
                                {"states": result["states"], "behavior_passed": result["behavior_passed"]}
                            )
                            st.caption(
                                "Expected: every component ACTIVE. Engineering approval also requires rules."
                            )
                            st.dataframe(pd.DataFrame(result["events"]), width="stretch")
                            st.json(result["engineering_findings"])
                            st.download_button(
                                "Export event trace", json.dumps(result, indent=2), "simulation.json"
                            )
            elif page == "Agent Review Queue":
                actor = principal.subject if principal else ""
                decision_headers = {"Authorization": f"Bearer {credential}"}
                st.subheader("Schema mappings")
                for mapping in report["mappings"]:
                    with st.expander(f"{mapping['key']} · {mapping['state']['status']}"):
                        st.json(mapping["state"])
                        if job["status"] == "mapping_review":
                            plan = st.text_area(
                                "Corrected structured mapping",
                                json.dumps(mapping["state"].get("plan", {}), indent=2),
                                key=mapping["key"],
                            )
                            approve_mapping = st.checkbox("Approve mapping", key=f"approve-{mapping['key']}")
                            if st.button(
                                "Submit mapping decision", key=f"submit-{mapping['key']}", disabled=not actor
                            ):
                                try:
                                    call(
                                        "POST",
                                        f"/jobs/{job_id}/mappings/decision",
                                        headers=decision_headers,
                                        json={
                                            "actor": actor,
                                            "approve": approve_mapping,
                                            "plan": json.loads(plan),
                                        },
                                    )
                                    st.rerun()
                                except ValueError as exc:
                                    st.error(str(exc))
                st.json(job.get("validation", {}))
                repair_mapper = st.selectbox("Repair planner", ["offline", "llm"])
                if st.button(
                    "Propose source restoration", disabled=job["status"] not in ["verified", "rejected"]
                ):
                    call(
                        "POST", f"/jobs/{job_id}/repairs",
                        params={"mapper": repair_mapper}, headers=decision_headers,
                    )
                    st.rerun()
                for proposal in report["repairs"]:
                    with st.expander(f"Repair {proposal['_id']} · {proposal['status']}"):
                        st.json(proposal)
                        approve = st.checkbox("Approve candidate", key=proposal["_id"])
                        if st.button(
                            "Submit repair decision",
                            key=f"repair-{proposal['_id']}",
                            disabled=not actor or proposal["status"] != "pending",
                        ):
                            call(
                                "POST",
                                f"/repairs/{proposal['_id']}/decision",
                                headers=decision_headers,
                                json={"actor": actor, "approve": approve},
                            )
                            st.rerun()
                if st.button(
                    "Approve engineering promotion", disabled=not actor or job["status"] != "verified"
                ):
                    result = call(
                        "POST", f"/jobs/{job_id}/promote", json={"approve": True}, headers=decision_headers
                    )
                    if result is not None:
                        st.rerun()
            elif page == "Audit Reports":
                st.json(report["audit"])
                for fmt in ["json", "csv", "html"]:
                    try:
                        response = httpx.get(
                            f"{base}/jobs/{job_id}/report", params={"format": fmt}, timeout=30,
                            headers={"Authorization": f"Bearer {credential}"}
                        )
                        response.raise_for_status()
                        st.download_button(f"Export {fmt.upper()}", response.content, f"{job_id}.{fmt}")
                    except httpx.HTTPError as exc:
                        st.error(str(exc))
