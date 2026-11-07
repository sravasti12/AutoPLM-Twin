"""Phase 2 acceptance checks: input realism, identity and isolated evaluation labels."""

import copy
import json
import random
import subprocess
import sys
from collections import Counter

import pytest

from app.data import FAULTS, corrupt_legacy, generate
from app.source_adapters import normalize_source
from app.verification import verify


@pytest.mark.parametrize("schema", ["A", "B"])
def test_seed_reproducibility_and_random_isolation(schema):
    random.seed(17)
    previous = random.getstate()
    first = generate(3, 42, schema)
    assert random.getstate() == previous
    assert first == generate(3, 42, schema)
    assert first != generate(3, 43, schema)


@pytest.mark.parametrize("fleets", [1, 3, 1000])
def test_configurable_size_and_clean_engineering(fleets):
    envelope, target, _ = generate(fleets)
    records = target.documents()
    assert len(records) == 13 * fleets
    assert Counter(r["kind"] for r in records) == {
        "platform": fleets,
        "change": fleets,
        "hardware": 4 * fleets,
        "software": 4 * fleets,
        "variant": 2 * fleets,
        "bom": fleets,
    }
    assert len({r["id"] for r in records}) == len(records)
    assert len({r["source_id"] for r in envelope["records"]}) == len(records)
    assert normalize_source(envelope["records"], "A") == records
    # Exercise full engineering checks on ordinary sizes; the upper bound verifies generation/schema capacity.
    if fleets < 1000:
        assert verify(records) == []


@pytest.mark.parametrize("fleets", [0, -1, 1001])
def test_size_limits(fleets):
    with pytest.raises(ValueError):
        generate(fleets)


def test_legacy_names_and_compatibility_diversity():
    a, target, _ = generate(2, source="A")
    b, other, _ = generate(2, source="B")
    assert target == other
    hardware_a = next(row["data"] for row in a["records"] if row["entity"] == "hardware")
    hardware_b = next(row["data"] for row in b["records"] if row["entity"] == "hardware")
    assert {"ECU_ID", "HW_REV", "Mass_g"}.issubset(hardware_a)
    assert {"ControllerCode", "HardwareLevel", "Mass_g"}.issubset(hardware_b)
    records = target.documents()
    hardware = [r for r in records if r["kind"] == "hardware"]
    assert {r["hardware_revision"] for r in hardware} == {"B", "C"}
    assert len({r["supplier"] for r in hardware}) == 2
    assert len({r["function"] for r in hardware}) == 4
    assert {r["version"] for r in records if r["kind"] == "software"} == {"2.10.0", "3.0.0"}
    assert len({r["electrical_architecture"] for r in records if r["kind"] == "platform"}) == 2


@pytest.mark.parametrize("schema", ["A", "B"])
@pytest.mark.parametrize("fault", FAULTS)
def test_fault_inputs_preserve_identity_and_isolate_labels(schema, fault):
    envelope, _, truth = generate(2, source=schema)
    for index, row in enumerate(envelope["records"]):
        row["source_id"] = f"supplier-record-{index * 7}"
    before, truth_before = copy.deepcopy(envelope), copy.deepcopy(truth)
    corrupted, label = corrupt_legacy(envelope, fault)
    assert envelope == before and truth == truth_before
    assert label == {"synthetic": True, "fault": fault, "affected_id": label["affected_id"]}
    assert corrupted["synthetic"] is True
    assert set(corrupted) == {"synthetic", "source_schema", "records"}
    assert all(set(row) == {"source_id", "entity", "data"} for row in corrupted["records"])
    assert fault not in json.dumps(corrupted)
    assert len({r["source_id"] for r in corrupted["records"]}) == len(corrupted["records"])
    original = {r["source_id"]: r for r in envelope["records"]}
    id_field = "ECU_ID" if schema == "A" else "ControllerCode"
    for row in corrupted["records"]:
        if row["source_id"] in original:
            assert row["data"][id_field] == original[row["source_id"]]["data"][id_field]
    if fault == "duplicate_record":
        assert len(corrupted["records"]) == len(original) + 1
        assert len(set(r["source_id"] for r in corrupted["records"]) - set(original)) == 1
    elif fault in ["missing_bom_component", "missing_dependency"]:
        assert len(corrupted["records"]) == len(original) - 1
    else:
        assert set(r["source_id"] for r in corrupted["records"]) == set(original)


def test_unsupported_and_ambiguous_inputs(generated):
    envelope = copy.deepcopy(generated[0])
    envelope["synthetic"] = False
    with pytest.raises(ValueError, match="synthetic"):
        corrupt_legacy(envelope, "invalid_interface")
    envelope = copy.deepcopy(generated[0])
    envelope["records"][1]["source_id"] = envelope["records"][0]["source_id"]
    with pytest.raises(ValueError, match="Duplicate source"):
        corrupt_legacy(envelope, "invalid_interface")
    with pytest.raises(ValueError):
        generate(source="unknown")


@pytest.mark.parametrize("schema", ["A", "B"])
def test_cli_exports_separate_input_truth_and_labels(tmp_path, schema):
    output = tmp_path / "inputs" / "legacy.json"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "app.cli",
            "generate",
            "--fleets",
            "2",
            "--source",
            schema,
            "--output",
            str(output),
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    original_bytes = output.read_bytes()
    envelope = json.loads(original_bytes)
    truth_dir = tmp_path / "data" / "ground_truth"
    canonical = json.loads((truth_dir / "legacy_canonical.json").read_text(encoding="utf-8"))
    assert canonical["synthetic"] is True
    assert canonical["records"] == normalize_source(envelope["records"], schema)
    assert (truth_dir / "legacy_mappings.json").exists()
    corrupted_path = tmp_path / "inputs" / "corrupted.json"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "app.cli",
            "inject",
            str(output),
            "--fault",
            "missing_dependency",
            "--output",
            str(corrupted_path),
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    label = json.loads((truth_dir / "corrupted_fault.json").read_text(encoding="utf-8"))
    corrupted = json.loads(corrupted_path.read_text(encoding="utf-8"))
    assert label["synthetic"] is True and label["fault"] == "missing_dependency"
    assert "missing_dependency" not in json.dumps(corrupted)
    assert output.read_bytes() == original_bytes
    surviving_ids = {row["source_id"] for row in corrupted["records"]}
    assert surviving_ids < {row["source_id"] for row in envelope["records"]}
