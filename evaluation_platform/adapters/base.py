import hashlib
import importlib.util
import json
from abc import ABC, abstractmethod
from pathlib import Path
from evaluation_platform.models import AgentSpec, AgentResult


def read_manifest(path):
    return json.loads((Path(path).resolve() / "eval_agent.json").read_text(encoding="utf-8"))


class BaseAdapter(ABC):
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.manifest = read_manifest(path)

    def source_digest(self):
        digest = hashlib.sha256()
        for file in sorted(self.path.rglob("*")):
            if file.is_file() and file.suffix in (".py", ".json", ".md") and "__pycache__" not in file.parts:
                digest.update(str(file.relative_to(self.path)).encode())
                digest.update(file.read_bytes())
        return digest.hexdigest()

    def build_spec(self, nodes, edges, branches):
        m = self.manifest
        return AgentSpec(agent_id=m["agent_id"], version=m["version"], framework=m["framework"],
            entry_point=m["entry_point"], nodes=nodes, branches=branches,
            workflows=[{"id": m.get("workflow_id", "main"), "edges": edges}], tools=m.get("tools", []),
            rag_sources=m.get("rag_sources", []), knowledge_sources=m.get("knowledge", []),
            capabilities=m.get("capabilities", []), probes=m.get("probes", []),
            metadata={"adapter_contract": "eval_agent.json-v1 (PoC, NOT actual GAIA)",
                      "source_digest": self.source_digest(), "edge_cases": m.get("edge_cases", []),
                      "failure_types": m.get("failure_types", [])})

    def trusted_module(self):
        filename, _ = self.manifest["entry_point"].split(":", 1)
        file = (self.path / filename).resolve()
        if not file.is_relative_to(self.path):
            raise ValueError("entry point escapes agent repository")
        spec = importlib.util.spec_from_file_location("agent_" + self.source_digest()[:12], file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    @abstractmethod
    def analyze(self) -> AgentSpec: ...

    @abstractmethod
    def execute(self, question: str, context) -> AgentResult: ...
