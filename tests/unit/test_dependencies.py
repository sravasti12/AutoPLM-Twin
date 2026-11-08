"""Focused Phase 3A graph checks; no database or live model required."""

import copy
import random

import networkx as nx
import pytest

from app.dependencies import build_dependency_graph, reverse_dependencies
from app.impact_models import DependencyEdge, EngineeringNode, NodeKind, Origin, RelationshipKind, Resolution
from app.twin import build_twin


def all_edges(product):
    return [data["edge"] for *_, data in product.graph.edges(data=True)]


def affected(result):
    return {path.node for path in result.potentially_affected}


def test_constructs_all_existing_entity_types_and_scoped_assemblies(generated):
    records = generated[1].documents()
    product = build_dependency_graph(records)
    assert isinstance(product.graph, nx.MultiDiGraph)
    for record in records:
        node = product.graph.nodes[("record", record["id"])]["node"]
        assert isinstance(node, EngineeringNode)
        assert node.kind == NodeKind(record["kind"])
        assert node.origin == Origin.EXPLICIT
        assert node.provenance.record_id == record["id"]
    assemblies = [
        data["node"] for _, data in product.graph.nodes(data=True) if data["node"].kind == NodeKind.ASSEMBLY
    ]
    assert len(assemblies) == 2
    assert all(node.origin == Origin.DERIVED and node.key[1] == "F0000-BOM" for node in assemblies)
    assert {edge.kind for edge in all_edges(product)} == set(RelationshipKind)
    assert all(
        isinstance(edge, DependencyEdge) and edge.assessment == "unassessed" for edge in all_edges(product)
    )


def test_parallel_relationship_types_and_variant_bindings_are_retained(generated):
    product = build_dependency_graph(generated[1].documents())
    edges = [
        data["edge"]
        for data in product.graph.get_edge_data(
            ("record", "F0000-brake"), ("record", "F0000-brake-sw")
        ).values()
    ]
    assert len(edges) == 3
    assert {edge.kind for edge in edges} == {RelationshipKind.RUNS, RelationshipKind.DECLARES_COMPATIBLE}
    assert len({edge.key for edge in edges}) == 3
    assert {edge.provenance.context.variant_id for edge in edges if edge.kind == RelationshipKind.RUNS} == {
        "F0000-standard",
        "F0000-touring",
    }


def test_bom_edge_provenance_and_direction_are_exact(generated):
    records = generated[1].documents()
    bom = next(record for record in records if record["kind"] == "bom")
    index = next(index for index, edge in enumerate(bom["edges"]) if edge["child"] == "F0000-brake")
    product = build_dependency_graph(records)
    edge = next(
        edge
        for edge in all_edges(product)
        if edge.kind == RelationshipKind.CONTAINS and edge.target == ("record", "F0000-brake")
    )
    assert edge.source == ("assembly", bom["id"], bom["edges"][index]["parent"])
    assert edge.provenance.source_field == f"/edges/{index}"
    assert edge.provenance.record_id == bom["id"] and edge.provenance.record_kind == "bom"
    assert edge.provenance.context.bom_id == bom["id"]
    assert edge.provenance.context.child_id == "F0000-brake"
    assert edge.provenance.context.quantity == bom["edges"][index]["quantity"]
    assert edge.provenance.context.revision == bom["edges"][index]["revision"]
    assert edge.origin == Origin.EXPLICIT and edge.resolution == Resolution.RESOLVED


def test_explicit_topology_has_nonpropagating_derived_reverse_edge(generated):
    product = build_dependency_graph(generated[1].documents())
    edges = [
        edge
        for edge in all_edges(product)
        if edge.kind == RelationshipKind.COMMUNICATES_WITH
        and edge.provenance.source_field == "/network_topology/0"
    ]
    assert len(edges) == 2
    assert {edge.origin for edge in edges} == {Origin.EXPLICIT, Origin.DERIVED}
    assert edges[0].source == edges[1].target and edges[0].target == edges[1].source
    assert all(not edge.propagates and edge.provenance.context.platform_id == "F0000-P" for edge in edges)


@pytest.mark.parametrize("case", ["software", "platform", "bom", "change", "network"])
def test_dangling_references_are_unassessed_and_do_not_propagate(generated, case):
    records = generated[1].documents()
    if case == "software":
        next(r for r in records if r["kind"] == "software")["dependencies"] = ["missing"]
    elif case == "platform":
        next(r for r in records if r["kind"] == "variant")["platform_id"] = "missing"
    elif case == "bom":
        next(r for r in records if r["kind"] == "bom")["edges"][-1]["child"] = "missing"
    elif case == "change":
        next(r for r in records if r["kind"] == "change")["affected_parts"] = ["missing"]
    else:
        next(r for r in records if r["kind"] == "platform")["network_topology"][0] = [
            "missing",
            "F0000-brake",
        ]
    product = build_dependency_graph(records)
    assert product.graph.nodes[("record", "missing")]["node"].kind == NodeKind.UNKNOWN
    assert any(
        issue.code == "DANGLING_REFERENCE"
        and issue.referenced_id == "missing"
        and issue.assessment == "unassessed"
        for issue in product.issues
    )
    incident = [edge for edge in all_edges(product) if ("record", "missing") in (edge.source, edge.target)]
    assert incident and all(
        edge.resolution == Resolution.DANGLING and not edge.propagates for edge in incident
    )
    with pytest.raises(ValueError):
        reverse_dependencies(product, "missing")


def test_duplicate_ids_never_select_an_arbitrary_record(generated):
    records = generated[1].documents()
    duplicate = copy.deepcopy(next(r for r in records if r["id"] == "F0000-brake"))
    duplicate["lifecycle"] = "draft"
    records.append(duplicate)
    product = build_dependency_graph(records)
    assert product.graph.nodes[("record", duplicate["id"])]["node"].kind == NodeKind.UNKNOWN
    assert any(issue.code == "DUPLICATE_ID" for issue in product.issues)
    assert any(edge.resolution == Resolution.AMBIGUOUS for edge in all_edges(product))
    assert product.to_dict() == build_dependency_graph(list(reversed(records))).to_dict()
    with pytest.raises(ValueError):
        reverse_dependencies(product, duplicate["id"])


def test_repeated_references_are_ambiguous_parallel_edges(generated):
    records = generated[1].documents()
    next(r for r in records if r["id"] == "F0000-brake-sw")["dependencies"] = ["F0000-gateway-sw"] * 2
    product = build_dependency_graph(records)
    edges = [edge for edge in all_edges(product) if edge.kind == RelationshipKind.REQUIRES]
    assert len(edges) == 2 and len({edge.key for edge in edges}) == 2
    assert all(edge.resolution == Resolution.AMBIGUOUS and not edge.propagates for edge in edges)
    assert any(issue.code == "AMBIGUOUS_RELATIONSHIP" for issue in product.issues)


def test_wrong_entity_type_and_uninstalled_binding_are_not_traversable(generated):
    records = generated[1].documents()
    variant = next(r for r in records if r["kind"] == "variant")
    variant["platform_id"] = "F0000-brake-sw"
    variant["installed_ecus"].remove("F0000-brake")
    product = build_dependency_graph(records)
    assert any(issue.code == "UNSUPPORTED_REFERENCE" for issue in product.issues)
    assert any(issue.code == "AMBIGUOUS_RELATIONSHIP" for issue in product.issues)
    assert all(
        not edge.propagates
        for edge in all_edges(product)
        if edge.provenance.record_id == variant["id"]
        and edge.kind in {RelationshipKind.RUNS, RelationshipKind.CONFIGURES}
        and edge.target == ("record", "F0000-brake-sw")
    )


@pytest.mark.parametrize("case", ["software", "bom"])
def test_cycles_are_reported_and_reverse_traversal_terminates(generated, case):
    records = generated[1].documents()
    if case == "software":
        next(r for r in records if r["id"] == "F0000-gateway-sw")["dependencies"] = ["F0000-brake-sw"]
    else:
        bom = next(r for r in records if r["kind"] == "bom")
        bom["edges"].append(
            {"parent": "F0000-controls", "child": bom["assembly_id"], "quantity": 1, "revision": "B"}
        )
    product = build_dependency_graph(records)
    assert any(issue.code == "DEPENDENCY_CYCLE" for issue in product.issues)
    seed = "F0000-gateway-sw" if case == "software" else "F0000-brake"
    result = reverse_dependencies(product, seed)
    assert not result.truncated
    assert len({(p.node, p.variant_context) for p in result.potentially_affected}) == len(
        result.potentially_affected
    )
    assert result.seed not in affected(result)


def test_reverse_dependency_discovery_and_explainable_paths(generated):
    product = build_dependency_graph(generated[1].documents())
    result = reverse_dependencies(product, "F0000-gateway-sw")
    assert {
        ("record", key)
        for key in [
            "F0000-brake-sw",
            "F0000-brake",
            "F0000-gateway",
            "F0000-standard",
            "F0000-touring",
            "F0000-BOM",
        ]
    }.issubset(affected(result))
    assert ("record", "F0000-cluster") not in affected(result), (
        "Communication alone must not propagate impact"
    )
    for path in result.potentially_affected:
        assert path.edges[0].source == path.node
        assert path.edges[-1].target == result.seed
        assert all(left.target == right.source for left, right in zip(path.edges, path.edges[1:]))
        assert all(edge.propagates and edge.provenance.source_field.startswith("/") for edge in path.edges)
    assert result.assessment == "potential_only"


def test_construction_traversal_and_twin_fingerprint_are_deterministic(generated):
    records = generated[1].documents()
    original = copy.deepcopy(records)
    fingerprint = build_twin(records, "F0000-standard")["fingerprint"]
    product = build_dependency_graph(records)
    shuffled = copy.deepcopy(records)
    random.Random(71).shuffle(shuffled)
    other = build_dependency_graph(shuffled)
    assert product.to_dict() == other.to_dict()
    assert (
        reverse_dependencies(product, "F0000-brake").model_dump()
        == reverse_dependencies(other, "F0000-brake").model_dump()
    )
    assert records == original
    assert build_twin(records, "F0000-standard")["fingerprint"] == fingerprint
    with pytest.raises(nx.NetworkXError):
        product.graph.add_node("unexpected")


def test_variant_context_does_not_leak_through_shared_hardware(generated):
    records = generated[1].documents()
    alternative = copy.deepcopy(next(r for r in records if r["id"] == "F0000-brake-sw"))
    alternative["id"] = "F0000-brake-sw-alternative"
    records.append(alternative)
    next(r for r in records if r["id"] == "F0000-brake")["compatible_software"].append(alternative["id"])
    next(r for r in records if r["id"] == "F0000-touring")["software_configuration"]["F0000-brake"] = (
        alternative["id"]
    )
    result = reverse_dependencies(build_dependency_graph(records), "F0000-brake-sw")
    assert ("record", "F0000-standard") in affected(result)
    assert ("record", "F0000-touring") not in affected(result)
    assert ("record", "F0000-brake") in affected(result)


def test_compatibility_declaration_does_not_imply_dependency_or_approval(generated):
    records = generated[1].documents()
    spare = copy.deepcopy(next(r for r in records if r["kind"] == "software"))
    spare["id"] = "uninstalled-software"
    spare["supported_hardware_revisions"] = ["Z"]
    records.append(spare)
    next(r for r in records if r["kind"] == "hardware")["compatible_software"].append(spare["id"])
    product = build_dependency_graph(records)
    assert reverse_dependencies(product, spare["id"]).potentially_affected == ()
    assert all(edge.assessment == "unassessed" for edge in all_edges(product))


@pytest.mark.parametrize("case", ["unsupported_entity", "unknown_relationship"])
def test_unsupported_records_or_relationships_remain_unassessed(generated, case):
    records = generated[1].documents()
    hardware = next(r for r in records if r["kind"] == "hardware")
    if case == "unsupported_entity":
        hardware["kind"] = "mechanical_part"
    else:
        hardware["unknown_relation"] = ["unmodeled"]
    product = build_dependency_graph(records)
    assert product.graph.nodes[("record", hardware["id"])]["node"].kind == NodeKind.UNKNOWN
    assert any(
        issue.code in {"UNSUPPORTED_RECORD", "INVALID_RECORD"} and issue.assessment == "unassessed"
        for issue in product.issues
    )


def test_feature_relationships_are_explicitly_unassessed(generated):
    product = build_dependency_graph(generated[1].documents())
    assert any(
        issue.code == "UNASSESSED_RELATIONSHIP" and issue.provenance.source_field == "/feature_dependencies"
        for issue in product.issues
    )
    assert reverse_dependencies(product, "F0000-brake").unassessed == product.issues


@pytest.mark.parametrize("setting", [{"max_depth": 1}, {"max_entities": 1}])
def test_traversal_limits_are_reported(generated, setting):
    result = reverse_dependencies(
        build_dependency_graph(generated[1].documents()), "F0000-gateway-sw", **setting
    )
    assert result.truncated
    if "max_entities" in setting:
        assert len(result.potentially_affected) == 1


@pytest.mark.parametrize("value", [0, -1, True, 1.5])
def test_invalid_traversal_limits_are_rejected(generated, value):
    with pytest.raises(ValueError):
        reverse_dependencies(build_dependency_graph(generated[1].documents()), "F0000-brake", max_depth=value)


def test_bom_assembly_identity_collision_is_not_silently_resolved(generated):
    records = generated[1].documents()
    bom = next(r for r in records if r["kind"] == "bom")
    bom["assembly_id"] = "F0000-brake"
    product = build_dependency_graph(records)
    assert any(issue.code == "AMBIGUOUS_RELATIONSHIP" for issue in product.issues)
    root = next(edge for edge in all_edges(product) if edge.kind == RelationshipKind.BOM_ROOT)
    assert root.resolution == Resolution.AMBIGUOUS and not root.propagates


def test_bom_assemblies_are_scoped_to_each_bom(generated):
    records = generated[1].documents()
    copied = copy.deepcopy(next(r for r in records if r["kind"] == "bom"))
    copied["id"] = "second-bom"
    records.append(copied)
    product = build_dependency_graph(records)
    assert ("assembly", "F0000-BOM", copied["assembly_id"]) in product.graph
    assert ("assembly", "second-bom", copied["assembly_id"]) in product.graph
    result = reverse_dependencies(product, "F0000-brake")
    assert {("record", "F0000-BOM"), ("record", "second-bom")}.issubset(affected(result))


def test_unrooted_bom_relationship_is_retained_as_unassessed(generated):
    records = generated[1].documents()
    bom = next(r for r in records if r["kind"] == "bom")
    bom["edges"][-1]["parent"] = "orphan"
    product = build_dependency_graph(records)
    assert any(issue.code == "UNASSESSED_BOM_CONTEXT" for issue in product.issues)
    edges = [edge for edge in all_edges(product) if edge.source == ("assembly", bom["id"], "orphan")]
    assert edges and all(not edge.propagates and edge.resolution == Resolution.UNSUPPORTED for edge in edges)


def test_repeated_network_pairs_remain_ambiguous(generated):
    records = generated[1].documents()
    platform = next(r for r in records if r["kind"] == "platform")
    platform["network_topology"].append(list(reversed(platform["network_topology"][0])))
    product = build_dependency_graph(records)
    assert any(
        issue.code == "AMBIGUOUS_RELATIONSHIP"
        and issue.provenance.source_field.startswith("/network_topology/")
        for issue in product.issues
    )
