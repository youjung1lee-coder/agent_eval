from typing import Any
from pydantic import BaseModel, Field


class AgentResult(BaseModel):
    output: str = ""
    status: str = "ok"
    error: str | None = None
    latency_ms: float = 0
    workflow_path: list[str] = Field(default_factory=list)
    branches: list[str] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    documents: list[dict[str, Any]] = Field(default_factory=list)
    retrieval_attempted: bool = False
    retries: int = 0
    interrupted: bool = False
    permission_denied: bool = False
    trace_id: str | None = None
    span_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvaluatorResult(BaseModel):
    evaluator_id: str
    score: float = Field(ge=0, le=1)
    passed: bool
    reason: str
    details: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
