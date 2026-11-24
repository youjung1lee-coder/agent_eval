from collections import Counter
from uuid import uuid5, NAMESPACE_URL
from fastapi import HTTPException
from . import schema_v1 as s
from .db import add, rows, one, now
from .trace import normalize
from .adapters import clean, phoenix, setting


def convert(dataset, item):
    x = clean(item)
    m = x.get("metadata") or {}
    trace = {
        "trace_id": m.get("trace_id"),
        "span_id": m.get("span_id"),
        "spans": x.get("spans", []),
    }
    parsed = normalize(trace["spans"])
    trace["root_span_id"] = parsed["root_span_id"]
    warnings = [] if trace["spans"] else ["원본 Trace 미연결 · 항목 스냅샷만 수집"]
    if m.get("session_id") or m.get("time_dependent"):
        warnings.append("세션 또는 시점에 의존하는 케이스")
    data = {
        "input": x["input"],
        "expected_output": m.get("expected_output"),
        "expected_tools": m.get("expected_tools"),
        "expected_behavior": m.get("expected_behavior"),
        "warnings": warnings,
        "source": {
            "dataset_id": dataset,
            "dataset_item_id": x["id"],
            "trace_id": trace["trace_id"],
            "span_id": trace["span_id"],
            "collected_at": now(),
        },
    }
    record = {
        "actual_output": x.get("output")
        if parsed["output"] is None
        else {"text": parsed["output"]}
        if isinstance(parsed["output"], str)
        else parsed["output"],
        "trace": trace,
        "metadata": m,
        "original_item": x,
        "retrieval_context": m.get("retrieval_context", parsed["documents"]),
        "tools_called": m.get("tools_called", parsed["tools"]),
    }
    return data, record


def import_dataset(c, dataset, version, agent):
    client = phoenix()
    source = setting("PHOENIX_MODE", "fixture") + ":" + dataset
    existing = rows(c, s.datasets, s.datasets.c.source == source)
    if existing:
        ds = existing[0]["id"]
        previous = rows(
            c,
            s.versions,
            s.versions.c.dataset == ds,
            s.versions.c.source_version == version,
        )
        if previous:
            return {"version": previous[0]["id"], "duplicate": True}
    info = next((d for d in client.list() if d["id"] == dataset), None)
    if not info:
        raise ValueError("Dataset 없음")
    items = client.load(dataset, version)
    ds = (
        existing[0]["id"]
        if existing
        else add(
            c, s.datasets, source=source, name=info["name"], agent=agent, created=now()
        )
    )
    v = add(
        c,
        s.versions,
        dataset=ds,
        number=len(rows(c, s.versions, s.versions.c.dataset == ds)) + 1,
        source_version=version,
        created=now(),
    )
    seen = set()
    traces = Counter((x.get("metadata") or {}).get("trace_id") for x in items)
    for x in items:
        case_id = str(uuid5(NAMESPACE_URL, source + "/" + str(x["id"])))
        if case_id in seen:
            continue
        seen.add(case_id)
        data, record = convert(dataset, x)
        tid = data["source"]["trace_id"]
        if tid and traces[tid] > 1:
            data["warnings"].append("여러 케이스가 같은 Trace를 참조")
        execution = add(
            c,
            s.executions,
            case_id=case_id,
            environment="Phoenix",
            record=record,
            status="DONE",
            created=now(),
        )
        add(c, s.cases, version=v, case_id=case_id, execution=execution, data=data)
    return {"version": v, "imported": len(seen), "skipped": len(items) - len(seen)}


def edit(c, version, case_id, change):
    v = one(c, s.versions, version)
    all_versions = rows(c, s.versions, s.versions.c.dataset == v["dataset"])
    if v["number"] != max(x["number"] for x in all_versions):
        raise HTTPException(409, "최신 버전에서 편집하세요")
    samples = rows(c, s.cases, s.cases.c.version == version)
    if not any(x["case_id"] == case_id for x in samples):
        raise HTTPException(404, "케이스 없음")
    new = add(
        c,
        s.versions,
        dataset=v["dataset"],
        number=v["number"] + 1,
        created=now(),
        source_version=v["source_version"],
    )
    for x in samples:
        data = {**x["data"], **clean(change)} if x["case_id"] == case_id else x["data"]
        add(
            c,
            s.cases,
            version=new,
            case_id=x["case_id"],
            execution=x["execution"],
            data=data,
        )
    return {"version": new}


def record(c, sample, execution=None):
    e = one(c, s.executions, execution or sample["execution"])
    meta = e["record"].get("metadata") or {}
    versions = {
        k: meta.get(k, "unknown")
        for k in (
            "agent_version",
            "model_version",
            "workflow_version",
            "knowledge_version",
        )
    }
    return {
        **e["record"],
        "versions": versions,
        **sample["data"],
        "case_id": sample["case_id"],
        "execution_id": e["id"],
    }
