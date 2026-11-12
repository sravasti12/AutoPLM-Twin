import csv
import io
import os
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StringConstraints
from pymongo.errors import PyMongoError

from app.data import generate
from app.investigation_review import (
    InvestigationReviews,
    ReviewHistory,
    ReviewInput,
    ReviewQueue,
    StoredInvestigation,
)
from app.investigation_service import (
    BaselineError,
    InvestigationInput,
    InvestigationResponse,
    InvestigationService,
)
from app.repository import Repository, public
from app.review_auth import ReviewPrincipal, authenticated_review_user, authorized_reviewer
from app.service import MigrationService, Upload


@asynccontextmanager
async def lifespan(application: FastAPI):
    if os.environ.get("AUTOPLM_ENVIRONMENT", "local") != "local":
        raise RuntimeError("Non-local startup blocked: production identity provider is not implemented")
    yield


app = FastAPI(
    lifespan=lifespan,
    title="AutoPLM Twin",
    version="0.1.0",
    description="Synthetic engineering prototype. Local trusted-user API; no production authentication.",
)


@app.middleware("http")
async def response_security(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@lru_cache
def get_service():
    return MigrationService(Repository.connect())


@app.exception_handler(KeyError)
async def not_found(request, exc):
    return JSONResponse(status_code=404, content={"detail": "Requested engineering record was not found"})


@app.exception_handler(ValueError)
async def invalid(request, exc):
    return JSONResponse(
        status_code=409,
        content={"detail": "Engineering operation rejected; inspect the job validation report"},
    )


@app.exception_handler(PyMongoError)
async def unavailable(request, exc):
    return JSONResponse(
        status_code=503, content={"detail": "MongoDB unavailable or database operation failed"}
    )


Actor = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GenerateRequest(RequestModel):
    fleets: int = Field(default=2, ge=1, le=1000)
    seed: int = 42
    source: Literal["A", "B"] = "A"


class MigrateRequest(RequestModel):
    dataset: Upload
    mapper: Literal["offline", "llm"] = "offline"


class Decision(RequestModel):
    actor: Actor | None = Field(
        default=None, deprecated=True, description="Ignored; authenticated identity is used"
    )
    approve: StrictBool


class PromotionDecision(RequestModel):
    approve: StrictBool
    actor: Actor | None = Field(
        default=None, deprecated=True, description="Ignored; identity comes from authentication"
    )


class SimulationRequest(RequestModel):
    variant_id: str
    scenario: str = "valid"
    ticks: int = Field(default=5, ge=1, le=1000)
    fault_at: int | None = Field(default=None, ge=0)


@app.get("/health")
def health():
    return {"status": "ok", "database": "not probed; /ready checks MongoDB", "synthetic": True}


@app.get("/ready")
def ready(service=Depends(get_service)):
    service.db.command("ping")
    return {"database": "connected"}


@app.post("/datasets/generate")
def dataset(request: GenerateRequest):
    envelope, _, _ = generate(request.fleets, request.seed, request.source)
    return envelope


@app.post("/jobs")
def migrate(request: MigrateRequest, service=Depends(get_service)):
    return service.migrate(request.dataset.model_dump(mode="json"), request.mapper)


@app.get("/jobs")
def jobs(service=Depends(get_service)):
    return public(list(service.db.migration_jobs.find().sort("created_at", -1).limit(200)))


@app.get("/jobs/{job_id}")
def job(job_id: str, service=Depends(get_service)):
    return public(service.repo.job(job_id))


@app.get("/jobs/{job_id}/approved")
def approved_records(job_id: str, service=Depends(get_service)):
    return public(service.repo.approved_records(job_id))


@app.get("/jobs/{job_id}/report")
def report(job_id: str, format: Literal["json", "csv", "html"] = "json", service=Depends(get_service)):
    data = service.report(job_id)
    if format == "json":
        return data
    if format == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(
            output, fieldnames=["finding_id", "rule_id", "severity", "expected", "actual"]
        )
        writer.writeheader()
        for finding in data["job"].get("validation", {}).get("findings", []):
            writer.writerow({key: finding[key] for key in writer.fieldnames})
        return Response(
            output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{job_id}-findings.csv"'},
        )
    import html
    import json

    return HTMLResponse(
        "<html><head><title>AutoPLM audit</title></head><body><h1>Synthetic migration audit</h1><pre>"
        + html.escape(json.dumps(data, indent=2))
        + "</pre></body></html>"
    )


@app.post("/jobs/{job_id}/promote")
def promote(
    job_id: str,
    request: PromotionDecision,
    principal: ReviewPrincipal = Depends(authorized_reviewer),
    service=Depends(get_service),
):
    if not request.approve:
        raise HTTPException(409, "Promotion requires explicit approval")
    return service.promote(job_id, principal.subject)


@app.post("/jobs/{job_id}/repairs")
def repair(
    job_id: str,
    mapper: Literal["offline", "llm"] = "offline",
    principal: ReviewPrincipal = Depends(authorized_reviewer),
    service=Depends(get_service),
):
    from app.resolution import LLMRepairPlanner

    return service.propose_repair(
        job_id, actor=principal.subject, provider=LLMRepairPlanner() if mapper == "llm" else None
    )


@app.post("/repairs/{proposal_id}/decision")
def decide(
    proposal_id: str,
    request: Decision,
    principal: ReviewPrincipal = Depends(authorized_reviewer),
    service=Depends(get_service),
):
    return service.decide_repair(proposal_id, request.approve, principal.subject)


@app.post("/jobs/{job_id}/simulations")
def simulation(job_id: str, request: SimulationRequest, service=Depends(get_service)):
    return service.run_simulation(job_id, **request.model_dump())


class MappingDecision(RequestModel):
    actor: Actor | None = Field(
        default=None, deprecated=True, description="Ignored; authenticated identity is used"
    )
    plan: dict
    approve: StrictBool


@app.post("/jobs/{job_id}/mappings/decision")
def mapping_decision(
    job_id: str,
    request: MappingDecision,
    principal: ReviewPrincipal = Depends(authorized_reviewer),
    service=Depends(get_service),
):
    return service.decide_mapping(job_id, request.plan, principal.subject, request.approve)


@app.post("/jobs/{job_id}/investigations", response_model=InvestigationResponse)
def engineering_investigation(job_id: str, request: InvestigationInput, service=Depends(get_service)):
    try:
        return InvestigationService(service.repo).run(job_id, request)
    except BaselineError as exc:
        raise HTTPException(exc.status, detail={"code": exc.code, "message": exc.message}) from None
    except PyMongoError:
        raise HTTPException(
            503, detail={"code": "database_unavailable", "message": "Database unavailable"}
        ) from None
    except Exception:
        raise HTTPException(
            500, detail={"code": "investigation_failed", "message": "Investigation failed"}
        ) from None


def review_result(operation):
    try:
        return operation()
    except BaselineError as exc:
        raise HTTPException(exc.status, detail={"code": exc.code, "message": exc.message}) from None
    except PyMongoError:
        raise HTTPException(
            503, detail={"code": "review_database_unavailable", "message": "Review database operation failed"}
        ) from None
    except Exception:
        raise HTTPException(
            500, detail={"code": "review_failed", "message": "Review operation failed"}
        ) from None


@app.get("/review/me", response_model=ReviewPrincipal)
def reviewer_identity(
    response: Response, principal: ReviewPrincipal = Depends(authenticated_review_user)
) -> ReviewPrincipal:
    response.headers["Cache-Control"] = "no-store"
    return principal


@app.post("/jobs/{job_id}/investigation-reports", response_model=StoredInvestigation, status_code=201)
def create_investigation_report(
    job_id: str,
    request: InvestigationInput,
    principal: ReviewPrincipal = Depends(authenticated_review_user),
    service=Depends(get_service),
):
    return review_result(lambda: InvestigationReviews(service.repo).create(job_id, request, principal))


@app.get("/investigation-reports", response_model=ReviewQueue)
def investigation_queue(
    review_status: Literal["pending", "accepted", "rejected", "all"] = "pending",
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=100000),
    principal: ReviewPrincipal = Depends(authenticated_review_user),
    service=Depends(get_service),
):
    return review_result(
        lambda: InvestigationReviews(service.repo).queue(
            None if review_status == "all" else review_status, limit, offset
        )
    )


@app.get("/investigation-reports/{investigation_id}", response_model=StoredInvestigation)
def investigation_report(
    investigation_id: str,
    principal: ReviewPrincipal = Depends(authenticated_review_user),
    service=Depends(get_service),
):
    return review_result(lambda: InvestigationReviews(service.repo).get(investigation_id))


@app.get("/investigation-reports/{investigation_id}/decisions", response_model=ReviewHistory)
def investigation_review_history(
    investigation_id: str,
    principal: ReviewPrincipal = Depends(authenticated_review_user),
    service=Depends(get_service),
):
    return review_result(lambda: InvestigationReviews(service.repo).history(investigation_id))


@app.post("/investigation-reports/{investigation_id}/decisions", response_model=ReviewHistory)
def investigation_review_decision(
    investigation_id: str,
    request: ReviewInput,
    principal: ReviewPrincipal = Depends(authorized_reviewer),
    service=Depends(get_service),
):
    return review_result(
        lambda: InvestigationReviews(service.repo).decide(investigation_id, request, principal)
    )
