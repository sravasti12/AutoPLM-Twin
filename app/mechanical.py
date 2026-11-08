"""Mechanical record/BOM integrity and product snapshots. No physical-fit inference."""

import copy
import hashlib
import json
from collections import Counter
from datetime import date

import networkx as nx

from app.dependencies import build_dependency_graph
from app.impact_models import NodeKind, RelationshipKind
from app.models import Finding


def verify_mechanical(records: list[dict], as_of: date) -> list[Finding]:
    """Called with schema-normalized records; electronic compatibility stays in verify()."""
    by_id = {record["id"]: record for record in records}
    mechanical = {
        key: value for key, value in by_id.items() if value["kind"] in {"assembly", "mechanical_part"}
    }
    findings: list[Finding] = []

    def emit(rule, ids, expected, actual, evidence=None):
        identifiers = sorted(set(ids))
        key = hashlib.sha256(json.dumps([rule, identifiers, actual], sort_keys=True).encode()).hexdigest()[
            :16
        ]
        findings.append(
            Finding(
                finding_id=key,
                rule_id=rule,
                affected_records=identifiers,
                expected=str(expected),
                actual=str(actual),
                evidence=evidence or {},
                remediation="Correct product records/BOM or supply an approved engineering change.",
            )
        )

    for record in mechanical.values():
        if record["lifecycle"] != "released":
            emit("MECH_LIFECYCLE", [record["id"]], "released", record["lifecycle"])
    for variant in (r for r in records if r["kind"] == "variant"):
        selections = variant.get("mechanical_bom_ids", [])
        if len(selections) != len(set(selections)):
            emit("MECH_VARIANT_DUPLICATE_BOM", [variant["id"]], "unique BOM selections", selections)
        for identifier in selections:
            bom = by_id.get(identifier)
            if not bom or bom["kind"] != "bom":
                emit(
                    "MECH_VARIANT_BOM_REFERENCE",
                    [variant["id"], identifier],
                    "existing BOM",
                    "missing/wrong type",
                )
            elif bom.get("domain", "electronic") != "mechanical":
                emit("MECH_VARIANT_BOM_DOMAIN", [variant["id"], identifier], "mechanical BOM", "electronic")
    for bom in (r for r in records if r["kind"] == "bom" and r.get("domain") == "mechanical"):
        bid, root = bom["id"], bom["assembly_id"]
        root_record = by_id.get(root)
        if not root_record or root_record["kind"] != "assembly":
            emit("MECH_BOM_ROOT", [bid, root], "explicit assembly root", "missing/wrong type")
        if not bom["edges"]:
            emit("MECH_BOM_EMPTY", [bid], "declared component relationships", "empty")
        graph = nx.DiGraph()
        graph.add_node(root)
        counts = Counter((edge["parent"], edge["child"]) for edge in bom["edges"])
        for pair, count in sorted(counts.items()):
            if count > 1:
                emit("MECH_BOM_DUPLICATE_EDGE", [bid, *pair], "unique parent-child pair", count)
        for index, edge in enumerate(bom["edges"]):
            graph.add_edge(edge["parent"], edge["child"], quantity=edge["quantity"])
            parent, child = by_id.get(edge["parent"]), by_id.get(edge["child"])
            evidence = {"bom_id": bid, "source_field": f"/edges/{index}", **edge}
            if not parent or parent["kind"] != "assembly":
                emit(
                    "MECH_BOM_PARENT",
                    [bid, edge["parent"]],
                    "explicit assembly parent",
                    "missing/wrong type",
                    evidence,
                )
            if not child:
                emit(
                    "MECH_BOM_MISSING_COMPONENT",
                    [bid, edge["child"]],
                    "existing component",
                    "missing",
                    evidence,
                )
            elif child["kind"] not in {"assembly", "mechanical_part", "hardware"}:
                emit(
                    "MECH_BOM_CHILD_TYPE",
                    [bid, child["id"]],
                    "physical component or assembly",
                    child["kind"],
                    evidence,
                )
            else:
                revision = child["hardware_revision"] if child["kind"] == "hardware" else child["revision"]
                if edge["revision"] != revision:
                    emit("MECH_BOM_REVISION", [bid, child["id"]], revision, edge["revision"], evidence)
        reachable = {root, *nx.descendants(graph, root)}
        if set(graph) != reachable:
            emit(
                "MECH_BOM_STRUCTURE",
                [bid],
                "all relationships rooted at assembly",
                sorted(set(graph) - reachable),
            )
        if not nx.is_directed_acyclic_graph(graph):
            emit("MECH_BOM_CYCLE", [bid], "acyclic structure", "cycle")
        else:
            totals = {root: 1.0}
            for node in nx.topological_sort(graph):
                for child_id in graph.successors(node):
                    totals[child_id] = (
                        totals.get(child_id, 0) + totals.get(node, 0) * graph[node][child_id]["quantity"]
                    )
            leaves = sum(totals.get(node, 0) for node in graph if graph.out_degree(node) == 0)
            if abs(leaves - bom["expected_leaf_quantity"]) > 1e-9:
                emit("MECH_BOM_ROLLUP", [bid], bom["expected_leaf_quantity"], leaves)
        if bom["lifecycle"] != "released" or bom["effective_date"] > as_of.isoformat():
            emit("MECH_BOM_EFFECTIVITY", [bid], "released and effective BOM", bom["effective_date"])
    for change in (r for r in records if r["kind"] == "change"):
        for identifier in change["affected_parts"]:
            part = mechanical.get(identifier)
            if not part:
                continue
            # Mechanical revision identifiers are opaque: do not invent an ordering.
            if change["old_revision"] == change["new_revision"]:
                emit(
                    "MECH_CHANGE_PROGRESSION",
                    [change["id"], identifier],
                    "distinct revisions",
                    change["new_revision"],
                )
            effective = change["effective_date"] <= as_of.isoformat()
            if change["approval_status"] != "approved" or not effective:
                if part["revision"] == change["new_revision"]:
                    emit(
                        "MECH_CHANGE_APPROVAL",
                        [change["id"], identifier],
                        "approved effective change",
                        "not approved/effective",
                    )
            elif part["revision"] != change["new_revision"]:
                emit(
                    "MECH_CHANGE_REVISION",
                    [change["id"], identifier],
                    change["new_revision"],
                    part["revision"],
                )
    return findings


def build_mechanical_structure(records: list[dict], bom_ids: list[str]) -> dict:
    """Reuse graph evidence; retain invalid/missing declarations for comparison too."""
    product = build_dependency_graph(records)
    selected = set(bom_ids)
    components: dict[str, dict] = {}
    boms: dict[str, dict] = {}
    relationships: list[dict] = []
    by_id = {r["id"]: r for r in records}
    for identifier in sorted(selected):
        node = product.graph.nodes.get(("record", identifier), {}).get("node")
        boms[identifier] = (
            copy.deepcopy(by_id[identifier])
            if node and node.kind == NodeKind.BOM
            else {"id": identifier, "kind": "unknown", "assessment": "unassessed"}
        )
    for *_, data in product.graph.edges(data=True):
        edge = data["edge"]
        if edge.provenance.context.bom_id not in selected or edge.kind not in {
            RelationshipKind.BOM_ROOT,
            RelationshipKind.CONTAINS,
        }:
            continue
        relationships.append(edge.model_dump(mode="json"))
        for key in (edge.source, edge.target):
            node = product.graph.nodes[key]["node"]
            if node.kind == NodeKind.BOM:
                continue
            components[node.entity_id] = (
                copy.deepcopy(by_id[node.entity_id])
                if (
                    node.origin == "explicit"
                    and node.kind in {NodeKind.MECHANICAL_PART, NodeKind.ASSEMBLY, NodeKind.HARDWARE}
                )
                else {"id": node.entity_id, "kind": "unknown", "assessment": "unassessed"}
            )
    changes = {
        record["id"]: copy.deepcopy(record)
        for record in records
        if record["kind"] == "change"
        and set(record["affected_parts"]) & set(components)
        and product.graph.nodes[("record", record["id"])]["node"].kind == NodeKind.CHANGE
    }
    return {
        "bom_ids": sorted(selected),
        "boms": dict(sorted(boms.items())),
        "components": dict(sorted(components.items())),
        "changes": dict(sorted(changes.items())),
        "relationships": sorted(relationships, key=lambda edge: edge["key"]),
        "unassessed": [
            issue.model_dump(mode="json")
            for issue in product.issues
            if issue.provenance.record_id in selected
        ],
    }
