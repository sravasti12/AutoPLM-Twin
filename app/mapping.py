"""Constrained field transformations; proposals are data, never executable code."""

import copy
from collections import Counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.data import ALIASES
from app.models import Bom, Change, Hardware, Platform, Software, Variant

MODELS: dict[str, type[BaseModel]] = {
    "hardware": Hardware,
    "software": Software,
    "platform": Platform,
    "variant": Variant,
    "bom": Bom,
    "change": Change,
}


def grams_to_kg(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError("Gram conversion requires a numeric quantity")
    return float(value) / 1000


TRANSFORMS = {
    "identity": lambda value: value,
    "grams_to_kg": grams_to_kg,
    "strip": lambda value: value.strip(),
    "lower": lambda value: value.lower(),
}

TRANSFORM_CONTRACT = {
    "identity": "Preserve source value and type; do not invent missing values.",
    "grams_to_kg": "Only numeric gram quantities with a documented gram field suffix to mass_kg.",
    "strip": "String source only; trim whitespace.",
    "lower": "String source only; lowercase.",
    "enum": "Explicit nonempty source-string to target-string dictionary; no fallback values.",
}
RELATIONSHIPS = {
    "platform_id": ["platform"],
    "platforms": ["platform"],
    "allowed_platforms": ["platform"],
    "change_id": ["change"],
    "dependencies": ["software"],
    "compatible_software": ["software"],
    "installed_ecus": ["hardware"],
    "software_configuration": ["hardware", "software"],
    "network_topology": ["hardware"],
    "edges": ["hardware", "assembly"],
    "affected_parts": ["hardware"],
}


class FieldMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    transform: Literal["identity", "grams_to_kg", "strip", "lower", "enum"] = "identity"
    enum_values: dict[str, str] = {}
    evidence: str
    confidence: float = Field(default=0.5, ge=0, le=1, description="Uncalibrated self-assessment")


class MappingPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity: Literal["hardware", "software", "platform", "variant", "bom", "change"]
    fields: list[FieldMapping] = Field(min_length=1)
    assumptions: list[str] = []


def profile(records: list[dict]) -> dict:
    keys = sorted({key for record in records for key in record})
    aliases = {value: key for source in ALIASES.values() for key, value in source.items()}
    return {
        key: {
            "types": sorted({type(r[key]).__name__ for r in records if key in r}),
            "missing": sum(r.get(key) is None for r in records),
            "examples": copy.deepcopy([r[key] for r in records if key in r][:3]),
            "unit_hint": "kilograms"
            if key.lower().endswith("_kg")
            else ("grams" if key.lower().endswith("_g") else None),
            "relationship_candidate": aliases.get(key, key) in RELATIONSHIPS,
            "relationship_targets": RELATIONSHIPS.get(aliases.get(key, key), []).copy(),
        }
        for key in keys
    }


def baseline(entity: str, fields: dict) -> MappingPlan:
    aliases = {value: key for source in ALIASES.values() for key, value in source.items()}
    mappings = []
    for key in fields:
        target = "mass_kg" if key == "Mass_g" else aliases.get(key, key)
        mappings.append(
            FieldMapping(
                source=key,
                target=target,
                transform="grams_to_kg" if key == "Mass_g" else "identity",
                evidence=f"Versioned legacy dictionary: {key} -> {target}",
                confidence=1,
            )
        )
    return MappingPlan.model_validate({"entity": entity, "fields": mappings})


def transform(record: dict, plan: MappingPlan) -> dict:
    result = {}
    for field in plan.fields:
        value = record[field.source]
        if field.transform in ["strip", "lower", "enum"] and not isinstance(value, str):
            raise ValueError(f"{field.transform} requires a string source: {field.source}")
        if field.transform == "enum":
            value = field.enum_values[str(value)]
        else:
            value = TRANSFORMS[field.transform](value)
        if field.target in result:
            raise ValueError(f"Ambiguous target: {field.target}")
        result[field.target] = copy.deepcopy(value)
    return result


def validate_plan(plan: MappingPlan, records: list[dict]) -> list[str]:
    if not records:
        return ["Mapping validation requires source records"]
    model = MODELS[plan.entity]
    errors = []
    if plan.assumptions:
        errors.append("Unsupported assumptions require human review")
    targets = [field.target for field in plan.fields]
    sources = [field.source for field in plan.fields]
    summary = profile(records)
    for key in sorted(set(summary) - set(sources)):
        errors.append(f"Unmapped source field: {key}")
    for key, count in Counter(sources).items():
        if count > 1:
            errors.append(f"Ambiguous source reuse: {key}")
    for key, count in Counter(targets).items():
        if count > 1:
            errors.append(f"Ambiguous target: {key}")
    for field in plan.fields:
        if field.target not in model.model_fields:
            errors.append(f"Unknown target: {field.target}")
        if not field.evidence.strip():
            errors.append(f"Missing evidence: {field.source}")
        source_unit = summary.get(field.source, {}).get("unit_hint")
        if field.transform == "grams_to_kg" and (source_unit != "grams" or field.target != "mass_kg"):
            errors.append(f"Unsupported unit conversion: {field.source} -> {field.target}")
        if source_unit == "grams" and field.target == "mass_kg" and field.transform != "grams_to_kg":
            errors.append(f"Required grams_to_kg conversion: {field.source}")
        if field.transform == "enum" and not field.enum_values:
            errors.append(f"Missing enum dictionary: {field.source}")
        if field.transform != "enum" and field.enum_values:
            errors.append(f"Unused enum dictionary: {field.source}")
    for name, model_field in model.model_fields.items():
        if model_field.is_required() and name not in targets:
            errors.append(f"Missing required target: {name}")
    for record in records:
        try:
            normalized = transform(record, plan)
            parsed = model.model_validate(normalized)
            if parsed.model_dump().get("kind") != plan.entity:
                raise ValueError("Entity mismatch")
        except (ValueError, KeyError, TypeError) as exc:
            errors.append(str(exc)[:600])
    return sorted(set(errors))
