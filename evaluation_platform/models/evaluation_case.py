from typing import Any, Literal
from uuid import uuid4
from pydantic import BaseModel, Field, model_validator


class ExpectedContract(BaseModel):
    reference_output: str | None = None
    reference_context: list[str] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    forbidden_tools: list[str] = Field(default_factory=list)
    required_nodes: list[str] = Field(default_factory=list)
    valid_paths: list[list[str]] = Field(default_factory=list)
    forbidden_nodes: list[str] = Field(default_factory=list)
    document_ids: list[str] = Field(default_factory=list)
    recall_k: int = Field(default=5, ge=1)
    expected_status: str = "ok"
    max_latency_ms: float = Field(default=5000, gt=0)
    required_output: list[str] = Field(default_factory=list)
    forbidden_output: list[str] = Field(default_factory=list)
    runtime_reference: str | None = None
    output_schema: dict[str, Any] | None = None
    permission_denied: bool | None = None

    def substantive(self) -> bool:
        return any((self.reference_output is not None, self.tool_calls, self.forbidden_tools,
                    self.required_nodes, self.valid_paths, self.document_ids, self.required_output,
                    self.forbidden_output, self.runtime_reference, self.output_schema,
                    self.permission_denied is not None, self.expected_status != "ok"))


class EvaluationBinding(BaseModel):
    evaluator_id: str
    role: Literal["gate", "quality"] = "quality"
    scope: Literal["dataset", "case", "type", "capability"] = "case"
    target: str | None = None

    def applies(self, case) -> bool:
        return self.scope == "dataset" or (self.scope == "case" and self.target in (None, case.id)) or \
            (self.scope == "type" and self.target in case.evaluation_areas) or \
            (self.scope == "capability" and self.target == case.capability)


class EvaluationCase(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    scenario_id: str = ""
    input: str = Field(min_length=1)
    input_variations: list[str] = Field(default_factory=list)
    expected: ExpectedContract = Field(default_factory=ExpectedContract)
    source: Literal["workflow", "rag", "production_trace", "phoenix_failure_candidate", "owner_manual"]
    sources: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1, ge=0, le=1)
    candidate_reason: str = ""
    capability: str = ""
    evaluation_areas: list[str] = Field(default_factory=list)
    targets: dict[str, list[str]] = Field(default_factory=dict)
    trace_id: str | None = None
    span_id: str | None = None
    failure_type: str | None = None
    original_input: str | None = None
    original_output: str | None = None
    error: str | None = None
    latency_ms: float | None = None
    bindings: list[EvaluationBinding] = Field(default_factory=list)
    review_status: Literal["pending", "approved", "excluded"] = "pending"


class JudgeDefinition(BaseModel):
    id: str = Field(default_factory=lambda: "owner_" + uuid4().hex[:12])
    name: str = Field(min_length=1)
    description: str = ""
    criteria: str = Field(min_length=3, max_length=4000)
    score_min: float = 0
    score_max: float = 1
    pass_threshold: float = 0.8
    scope: Literal["dataset", "case", "type", "capability"] = "case"
    target: str | None = None
    active: bool = True
    version: int = 1

    @model_validator(mode="after")
    def validate_scale(self):
        if self.score_max <= self.score_min or not self.score_min <= self.pass_threshold <= self.score_max:
            raise ValueError("threshold must be within a non-empty score scale")
        return self
