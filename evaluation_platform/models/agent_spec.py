import hashlib
import json
from typing import Any, Literal
from pydantic import BaseModel, Field
from .evaluation_case import ExpectedContract


class KnowledgeUnit(BaseModel):
    id: str
    content: str
    question: str | None = None
    reference_answer: str | None = None
    source: str = "mock_document"


class Probe(BaseModel):
    id: str
    input: str
    capability: str
    expected: ExpectedContract
    targets: dict[str, list[str]] = Field(default_factory=dict)
    evidence: str
    confidence: float = Field(default=1, ge=0, le=1)


class AgentSpec(BaseModel):
    schema_version: str = "1.0"
    agent_id: str
    version: str
    framework: Literal["langgraph", "langflow"]
    entry_point: str
    workflows: list[dict[str, Any]]
    nodes: list[str]
    branches: list[str]
    tools: list[dict[str, Any]] = Field(default_factory=list)
    rag_sources: list[str] = Field(default_factory=list)
    knowledge_sources: list[KnowledgeUnit] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    probes: list[Probe] = Field(default_factory=list)
    phoenix_config: dict[str, str] = Field(default_factory=lambda: {"production": "prd", "evaluation": "evaluate"})
    metadata: dict[str, Any] = Field(default_factory=dict)

    def fingerprint(self) -> str:
        return hashlib.sha256(json.dumps(self.model_dump(), sort_keys=True).encode()).hexdigest()
