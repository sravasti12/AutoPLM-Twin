"""Presentation adapters for existing twins and assessments; no compatibility rules."""

import copy
import html

from app.dependencies import build_dependency_graph
from app.twin import build_twin
from app.what_if import Assessment, baseline_digest

COLORS = {
    "unchanged": "#64748b", "modified": "#b7791f", "potentially affected": "#7560a8",
    "added": "#23856d", "removed": "#c2414b", "unknown/unassessed": "#52647c",
}


def twin_members(snapshot: dict) -> set[str]:
    if not snapshot:
        return set()
    variant = snapshot["variant"]
    structure = snapshot.get("product_structure", {})
    return {variant["id"], variant["platform_id"], *variant["installed_ecus"],
            *variant["software_configuration"].values(), *(b["id"] for b in snapshot["boms"]),
            *structure.get("components", {}), *structure.get("boms", {})}


def vehicle_view(records: list[dict], variant: str, assessment: Assessment | None = None,
                 proposed: bool = False) -> dict:
    """Map actual twin membership to records, retaining removed/added markers in both views."""
    if assessment and (assessment.status != "assessed"
                       or assessment.proposal.baseline_digest != baseline_digest(records)):
        raise ValueError("Proposal is stale, discarded or not assessed")
    original = copy.deepcopy(records)
    candidate = copy.deepcopy(assessment.proposed_snapshot) if assessment else original
    candidate = candidate if candidate is not None else original
    selected = candidate if proposed else original
    catalogs = [{r["id"]: r for r in rows} for rows in (original, candidate)]
    snapshots = []
    members: set[str] = set()
    for rows, catalog in zip((original, candidate), catalogs):
        snapshot = build_twin(rows, variant) if catalog.get(variant, {}).get("kind") == "variant" else {}
        snapshots.append(snapshot)
        members.update(twin_members(snapshot))
    applicability = []
    for rows in (original, candidate):
        applicability.append({r["id"]: twin_members(build_twin(rows, r["id"]))
                              for r in rows if r["kind"] == "variant"})
    report = assessment.report if assessment else {}
    direct = {c["id"]: c for c in report.get("direct_changes", []) if c["before"] != c["after"]}
    paths = [path for side in report.get("impact", {}).values() for traversal in side.values()
             for path in traversal["potentially_affected"]
             if path["variant_context"] in (None, variant)]
    affected = {p["node"][1] for p in paths if p["node"][0] == "record"}
    graph = build_dependency_graph(selected)
    relationships = [data["edge"].model_dump(mode="json") for *_, data in graph.graph.edges(data=True)]
    components = []
    active = {r["id"]: r for r in selected}
    for identifier in sorted(members):
        before, after = (catalog.get(identifier) for catalog in catalogs)
        record = active.get(identifier)
        state = "unchanged"
        if identifier in affected:
            state = "potentially affected"
        if identifier in direct:
            state = "added" if before is None else "removed" if after is None else "modified"
        if record is None and state not in ("added", "removed"):
            state = "unknown/unassessed"
        evidence = [e for e in relationships if ("record", identifier) in
                    (tuple(e["source"]), tuple(e["target"]))]
        if any(e["resolution"] != "resolved" for e in evidence) and state == "unchanged":
            state = "unknown/unassessed"
        components.append({
            "id": identifier, "name": (record or before or after or {}).get("part_number", identifier),
            "type": (record or before or after or {}).get("kind", "unknown"), "state": state,
            "record": record, "original_revision": revision(before), "proposed_revision": revision(after),
            "relationships": evidence,
            "paths": [p for p in paths if identifier == p["node"][1]],
            "variant": variant,
            "present_in_view": record is not None,
            "applicability": {
                label: sorted(v for v, identifiers in membership.items() if identifier in identifiers)
                for label, membership in zip(("original", "proposed"), applicability)
            },
            "electronic_configuration": [node for node in snapshots[int(proposed)].get("nodes", [])
                                         if node["id"] == identifier
                                         or (node.get("software") or {}).get("id") == identifier],
        })
    return {"components": components, "snapshot": snapshots[int(proposed)],
            "findings": report.get("proposed_findings" if proposed else "baseline_findings", []),
            "diagnostics": [i.model_dump(mode="json") for i in graph.issues],
            "unassessed": report.get("unassessed", []),
            "status": assessment.status if assessment else "original"}


def revision(record: dict | None) -> str | None:
    if record is None:
        return None
    return record.get("hardware_revision", record.get("revision", record.get("version")))


def vehicle_svg(view: dict, selected: str | None = None) -> str:
    """Illustrative zones only. Every clickable element carries a real twin identifier."""
    height = max(420, 100 + len(view["components"]) * 30)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 940 {height}" '
             'role="img" aria-label="Illustrative vehicle and engineering record markers">',
             '<rect width="940" height="100%" rx="18" fill="#ffffff"/>',
             '<path d="M110 85 Q260 20 410 85 L445 300 Q260 380 75 300 Z" '
             'fill="#edf2f8" stroke="#94a3b8" stroke-width="3"/>']
    zones = [(80, 105, "Brakes / suspension"), (155, 175, "Battery / powertrain"),
             (135, 245, "Mechanical assemblies"), (155, 285, "ECUs / sensors / gateway")]
    for x, y, label in zones:
        parts.append(f'<text x="{x}" y="{y}" fill="#52647c" font-size="13">{label}</text>')
    for x in (65, 425):
        for y in (90, 270):
            parts.append(f'<rect x="{x}" y="{y}" width="30" height="60" rx="8" fill="#52647c"/>')
    # Placement is illustrative; categories use explicit record metadata, never inferred compatibility.
    slots = {"brake": (100, 125), "speed_sensor": (115, 325), "gateway": (265, 325),
             "mechanical_part": (155, 220), "assembly": (275, 220),
             "battery": (150, 190), "powertrain": (285, 190)}
    occupied = set()
    for component in view["components"]:
        record = component.get("record") or {}
        slot = record.get("function", component["type"])
        if slot not in slots or slot in occupied:
            continue
        occupied.add(slot)
        x, y = slots[slot]
        identifier = html.escape(component["id"], quote=True)
        color = COLORS[component["state"]]
        parts.append(f'<g data-record="{identifier}" tabindex="0" role="button" '
                     f'aria-label="Select {identifier}"><title>{identifier}</title>'
                     f'<rect x="{x}" y="{y}" width="110" height="24" rx="6" fill="{color}"/>'
                     f'<text x="{x + 6}" y="{y + 16}" font-size="11" fill="#ffffff">{slot}</text></g>')
    parts.append('<text x="40" y="400" fill="#52647c" font-size="12">'
                 'Illustrative zones; no CAD placement</text>')
    for index, component in enumerate(view["components"]):
        identifier = html.escape(component["id"], quote=True)
        color = COLORS[component["state"]]
        y = 30 + index * 30
        stroke = "#2563eb" if component["id"] == selected else color
        parts.append(f'<g data-record="{identifier}" tabindex="0" role="button" '
                     f'aria-label="Select {identifier}"><title>{identifier}: {component["state"]}</title>'
                     f'<rect x="490" y="{y}" width="425" height="25" rx="5" fill="#f8fafc" '
                     f'stroke="{stroke}" stroke-width="2"/>'
                     f'<circle cx="505" cy="{y + 12}" r="5" fill="{color}"/>'
                     f'<text x="520" y="{y + 17}" fill="#172b4d" font-size="12">'
                     f'{identifier} · {html.escape(component["type"])} · {component["state"]}</text></g>')
    return "".join(parts) + "</svg>"
