"""Strict, packaged public projections. No repository, provider or database access."""

import hashlib
import json
from importlib.resources import files
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
SampleId = Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")]


class PublicModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class SampleSummary(PublicModel):
    sample_id: SampleId
    version: Literal["1.0.0"]
    title: str
    synthetic: Literal[True]
    artifact_sha256: Hash


class SampleCatalog(PublicModel):
    schema_version: Literal["1.0"]
    samples: list[SampleSummary] = Field(min_length=1, max_length=20)


class Provenance(PublicModel):
    generator: Literal["app.data.generate"]
    seed: int
    source_schema: Literal["A", "B"]
    source_records_sha256: Hash
    target_records_sha256: Hash
    original_report_sha256: Hash
    projection: Literal["public-allowlist-v1"]
    scenario: Literal["equivalent", "hardware-revision-drift"]


class MigrationSummary(PublicModel):
    records: int = Field(ge=0)
    validation_passed: bool
    engineering_findings: int = Field(ge=0)
    twin_differences: int = Field(ge=0)
    disposition: Literal["validation_passed_not_approved", "validation_failed"]


class Difference(PublicModel):
    path: str
    source: str | int | float | bool | None
    target: str | int | float | bool | None


class TwinComparison(PublicModel):
    variant_id: str
    source_fingerprint: Hash
    target_fingerprint: Hash
    differences: list[Difference]


class PublicFinding(PublicModel):
    finding_id: str
    rule_id: str
    severity: str
    affected_records: list[str]
    expected: str
    actual: str


class PublicRecord(PublicModel):
    record_id: str
    kind: str
    revision: str | None
    function: str | None


class PublicEvidence(PublicModel):
    evidence_id: str
    classification: Literal["record_fact", "deterministic_result", "potential_exposure", "unknown"]
    tool: str
    entity_id: str | None
    status: Literal["ok", "error"]
    source_pointer: str
    record: PublicRecord | None


class PublicInvestigation(PublicModel):
    request: str
    mode: Literal["offline"]
    status: Literal["complete", "partial", "limit_reached"]
    identified_components: list[str]
    identified_variants: list[str]
    evidence: list[PublicEvidence]
    findings: list[PublicFinding]
    missing_evidence: list[str]
    uncertainties: list[str]
    recommendations: list[str]


class SampleData(PublicModel):
    sample_id: SampleId
    version: Literal["1.0.0"]
    title: str
    synthetic: Literal[True]
    label: Literal["Synthetic demonstration data - recorded offline, read-only; not engineering approval"]
    provenance: Provenance
    migration: MigrationSummary
    twin: TwinComparison
    investigation: PublicInvestigation


class SampleArtifact(PublicModel):
    schema_version: Literal["1.0"]
    artifact_sha256: Hash
    sample: SampleData


def artifact_hash(value: dict) -> str:
    """Hash only the public sample payload, excluding its wrapping hash field."""
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def load_catalog() -> SampleCatalog:
    catalog = SampleCatalog.model_validate_json(
        files("app").joinpath("public_data", "catalog.json").read_text(encoding="utf-8")
    )
    identifiers = [item.sample_id for item in catalog.samples]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("Duplicate public sample identifier")
    return catalog


def load_sample(sample_id: str) -> SampleArtifact:
    # Resolve only catalog entries; never interpolate an untrusted ID into a path.
    entry = next((item for item in load_catalog().samples if item.sample_id == sample_id), None)
    if entry is None:
        raise KeyError("Unknown public sample")
    artifact = SampleArtifact.model_validate_json(
        files("app").joinpath("public_data", entry.sample_id + ".json").read_text(encoding="utf-8")
    )
    data = artifact.sample
    if (
        data.sample_id != entry.sample_id
        or data.version != entry.version
        or data.title != entry.title
        or artifact.artifact_sha256 != entry.artifact_sha256
        or artifact_hash(data.model_dump(mode="json")) != entry.artifact_sha256
    ):
        raise ValueError("Public artifact integrity check failed")
    return artifact
