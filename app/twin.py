
"""Configuration twin and a deliberately fictional signal-level behavioral model."""

import copy
import hashlib
import json

import networkx as nx
import simpy

from app.mechanical import build_mechanical_structure

SCENARIOS = [
    "valid",
    "incompatible_software",
    "missing_ecu",
    "unsupported_variant",
    "missing_interface",
    "broken_bom",
    "incorrect_revision",
]


def build_twin(records: list[dict], variant_id: str) -> dict:
    by_id = {r["id"]: r for r in records}
    variant = by_id.get(variant_id)

    if not variant or variant["kind"] != "variant":
        raise ValueError("Unknown vehicle variant")

    # Canonicalize ECU ordering without modifying the original records.
    variant = copy.deepcopy(variant)
    variant["installed_ecus"] = sorted(variant["installed_ecus"])

    platform = by_id.get(variant["platform_id"])
    nodes = []

    for identifier in variant["installed_ecus"]:
        hw = by_id.get(identifier)
        sw_id = variant["software_configuration"].get(identifier)
        sw = by_id.get(sw_id)
        nodes.append(
            {
                "id": identifier,
                "hardware": hw,
                "software": sw,
                "state": "OFF",
            }
        )

    edges = platform["network_topology"] if platform else []

    related = {
        variant_id,
        variant["platform_id"],
        *variant["installed_ecus"],
        *variant["software_configuration"].values(),
    }

    boms = [
        r
        for r in records
        if r["kind"] == "bom" and r.get("domain", "electronic") == "electronic"
        and any(edge["child"] in related for edge in r["edges"])
    ]

    changes = [
        r
        for r in records
        if r["kind"] == "change"
        and set(r["affected_parts"]) & related
    ]

    snapshot = {
        "schema_version": "1.0",
        "variant": variant,
        "platform": platform,
        "nodes": nodes,
        "edges": edges,
        "boms": boms,
        "changes": changes,
        "synthetic": True,
    }

    if variant.get("mechanical_bom_ids"):
        variant["mechanical_bom_ids"] = sorted(variant["mechanical_bom_ids"])
        snapshot["schema_version"] = "1.1"
        snapshot["product_structure"] = build_mechanical_structure(records, variant["mechanical_bom_ids"])

    snapshot["fingerprint"] = hashlib.sha256(
        json.dumps(snapshot, sort_keys=True).encode()
    ).hexdigest()

    return snapshot



def compare_twins(source: dict, target: dict) -> list[dict]:
    differences = []

    def compare(before, after, path):
        if isinstance(before, dict) and isinstance(after, dict):
            for key in sorted(set(before) | set(after)):
                if key == "fingerprint":
                    continue

                compare(
                    before.get(key),
                    after.get(key),
                    f"{path}/{key}",
                )

        elif (
            path == "/nodes"
            and isinstance(before, list)
            and isinstance(after, list)
        ):
            source_nodes = {node["id"]: node for node in before}
            target_nodes = {node["id"]: node for node in after}

            for ecu_id in sorted(set(source_nodes) | set(target_nodes)):
                node_path = f"{path}/{ecu_id}"

                if ecu_id not in source_nodes:
                    differences.append({
                        "path": node_path,
                        "source": None,
                        "target": target_nodes[ecu_id],
                    })
                elif ecu_id not in target_nodes:
                    differences.append({
                        "path": node_path,
                        "source": source_nodes[ecu_id],
                        "target": None,
                    })
                else:
                    compare(
                        source_nodes[ecu_id],
                        target_nodes[ecu_id],
                        node_path,
                    )

        elif before != after:
            differences.append({
                "path": path,
                "source": before,
                "target": after,
            })

    compare(source, target, "")
    return differences

def scenario_records(
    records: list[dict], variant_id: str, scenario: str
) -> list[dict]:
    if scenario not in SCENARIOS:
        raise ValueError("Unknown simulation scenario")

    result = copy.deepcopy(records)
    variant = next(r for r in result if r["id"] == variant_id)

    brake = next(
        r
        for r in result
        if r["kind"] == "hardware"
        and r["function"] == "brake"
        and r["id"] in variant["installed_ecus"]
    )

    sw = next(
        r
        for r in result
        if r["id"] == variant["software_configuration"][brake["id"]]
    )

    if scenario == "incompatible_software":
        sw["supported_hardware_revisions"] = ["C"]

    elif scenario == "missing_ecu":
        result.remove(brake)

    elif scenario == "unsupported_variant":
        variant["platform_id"] = "unsupported"

    elif scenario == "missing_interface":
        brake["interfaces"] = ["LIN"]

    elif scenario == "broken_bom":
        bom = next(
            r
            for r in result
            if r["kind"] == "bom"
            and any(e["child"] == brake["id"] for e in r["edges"])
        )
        next(
            e for e in bom["edges"] if e["child"] == brake["id"]
        )["parent"] = "orphan"

    elif scenario == "incorrect_revision":
        brake["hardware_revision"] = "A"

    return result


def simulate(
    twin: dict, ticks: int = 5, fault_at: int | None = None
) -> dict:
    if not 1 <= ticks <= 1000:
        raise ValueError("ticks must be in 1..1000")

    env = simpy.Environment()
    events = []
    states = {}

    nodes = {
        node["hardware"]["function"]: node
        for node in twin["nodes"]
        if node["hardware"]
    }

    network = nx.Graph()
    network.add_edges_from(twin["edges"])

    signals = {"sensor": None, "gateway": None}

    def event(component, state, signal=None):
        states[component] = state
        events.append(
            {
                "time": env.now,
                "component": component,
                "state": state,
                "signal": signal,
            }
        )

    def connected(left, right):
        a, b = nodes[left]["id"], nodes[right]["id"]

        return (
            a in network
            and b in network
            and nx.has_path(
                network.subgraph(
                    [
                        node["id"]
                        for node in twin["nodes"]
                        if node["hardware"]
                    ]
                ),
                a,
                b,
            )
        )

    def worker(function):
        event(function, "INITIALIZING")
        yield env.timeout(0.1)

        node = nodes.get(function)

        if node is None or twin["platform"] is None:
            event(function, "FAILED", "missing component/platform")
            return

        hw, sw = node["hardware"], node["software"]

        if (
            not sw
            or hw["hardware_revision"]
            not in sw["supported_hardware_revisions"]
            or not set(sw["required_interfaces"]).issubset(
                hw["interfaces"]
            )
            or sw["id"] not in hw["compatible_software"]
        ):
            event(
                function,
                "FAILED",
                "fictional interface initialization rejected",
            )
            return

        event(function, "READY")

        for tick in range(ticks):
            yield env.timeout(1)

            if function == "speed_sensor":
                signals["sensor"] = (
                    None
                    if fault_at is not None and tick >= fault_at
                    else 50 - tick * 2
                )

                event(
                    function,
                    "ACTIVE"
                    if signals["sensor"] is not None
                    else "FAILED",
                    signals["sensor"],
                )

            elif function == "gateway":
                signals["gateway"] = (
                    signals["sensor"]
                    if (
                        "speed_sensor" in nodes
                        and connected("speed_sensor", "gateway")
                    )
                    else None
                )

                event(
                    function,
                    "ACTIVE"
                    if signals["gateway"] is not None
                    else "DEGRADED",
                    signals["gateway"],
                )

            else:
                value = (
                    signals["gateway"]
                    if (
                        "gateway" in nodes
                        and connected("gateway", function)
                    )
                    else None
                )

                event(
                    function,
                    "ACTIVE"
                    if value is not None
                    else "DEGRADED",
                    {
                        "speed_kph": value,
                        "brake_command": bool(
                            value is not None and value > 0
                        ),
                    }
                    if function == "brake"
                    else value,
                )

    # Explicit zero-latency fictional scheduling assumption.
    for function in [
        "speed_sensor",
        "gateway",
        "brake",
        "cluster",
    ]:
        env.process(worker(function))

    env.run()

    return {
        "synthetic": True,
        "model": "fictional-speed-brake-v1",
        "events": events,
        "states": states,
        "behavior_passed": all(
            state == "ACTIVE" for state in states.values()
        ),
        "ticks": ticks,
        "fault_at": fault_at,
    }
