"""Seeded fictional data. Truth never enters the mapping workflow."""

import copy
import random

from app.models import Dataset

ALIASES = {
    "A": {"id": "ECU_ID", "hardware_revision": "HW_REV", "version": "SW_REL", "trim": "VEH_TRIM"},
    "B": {
        "id": "ControllerCode",
        "hardware_revision": "HardwareLevel",
        "version": "FirmwareRelease",
        "trim": "VariantCode",
    },
}


def generate(fleets: int = 2, seed: int = 42, source: str = "A") -> tuple[dict, Dataset, dict]:
    if not 1 <= fleets <= 1000:
        raise ValueError("fleets must be between 1 and 1000")
    if source not in ALIASES:
        raise ValueError("Unknown legacy source")
    rng = random.Random(seed)
    records = []
    functions = ["speed_sensor", "brake", "gateway", "cluster"]
    for fleet in range(fleets):
        prefix = f"F{fleet:04d}"
        platform = f"{prefix}-P"
        change = f"{prefix}-ECR"
        revision = "B" if fleet % 2 == 0 else "C"
        old_revision = "A" if fleet % 2 == 0 else "B"
        signal = "speed.v1" if fleet % 2 == 0 else "speed.v2"
        version = "2.10.0" if fleet % 2 == 0 else "3.0.0"
        ids = [f"{prefix}-{function}" for function in functions]
        software = {ecu: f"{ecu}-sw" for ecu in ids}
        records.extend(
            [
                dict(
                    kind="platform",
                    id=platform,
                    electrical_architecture=f"fictional-CAN-{signal}",
                    supported_functions=functions,
                    network_topology=list(zip(ids, ids[1:])),
                    interfaces=["CAN", signal],
                    revision="A",
                ),
                dict(
                    kind="change",
                    id=change,
                    affected_parts=ids,
                    old_revision=old_revision,
                    new_revision=revision,
                    approval_status="approved",
                    effective_date="2025-01-01",
                ),
            ]
        )
        for ecu, function in zip(ids, functions):
            records.append(
                dict(
                    kind="hardware",
                    id=ecu,
                    part_number=f"SYN-{ecu}",
                    hardware_revision=revision,
                    supplier=rng.choice(["Fictional Aster", "Fictional Boreal"]),
                    function=function,
                    interfaces=["CAN", signal],
                    lifecycle="released",
                    compatible_software=[software[ecu]],
                    platforms=[platform],
                    mass_kg=round(rng.uniform(0.2, 2), 3),
                )
            )
            records.append(
                dict(
                    kind="software",
                    id=software[ecu],
                    version=version,
                    release_status="released",
                    supported_hardware_revisions=[revision],
                    dependencies=([software[ids[2]]] if function == "brake" else []),
                    required_interfaces=["CAN", signal],
                    capabilities=[function],
                    release_date="2025-02-01",
                    change_id=change,
                )
            )
        for trim in ["standard", "touring"]:
            records.append(
                dict(
                    kind="variant",
                    id=f"{prefix}-{trim}",
                    platform_id=platform,
                    trim=trim,
                    required_functions=functions,
                    installed_ecus=ids,
                    optional_features=["speed_display"],
                    feature_dependencies={"speed_display": ["cluster", "speed_sensor"]},
                    software_configuration=software,
                    allowed_platforms=[platform],
                )
            )
        assembly = f"{prefix}-assembly"
        subassembly = f"{prefix}-controls"
        records.append(
            dict(
                kind="bom",
                id=f"{prefix}-BOM",
                assembly_id=assembly,
                edges=[dict(parent=assembly, child=subassembly, quantity=1, revision=revision)]
                + [dict(parent=subassembly, child=ecu, quantity=1, revision=revision) for ecu in ids],
                effective_date="2025-02-01",
                lifecycle="released",
                expected_leaf_quantity=4,
            )
        )
    dataset = Dataset.model_validate({"records": records})
    aliases = ALIASES[source]
    legacy = []
    truth = {}
    for index, record in enumerate(dataset.documents()):
        converted = {}
        mapping = {}
        for key, value in record.items():
            legacy_key = aliases.get(key, key)
            if key == "mass_kg":
                legacy_key, value = "Mass_g", round(value * 1000, 6)
            converted[legacy_key] = value
            mapping[legacy_key] = {
                "target": key,
                "transform": "grams_to_kg" if key == "mass_kg" else "identity",
            }
        legacy.append({"source_id": f"{source}:{index:08d}", "entity": record["kind"], "data": converted})
        truth[record["kind"]] = mapping
    return {"synthetic": True, "source_schema": source, "records": legacy}, dataset, truth


FAULTS = [
    "incorrect_software_version",
    "unsupported_hardware_revision",
    "missing_bom_component",
    "broken_relationship",
    "invalid_vehicle_variant",
    "incorrect_unit_conversion",
    "duplicate_record",
    "incorrect_lifecycle",
    "missing_dependency",
    "invalid_interface",
]


def inject(records: list[dict], fault: str) -> tuple[list[dict], dict]:
    if fault not in FAULTS:
        raise ValueError(f"Unknown fault: {fault}")
    result = copy.deepcopy(records)
    hardware = next(r for r in result if r["kind"] == "hardware")
    software = next(r for r in result if r["kind"] == "software")
    variant = next(r for r in result if r["kind"] == "variant")
    bom = next(r for r in result if r["kind"] == "bom")
    affected = hardware["id"]
    if fault == "incorrect_software_version":
        software["version"] = "99.0.0"
        affected = software["id"]
    elif fault == "unsupported_hardware_revision":
        hardware["hardware_revision"] = "Z"
    elif fault == "missing_bom_component":
        result.remove(hardware)
    elif fault == "broken_relationship":
        bom["edges"][1]["parent"] = "unknown-assembly"
        affected = bom["id"]
    elif fault == "invalid_vehicle_variant":
        variant["platform_id"] = "unsupported-platform"
        affected = variant["id"]
    elif fault == "incorrect_unit_conversion":
        hardware["mass_kg"] *= 1000
    elif fault == "duplicate_record":
        result.append(copy.deepcopy(hardware))
    elif fault == "incorrect_lifecycle":
        hardware["lifecycle"] = "superseded"
    elif fault == "missing_dependency":
        dependency = next(r for r in result if r["kind"] == "software" and "gateway" in r["id"])
        result.remove(dependency)
        affected = dependency["id"]
    elif fault == "invalid_interface":
        hardware["interfaces"] = ["LIN"]
    return result, {"synthetic": True, "fault": fault, "affected_id": affected}


def corrupt_legacy(envelope: dict, fault: str) -> tuple[dict, dict]:
    """Export corrupt input separately from labels; do not pass labels to the mapper."""
    from app.source_adapters import normalize_source

    if envelope.get("synthetic") is not True:
        raise ValueError("Fault export requires an explicitly synthetic dataset")
    schema = envelope["source_schema"]
    source_rows = envelope["records"]
    source_ids = [row["source_id"] for row in source_rows]
    if not source_rows or any(not isinstance(key, str) or not key for key in source_ids):
        raise ValueError("Fault export requires nonempty source identifiers")
    if len(set(source_ids)) != len(source_ids):
        raise ValueError("Duplicate source identifiers")
    canonical = normalize_source(source_rows, schema)
    identities = [(record["kind"], record["id"]) for record in canonical]
    if len(set(identities)) != len(identities):
        raise ValueError("Fault export requires an unambiguous clean record identity")
    origins = dict(zip(identities, source_ids, strict=True))
    corrupted, label = inject(canonical, fault)
    aliases = ALIASES[schema]
    rows = []
    used_ids = set()
    reserved_ids = set(source_ids)
    for index, record in enumerate(corrupted):
        raw = {aliases.get(key, key): value for key, value in record.items() if key != "mass_kg"}
        if "mass_kg" in record:
            raw["Mass_g"] = record["mass_kg"] * 1000
        source_id = origins[(record["kind"], record["id"])]
        if source_id in used_ids:
            suffix = index
            candidate = f"{source_id}:copy:{suffix}"
            while candidate in reserved_ids or candidate in used_ids:
                suffix += 1
                candidate = f"{source_id}:copy:{suffix}"
            source_id = candidate
        used_ids.add(source_id)
        rows.append({"source_id": source_id, "entity": record["kind"], "data": raw})
    return {"synthetic": True, "source_schema": schema, "records": rows}, label
