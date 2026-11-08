"""Independent engineering rules. Unknown compatibility fails closed."""

import hashlib
import json
from collections import Counter
from datetime import date

import networkx as nx
from packaging.version import Version
from pydantic import ValidationError

from app.mapping import MODELS
from app.mechanical import verify_mechanical
from app.models import Finding


def verify(
    records: list[dict], reference: list[dict] | None = None, as_of: date = date(2025, 6, 1)
) -> list[Finding]:
    findings = []

    def emit(rule, ids, expected, actual, evidence=None, severity="error", unknown=False):
        ids = sorted(set(ids))
        digest = hashlib.sha256(json.dumps([rule, ids, actual], sort_keys=True).encode()).hexdigest()[:16]
        findings.append(
            Finding(
                finding_id=digest,
                rule_id=rule,
                affected_records=ids,
                severity=severity,
                evidence=evidence or {},
                expected=str(expected),
                actual=str(actual),
                remediation="Restore the authoritative source or obtain an approved engineering change.",
                verification_status="unknown" if unknown else "failed",
            )
        )

    counts = Counter(record.get("id") for record in records)
    for identifier, count in counts.items():
        if count > 1:
            emit("IDENTITY_DUPLICATE", [identifier or "<missing>"], 1, count)
    valid = []
    for record in records:
        try:
            model = MODELS[record["kind"]].model_validate(record)
            valid.append(model.model_dump(mode="json"))
        except (ValidationError, KeyError, TypeError) as exc:
            emit(
                "SCHEMA_INVALID",
                [record.get("id", "<missing>")],
                "versioned entity schema",
                str(exc)[:600],
                severity="critical",
            )
    by_id = {record["id"]: record for record in valid}
    hardware = {key: value for key, value in by_id.items() if value["kind"] == "hardware"}
    software = {key: value for key, value in by_id.items() if value["kind"] == "software"}
    platforms = {key: value for key, value in by_id.items() if value["kind"] == "platform"}
    changes = {key: value for key, value in by_id.items() if value["kind"] == "change"}
    hw: dict | None
    sw: dict | None
    for hw in hardware.values():
        if hw["lifecycle"] != "released":
            emit("HW_LIFECYCLE", [hw["id"]], "released", hw["lifecycle"])
        for sw_id in hw["compatible_software"]:
            if sw_id not in software:
                emit("SOFTWARE_REFERENCE", [hw["id"], sw_id], "existing software", "missing")
        for platform_id in hw["platforms"]:
            if platform_id not in platforms:
                emit("PLATFORM_REFERENCE", [hw["id"], platform_id], "existing platform", "missing")
    dependency_graph = nx.DiGraph()
    for sw in software.values():
        dependency_graph.add_node(sw["id"])
        for dep in sw["dependencies"]:
            dependency_graph.add_edge(sw["id"], dep)
            if dep not in software:
                emit(
                    "SW_DEPENDENCY",
                    [sw["id"], dep],
                    "existing software dependency",
                    "missing",
                    severity="critical",
                )
        change = changes.get(sw["change_id"])
        if change is None or change["approval_status"] != "approved":
            emit(
                "CHANGE_RELEASE",
                [sw["id"], sw["change_id"]],
                "approved engineering change",
                "missing/unapproved",
            )
        elif sw["release_date"] < change["effective_date"] or sw["release_date"] > as_of.isoformat():
            emit("SW_EFFECTIVITY", [sw["id"]], "effective approved release", sw["release_date"])
    if not nx.is_directed_acyclic_graph(dependency_graph):
        emit("SW_DEPENDENCY_CYCLE", list(dependency_graph.nodes), "acyclic dependencies", "cycle")
    for variant in (r for r in valid if r["kind"] == "variant"):
        vid = variant["id"]
        platform = platforms.get(variant["platform_id"])
        if not platform or variant["platform_id"] not in variant["allowed_platforms"]:
            emit(
                "VARIANT_PLATFORM",
                [vid],
                "allowed existing platform",
                variant["platform_id"],
                severity="critical",
                unknown=not platform,
            )
        installed = [hardware[ecu] for ecu in variant["installed_ecus"] if ecu in hardware]
        functions = {hw["function"] for hw in installed}
        missing = set(variant["required_functions"]) - functions
        if missing:
            emit(
                "VARIANT_REQUIRED_ECU", [vid], "all required functions", sorted(missing), severity="critical"
            )
        if len(variant["installed_ecus"]) != len(set(variant["installed_ecus"])):
            emit("VARIANT_DUPLICATE_ECU", [vid], "unique ECU installations", variant["installed_ecus"])
        for feature in variant["optional_features"]:
            required = variant["feature_dependencies"].get(feature)
            if required is None or not set(required).issubset(functions):
                emit("FEATURE_DEPENDENCY", [vid], f"known requirements for {feature}", required)
        installed_sw = set(variant["software_configuration"].values())
        for ecu in variant["installed_ecus"]:
            hw = hardware.get(ecu)
            sw_id = variant["software_configuration"].get(ecu)
            sw = software.get(sw_id)
            if not hw or not sw:
                emit(
                    "COMPATIBILITY_UNKNOWN",
                    [vid, ecu],
                    "existing hardware and installed software",
                    {"hardware": bool(hw), "software": sw_id},
                    severity="critical",
                    unknown=True,
                )
                continue
            if not hw["compatible_software"] or sw_id not in hw["compatible_software"]:
                emit(
                    "HW_SW_ALLOWLIST",
                    [vid, ecu, sw_id],
                    "explicitly compatible software",
                    sw_id,
                    severity="critical",
                )
            if hw["hardware_revision"] not in sw["supported_hardware_revisions"]:
                emit(
                    "HW_SW_REVISION",
                    [vid, ecu, sw_id],
                    sw["supported_hardware_revisions"],
                    hw["hardware_revision"],
                    severity="critical",
                )
            missing_interfaces = set(sw["required_interfaces"]) - set(hw["interfaces"])
            if missing_interfaces:
                emit(
                    "SW_INTERFACE",
                    [vid, ecu, sw_id],
                    sw["required_interfaces"],
                    hw["interfaces"],
                    severity="critical",
                )
            if sw["release_status"] != "released":
                emit("SW_RELEASE", [vid, sw_id], "released", sw["release_status"])
            if not set(sw["dependencies"]).issubset(installed_sw):
                emit("SW_INSTALLED_DEPENDENCY", [vid, sw_id], sw["dependencies"], sorted(installed_sw))
            if platform and (
                platform["id"] not in hw["platforms"] or hw["function"] not in platform["supported_functions"]
            ):
                emit("ECU_PLATFORM", [vid, ecu], "platform-supported ECU", platform["id"])
            if platform and not set(sw["required_interfaces"]).issubset(platform["interfaces"]):
                emit("NETWORK_INTERFACE", [vid, ecu], sw["required_interfaces"], platform["interfaces"])
        for ecu in set(variant["software_configuration"]) - set(variant["installed_ecus"]):
            emit(
                "VARIANT_EXTRA_CONFIGURATION", [vid, ecu], "installed ECU", "software assigned to absent ECU"
            )
        if platform:
            graph = nx.Graph()
            graph.add_edges_from(platform["network_topology"])
            for hw in installed:
                if hw["id"] not in graph:
                    emit("NETWORK_TOPOLOGY", [vid, hw["id"]], "ECU in topology", "absent")
            subgraph = graph.subgraph(variant["installed_ecus"])
            if len(subgraph) > 1 and not nx.is_connected(subgraph):
                emit("NETWORK_DISCONNECTED", [vid], "connected installed network", "disconnected")
    findings.extend(verify_mechanical(valid, as_of))
    for bom in (r for r in valid if r["kind"] == "bom" and r.get("domain", "electronic") == "electronic"):
        graph = nx.DiGraph()
        bid = bom["id"]
        edge_counts = Counter((e["parent"], e["child"]) for e in bom["edges"])
        parents = {e["parent"] for e in bom["edges"]}
        for pair, count in edge_counts.items():
            if count > 1:
                emit("BOM_DUPLICATE_EDGE", [bid], "unique edges", pair)
        for edge in bom["edges"]:
            graph.add_edge(edge["parent"], edge["child"], quantity=edge["quantity"])
            child = hardware.get(edge["child"])
            if not child and edge["child"] not in parents:
                emit("BOM_MISSING_COMPONENT", [bid, edge["child"]], "existing part/subassembly", "missing")
            if child and edge["revision"] != child["hardware_revision"]:
                emit("BOM_REVISION", [bid, child["id"]], child["hardware_revision"], edge["revision"])
        if not nx.is_directed_acyclic_graph(graph):
            emit("BOM_CYCLE", [bid], "acyclic BOM", "cycle")
            continue
        root = bom["assembly_id"]
        reachable = nx.descendants(graph, root) | {root} if root in graph else set()
        if set(graph) != reachable:
            emit("BOM_PARENT_CHILD", [bid], "all edges rooted at assembly", sorted(set(graph) - reachable))
        if any(graph.in_degree(node) > 1 for node in graph):
            emit("BOM_MULTIPLE_PARENTS", [bid], "tree-shaped assembly occurrences", "shared occurrence")
        totals = {root: 1.0}
        for node in nx.topological_sort(graph):
            for child in graph.successors(node):
                totals[child] = totals.get(child, 0) + totals.get(node, 0) * graph[node][child]["quantity"]
        rollup = sum(totals.get(node, 0) for node in graph if graph.out_degree(node) == 0)
        if abs(rollup - bom["expected_leaf_quantity"]) > 1e-9:
            emit("BOM_ROLLUP", [bid], bom["expected_leaf_quantity"], rollup)
        if bom["effective_date"] > as_of.isoformat() or bom["lifecycle"] != "released":
            emit("BOM_EFFECTIVITY", [bid], "effective released BOM", bom["effective_date"])
    mechanical_ids = {r["id"] for r in valid if r["kind"] in {"assembly", "mechanical_part"}}
    for change in changes.values():
        electronic_change = not any(part in mechanical_ids for part in change["affected_parts"]) or any(
            part in hardware for part in change["affected_parts"]
        )
        if electronic_change and change["new_revision"] <= change["old_revision"]:
            emit(
                "CHANGE_PROGRESSION", [change["id"]], "increasing alphabetic revision", change["new_revision"]
            )
        for part in change["affected_parts"]:
            if part in mechanical_ids:
                continue
            hw = hardware.get(part)
            if not hw:
                emit("CHANGE_PART_REFERENCE", [change["id"], part], "existing affected hardware", "missing")
            elif (
                change["approval_status"] != "approved" or change["effective_date"] > as_of.isoformat()
            ) and (hw["hardware_revision"] == change["new_revision"]):
                emit(
                    "CHANGE_APPROVAL",
                    [change["id"], part],
                    "approved effective change",
                    change["approval_status"],
                )
            elif change["approval_status"] == "approved" and change["effective_date"] <= as_of.isoformat():
                if hw["hardware_revision"] != change["new_revision"]:
                    emit(
                        "CHANGE_SUPERSEDED",
                        [part, change["id"]],
                        change["new_revision"],
                        hw["hardware_revision"],
                    )
    if reference is not None:
        expected = {r["id"]: r for r in reference}
        for identifier in set(expected) | set(by_id):
            before, after = expected.get(identifier), by_id.get(identifier)
            if before is None or after is None:
                emit(
                    "RECONCILIATION_IDENTITY",
                    [identifier],
                    "source-target identity preserved",
                    "missing" if after is None else "unexpected",
                )
                continue
            for key in set(before) | set(after):
                if before.get(key) != after.get(key):
                    emit(
                        "RECONCILIATION_VALUE",
                        [identifier],
                        before.get(key),
                        after.get(key),
                        {"field": key, "source": before.get(key), "target": after.get(key)},
                    )
            if before["kind"] == "software" and Version(before["version"]) != Version(after["version"]):
                emit("SW_VERSION_PRESERVATION", [identifier], before["version"], after["version"])
    return findings
