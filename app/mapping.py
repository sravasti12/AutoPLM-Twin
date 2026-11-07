"""Constrained field transformations; proposals are data, never executable code."""

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
TRANSFORMS = {
    "identity": lambda value: value,
    "grams_to_kg": lambda value: float(value) / 1000,
    "strip": lambda value: str(value).strip(),
    "lower": lambda value: str(value).lower(),
}


class FieldMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str
    target: str
    transform: Literal["identity", "grams_to_kg", "strip", "lower", "enum"] = "identity"
    enum_values: dict[str, str] = {}
    evidence: str
    confidence: float = Field(default=0.5, ge=0, le=1, description="Uncalibrated self-assessment")


class MappingPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity: Literal["hardware", "software", "platform", "variant", "bom", "change"]
    fields: list[FieldMapping]
    assumptions: list[str] = []


def profile(records: list[dict]) -> dict:
    keys = sorted({key for record in records for key in record})
    return {
        key: {
            "types": sorted({type(r[key]).__name__ for r in records if key in r}),
            "missing": sum(r.get(key) is None for r in records),
            "examples": [r[key] for r in records if key in r][:3],
            "unit_hint": "grams" if key == "Mass_g" else None,
            "relationship_candidate": key.endswith(("_id", "_ecus", "dependencies")),
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
        if field.transform == "enum":
            value = field.enum_values[str(value)]
        else:
            value = TRANSFORMS[field.transform](value)
        if field.target in result:
            raise ValueError(f"Ambiguous target: {field.target}")
        result[field.target] = value
    return result


def validate_plan(plan: MappingPlan, records: list[dict]) -> list[str]:
    model = MODELS[plan.entity]
    errors = []
    if plan.assumptions:
        errors.append("Unsupported assumptions require human review")
    targets = [field.target for field in plan.fields]
    for key, count in Counter(targets).items():
        if count > 1:
            errors.append(f"Ambiguous target: {key}")
    for field in plan.fields:
        if field.target not in model.model_fields:
            errors.append(f"Unknown target: {field.target}")
        if not field.evidence.strip():
            errors.append(f"Missing evidence: {field.source}")
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
