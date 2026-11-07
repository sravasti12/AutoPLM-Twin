from datetime import date
from enum import StrEnum
from typing import Annotated, Literal

from packaging.version import InvalidVersion, Version
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Lifecycle(StrEnum):
    RELEASED = "released"
    DRAFT = "draft"
    SUPERSEDED = "superseded"


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    schema_version: Literal["1.0"] = "1.0"
    id: str = Field(min_length=1)


class Hardware(Record):
    kind: Literal["hardware"] = "hardware"
    part_number: str
    hardware_revision: str
    supplier: str
    function: str
    interfaces: list[str]
    lifecycle: Lifecycle = Lifecycle.RELEASED
    compatible_software: list[str]
    platforms: list[str]
    mass_kg: float = Field(gt=0)


class Software(Record):
    kind: Literal["software"] = "software"
    version: str
    release_status: Lifecycle = Lifecycle.RELEASED
    supported_hardware_revisions: list[str]
    dependencies: list[str] = []
    required_interfaces: list[str]
    capabilities: list[str]
    release_date: date
    change_id: str

    @field_validator("version")
    @classmethod
    def valid_version(cls, value: str) -> str:
        try:
            Version(value)
        except InvalidVersion as exc:
            raise ValueError("Expected a semantic/PEP 440 version string") from exc
        return value


class Platform(Record):
    kind: Literal["platform"] = "platform"
    electrical_architecture: str
    supported_functions: list[str]
    network_topology: list[tuple[str, str]]
    interfaces: list[str]
    revision: str


class Variant(Record):
    kind: Literal["variant"] = "variant"
    platform_id: str
    trim: str
    required_functions: list[str]
    installed_ecus: list[str]
    optional_features: list[str]
    feature_dependencies: dict[str, list[str]]
    software_configuration: dict[str, str]
    allowed_platforms: list[str]


class BomEdge(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    parent: str
    child: str
    quantity: float = Field(gt=0)
    revision: str


class Bom(Record):
    kind: Literal["bom"] = "bom"
    assembly_id: str
    edges: list[BomEdge]
    effective_date: date
    lifecycle: Lifecycle = Lifecycle.RELEASED
    expected_leaf_quantity: float = Field(gt=0)


class Change(Record):
    kind: Literal["change"] = "change"
    affected_parts: list[str]
    old_revision: str
    new_revision: str
    approval_status: Literal["approved", "pending", "rejected"]
    effective_date: date


Entity = Annotated[Hardware | Software | Platform | Variant | Bom | Change, Field(discriminator="kind")]


class Dataset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    synthetic: Literal[True] = True
    records: list[Entity]

    def documents(self) -> list[dict]:
        return [record.model_dump(mode="json") for record in self.records]


class Finding(BaseModel):
    finding_id: str
    rule_id: str
    affected_records: list[str]
    severity: Literal["critical", "error", "warning"] = "error"
    evidence: dict
    expected: str
    actual: str
    remediation: str
    verification_status: Literal["failed", "unknown"] = "failed"
