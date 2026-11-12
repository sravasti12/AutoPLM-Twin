"""Authoritative, read-only adapter between publication readers and investigations."""

import copy
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.dependencies import build_dependency_graph
from app.investigation import InvestigationReport, investigate
from app.models import Dataset
from app.repository import Repository, digest
from app.source_adapters import normalize_source
from app.twin import build_twin
from app.what_if import baseline_digest

Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=256)]


class InvestigationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10000)]
    variant_id: Identifier
    component_id: Identifier | None = None
    proposal_id: Identifier | None = None
    expected_fingerprint: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    mode: Literal["offline", "llm"] = "offline"
    max_steps: int = Field(default=12, ge=1, le=30, strict=True)


class BaselineContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    baseline_id: str
    job_id: str
    variant_id: str
    component_id: str | None
    publication_digest: str
    baseline_digest: str
    fingerprint: str
    associated_record_ids: list[str]
    source_provenance: list[dict]
    diagnostics: list[dict]


class InvestigationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    baseline: BaselineContext
    report: InvestigationReport


class BaselineError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message
        super().__init__(message)


class InvestigationService:
    def __init__(self, repository: Repository):
        self.repo = repository

    def load(self, job_id: str, request: InvestigationInput) -> tuple[list[dict], BaselineContext]:
        try:
            job = self.repo.job(job_id)
        except KeyError:
            raise BaselineError(404, "baseline_not_found", "Migration job was not found") from None
        if job["status"] != "approved":
            raise BaselineError(
                409, "baseline_not_approved", "Investigation requires an approved publication"
            )
        try:
            records = copy.deepcopy(self.repo.approved_records(job_id))
            source = self.repo.source(job_id)
            expected = normalize_source(source, job["source_schema"])
            records = Dataset.model_validate({"records": records}).documents()
            if not records:
                raise ValueError("Empty publication")
            actual_digest = baseline_digest(records)
            if actual_digest != baseline_digest(expected):
                raise ValueError("Publication differs from authoritative source")
            by_id = {r["id"]: r for r in records}
            # Preserve source ordering for legacy twin list serialization/fingerprints.
            records = [by_id[r["id"]] for r in expected]
            graph = build_dependency_graph(records)
        except (ValueError, KeyError, TypeError):
            raise BaselineError(
                409, "baseline_integrity", "Baseline integrity or source provenance failed"
            ) from None
        variant = by_id.get(request.variant_id)
        if variant is None or variant["kind"] != "variant":
            raise BaselineError(404, "variant_not_found", "Vehicle variant was not found in the baseline")
        blocking = [i for i in graph.issues if i.code != "UNASSESSED_RELATIONSHIP"]
        if blocking:
            raise BaselineError(
                409, "inconsistent_references", "Baseline has missing or inconsistent relationships"
            )
        twin = build_twin(copy.deepcopy(records), request.variant_id)
        source_twin = build_twin(copy.deepcopy(expected), request.variant_id)
        if twin["fingerprint"] != source_twin["fingerprint"] or (
            request.expected_fingerprint is not None and request.expected_fingerprint != twin["fingerprint"]
        ):
            raise BaselineError(
                409, "fingerprint_mismatch", "Baseline fingerprint does not match expectations"
            )
        associated = {
            request.variant_id,
            variant["platform_id"],
            *variant["installed_ecus"],
            *variant["software_configuration"].values(),
        }
        associated.update(r["id"] for r in twin["boms"] + twin["changes"])
        structure = twin.get("product_structure", {})
        for field in ("components", "boms", "changes"):
            associated.update(structure.get(field, {}))
        if request.component_id is not None:
            if request.component_id not in by_id:
                raise BaselineError(404, "component_not_found", "Component was not found in the baseline")
            if request.component_id not in associated:
                raise BaselineError(
                    409, "component_outside_variant", "Component is outside the selected variant"
                )
        if request.proposal_id is not None:
            raise BaselineError(
                422, "proposal_store_unavailable", "Persisted engineering proposals are not supported"
            )
        provenance = [
            {
                "record_id": record["id"],
                "source_id": row["source_id"],
                "source_schema": job["source_schema"],
                "source_sha256": digest(row),
            }
            for row, record in zip(source, expected, strict=True)
        ]
        return records, BaselineContext(
            baseline_id=f"approved:{job_id}",
            job_id=job_id,
            variant_id=request.variant_id,
            component_id=request.component_id,
            publication_digest=job["approved_digest"],
            baseline_digest=actual_digest,
            fingerprint=twin["fingerprint"],
            associated_record_ids=sorted(associated),
            source_provenance=provenance,
            diagnostics=[i.model_dump(mode="json") for i in graph.issues],
        )

    def run(self, job_id: str, request: InvestigationInput, *, provider=None) -> InvestigationResponse:
        records, context = self.load(job_id, request)
        # Explicit context complements natural-language extraction without altering the original request.
        from app.investigation import LLMInvestigator, OfflineInvestigator

        delegate = provider
        if delegate is None and request.mode == "offline":
            delegate = OfflineInvestigator()
        elif delegate is None:
            try:
                delegate = LLMInvestigator()
            except Exception:
                delegate = None  # Phase 4A records sanitized initialization failures.

        class ContextProvider:
            def extract(self, text, catalog):
                from app.investigation import InvestigationRequest

                result = delegate.extract(text, catalog)
                spec = InvestigationRequest.model_validate(
                    result.model_dump() if isinstance(result, BaseModel) else result
                )
                spec.variants = sorted(set(spec.variants + [request.variant_id]))
                if request.component_id:
                    spec.components = sorted(set(spec.components + [request.component_id]))
                return spec

            def decide(self, state):
                return delegate.decide(state)

        report = investigate(
            request.request,
            records,
            provider=ContextProvider() if delegate else None,
            mode=request.mode,
            max_steps=request.max_steps,
        )
        # Detect publication/source changes during execution; never return a stale success snapshot.
        current_records, current_context = self.load(job_id, request)
        if baseline_digest(current_records) != context.baseline_digest or current_context != context:
            raise BaselineError(
                409, "baseline_changed", "Authoritative baseline changed during investigation"
            )
        return InvestigationResponse(baseline=context, report=report)
