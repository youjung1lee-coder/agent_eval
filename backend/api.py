import hmac
from pathlib import Path
from typing import Literal
import httpx
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from . import schema_v1 as s
from .adapters import clean, demo, phoenix, setting
from .datasets import convert, edit, import_dataset, record
from .db import add, engine, now, one, rows, uid
from .experiments import compare, detail, launch, refresh
from .metrics import catalog, evaluate, preview, recommend

app = FastAPI(title="GAIA Evaluation", version="1.0")


def auth(request: Request, authorization: str = Header("")):
    if demo():
        return "demo"
    token = authorization.removeprefix("Bearer ")
    for role, key in [("editor", "GAIA_API_KEY"), ("reader", "GAIA_READ_KEY")]:
        if (
            setting(key)
            and authorization.startswith("Bearer ")
            and hmac.compare_digest(token.encode(), setting(key).encode())
        ):
            if role == "reader" and request.method != "GET":
                raise HTTPException(403, "편집 권한 필요")
            return role
    raise HTTPException(401, "API 키 인증 필요")


api = APIRouter(prefix="/api", dependencies=[Depends(auth)])


def conn():
    with engine.begin() as c:
        yield c


DB = Depends(conn)


@app.exception_handler(ValueError)
async def invalid(_, exc):
    return JSONResponse({"detail": str(exc)}, 422)


@app.exception_handler(IntegrityError)
async def conflict(_, exc):
    return JSONResponse(
        {"detail": "동시 변경 또는 중복 요청 · 새로고침 후 확인하세요"}, 409
    )


@app.exception_handler(httpx.HTTPError)
async def upstream(_, exc):
    return JSONResponse(
        {"detail": "외부 서비스 연결 실패 · 주소 및 권한을 확인하세요"}, 502
    )


@app.get("/health")
def health():
    from sqlalchemy import text

    with engine.connect() as c:
        c.execute(text("SELECT 1"))
    return {"status": "ok"}


@api.get("/state")
def state(c=DB):
    datasets = rows(c, s.datasets)
    for d in datasets:
        d["versions"] = sorted(
            rows(c, s.versions, s.versions.c.dataset == d["id"]),
            key=lambda v: -v["number"],
        )
        for v in d["versions"]:
            v["count"] = len(rows(c, s.cases, s.cases.c.version == v["id"]))
    mappings = rows(c, s.mappings)
    for m in mappings:
        m["definition"] = one(c, s.evaluators, m["evaluator"])
    return dict(
        datasets=datasets,
        mappings=mappings,
        metrics=list(catalog().values()),
        experiments=sorted(
            rows(c, s.experiments), key=lambda x: x["created"], reverse=True
        ),
        mode="Demo" if demo() else "Authenticated",
        phoenix=setting("PHOENIX_MODE", "fixture"),
        agent_mode=setting("AGENT_MODE", "mock"),
    )


@api.get("/sources")
def sources():
    return clean(phoenix().list())


@api.get("/sources/{source}/versions")
def source_versions(source: str):
    return clean(phoenix().versions(source))


@api.get("/sources/{source}/preview")
def source_preview(source: str, version: str):
    items = phoenix().load(source, version)
    return {"count": len(items), "samples": [convert(source, x)[0] for x in items[:3]]}


class Import(BaseModel):
    source: str
    version: str
    agent: str = Field(default="policy-agent", min_length=1, max_length=100)


@api.post("/imports")
def importing(body: Import, c=DB):
    return import_dataset(c, body.source, body.version, body.agent)


@api.get("/versions/{vid}/cases")
def samples(vid: str, c=DB):
    one(c, s.versions, vid)
    items = rows(c, s.cases, s.cases.c.version == vid)
    return [
        {**x, "record": record(c, x)}
        for x in sorted(items, key=lambda x: x["data"]["source"]["dataset_item_id"])
    ]


class Edit(BaseModel):
    expected_output: object = None
    expected_behavior: object = None
    input: dict | str | None = None


@api.patch("/versions/{vid}/cases/{cid}")
def editing(vid: str, cid: str, b: Edit, c=DB):
    return edit(c, vid, cid, b.model_dump(exclude_unset=True))


class Definition(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    metric: Literal[
        "tools",
        "exact",
        "faith",
        "numeric",
        "present",
        "judge",
        "goal",
        "task",
        "relevancy",
        "deep_faith",
        "precision",
        "recall",
    ]
    description: str = ""
    threshold: float = Field(default=0.5, ge=0, le=1)
    prompt: str = "{{input}}\n{{actual_output}}"
    rubric: str = "응답의 정확성과 관련성"
    score_type: Literal["number", "boolean", "category"] = "number"
    categories: dict[str, float] = Field(
        default_factory=lambda: {"pass": 1.0, "fail": 0.0}
    )
    retries: int = Field(default=0, ge=0, le=2)
    model: str = ""
    timeout: int = Field(default=60, ge=1, le=120)
    temperature: float = Field(default=0, ge=0, le=2)


class Mapping(BaseModel):
    version: str
    sample: str
    spec: Definition
    rules: dict[str, dict]
    family: str | None = None
    evaluator: str | None = None


def selected(c, b):
    sample = one(c, s.cases, b.sample)
    if sample["version"] != b.version:
        raise ValueError("Dataset 버전 불일치")
    return record(c, sample)


@api.get("/recommend/{sample}/{metric}")
def recommendation(sample: str, metric: str, c=DB):
    if metric not in catalog():
        raise ValueError("Metric 없음")
    return recommend(record(c, one(c, s.cases, sample)), metric)


@api.post("/mapping/{action}")
def mapping(
    action: Literal["preview", "test", "validate", "publish"], b: Mapping, c=DB
):
    rec = selected(c, b)
    spec = clean(b.spec.model_dump())
    if catalog()[spec["metric"]]["model_requirement"] and not spec["model"]:
        spec["model"] = setting("JUDGE_MODEL")
    if any(not 0 <= v <= 1 for v in spec["categories"].values()):
        raise ValueError("범주별 점수는 0부터 1 사이여야 합니다")
    rules = clean(b.rules)
    if action == "preview":
        return preview(rec, spec, rules)
    if action == "test":
        return evaluate(rec, spec, rules)
    if action == "validate":
        details = []
        for x in rows(c, s.cases, s.cases.c.version == b.version):
            fields = preview(record(c, x), spec, rules)
            details.append(
                {
                    "case_id": x["case_id"],
                    "ok": all(f["ok"] for f in fields.values()),
                    "fields": fields,
                }
            )
        return {
            "total": len(details),
            "valid": sum(x["ok"] for x in details),
            "cases": details,
        }
    if not all(i["ok"] for i in preview(rec, spec, rules).values()):
        raise ValueError("선택 케이스의 필수 매핑을 확인하세요")
    v = one(c, s.versions, b.version)
    agent = one(c, s.datasets, v["dataset"])["agent"]
    if b.evaluator:
        e = one(c, s.evaluators, b.evaluator)
        if e["spec"] != spec:
            raise ValueError("기존 정의의 새 매핑은 동일 설정이 필요합니다")
        eid = e["id"]
    else:
        family = b.family or uid()
        number = len(rows(c, s.evaluators, s.evaluators.c.family == family)) + 1
        eid = add(
            c, s.evaluators, family=family, number=number, spec=spec, created=now()
        )
    return {
        "mapping": add(
            c, s.mappings, evaluator=eid, agent=agent, rules=rules, created=now()
        )
    }


class Run(BaseModel):
    version: str
    mode: Literal["historical", "single", "ab"]
    environment: Literal["STG", "PRD"] = "STG"
    name: str = Field(min_length=1, max_length=120)
    selection: list[str] = Field(min_length=1, max_length=20)
    baseline: str | None = None
    request_id: str = Field(min_length=1, max_length=128)


@api.post("/preflight")
def preflight(b: Run, c=DB):
    samples = rows(c, s.cases, s.cases.c.version == b.version)
    checks = []
    for mid in b.selection:
        m = one(c, s.mappings, mid)
        spec = one(c, s.evaluators, m["evaluator"])["spec"]
        failures = []
        for sample in samples:
            fields = preview(record(c, sample), spec, m["rules"])
            if any(not f["ok"] for f in fields.values()):
                failures.append(sample["case_id"])
        checks.append(
            {
                "name": spec["name"],
                "valid": len(samples) - len(failures),
                "missing": failures,
                "engine_ready": catalog()[spec["metric"]]["available"],
            }
        )
    return {
        "cases": len(samples),
        "checks": checks,
        "estimated_cost": None,
        "note": "가져온 Trace 기준입니다. 신규 실행 결과의 구조는 달라질 수 있습니다.",
    }


@api.post("/experiments")
def run(b: Run, c=DB, role=Depends(auth)):
    def create(env, suffix=""):
        return launch(
            c,
            b.version,
            "single" if b.mode == "ab" else b.mode,
            env,
            b.name + suffix,
            b.selection,
            b.request_id + suffix,
            role,
            b.baseline,
        )

    if b.mode == "ab":
        a, bid = create("PRD", " · A"), create("STG", " · B")
        existing = rows(
            c,
            s.comparisons,
            s.comparisons.c.baseline == a,
            s.comparisons.c.candidate == bid,
        )
        if not existing:
            add(c, s.comparisons, baseline=a, candidate=bid, created=now())
        return {"id": bid, "baseline": a}
    return {"id": create(b.environment)}


@api.get("/experiments/{eid}")
def experiment(eid: str, c=DB):
    return detail(c, eid)


@api.get("/compare")
def comparison(a: str, b: str, c=DB):
    return compare(c, a, b)


@api.post("/experiments/{eid}/{action}")
def control(eid: str, action: Literal["retry", "cancel"], job: str | None = None, c=DB):
    one(c, s.experiments, eid)
    query = s.jobs.update().where(s.jobs.c.experiment == eid)
    if job:
        query = query.where(s.jobs.c.id == job)
    if action == "retry":
        query = query.where(s.jobs.c.status == "ERROR").values(
            status="QUEUED", error=""
        )
    else:
        query = query.where(s.jobs.c.status == "QUEUED").values(status="CANCELLED")
    changed = c.execute(query).rowcount
    refresh(c, eid)
    return {"affected": changed}


app.include_router(api)
dist = Path(__file__).resolve().parents[1] / "frontend/dist"
if dist.exists():
    app.mount("/", StaticFiles(directory=dist, html=True), name="ui")
