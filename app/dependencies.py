"""Pure typed product graph. Connectivity never certifies compatibility or approval."""

import hashlib
import json
from collections import Counter, defaultdict, deque
from dataclasses import dataclass

import networkx as nx
from pydantic import ValidationError

from app.impact_models import (
    DependencyEdge,
    DependencyTraversal,
    EngineeringNode,
    GraphIssue,
    ImpactPath,
    NodeKey,
    NodeKind,
    Origin,
    Provenance,
    RelationshipContext,
    RelationshipKind,
    Resolution,
)
from app.mapping import MODELS

# Dependent -> dependency. Constraints, communication and historical annotations
# are represented, but do not propagate structural impact by default.
PROPAGATING = frozenset(
    {
        RelationshipKind.BOM_ROOT,
        RelationshipKind.CONTAINS,
        RelationshipKind.BASED_ON,
        RelationshipKind.INSTALLS,
        RelationshipKind.RUNS,
        RelationshipKind.CONFIGURES,
        RelationshipKind.REQUIRES,
        RelationshipKind.RELEASED_UNDER,
    }
)


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def pointer(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


@dataclass(frozen=True)
class EngineeringDependencyGraph:
    graph: nx.MultiDiGraph
    issues: tuple[GraphIssue, ...]

    def to_dict(self) -> dict:
        return {
            "schema_version": "1.0",
            "nodes": [self.graph.nodes[key]["node"].model_dump(mode="json") for key in sorted(self.graph)],
            "edges": sorted(
                [data["edge"].model_dump(mode="json") for *_, data in self.graph.edges(data=True)],
                key=lambda edge: edge["key"],
            ),
            "unassessed": [issue.model_dump(mode="json") for issue in self.issues],
        }


def build_dependency_graph(records: list[dict]) -> EngineeringDependencyGraph:
    graph = nx.MultiDiGraph()
    issues: list[GraphIssue] = []
    groups = defaultdict(list)
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("id"), str) or not record["id"]:
            raise ValueError("Graph records require nonempty string identifiers")
        groups[record["id"]].append(record)
    valid = {}

    def evidence(record, field, **context):
        return Provenance(
            record_id=record["id"],
            record_kind=record["kind"],
            source_field=field,
            context=RelationshipContext(**context),
        )

    def issue(code, message, provenance, referenced=None):
        issues.append(GraphIssue(code=code, message=message, provenance=provenance, referenced_id=referenced))

    for identifier, candidates in sorted(groups.items()):
        record = candidates[0] if len(candidates) == 1 else {"id": identifier, "kind": "unknown"}
        provenance = Provenance(
            record_id=identifier, record_kind=str(record.get("kind", "unknown")), source_field="/id"
        )
        kind = NodeKind.UNKNOWN
        if len(candidates) != 1:
            issue(
                "DUPLICATE_ID",
                "Ambiguous engineering identity; no candidate is selected.",
                provenance,
                identifier,
            )
        elif record.get("kind") not in MODELS:
            issue(
                "UNSUPPORTED_RECORD", "Unsupported entity schema; relationships are unassessed.", provenance
            )
        else:
            try:
                parsed = MODELS[record["kind"]].model_validate(record).model_dump(mode="json")
                valid[identifier] = parsed
                kind = NodeKind(parsed["kind"])
            except ValidationError:
                issue("INVALID_RECORD", "Invalid source schema; relationships are unassessed.", provenance)
        key: NodeKey = ("record", identifier)
        graph.add_node(
            key,
            node=EngineeringNode(
                key=key, entity_id=identifier, kind=kind, origin=Origin.EXPLICIT, provenance=provenance
            ),
        )

    def resolve(identifier, expected, provenance):
        key = ("record", identifier)
        if key not in graph:
            graph.add_node(
                key,
                node=EngineeringNode(
                    key=key,
                    entity_id=identifier,
                    kind=NodeKind.UNKNOWN,
                    origin=Origin.DERIVED,
                    provenance=provenance,
                ),
            )
        node = graph.nodes[key]["node"]
        if identifier not in groups:
            issue("DANGLING_REFERENCE", "Referenced record is absent.", provenance, identifier)
            return key, Resolution.DANGLING
        if len(groups[identifier]) != 1:
            issue("AMBIGUOUS_REFERENCE", "Referenced identity is not unique.", provenance, identifier)
            return key, Resolution.AMBIGUOUS
        if node.kind not in expected:
            issue(
                "UNSUPPORTED_REFERENCE",
                "Referenced entity has an unsupported or unexpected type.",
                provenance,
                identifier,
            )
            return key, Resolution.UNSUPPORTED
        return key, Resolution.RESOLVED

    def connect(source, target, kind, provenance, resolution=Resolution.RESOLVED, origin=Origin.EXPLICIT):
        payload = dict(
            source=source,
            target=target,
            kind=kind,
            provenance=provenance,
            resolution=resolution,
            origin=origin,
            propagates=resolution == Resolution.RESOLVED and kind in PROPAGATING,
        )
        key = hashlib.sha256(
            canonical(DependencyEdge(key="", **payload).model_dump(mode="json")).encode()
        ).hexdigest()
        graph.add_edge(source, target, key=key, edge=DependencyEdge(key=key, **payload))

    def reference(source, identifier, expected, kind, provenance, origin=Origin.EXPLICIT, ambiguous=False):
        target, resolution = resolve(identifier, expected, provenance)
        if ambiguous:
            issue(
                "AMBIGUOUS_RELATIONSHIP",
                "Repeated or unsupported relationship binding.",
                provenance,
                identifier,
            )
            resolution = Resolution.AMBIGUOUS
        connect(source, target, kind, provenance, resolution, origin)
        return target, resolution

    def references(record, field, expected, kind, **context):
        counts = Counter(record[field])
        for index, identifier in enumerate(record[field]):
            reference(
                ("record", record["id"]),
                identifier,
                expected,
                kind,
                evidence(record, f"/{field}/{index}", **context),
                ambiguous=counts[identifier] > 1,
            )

    for record in valid.values():
        identifier, kind = record["id"], record["kind"]
        source = ("record", identifier)
        if kind == "hardware":
            references(
                record, "compatible_software", {NodeKind.SOFTWARE}, RelationshipKind.DECLARES_COMPATIBLE
            )
            references(record, "platforms", {NodeKind.PLATFORM}, RelationshipKind.APPLICABLE_TO)
        elif kind == "software":
            references(record, "dependencies", {NodeKind.SOFTWARE}, RelationshipKind.REQUIRES)
            reference(
                source,
                record["change_id"],
                {NodeKind.CHANGE},
                RelationshipKind.RELEASED_UNDER,
                evidence(record, "/change_id"),
            )
        elif kind == "variant":
            context = {"variant_id": identifier}
            reference(
                source,
                record["platform_id"],
                {NodeKind.PLATFORM},
                RelationshipKind.BASED_ON,
                evidence(record, "/platform_id", **context),
            )
            references(record, "installed_ecus", {NodeKind.HARDWARE}, RelationshipKind.INSTALLS, **context)
            references(
                record, "allowed_platforms", {NodeKind.PLATFORM}, RelationshipKind.ALLOWS_PLATFORM, **context
            )
            if record.get("mechanical_bom_ids"):
                references(
                    record, "mechanical_bom_ids", {NodeKind.BOM}, RelationshipKind.CONFIGURES, **context
                )
            for ecu, software in sorted(record["software_configuration"].items()):
                provenance = evidence(record, f"/software_configuration/{pointer(ecu)}", **context)
                hw, hw_resolution = resolve(ecu, {NodeKind.HARDWARE}, provenance)
                sw, sw_resolution = resolve(software, {NodeKind.SOFTWARE}, provenance)
                resolution = hw_resolution if hw_resolution != Resolution.RESOLVED else sw_resolution
                if ecu not in record["installed_ecus"]:
                    issue(
                        "AMBIGUOUS_RELATIONSHIP",
                        "Software binding refers to an uninstalled ECU.",
                        provenance,
                        ecu,
                    )
                    resolution = Resolution.AMBIGUOUS
                connect(hw, sw, RelationshipKind.RUNS, provenance, resolution)
                connect(source, sw, RelationshipKind.CONFIGURES, provenance, resolution, Origin.DERIVED)
            for field in ["feature_dependencies", "required_functions", "optional_features"]:
                if record[field]:
                    issue(
                        "UNASSESSED_RELATIONSHIP",
                        "Feature/function names are not typed record references.",
                        evidence(record, f"/{field}"),
                    )
        elif kind == "platform":
            pairs = Counter(tuple(sorted(pair)) for pair in record["network_topology"])
            for index, (left, right) in enumerate(record["network_topology"]):
                provenance = evidence(record, f"/network_topology/{index}", platform_id=identifier)
                left_key, left_resolution = resolve(left, {NodeKind.HARDWARE}, provenance)
                right_key, right_resolution = resolve(right, {NodeKind.HARDWARE}, provenance)
                resolution = left_resolution if left_resolution != Resolution.RESOLVED else right_resolution
                if pairs[tuple(sorted((left, right)))] > 1:
                    issue(
                        "AMBIGUOUS_RELATIONSHIP",
                        "Repeated undirected network pair has no distinct link identity.",
                        provenance,
                    )
                    resolution = Resolution.AMBIGUOUS
                connect(left_key, right_key, RelationshipKind.COMMUNICATES_WITH, provenance, resolution)
                connect(
                    right_key,
                    left_key,
                    RelationshipKind.COMMUNICATES_WITH,
                    provenance,
                    resolution,
                    Origin.DERIVED,
                )
        elif kind == "change":
            references(
                record,
                "affected_parts",
                {NodeKind.HARDWARE, NodeKind.MECHANICAL_PART, NodeKind.ASSEMBLY},
                RelationshipKind.AFFECTS,
            )
        elif kind == "bom":
            mechanical = record.get("domain") == "mechanical"
            assemblies = {record["assembly_id"], *(edge["parent"] for edge in record["edges"])}
            for assembly in sorted(assemblies) if not mechanical else []:
                key = ("assembly", identifier, assembly)
                field = "/assembly_id"
                if assembly != record["assembly_id"]:
                    parent_index = next(
                        i for i, edge in enumerate(record["edges"]) if edge["parent"] == assembly
                    )
                    field = f"/edges/{parent_index}/parent"
                graph.add_node(
                    key,
                    node=EngineeringNode(
                        key=key,
                        entity_id=assembly,
                        kind=NodeKind.ASSEMBLY,
                        origin=Origin.DERIVED,
                        provenance=evidence(record, field, bom_id=identifier),
                    ),
                )
            root = ("assembly", identifier, record["assembly_id"])
            root_resolution = Resolution.RESOLVED
            if mechanical:
                root, root_resolution = resolve(
                    record["assembly_id"],
                    {NodeKind.ASSEMBLY},
                    evidence(record, "/assembly_id", bom_id=identifier),
                )
            elif record["assembly_id"] in groups:
                issue(
                    "AMBIGUOUS_RELATIONSHIP",
                    "Assembly identifier collides with an engineering record.",
                    evidence(record, "/assembly_id"),
                    record["assembly_id"],
                )
                root_resolution = Resolution.AMBIGUOUS
            connect(
                source,
                root,
                RelationshipKind.BOM_ROOT,
                evidence(record, "/assembly_id", bom_id=identifier),
                root_resolution,
            )
            counts = Counter((edge["parent"], edge["child"]) for edge in record["edges"])
            bom_structure = nx.DiGraph()
            bom_structure.add_node(record["assembly_id"])
            bom_structure.add_edges_from((edge["parent"], edge["child"]) for edge in record["edges"])
            reachable = {record["assembly_id"], *nx.descendants(bom_structure, record["assembly_id"])}
            for index, edge in enumerate(record["edges"]):
                provenance = evidence(
                    record,
                    f"/edges/{index}",
                    bom_id=identifier,
                    parent_id=edge["parent"],
                    child_id=edge["child"],
                    quantity=edge["quantity"],
                    revision=edge["revision"],
                )
                parent = ("assembly", identifier, edge["parent"])
                resolution = Resolution.RESOLVED
                if mechanical:
                    parent, parent_resolution = resolve(edge["parent"], {NodeKind.ASSEMBLY}, provenance)
                    child, child_resolution = resolve(
                        edge["child"],
                        {NodeKind.HARDWARE, NodeKind.MECHANICAL_PART, NodeKind.ASSEMBLY},
                        provenance,
                    )
                    resolution = (
                        parent_resolution if parent_resolution != Resolution.RESOLVED else child_resolution
                    )
                elif edge["child"] in assemblies:
                    child = ("assembly", identifier, edge["child"])
                else:
                    child, resolution = resolve(edge["child"], {NodeKind.HARDWARE}, provenance)
                if edge["parent"] not in reachable:
                    issue(
                        "UNASSESSED_BOM_CONTEXT",
                        "BOM parent is not reachable from the declared root.",
                        provenance,
                    )
                    resolution = Resolution.UNSUPPORTED
                if counts[(edge["parent"], edge["child"])] > 1 or (
                    not mechanical
                    and (edge["parent"] in groups or edge["child"] in assemblies and edge["child"] in groups)
                ):
                    issue(
                        "AMBIGUOUS_RELATIONSHIP", "Ambiguous BOM occurrence or assembly identity.", provenance
                    )
                    resolution = Resolution.AMBIGUOUS
                connect(parent, child, RelationshipKind.CONTAINS, provenance, resolution)

    structural = nx.DiGraph()
    structural.add_edges_from(
        (left, right) for left, right, data in graph.edges(data=True) if data["edge"].propagates
    )
    components = sorted(
        tuple(sorted(component))
        for component in nx.strongly_connected_components(structural)
        if len(component) > 1 or any(structural.has_edge(node, node) for node in component)
    )
    for component in components:
        provenance = graph.nodes[component[0]]["node"].provenance
        issue("DEPENDENCY_CYCLE", "Structural dependency cycle: " + canonical(component), provenance)
    ordered_issues = tuple(sorted(set(issues), key=lambda item: canonical(item.model_dump(mode="json"))))
    return EngineeringDependencyGraph(nx.freeze(graph), ordered_issues)


def reverse_dependencies(
    product: EngineeringDependencyGraph,
    changed: str | NodeKey,
    *,
    max_depth: int = 20,
    max_entities: int = 1000,
) -> DependencyTraversal:
    """Bounded reverse BFS: shortest deterministic witness per node/variant context.

    Paths are potential exposure, not confirmed failures. Variant-scoped software
    bindings cannot leak impact into another variant's installation of the ECU.
    """
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 1
        for value in (max_depth, max_entities)
    ):
        raise ValueError("Traversal bounds must be positive integers")
    seed = ("record", changed) if isinstance(changed, str) else changed
    graph = product.graph
    if seed not in graph or graph.nodes[seed]["node"].kind == NodeKind.UNKNOWN:
        raise ValueError("Changed entity is absent, ambiguous or unsupported")
    pending: deque[tuple[NodeKey, tuple[DependencyEdge, ...], str | None]] = deque([(seed, (), None)])
    visited: set[tuple[NodeKey, str | None]] = {(seed, None)}
    paths: list[ImpactPath] = []
    truncated = False
    while pending:
        node, path, variant = pending.popleft()
        incoming = sorted(
            (data["edge"] for *_, data in graph.in_edges(node, data=True)),
            key=lambda edge: (edge.source, edge.kind.value, edge.key),
        )
        for edge in incoming:
            if not edge.propagates or edge.source == seed:
                continue
            context = edge.provenance.context.variant_id
            if context and variant and context != variant:
                continue
            context = context or variant
            state = (edge.source, context)
            if state in visited:
                continue
            if len(path) >= max_depth or len(paths) >= max_entities:
                truncated = True
                continue
            visited.add(state)
            next_path = (edge, *path)
            paths.append(ImpactPath(node=edge.source, variant_context=context, edges=next_path))
            pending.append((edge.source, next_path, context))
    return DependencyTraversal(
        seed=seed, potentially_affected=tuple(paths), unassessed=product.issues, truncated=truncated
    )
