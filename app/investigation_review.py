"""Durable report snapshots and atomic recommendation review, never change approval."""

from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.investigation_service import (
    BaselineError,
    InvestigationInput,
    InvestigationResponse,
    InvestigationService,
)
from app.repository import Repository, digest
from app.review_auth import ReviewPrincipal

ReviewStatus = Literal["pending", "accepted", "rejected"]


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["ACCEPT", "REJECT"]
    comments: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10000)]


class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision_id: str
    investigation_id: str
    reviewer: str
    decision: Literal["ACCEPT", "REJECT"]
    comments: str
    decided_at: datetime
    baseline_fingerprint: str
    report_digest: str
    audit_event_id: str


class StoredInvestigation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    investigation_id: str
    created_at: datetime
    created_by: str
    input: InvestigationInput
    investigation: InvestigationResponse
    report_digest: str
    review_status: ReviewStatus
    decisions: list[ReviewDecision] = Field(default_factory=list)


class ReviewHistory(BaseModel):
    investigation_id: str
    decisions: list[ReviewDecision]
    audit_mirrored: bool


class ReviewQueue(BaseModel):
    items: list[StoredInvestigation]
    limit: int
    offset: int


class InvestigationReviews:
    def __init__(self, repository: Repository):
        self.repo = repository
        self.collection = repository.db.investigation_reports

    def _read(self, row: dict | None) -> StoredInvestigation:
        if row is None:
            raise BaselineError(404, "investigation_not_found", "Investigation report was not found")
        payload = {key: value for key, value in row.items() if key != "_id"}
        try:
            result = StoredInvestigation.model_validate(payload)
            if result.report_digest != digest(
                {
                    "input": result.input.model_dump(mode="json"),
                    "investigation": result.investigation.model_dump(mode="json"),
                }
            ):
                raise ValueError("Report digest mismatch")
            if result.investigation_id != row["_id"]:
                raise ValueError("Report identity mismatch")
            if result.review_status == "pending" and result.decisions:
                raise ValueError("Invalid pending history")
            if result.review_status != "pending":
                if len(result.decisions) != 1:
                    raise ValueError("Invalid decision history")
                decision = result.decisions[0]
                expected = "accepted" if decision.decision == "ACCEPT" else "rejected"
                if (
                    result.review_status != expected
                    or decision.investigation_id != result.investigation_id
                    or decision.report_digest != result.report_digest
                    or decision.baseline_fingerprint != result.investigation.baseline.fingerprint
                ):
                    raise ValueError("Decision binding mismatch")
            return result
        except (ValueError, KeyError):
            raise BaselineError(
                409, "report_integrity", "Stored investigation integrity check failed"
            ) from None

    def create(
        self, job_id: str, request: InvestigationInput, principal: ReviewPrincipal
    ) -> StoredInvestigation:
        response = InvestigationService(self.repo).run(job_id, request)
        identifier = str(uuid4())
        payload = {
            "input": request.model_dump(mode="json"),
            "investigation": response.model_dump(mode="json"),
        }
        result = StoredInvestigation(
            investigation_id=identifier,
            created_at=datetime.now(timezone.utc),
            created_by=principal.subject,
            input=request,
            investigation=response,
            report_digest=digest(payload),
            review_status="pending",
        )
        # A single document preserves the immutable report and its terminal decision together.
        self.collection.insert_one({"_id": identifier, **result.model_dump(mode="json")})
        return result

    def get(self, identifier: str) -> StoredInvestigation:
        return self._read(self.collection.find_one({"_id": identifier}))

    def queue(self, status: ReviewStatus | None = "pending", limit: int = 50, offset: int = 0) -> ReviewQueue:
        query = {"review_status": status} if status else {}
        rows = self.collection.find(query).sort([("created_at", 1), ("_id", 1)]).skip(offset).limit(limit)
        return ReviewQueue(items=[self._read(row) for row in rows], limit=limit, offset=offset)

    def history(self, identifier: str) -> ReviewHistory:
        report = self.get(identifier)
        mirrored = all(
            self.repo.db.audit_events.find_one({"_id": d.audit_event_id}) is not None
            for d in report.decisions
        )
        return ReviewHistory(investigation_id=identifier, decisions=report.decisions, audit_mirrored=mirrored)

    def decide(self, identifier: str, request: ReviewInput, principal: ReviewPrincipal) -> ReviewHistory:
        if "engineering_reviewer" not in principal.roles:
            raise BaselineError(403, "review_forbidden", "Engineering reviewer role required")
        report = self.get(identifier)
        decision = ReviewDecision(
            decision_id=str(uuid4()),
            investigation_id=identifier,
            reviewer=principal.subject,
            decision=request.decision,
            comments=request.comments,
            decided_at=datetime.now(timezone.utc),
            baseline_fingerprint=report.investigation.baseline.fingerprint,
            report_digest=report.report_digest,
            audit_event_id=str(uuid4()),
        )
        row = self.collection.find_one_and_update(
            {
                "_id": identifier,
                "review_status": "pending",
                "report_digest": report.report_digest,
                "decisions": [],
            },
            {
                "$set": {"review_status": "accepted" if request.decision == "ACCEPT" else "rejected"},
                "$push": {"decisions": decision.model_dump(mode="json")},
            },
            return_document=ReturnDocument.AFTER,
        )
        if row is None:
            raise BaselineError(409, "already_reviewed", "Investigation has already been reviewed or changed")
        self._read(row)
        # Canonical audit is embedded atomically. Mirror through existing audit infrastructure.
        mirrored = True
        try:
            self.repo.audit(
                report.investigation.baseline.job_id,
                "investigation_recommendation_reviewed",
                decision.model_dump(mode="json"),
                event_id=decision.audit_event_id,
            )
        except DuplicateKeyError:
            pass
        except PyMongoError:
            mirrored = False
        return ReviewHistory(investigation_id=identifier, decisions=[decision], audit_mirrored=mirrored)
