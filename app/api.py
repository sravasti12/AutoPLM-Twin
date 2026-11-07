import csv
import io
from functools import lru_cache
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StringConstraints
from pymongo.errors import PyMongoError

from app.data import generate
from app.repository import Repository, public
from app.service import MigrationService, Upload

app = FastAPI(
    title="AutoPLM Twin",
    version="0.1.0",
    description="Synthetic engineering prototype. Local trusted-user API; no production authentication.",
)


@lru_cache
def get_service():
    return MigrationService(Repository.connect())


@app.exception_handler(KeyError)
async def not_found(request, exc):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(ValueError)
async def invalid(request, exc):
    return JSONResponse(status_code=409, content={"detail": str(exc)[:1000]})


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
    actor: Actor
    approve: StrictBool


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
def promote(job_id: str, request: Decision, service=Depends(get_service)):
    if not request.approve:
        raise HTTPException(409, "Promotion requires explicit approval")
    return service.promote(job_id, request.actor)


@app.post("/jobs/{job_id}/repairs")
def repair(job_id: str, mapper: Literal["offline", "llm"] = "offline", service=Depends(get_service)):
    from app.resolution import LLMRepairPlanner

    return service.propose_repair(
        job_id, actor=mapper, provider=LLMRepairPlanner() if mapper == "llm" else None
    )


@app.post("/repairs/{proposal_id}/decision")
def decide(proposal_id: str, request: Decision, service=Depends(get_service)):
    return service.decide_repair(proposal_id, request.approve, request.actor)


@app.post("/jobs/{job_id}/simulations")
def simulation(job_id: str, request: SimulationRequest, service=Depends(get_service)):
    return service.run_simulation(job_id, **request.model_dump())


class MappingDecision(RequestModel):
    actor: Actor
    plan: dict
    approve: StrictBool


@app.post("/jobs/{job_id}/mappings/decision")
def mapping_decision(job_id: str, request: MappingDecision, service=Depends(get_service)):
    return service.decide_mapping(job_id, request.plan, request.actor, request.approve)
