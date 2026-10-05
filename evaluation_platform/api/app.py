import os
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from evaluation_platform.service import Platform


class RegisterRequest(BaseModel):
    path: str


class ExecutionRequest(BaseModel):
    input: str = Field(min_length=1)


class RunRequest(BaseModel):
    dataset_id: str
    kind: Literal["registration", "regression", "platform_quality"] = "regression"
    dependency_ids: list[str] | None = None


def create_app(platform=None):
    platform = platform or Platform(os.getenv("EVAL_DATA_DIR", "data"))
    app = FastAPI(title="GAIA Agent Evaluation Platform", version="1.0")
    app.state.platform = platform

    @app.middleware("http")
    async def local_origin_guard(request: Request, call_next):
        # Prevent a malicious website from posting to the trusted-code local API.
        from urllib.parse import urlparse
        origin = request.headers.get("origin")
        if origin and urlparse(origin).netloc != request.headers.get("host"):
            return JSONResponse({"detail": "Cross-origin access denied"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'"
        return response

    @app.exception_handler(KeyError)
    async def not_found(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=404)

    @app.exception_handler(ValueError)
    async def invalid(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.get("/api/health")
    def health():
        return {"platform": "ok", "phoenix": platform.phoenix.health()}

    @app.get("/api/agents")
    def agents():
        return platform.store.list("agents")

    @app.post("/api/agents", status_code=201)
    def register(body: RegisterRequest):
        return platform.register(body.path)

    @app.post("/api/agents/{agent_id}/execute")
    def execute(agent_id: str, body: ExecutionRequest):
        return platform.execute(agent_id, body.input).model_dump()

    @app.get("/api/agents/{agent_id}/analysis")
    def analysis(agent_id: str):
        return platform.analysis(agent_id)

    @app.post("/api/agents/{agent_id}/generate")
    def generate(agent_id: str):
        return platform.generate(agent_id)

    @app.get("/api/agents/{agent_id}/cases")
    def cases(agent_id: str):
        return [c.model_dump() for c in platform.candidates(agent_id)]

    @app.post("/api/agents/{agent_id}/cases", status_code=201)
    def add(agent_id: str, body: dict):
        return platform.add_case(agent_id, body)

    @app.patch("/api/agents/{agent_id}/cases/{case_id}")
    def edit(agent_id: str, case_id: str, body: dict):
        return platform.save_case(agent_id, case_id, body)

    @app.delete("/api/agents/{agent_id}/cases/{case_id}")
    def delete(agent_id: str, case_id: str):
        platform.delete_case(agent_id, case_id)
        return {"deleted": case_id}

    @app.post("/api/agents/{agent_id}/golden", status_code=201)
    def golden(agent_id: str, body: dict):
        return platform.golden(agent_id, body.get("bindings", []))

    @app.get("/api/golden")
    def datasets():
        return platform.store.list("golden")

    @app.get("/api/evaluators")
    def evaluators():
        return {"catalog": platform.registry().catalog(), "custom": platform.store.list("judges")}

    @app.post("/api/evaluators/preview")
    def preview(body: dict):
        return platform.preview_judge(body["definition"], body["case"], body["answer"])

    @app.post("/api/evaluators", status_code=201)
    def create_judge(body: dict):
        return platform.register_judge(body["definition"], body["preview_id"])

    @app.post("/api/runs", status_code=201)
    def run(body: RunRequest):
        return platform.run(body.dataset_id, body.kind, body.dependency_ids)

    @app.get("/api/runs")
    def runs():
        return platform.store.list("runs")

    @app.get("/api/runs/{run_id}")
    def run_detail(run_id: str):
        return platform.store.get("runs", run_id)

    @app.get("/api/audit")
    def audit():
        return platform.store.list("audit")

    ui = Path(__file__).resolve().parents[2] / "ui"
    app.mount("/static", StaticFiles(directory=ui), name="static")

    @app.get("/")
    def index():
        return FileResponse(ui / "index.html")

    return app
