from datetime import datetime, timezone
from uuid import uuid4
from contextlib import nullcontext
from importlib.metadata import version, PackageNotFoundError
from evaluation_platform.models import EvaluationCase, EvaluationBinding, EvaluatorResult


def run_evaluation(golden, execute, registry, spec, kind="regression", dependency_ids=None, trace=None):
    cases = [EvaluationCase.model_validate(c) for c in golden["cases"]]
    if dependency_ids:
        subset = [c for c in cases if set(dependency_ids) & set(sum(c.targets.values(), []))]
        # Unknown impact falls back to the whole golden, never silently zero cases.
        if subset:
            cases = subset
    rows = []
    run_id = uuid4().hex
    for case in cases:
        actual = execute(case.input, run_id)
        bindings = case.bindings + [EvaluationBinding.model_validate(b) for b in golden.get("bindings", [])]
        evaluated = []
        seen = set()
        for binding in bindings:
            if not binding.applies(case) or (binding.evaluator_id, binding.role) in seen:
                continue
            seen.add((binding.evaluator_id, binding.role))
            try:
                tracing = trace.span("evaluator." + binding.evaluator_id, "CHAIN", {"gaia.case_id": case.id}) if trace else nullcontext()
                with tracing as span:
                    result = registry.resolve(binding.evaluator_id).evaluate(case, actual)
                    if span:
                        span.set_attribute("output.value", result.model_dump_json())
            except Exception as exc:
                result = EvaluatorResult(evaluator_id=binding.evaluator_id, score=0, passed=False,
                                         reason=f"Evaluator execution failed: {exc}", error=str(exc))
            evaluated.append({**result.model_dump(), "role": binding.role})
        if not evaluated:
            evaluated.append({"evaluator_id": "missing_binding", "score": 0, "passed": False,
                              "reason": "No evaluator applies", "role": "gate", "error": "unconfigured"})
        gate_failed = any(e["role"] == "gate" and not e["passed"] for e in evaluated)
        rows.append({"case": case.model_dump(), "actual": actual.model_dump(), "evaluators": evaluated,
                     "gate_passed": not gate_failed, "passed": all(e["passed"] for e in evaluated)})
    quality = [e["score"] for row in rows for e in row["evaluators"] if e["role"] == "quality"]
    overall = sum(quality) / len(quality) if quality else None
    gate_failed = any(not row["gate_passed"] for row in rows)
    evaluator_error = any(e.get("error") for row in rows for e in row["evaluators"])
    passed = bool(rows) and not gate_failed and not evaluator_error and all(row["passed"] for row in rows)
    runtime_versions = {}
    for package in ("pydantic", "langgraph", "lfx", "llama-cpp-python", "arize-phoenix-client", "opentelemetry-sdk"):
        try:
            runtime_versions[package] = version(package)
        except PackageNotFoundError:
            runtime_versions[package] = "not installed"
    return {"id": run_id, "agent_id": spec.agent_id, "agent_version": spec.version, "agent_fingerprint": spec.fingerprint(),
            "dataset_id": golden["id"], "dataset_version": golden["version"], "kind": kind,
            "created_at": datetime.now(timezone.utc).isoformat(), "overall_score": overall,
            "gate_passed": not gate_failed, "passed": passed,
            "decision": "PASS" if passed else "HOLD", "cases": rows,
            "failure_count": sum(not row["passed"] for row in rows),
            "evaluator_versions": registry.catalog(), "evaluator_definitions": golden.get("evaluators", []),
            "runtime_versions": runtime_versions,
            "dependency_filter": dependency_ids or [], "agent_snapshot": spec.model_dump()}
