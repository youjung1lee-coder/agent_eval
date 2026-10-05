from contextvars import ContextVar
from typing import Protocol

active_context = ContextVar("gaia_runtime_context")


class KnowledgeConnector(Protocol):
    def search(self, query: str, k: int = 5) -> list[dict]: ...


class ToolConnector(Protocol):
    def call(self, name: str, args: dict) -> dict: ...


class MockKnowledge:
    def __init__(self, units):
        self.units = units

    def search(self, query, k=5):
        tokens = set(query.casefold().split())
        scored = [(len(tokens & set((d.content + " " + (d.question or "")).casefold().split())), d) for d in self.units]
        return [{"id": d.id, "content": d.content} for score, d in sorted(scored, key=lambda x: x[0], reverse=True)[:k] if score > 0]


class MockTools:
    def __init__(self, definitions):
        self.definitions = {d["name"]: d for d in definitions}

    def call(self, name, args):
        import jsonschema
        definition = self.definitions[name]
        jsonschema.validate(args, definition.get("input_schema", {}))
        if args.get("simulate_error"):
            raise RuntimeError("simulated downstream tool error")
        return definition.get("mock_result", {})


class RuntimeContext:
    def __init__(self, spec, trace, tools=None, knowledge=None):
        self.trace = trace
        self.tools = tools or MockTools(spec.tools)
        self.knowledge = knowledge or MockKnowledge(spec.knowledge_sources)

    def tool(self, name, args):
        with self.trace.span(name, "TOOL", {"tool.name": name, "input.value": __import__("json").dumps(args)}) as span:
            result = self.tools.call(name, args)
            span.set_attribute("output.value", __import__("json").dumps(result))
            return result

    def retrieve(self, query):
        with self.trace.span("retrieval", "RETRIEVER", {"input.value": query}) as span:
            docs = self.knowledge.search(query)
            span.set_attribute("gaia.retrieval_count", len(docs))
            for i, d in enumerate(docs):
                span.set_attribute(f"retrieval.documents.{i}.document.id", d["id"])
                span.set_attribute(f"retrieval.documents.{i}.document.content", d["content"])
            return docs
