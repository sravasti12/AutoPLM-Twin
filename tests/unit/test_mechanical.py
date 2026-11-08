"""Synthetic mixed-product modelling, without physical compatibility assumptions."""

import copy
import random

import pytest
from pydantic import ValidationError

from app.data import generate
from app.dependencies import build_dependency_graph, reverse_dependencies
from app.impact_models import NodeKind, Origin, RelationshipKind, Resolution
from app.mapping import baseline, profile, transform
from app.models import Assembly, Dataset, MechanicalPart
from app.repository import digest
from app.twin import build_twin, compare_twins
from app.verification import verify


@pytest.fixture
def mechanical_records(generated):
    records = generated[1].documents()
    records.extend(
        [
            {
                "kind": "mechanical_part",
                "id": "M-MOUNT",
                "part_number": "SYN-MOUNT",
                "revision": "R1",
                "mass_kg": 0.4,
            },
            {"kind": "assembly", "id": "M-CHASSIS", "part_number": "SYN-CHASSIS", "revision": "R1"},
            {"kind": "assembly", "id": "M-FRONT", "part_number": "SYN-FRONT", "revision": "R1"},
            {
                "kind": "bom",
                "id": "M-BOM",
                "domain": "mechanical",
                "assembly_id": "M-CHASSIS",
                "edges": [
                    {"parent": "M-CHASSIS", "child": "M-FRONT", "quantity": 2, "revision": "R1"},
                    {"parent": "M-FRONT", "child": "M-MOUNT", "quantity": 3, "revision": "R1"},
                ],
                "effective_date": "2025-02-01",
                "expected_leaf_quantity": 6,
            },
        ]
    )
    next(r for r in records if r["id"] == "F0000-standard")["mechanical_bom_ids"] = ["M-BOM"]
    return Dataset.model_validate({"records": records}).documents()


def test_typed_records_and_quantity_rollup(mechanical_records):
    assert verify(mechanical_records) == []
    parts = [
        r
        for r in Dataset.model_validate({"records": mechanical_records}).records
        if isinstance(r, (MechanicalPart, Assembly))
    ]
    assert len(parts) == 3
    assert MechanicalPart(id="unknown-mass", part_number="SYN", revision="rev-1").mass_kg is None


def test_optional_identity_defaults_preserve_present_values_and_required_fields(mechanical_records):
    variants = [r for r in mechanical_records if r["kind"] == "variant"]
    plan = baseline("variant", profile(variants))
    selected = next(r for r in variants if r.get("mechanical_bom_ids"))
    unselected = next(r for r in variants if not r.get("mechanical_bom_ids"))
    assert transform(selected, plan)["mechanical_bom_ids"] == ["M-BOM"]
    assert "mechanical_bom_ids" not in transform(unselected, plan)
    missing_required = copy.deepcopy(selected)
    del missing_required["platform_id"]
    with pytest.raises(KeyError):
        transform(missing_required, plan)
    field = next(field for field in plan.fields if field.target == "mechanical_bom_ids")
    field.source = "invented_alias"
    with pytest.raises(KeyError):
        transform(selected, plan)


@pytest.mark.parametrize("revision", ["", " ", "A B"])
def test_invalid_mechanical_revision_schema(revision):
    with pytest.raises(ValidationError):
        MechanicalPart(id="part", part_number="SYN", revision=revision)


@pytest.mark.parametrize("mass", [0, -1, float("nan"), float("inf")])
def test_invalid_mechanical_mass_schema(mass):
    with pytest.raises(ValidationError):
        MechanicalPart(id="part", part_number="SYN", revision="R1", mass_kg=mass)


@pytest.mark.parametrize("quantity", [0, -1, float("nan"), float("inf")])
def test_invalid_bom_quantities_remain_schema_failures(mechanical_records, quantity):
    next(r for r in mechanical_records if r["id"] == "M-BOM")["edges"][0]["quantity"] = quantity
    assert any(
        f.rule_id == "SCHEMA_INVALID" and "M-BOM" in f.affected_records for f in verify(mechanical_records)
    )


@pytest.mark.parametrize(
    "mutation,rule",
    [
        ("missing_root", "MECH_BOM_ROOT"),
        ("missing_part", "MECH_BOM_MISSING_COMPONENT"),
        ("missing_subassembly", "MECH_BOM_PARENT"),
        ("revision", "MECH_BOM_REVISION"),
        ("duplicate", "MECH_BOM_DUPLICATE_EDGE"),
        ("cycle", "MECH_BOM_CYCLE"),
        ("orphan", "MECH_BOM_STRUCTURE"),
        ("part_parent", "MECH_BOM_PARENT"),
        ("software_child", "MECH_BOM_CHILD_TYPE"),
        ("rollup", "MECH_BOM_ROLLUP"),
        ("empty", "MECH_BOM_EMPTY"),
        ("future", "MECH_BOM_EFFECTIVITY"),
        ("lifecycle", "MECH_LIFECYCLE"),
    ],
)
def test_mechanical_bom_integrity(mechanical_records, mutation, rule):
    records = mechanical_records
    bom = next(r for r in records if r["id"] == "M-BOM")
    if mutation in {"missing_root", "missing_part", "missing_subassembly"}:
        missing = {"missing_root": "M-CHASSIS", "missing_part": "M-MOUNT", "missing_subassembly": "M-FRONT"}[
            mutation
        ]
        records[:] = [r for r in records if r["id"] != missing]
    elif mutation == "revision":
        bom["edges"][-1]["revision"] = "unknown-revision"
    elif mutation == "duplicate":
        bom["edges"].append(copy.deepcopy(bom["edges"][-1]))
    elif mutation == "cycle":
        bom["edges"].append({"parent": "M-FRONT", "child": "M-CHASSIS", "quantity": 1, "revision": "R1"})
    elif mutation == "orphan":
        records.append({"kind": "assembly", "id": "M-ORPHAN", "part_number": "SYN-ORPHAN", "revision": "R1"})
        bom["edges"][-1]["parent"] = "M-ORPHAN"
    elif mutation == "part_parent":
        bom["edges"][-1]["parent"] = "M-MOUNT"
    elif mutation == "software_child":
        bom["edges"][-1]["child"] = "F0000-brake-sw"
    elif mutation == "rollup":
        bom["expected_leaf_quantity"] = 99
    elif mutation == "empty":
        bom["edges"] = []
    elif mutation == "future":
        bom["effective_date"] = "2030-01-01"
    else:
        next(r for r in records if r["id"] == "M-MOUNT")["lifecycle"] = "draft"
    assert rule in {finding.rule_id for finding in verify(records)}


@pytest.mark.parametrize(
    "selection,rule",
    [
        (["missing"], "MECH_VARIANT_BOM_REFERENCE"),
        (["M-BOM", "M-BOM"], "MECH_VARIANT_DUPLICATE_BOM"),
        (["F0000-BOM"], "MECH_VARIANT_BOM_DOMAIN"),
    ],
)
def test_explicit_variant_applicability_validation(mechanical_records, selection, rule):
    next(r for r in mechanical_records if r["id"] == "F0000-standard")["mechanical_bom_ids"] = selection
    assert rule in {finding.rule_id for finding in verify(mechanical_records)}


def test_shared_part_definitions_have_path_weighted_quantities(mechanical_records):
    bom = next(r for r in mechanical_records if r["id"] == "M-BOM")
    bom["edges"].append({"parent": "M-CHASSIS", "child": "M-MOUNT", "quantity": 1, "revision": "R1"})
    bom["expected_leaf_quantity"] = 7
    assert verify(mechanical_records) == []


def test_mechanical_graph_provenance_and_variant_discovery(mechanical_records):
    product = build_dependency_graph(mechanical_records)
    assert product.graph.nodes[("record", "M-MOUNT")]["node"].kind == NodeKind.MECHANICAL_PART
    assert product.graph.nodes[("record", "M-FRONT")]["node"].origin == Origin.EXPLICIT
    result = reverse_dependencies(product, "M-MOUNT")
    nodes = {path.node for path in result.potentially_affected}
    assert {("record", key) for key in ["M-FRONT", "M-CHASSIS", "M-BOM", "F0000-standard"]}.issubset(nodes)
    assert ("record", "F0000-touring") not in nodes
    edge = next(
        data["edge"]
        for *_, data in product.graph.edges(data=True)
        if data["edge"].source == ("record", "F0000-standard") and data["edge"].target == ("record", "M-BOM")
    )
    assert edge.kind == RelationshipKind.CONFIGURES and edge.origin == Origin.EXPLICIT
    assert edge.provenance.source_field == "/mechanical_bom_ids/0"
    assert edge.provenance.context.variant_id == "F0000-standard"
    containment = next(
        data["edge"]
        for *_, data in product.graph.edges(data=True)
        if data["edge"].target == ("record", "M-MOUNT")
    )
    assert containment.provenance.context.quantity == 3
    assert containment.provenance.context.revision == "R1"


def test_mechanical_dangling_reference_is_not_invented(mechanical_records):
    mechanical_records[:] = [r for r in mechanical_records if r["id"] != "M-MOUNT"]
    product = build_dependency_graph(mechanical_records)
    edge = next(
        data["edge"]
        for *_, data in product.graph.edges(data=True)
        if data["edge"].target == ("record", "M-MOUNT")
    )
    assert edge.resolution == Resolution.DANGLING and not edge.propagates
    assert any(issue.referenced_id == "M-MOUNT" for issue in product.issues)
    twin = build_twin(mechanical_records, "F0000-standard")
    assert twin["product_structure"]["components"]["M-MOUNT"]["assessment"] == "unassessed"


def test_mechanical_twin_structure_and_determinism(mechanical_records, generated):
    original = copy.deepcopy(mechanical_records)
    twin = build_twin(mechanical_records, "F0000-standard")
    assert twin["schema_version"] == "1.1"
    structure = twin["product_structure"]
    assert set(structure["components"]) == {"M-MOUNT", "M-CHASSIS", "M-FRONT"}
    assert structure["boms"]["M-BOM"]["edges"][0]["quantity"] == 2
    shuffled = copy.deepcopy(mechanical_records)
    random.Random(17).shuffle(shuffled)
    assert twin == build_twin(shuffled, "F0000-standard")
    assert mechanical_records == original
    assert build_twin(mechanical_records, "F0000-touring") == build_twin(
        generated[1].documents(), "F0000-touring"
    )


def test_mechanical_revision_changes_have_precise_twin_paths(mechanical_records):
    before = build_twin(mechanical_records, "F0000-standard")
    next(r for r in mechanical_records if r["id"] == "M-MOUNT")["revision"] = "R2"
    differences = compare_twins(before, build_twin(mechanical_records, "F0000-standard"))
    assert differences == [
        {"path": "/product_structure/components/M-MOUNT/revision", "source": "R1", "target": "R2"}
    ]
    assert "MECH_BOM_REVISION" in {finding.rule_id for finding in verify(mechanical_records)}


@pytest.mark.parametrize(
    "status,revision,rule",
    [
        ("approved", "R1", None),
        ("pending", "R1", "MECH_CHANGE_APPROVAL"),
        ("approved", "R2", "MECH_CHANGE_REVISION"),
    ],
)
def test_mechanical_changes_use_catalog_revision_not_software_rules(
    mechanical_records, status, revision, rule
):
    change = copy.deepcopy(next(r for r in mechanical_records if r["kind"] == "change"))
    change.update(
        id="M-CHANGE",
        affected_parts=["M-MOUNT"],
        old_revision="R0",
        new_revision=revision,
        approval_status=status,
    )
    mechanical_records.append(change)
    findings = verify(mechanical_records)
    if rule:
        assert rule in {finding.rule_id for finding in findings}
    else:
        assert findings == []
    product = build_dependency_graph(mechanical_records)
    edge = next(
        data["edge"]
        for *_, data in product.graph.edges(data=True)
        if data["edge"].source == ("record", "M-CHANGE")
    )
    assert edge.resolution == Resolution.RESOLVED and not edge.propagates
    assert "M-CHANGE" in build_twin(mechanical_records, "F0000-standard")["product_structure"]["changes"]


def test_mixed_product_migration_and_promotion_preserve_safeguards(service, mechanical_records):
    envelope = {
        "synthetic": True,
        "source_schema": "A",
        "records": [
            {"source_id": f"mixed:{index:04}", "entity": record["kind"], "data": copy.deepcopy(record)}
            for index, record in enumerate(mechanical_records)
        ],
    }
    job = service.migrate(envelope)
    assert job["status"] == "verified" and job["validation"]["passed"]
    assert service.migrate(envelope)["_id"] == job["_id"]
    source = service.repo.source(job["_id"])
    service.db.staging_records.update_one(
        {"job_id": job["_id"], "record.id": "M-MOUNT"}, {"$set": {"record.revision": "R2"}}
    )
    validation = service.validate(job["_id"])
    assert not validation["passed"] and validation["twin_differences"]
    assert any(finding["rule_id"] == "MECH_BOM_REVISION" for finding in validation["findings"])
    service.db.migration_jobs.update_one({"_id": job["_id"]}, {"$set": {"status": "verified"}})
    assert service.repo.job(job["_id"])["staging_digest"] == digest(service.repo.records(job["_id"]))
    with pytest.raises(ValueError, match="failed revalidation"):
        service.promote(job["_id"], "engineer")
    proposal = service.propose_repair(job["_id"])
    service.decide_repair(proposal["_id"], True, "engineer")
    assert service.promote(job["_id"], "engineer")["status"] == "approved"
    approved = service.repo.approved_records(job["_id"])
    assert len([r for r in approved if r["kind"] == "assembly"]) == 2
    assert len([r for r in approved if r["kind"] == "mechanical_part"]) == 1
    assert service.repo.source(job["_id"]) == source


def test_legacy_ecu_fingerprints_are_byte_for_byte_unchanged():
    records = generate(2)[1].documents()
    expected = {
        "F0000-standard": "7fe9acfe2ef1e46c4bca359dbc6077adfab01822a1f28b7561badd9da1ed568d",
        "F0000-touring": "37504a4cd2b3096d9fd19ef9a13c07a09144857461f0a790a3c8a92bfa7b8d81",
        "F0001-standard": "9126aad4aebf87151368f5217a4109b4545cc6df801fed6e8adee39b218e4490",
        "F0001-touring": "e2f3f44d225fc3a6b078d0b10d7f9c011cab0356d1635ffebf8b4a17c067c560",
    }
    for variant, fingerprint in expected.items():
        twin = build_twin(records, variant)
        assert twin["fingerprint"] == fingerprint
        assert "product_structure" not in twin and twin["schema_version"] == "1.0"
    assert all("mechanical_bom_ids" not in r for r in records if r["kind"] == "variant")
    assert all("domain" not in r for r in records if r["kind"] == "bom")
