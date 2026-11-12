"""Opt-in provider smoke test; never enabled by credentials alone."""

import os

import pytest

from app.data import generate
from app.investigation import investigate


@pytest.mark.skipif(os.getenv("AUTOPLM_RUN_LIVE_INVESTIGATION") != "1", reason="Live LLM test is opt-in")
def test_configured_live_investigation():
    assert os.getenv("AUTOPLM_LLM_MODEL") and os.getenv("OPENAI_API_KEY"), (
        "Configure provider before opting in"
    )
    report = investigate(
        "Retrieve F0000-brake and report its recorded hardware revision.",
        generate(1, seed=42)[1].documents(),
        mode="llm",
        max_steps=6,
    )
    assert report.evidence and len(report.evidence) <= 6
    assert report.reasoning_status == "validated", report.missing_evidence
    assert all(e.status == "ok" for e in report.evidence)
    assert "F0000-brake" in report.identified_components
    assert report.human_review_status == "required"
