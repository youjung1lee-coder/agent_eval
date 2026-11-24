"""Isolated HTTP fixture agent. No tools or side effects."""

import json
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

policies = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures/policies.json").read_text()
)
app = FastAPI()


class Request(BaseModel):
    input: dict
    environment: str
    session_id: str
    agent_id: str


@app.get("/health")
def health():
    return {"mode": "mock"}


@app.post("/run")
def run(req: Request):
    query = req.input.get("text", "")
    index = next((i for i, p in enumerate(policies) if p["topic"] in query), None)
    if index is None:
        raise HTTPException(422, "지원하지 않는 합성 질문")
    p = policies[index]
    miss = index % (7 if req.environment == "STG" else 11) == 1
    return {
        "actual_output": {
            "text": "관련 안내를 찾지 못했습니다." if miss else p["answer"]
        },
        "retrieval_context": [] if miss else [p["answer"]],
        "tools_called": [{"name": "policy_search", "arguments": {"topic": p["topic"]}}],
        "trace": {
            "trace_id": req.session_id,
            "spans": [
                {"id": "root", "parent_id": None, "kind": "CHAIN", "output": p["topic"]}
            ],
        },
        "metadata": {
            "agent_version": "mock-1",
            "model_version": "fixture",
            "workflow_version": "1",
            "knowledge_version": "manual-1",
        },
    }
