"""Public presentation of packaged projections; never calls the engineering API."""

import streamlit as st

from app.public_samples import load_catalog, load_sample


def render_public_workspace() -> None:
    st.subheader("Public demonstration")
    st.caption("Curated synthetic snapshots. Browsing cannot execute or approve engineering operations.")
    try:
        catalog = load_catalog()
        entries = {item.sample_id: item for item in catalog.samples}
        identifier = st.selectbox(
            "Demonstration sample", list(entries), format_func=lambda value: entries[value].title
        )
        artifact = load_sample(identifier)
    except (OSError, ValueError, KeyError):
        st.error("The packaged demonstration is unavailable. No database fallback is used.")
        return
    sample = artifact.sample
    st.info(sample.label)
    st.caption(f"Sample: {sample.sample_id} | Version: {sample.version}")
    migration, twin, investigation, provenance = st.tabs(
        ["Migration summary", "Digital twin comparison", "Investigation evidence", "Provenance"]
    )
    with migration:
        st.json(sample.migration.model_dump(mode="json"))
        st.caption("Recorded validation is not approval or publication. No live job is created.")
    with twin:
        st.json(sample.twin.model_dump(mode="json"))
    with investigation:
        st.write(sample.investigation.request)
        st.caption(
            "Offline deterministic investigation; potential exposure does not establish incompatibility."
        )
        st.json(sample.investigation.model_dump(mode="json", exclude={"evidence"}))
        for item in sample.investigation.evidence:
            with st.expander(f"{item.evidence_id} | {item.tool} | {item.classification}"):
                st.json(item.model_dump(mode="json"))
    with provenance:
        st.json(sample.provenance.model_dump(mode="json"))
        st.code(artifact.artifact_sha256, language=None)
        st.caption(
            "Artifact SHA-256 covers the canonical public sample payload. Evidence pointers refer to the "
            "original offline report identified by original_report_sha256; raw reports are not published."
        )
