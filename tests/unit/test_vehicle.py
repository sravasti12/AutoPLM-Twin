import copy
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

import pytest
from streamlit.testing.v1 import AppTest

from app.what_if import assess
from dashboard.vehicle import COLORS, vehicle_svg, vehicle_view
from tests.unit.test_mechanical import mechanical_records as mixed_records
from tests.unit.test_what_if import proposal, replace

mechanical_records = mixed_records


def component(view, identifier):
    return next(c for c in view["components"] if c["id"] == identifier)


def changed_part(records):
    part = copy.deepcopy(next(r for r in records if r["id"] == "M-MOUNT"))
    part["revision"] = "R2"
    return assess(proposal(records, [replace(part)]), records)


def test_component_mapping_and_provenance(mechanical_records):
    view = vehicle_view(mechanical_records, "F0000-standard")
    part = component(view, "M-MOUNT")
    assert part["record"] in mechanical_records
    assert part["original_revision"] == "R1"
    assert part["type"] == "mechanical_part"
    assert part["variant"] == "F0000-standard"
    assert any(e["provenance"]["source_field"] == "/edges/1" for e in part["relationships"])
    assert "M-MOUNT" not in {c["id"] for c in vehicle_view(mechanical_records, "F0000-touring")["components"]}
    brake = component(view, "F0000-brake")
    assert any(e["kind"] == "runs" for e in brake["relationships"])


def test_svg_selectable_records_and_no_invented_components(generated):
    records = generated[1].documents()
    view = vehicle_view(records, "F0000-standard")
    svg = vehicle_svg(view, "F0000-brake")
    root = ET.fromstring(svg)
    markers = [el for el in root.iter() if "data-record" in el.attrib]
    assert {el.attrib["data-record"] for el in markers} == {c["id"] for c in view["components"]}
    assert all(el.attrib["role"] == "button" and el.attrib["tabindex"] == "0" for el in markers)
    assert 'stroke="#2563eb"' in svg
    assert not any(c["type"] == "mechanical_part" for c in view["components"])


def test_switching_highlights_and_baseline_immutability(mechanical_records):
    baseline = copy.deepcopy(mechanical_records)
    result = changed_part(baseline)
    original = vehicle_view(baseline, "F0000-standard", result)
    proposed = vehicle_view(baseline, "F0000-standard", result, proposed=True)
    assert component(original, "M-MOUNT")["record"]["revision"] == "R1"
    assert component(proposed, "M-MOUNT")["record"]["revision"] == "R2"
    assert component(proposed, "M-MOUNT")["state"] == "modified"
    assert component(proposed, "M-FRONT")["state"] == "potentially affected"
    assert component(proposed, "M-FRONT")["paths"]
    assert proposed["findings"] == result.report["proposed_findings"]
    assert original["snapshot"]["fingerprint"] != proposed["snapshot"]["fingerprint"]
    assert COLORS["modified"] in vehicle_svg(proposed)
    assert baseline == mechanical_records


def test_missing_reference_is_unknown(generated):
    records = generated[1].documents()
    records = [r for r in records if r["id"] != "F0000-brake"]
    view = vehicle_view(records, "F0000-standard")
    missing = component(view, "F0000-brake")
    assert missing["record"] is None and missing["state"] == "unknown/unassessed"
    assert view["diagnostics"]


def test_added_and_removed_markers(mechanical_records):
    records = mechanical_records
    bom = copy.deepcopy(next(r for r in records if r["id"] == "M-BOM"))
    bom["edges"][1]["child"] = "new-mount"
    new = {"kind": "mechanical_part", "id": "new-mount", "part_number": "SYN", "revision": "R1"}
    result = assess(proposal(records, [replace(bom),
        {"operation": "add", "record_id": "new-mount", "record": new},
        {"operation": "remove", "record_id": "M-MOUNT"}]), records)
    for proposed in (False, True):
        view = vehicle_view(records, "F0000-standard", result, proposed)
        assert component(view, "new-mount")["state"] == "added"
        assert component(view, "M-MOUNT")["state"] == "removed"


def test_stale_result_not_displayed(mechanical_records):
    result = changed_part(mechanical_records)
    changed = copy.deepcopy(mechanical_records)
    changed[0]["id"] = "different"
    with pytest.raises(ValueError, match="stale"):
        vehicle_view(changed, "F0000-standard", result)


def test_svg_escapes_record_content():
    view = {"components": [{"id": '<script>"&', "type": "unknown", "state": "unknown/unassessed"}]}
    svg = vehicle_svg(view)
    assert "<script>" not in svg
    assert ET.fromstring(svg) is not None


def test_svg_component_event_protocol():
    source = Path("dashboard/vehicle_component/index.html").read_text()
    for event in ("streamlit:render", "streamlit:componentReady", "streamlit:setComponentValue"):
        assert event in source
    assert 'closest("[data-record]")' in source
    assert 'event.key==="Enter"' in source


def test_workspace_selection_proposal_switch_and_reset(mechanical_records):
    script = '''
import streamlit as st
from dashboard.vehicle_workspace import render_vehicle
render_vehicle(st.session_state["records"], "test-job")
'''
    view = AppTest.from_string(script, default_timeout=20)
    view.session_state["records"] = mechanical_records
    with patch("dashboard.vehicle_workspace.select_vehicle", return_value=None):
        view.run()
        assert not view.exception
        view.text_area[0].set_value(changed_part(mechanical_records).proposal.model_dump_json()).run()
        view.button[0].click().run()
        view.selectbox[0].select("synthetic-proposal").run()
        view.radio[0].set_value("Proposed").run()
        assert not view.exception
        view.selectbox[2].select("M-MOUNT").run()
        assert any("R2" in element.value for element in view.json)
        view.button[1].click().run()
        assert view.radio[0].value == "Original"
    with patch("dashboard.vehicle_workspace.select_vehicle", return_value={"id": "M-FRONT", "event": 1}):
        view.run()
        assert not view.exception
        assert view.selectbox[2].value == "M-FRONT"
