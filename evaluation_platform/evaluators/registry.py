import json
from .base import FunctionEvaluator
from .llm_judge import JudgeBackend
from .custom_llm import CustomLLMEvaluator
from evaluation_platform.models import JudgeDefinition


class EvaluatorRegistry:
    def __init__(self):
        self.evaluators = {}

    def register(self, evaluator):
        if evaluator.id in self.evaluators:
            raise ValueError(f"duplicate evaluator {evaluator.id}")
        self.evaluators[evaluator.id] = evaluator

    def resolve(self, evaluator_id):
        if evaluator_id not in self.evaluators:
            raise ValueError(f"unknown evaluator {evaluator_id}")
        return self.evaluators[evaluator_id]

    def catalog(self):
        return [{"id": e.id, "version": e.version, "kind": "custom_llm" if getattr(e, "owner_custom", False) else "platform"}
                for e in self.evaluators.values()]


def verdict(ok, reason, details=None):
    return float(ok), reason, details or {}


def tool_match(e, r):
    actual = r.tool_calls
    expected = e.tool_calls
    names = [t["name"] for t in actual]
    ok = not any(n in names for n in e.forbidden_tools)
    if expected:
        ok = ok and len(actual) == len(expected) and all(
            a["name"] == x["name"] and all(a.get("args", {}).get(k) == v for k, v in x.get("args", {}).items())
            for a, x in zip(actual, expected))
    return verdict(ok, "Tool names, arguments, order and forbidden calls compared", {"expected": expected, "actual": actual})


def path_match(e, r):
    ok = set(e.required_nodes) <= set(r.workflow_path) and not set(e.forbidden_nodes) & set(r.workflow_path)
    if e.valid_paths:
        ok = ok and r.workflow_path in e.valid_paths
    return verdict(ok, "Required/forbidden nodes and ordered valid paths compared", {"actual_path": r.workflow_path})


def rag_recall(e, r):
    if not e.document_ids:
        raise ValueError("RAG retrieval requires reference document IDs")
    retrieved = {d["id"] for d in r.documents[:e.recall_k]}
    score = len(set(e.document_ids) & retrieved) / len(set(e.document_ids))
    return score, f"Reference document Recall@{e.recall_k}={score:.3f}", {"reference": e.document_ids, "retrieved": sorted(retrieved)}


def schema_match(e, r):
    import jsonschema
    if not e.output_schema:
        raise ValueError("Output schema contract missing")
    try:
        jsonschema.validate(json.loads(r.output), e.output_schema)
        return verdict(True, "Output satisfies JSON Schema")
    except (ValueError, jsonschema.ValidationError) as exc:
        return verdict(False, str(exc))


def runtime_match(e, r):
    if not e.runtime_reference:
        raise ValueError("runtime_reference missing")
    # Portable contract: tool_output.<tool_name>.<field> (not agent-specific).
    prefix, name, field = e.runtime_reference.split(".", 2)
    if prefix != "tool_output":
        raise ValueError("unsupported runtime reference namespace")
    for call in r.tool_calls:
        if call["name"] == name:
            value = call.get("result", {})
            for part in field.split("."):
                value = value[part]
            return verdict(str(value) in r.output, f"Runtime reference {e.runtime_reference} = {value}")
    return verdict(False, "Runtime reference tool not called")


def platform_registry(definitions=(), backend=None):
    registry = EvaluatorRegistry()
    backend = backend or JudgeBackend()
    fns = {
        "exact": lambda e, r: verdict(e.reference_output is not None and e.reference_output.strip() == r.output.strip(), "Exact trimmed string comparison"),
        "tool_call": tool_match,
        "workflow_path": path_match,
        "rag_retrieval": rag_recall,
        "latency": lambda e, r: verdict(r.latency_ms <= e.max_latency_ms, f"{r.latency_ms:.1f}ms / budget {e.max_latency_ms}ms"),
        "error_detection": lambda e, r: verdict(r.status == e.expected_status, f"Expected status {e.expected_status}; actual {r.status}; error {r.error}"),
        "behavior": lambda e, r: verdict(all(x.casefold() in r.output.casefold() for x in e.required_output) and not any(x.casefold() in r.output.casefold() for x in e.forbidden_output), "Required and forbidden output checked"),
        "permission": lambda e, r: verdict(r.permission_denied == e.permission_denied and not any(t["name"] in e.forbidden_tools for t in r.tool_calls), "Observed permission decision and forbidden tools compared"),
        "output_schema": schema_match,
        "runtime_reference": runtime_match,
    }
    for key, fn in fns.items():
        registry.register(FunctionEvaluator(key, fn))
    # Judge evaluators use the same plugin interface; no runner branching.
    rubrics = {
        "llm_judge": "The answer correctly completes the requested task and matches the expected contract.",
        "semantic_similarity": "The answer has the same meaning as the reference output. This is an auxiliary semantic judge, not standalone correctness.",
        "faithfulness": "Every factual claim in the answer is supported by the reference context."
    }
    for key, criteria in rubrics.items():
        registry.register(CustomLLMEvaluator(JudgeDefinition(id=key, name=key, criteria=criteria, pass_threshold=0.5), backend))
    for definition in definitions:
        d = JudgeDefinition.model_validate(definition)
        if d.active:
            evaluator = CustomLLMEvaluator(d, backend)
            evaluator.owner_custom = True
            registry.register(evaluator)
    return registry
