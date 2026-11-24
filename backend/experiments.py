from collections import Counter
from datetime import datetime, timedelta, timezone
import time
from sqlalchemy import and_, or_, select
from fastapi import HTTPException
from . import schema_v1 as s
from .schema_v2 import attempts
from .adapters import HTTPAgent, demo, setting
from .db import add, engine, now, one, rows, uid
from .datasets import record
from .metrics import evaluate
from .summary import summarize


def launch(
    c, version, mode, environment, name, selection, request_id, author, baseline=None
):
    old = rows(c, s.experiments, s.experiments.c.request_id == request_id)
    if old:
        return old[0]["id"]
    v = one(c, s.versions, version)
    ds = one(c, s.datasets, v["dataset"])
    if not selection or len(selection) != len(set(selection)):
        raise ValueError("중복 없는 Evaluator 선택 필요")
    for mid in selection:
        if one(c, s.mappings, mid)["agent"] != ds["agent"]:
            raise ValueError("에이전트 매핑 불일치")
    historical = mode == "historical"
    if (
        not historical
        and setting("AGENT_MODE", "mock") != "mock"
        and (
            environment == "PRD"
            or demo()
            or ds["agent"] != setting("STG_ALLOWED_AGENT")
            or not setting("STG_AGENT_TOKEN")
        )
    ):
        raise HTTPException(403, "실제 Agent 실행 정책 차단")
    samples = rows(c, s.cases, s.cases.c.version == version)
    if not samples:
        raise ValueError("빈 Dataset")
    eid = add(
        c,
        s.experiments,
        version=version,
        agent=ds["agent"],
        environment="Phoenix" if historical else environment,
        mode=mode,
        name=name,
        selection=selection,
        created=now(),
        author=author,
        status="QUEUED",
        request_id=request_id,
    )
    references = {}
    if baseline:
        previous = one(c, s.experiments, baseline)
        if not historical or previous["version"] != version:
            raise ValueError("같은 Dataset 버전의 기존 실행을 지정하세요")
        references = {
            j["sample"]: j["execution"]
            for j in rows(c, s.jobs, s.jobs.c.experiment == baseline)
            if j["execution"] and j["status"] == "DONE"
        }
        if len(references) != len(samples):
            raise ValueError("기준 실험의 실행이 완료되어야 합니다")
        c.execute(
            s.experiments.update()
            .where(s.experiments.c.id == eid)
            .values(environment=previous["environment"])
        )
    for x in samples:
        add(
            c,
            s.jobs,
            experiment=eid,
            sample=x["id"],
            execution=references.get(x["id"], x["execution"]) if historical else None,
            status="QUEUED",
            lease="",
            owner="",
            error="",
        )
    return eid


def compare(c, a, b):
    left, right = [one(c, s.experiments, k) for k in (a, b)]
    if (
        a == b
        or left["version"] != right["version"]
        or sorted(left["selection"]) != sorted(right["selection"])
    ):
        raise HTTPException(
            409, "동일 Dataset·Evaluator·매핑 버전의 서로 다른 실험을 선택하세요"
        )
    by_case = [{x["case_id"]: x for x in detail(c, e)["cases"]} for e in (a, b)]
    output = []
    for case_id, x in by_case[0].items():
        y = by_case[1][case_id]
        for mid in left["selection"]:
            p, q = x["scores"].get(mid, {}), y["scores"].get(mid, {})
            delta, label = None, "NOT_EVALUABLE"
            if p.get("score") is not None and q.get("score") is not None:
                delta = q["score"] - p["score"]
                label = (
                    "regression"
                    if p["passed"] and not q["passed"]
                    else "improvement"
                    if q["passed"] and not p["passed"]
                    else "win"
                    if delta > 0
                    else "loss"
                    if delta < 0
                    else "tie"
                )
            output.append(
                dict(case_id=case_id, mapping=mid, delta=delta, label=label, a=x, b=y)
            )
    output.sort(key=lambda x: x["label"] != "regression")
    return {"counts": dict(Counter(x["label"] for x in output)), "pairs": output}


def detail(c, eid):
    exp = one(c, s.experiments, eid)
    items = []
    for j in rows(c, s.jobs, s.jobs.c.experiment == eid):
        sample = one(c, s.cases, j["sample"])
        scores = {
            x["mapping"]: x["data"]
            for x in rows(c, s.results, s.results.c.job == j["id"])
        }
        rec = record(c, sample, j["execution"]) if j["execution"] else sample["data"]
        items.append(
            {
                **j,
                "case_id": sample["case_id"],
                "record": rec,
                "scores": scores,
                "attempts": rows(c, attempts, attempts.c.job == j["id"]),
            }
        )
    return {**exp, "cases": items, "summary": summarize(items)}


def refresh(c, eid):
    c.execute(
        select(s.experiments.c.id).where(s.experiments.c.id == eid).with_for_update()
    )
    states = [r["status"] for r in rows(c, s.jobs, s.jobs.c.experiment == eid)]
    if "RUNNING" in states or "QUEUED" in states:
        state = "RUNNING"
    elif "CANCELLED" in states:
        state = "CANCELLED"
    elif "ERROR" in states:
        state = "FAILED" if all(x == "ERROR" for x in states) else "PARTIAL"
    else:
        state = "DONE"
    c.execute(
        s.experiments.update().where(s.experiments.c.id == eid).values(status=state)
    )


def process_one():
    token = uid()
    eligible = or_(
        s.jobs.c.status == "QUEUED",
        and_(s.jobs.c.status == "RUNNING", s.jobs.c.lease < now()),
    )
    with engine.begin() as c:
        j = (
            c.execute(
                select(s.jobs)
                .where(eligible)
                .order_by(s.jobs.c.id)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            .mappings()
            .first()
        )
        if not j:
            return False

        def lease():
            return (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()

        if not c.execute(
            s.jobs.update()
            .where(s.jobs.c.id == j["id"], eligible)
            .values(status="RUNNING", owner=token, lease=lease())
        ).rowcount:
            return True
        exp = one(c, s.experiments, j["experiment"])
        sample = one(c, s.cases, j["sample"])
        refresh(c, exp["id"])
    owned = and_(s.jobs.c.id == j["id"], s.jobs.c.owner == token)
    failure = ""
    try:
        execution = j["execution"]
        if execution:
            with engine.connect() as c:
                if one(c, s.executions, execution)["status"] == "ERROR":
                    execution = None
        if not execution:
            start = time.monotonic()
            try:
                new = HTTPAgent().run(
                    sample["data"], exp["environment"], exp["agent"], j["id"]
                )
            except Exception as exc:
                with engine.begin() as c:
                    failed = add(
                        c,
                        s.executions,
                        case_id=sample["case_id"],
                        environment=exp["environment"],
                        record={
                            "error": type(exc).__name__,
                            "latency_ms": round((time.monotonic() - start) * 1000),
                        },
                        status="ERROR",
                        created=now(),
                    )
                    if c.execute(
                        s.jobs.update().where(owned).values(execution=failed)
                    ).rowcount:
                        add(c, attempts, job=j["id"], execution=failed, created=now())
                raise
            new["latency_ms"] = round((time.monotonic() - start) * 1000)
            with engine.begin() as c:
                execution = add(
                    c,
                    s.executions,
                    case_id=sample["case_id"],
                    environment=exp["environment"],
                    record=new,
                    status="DONE",
                    created=now(),
                )
                if not c.execute(
                    s.jobs.update().where(owned).values(execution=execution)
                ).rowcount:
                    raise RuntimeError("lease expired")
                add(c, attempts, job=j["id"], execution=execution, created=now())
        for mid in exp["selection"]:
            with engine.begin() as c:
                if not c.execute(
                    s.jobs.update().where(owned).values(lease=lease())
                ).rowcount:
                    return True
                previous = rows(
                    c, s.results, s.results.c.job == j["id"], s.results.c.mapping == mid
                )
                if previous and previous[0]["data"]["status"] not in (
                    "ERROR",
                    "NOT_RUN",
                ):
                    continue
                mapping = one(c, s.mappings, mid)
                ev = one(c, s.evaluators, mapping["evaluator"])
                rec = record(c, sample, execution)
            result = evaluate(rec, ev["spec"], mapping["rules"])
            if result["status"] in ("ERROR", "NOT_RUN"):
                failure = result["error_code"]
            with engine.begin() as c:
                if not c.execute(
                    s.jobs.update().where(owned).values(lease=lease())
                ).rowcount:
                    return True
                if previous:
                    c.execute(
                        s.results.update()
                        .where(s.results.c.id == previous[0]["id"])
                        .values(data=result)
                    )
                else:
                    add(c, s.results, job=j["id"], mapping=mid, data=result)
    except Exception as exc:
        failure = type(exc).__name__
    with engine.begin() as c:
        c.execute(
            s.jobs.update()
            .where(owned)
            .values(
                status="ERROR" if failure else "DONE", error=failure, owner="", lease=""
            )
        )
        refresh(c, exp["id"])
    return True
