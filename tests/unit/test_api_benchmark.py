import pytest
from fastapi.testclient import TestClient

from app.api import app, get_service
from app.benchmark import run_benchmark, score


def test_metrics():
    result = score([True, True, False, False], [True, False, True, False])
    assert result["precision"] == result["recall"] == result["false_positive_rate"] == 0.5
    assert score([], [])["precision"] is None
    with pytest.raises(ValueError):
        score([True], [])


def test_benchmark_real_calculation():
    result = run_benchmark(1)
    assert len(result["runs"]) == 6
    assert len(result["cases"]) == 66
    for run in result["runs"]:
        assert run["mapping_accuracy"] == 1
        assert run["false_positive_rate"] == 0
        assert run["recall"] == (1 if run["mode"] == "agent_engineering_twin" else 0)


def test_api_end_to_end_with_mock_database(service, generated):
    app.dependency_overrides[get_service] = lambda: service
    try:
        with TestClient(app) as client:
            assert client.get("/health").status_code == 200
            assert client.get("/jobs/unknown").status_code == 404
            response = client.post("/jobs", json={"dataset": generated[0]})
            assert response.status_code == 200, response.text
            job = response.json()["_id"]
            assert client.get("/jobs").json()
            assert client.get(f"/jobs/{job}/report").status_code == 200
            for fmt in ["json", "csv", "html"]:
                assert client.get(f"/jobs/{job}/report", params={"format": fmt}).status_code == 200
            sim = client.post(f"/jobs/{job}/simulations", json={"variant_id": "F0000-standard"})
            assert sim.status_code == 200
            assert sim.json()["behavior_passed"]
            assert (
                client.post(f"/jobs/{job}/promote", json={"actor": "engineer", "approve": True}).status_code
                == 200
            )
    finally:
        app.dependency_overrides.clear()
