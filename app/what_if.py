"""Pure, in-memory engineering assessment; never migration or change authorization."""

import copy
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.dependencies import build_dependency_graph, reverse_dependencies
from app.models import Dataset, Entity
from app.repository import digest
from app.twin import build_twin, compare_twins
from app.verification import verify


class ProposalModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RecordChange(ProposalModel):
    """Whole-record replacement avoids ambiguous nested patch semantics."""

    operation: Literal["add", "replace", "remove"]
    record_id: str = Field(min_length=1)
    record: Entity | None = None


class EngineeringProposal(ProposalModel):
    proposal_id: str = Field(min_length=1)
    baseline_reference: str = Field(min_length=1)
    baseline_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    creator: str = Field(min_length=1)
    created_at: datetime
    job_id: str | None = None
    product_id: str | None = None
    variant_ids: tuple[str, ...] = ()
    changes: tuple[RecordChange, ...] = Field(min_length=1)
    evidence: tuple[str, ...] = ()

    @field_validator("created_at")
    @classmethod
    def aware_timestamp(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Proposal timestamp must include a timezone")
        return value


class Assessment(ProposalModel):
    proposal: EngineeringProposal
    status: Literal["assessed", "stale", "discarded"]
    proposed_snapshot: list[dict] | None = None
    report: dict = Field(default_factory=dict)


def _records(records: list[dict]) -> list[dict]:
    result = Dataset.model_validate({"records": copy.deepcopy(records)}).documents()
    if len({r["id"] for r in result}) != len(result):
        raise ValueError("Baseline record identities must be unique")
    return sorted(result, key=lambda r: r["id"])


def baseline_digest(records: list[dict]) -> str:
    """Canonical model defaults and record ordering; list semantics remain unchanged."""
    return digest(_records(records))


def assess(
    proposal: EngineeringProposal,
    baseline: list[dict],
    *,
    as_of: date = date(2025, 6, 1),
    max_depth: int = 20,
    max_entities: int = 1000,
) -> Assessment:
    # Revalidate nested models, which callers may have mutated after construction.
    proposal = EngineeringProposal.model_validate(proposal.model_dump(mode="json"))
    original = _records(baseline)
    if digest(original) != proposal.baseline_digest:
        return Assessment(proposal=proposal, status="stale", report={"reason": "Baseline digest changed"})
    before = {r["id"]: r for r in original}
    after = copy.deepcopy(before)
    changed = sorted(change.record_id for change in proposal.changes)
    if len(set(changed)) != len(changed):
        raise ValueError("Only one operation per record is supported")
    for change in sorted(proposal.changes, key=lambda c: c.record_id):
        exists = change.record_id in before
        if (change.operation == "add") == exists:
            raise ValueError("Change operation does not match baseline identity")
        if change.operation == "remove":
            if change.record is not None:
                raise ValueError("Remove must not include a replacement")
            del after[change.record_id]
        else:
            if change.record is None or change.record.id != change.record_id:
                raise ValueError("Replacement must match the change identity")
            record = change.record.model_dump(mode="json")
            if exists and record["kind"] != before[change.record_id]["kind"]:
                raise ValueError("Changing an entity kind is unsupported")
            after[change.record_id] = record
    candidate = sorted(after.values(), key=lambda r: r["id"])
    variants = sorted({r["id"] for r in original + candidate if r["kind"] == "variant"})
    if set(proposal.variant_ids) - set(variants):
        raise ValueError("Unknown variant context")
    # Always compare every variant: a requested context cannot hide shared-record exposure.
    twins = {}
    for variant in variants:
        left = build_twin(copy.deepcopy(original), variant) if variant in before else {}
        right = build_twin(copy.deepcopy(candidate), variant) if variant in after else {}
        twins[variant] = {"original": left, "proposed": right, "differences": compare_twins(left, right)}
    impact = {}
    diagnostics = {}
    for label, records in (("original", original), ("proposed", candidate)):
        graph = build_dependency_graph(records)
        diagnostics[label] = [issue.model_dump(mode="json") for issue in graph.issues]
        impact[label] = {
            identifier: reverse_dependencies(
                graph, identifier, max_depth=max_depth, max_entities=max_entities
            ).model_dump(mode="json")
            for identifier in changed
            if identifier in {r["id"] for r in records}
        }
    return Assessment(
        proposal=proposal,
        status="assessed",
        proposed_snapshot=copy.deepcopy(candidate),
        report={
            "assessment": "potential_only",
            "as_of": as_of.isoformat(),
            "direct_changes": [
                {"id": identifier, "before": before.get(identifier), "after": after.get(identifier)}
                for identifier in changed
            ],
            "baseline_findings": [f.model_dump(mode="json") for f in verify(original, as_of=as_of)],
            "proposed_findings": [f.model_dump(mode="json") for f in verify(candidate, as_of=as_of)],
            "twins": twins,
            "impact": impact,
            "diagnostics": diagnostics,
            "unassessed": [
                "Exposure is not compatibility, safety approval or authorization.",
                "Physical fit, strength and unsupported relationships remain unassessed.",
                "Traversal bounds may truncate paths; inspect each traversal's truncated flag.",
            ],
        },
    )


def discard(assessment: Assessment) -> Assessment:
    """Return a discarded copy with candidate/evaluation payload removed; no storage writes."""
    return Assessment(proposal=assessment.proposal.model_copy(deep=True), status="discarded")
