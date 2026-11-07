"""Reviewed source contracts, independent of mapping proposals and their transform registry.

Keep these adapters separate from the baseline mapper: shared execution code would
allow a migration conversion defect to corrupt its own reconciliation reference.
"""

import copy
from decimal import Decimal, InvalidOperation

from app.models import Dataset

# Source-facing names are intentionally declared here, rather than imported from
# the synthetic generator or mapper. Changes require adapter contract tests.
SOURCE_FIELDS = {
    "A": {"ECU_ID": "id", "HW_REV": "hardware_revision", "SW_REL": "version", "VEH_TRIM": "trim"},
    "B": {
        "ControllerCode": "id",
        "HardwareLevel": "hardware_revision",
        "FirmwareRelease": "version",
        "VariantCode": "trim",
    },
}


def normalize_source(rows: list[dict], schema: str) -> list[dict]:
    if schema not in SOURCE_FIELDS:
        raise ValueError("Unsupported source adapter")
    normalized = []
    for row in rows:
        raw = copy.deepcopy(row["data"])
        record = {}
        for source_name, value in raw.items():
            target_name = SOURCE_FIELDS[schema].get(source_name, source_name)
            if source_name == "Mass_g":
                target_name = "mass_kg"
                try:
                    mass = Decimal(str(value)) / Decimal("1000")
                except (InvalidOperation, ValueError) as exc:
                    raise ValueError("Source mass must be a finite quantity in grams") from exc
                if not mass.is_finite():
                    raise ValueError("Source mass must be finite")
                value = float(mass)
            if target_name in record:
                raise ValueError(f"Ambiguous source fields for {target_name}")
            record[target_name] = value
        if record.get("kind", row["entity"]) != row["entity"]:
            raise ValueError("Source envelope and record entity disagree")
        record.setdefault("kind", row["entity"])
        normalized.append(record)
    # The shared domain schema supplies defaults, not mapping/conversion behavior.
    return Dataset.model_validate({"records": normalized}).documents()
