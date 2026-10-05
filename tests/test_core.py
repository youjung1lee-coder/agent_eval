import pytest
from pydantic import ValidationError
from evaluation_platform.models import AgentResult, EvaluationCase, ExpectedContract, JudgeDefinition, EvaluationBinding
from evaluation_platform.candidates.failure_detector import detect
from evaluation_platform.dataset.generator import generate
from evaluation_platform.coverage import coverage
from evaluation_platform.evaluators.registry import platform_registry, EvaluatorRegistry
from evaluation_platform.evaluators.base import FunctionEvaluator
from evaluation_platform.runner.runner import run_evaluation


@pytest.mark.parametrize("result,kind", [
    (AgentResult(status="timeout"), "timeout"),
    (AgentResult(error="exception"), "execution_error"),
    (AgentResult(output="ok", tool_calls=[{"name": "x", "status": "error"}]), "tool_failure"),
    (AgentResult(output="ok", retrieval_attempted=True), "empty_retrieval"),
    (AgentResult(output=""), "empty_response"),
    (AgentResult(output="ok", latency_ms=6001), "high_latency"),
    (AgentResult(output="ok", interrupted=True), "workflow_interrupted"),
    (AgentResult(output="ok", retries=4), "repeated_retry"),
])
def test_observed_failures(result, kind):
    assert kind in {k for k, _ in detect(result)}


def test_detector_does_not_invent_missing_retrieval_or_interruption():
    assert detect(AgentResult(output="a normal answer")) == []


def test_trace_response_is_never_ground_truth(platform):
    spec, _ = platform.agent("hr-langgraph")
    result = AgentResult(output="wrong sensitive response", status="error", error="boom", trace_id="abc", span_id="def")
    cases = generate(spec, [{"input": "query", "result": result.model_dump(), "evidence": "observed"}])
    traces = [c for c in cases if c.trace_id]
    assert traces and all(c.expected.reference_output is None and c.review_status == "pending" for c in traces)
    assert all(c.original_output == result.output and c.span_id == "def" for c in traces)


def test_unknown_coverage_is_not_fabricated(platform):
    spec, _ = platform.agent("hr-langgraph")
    spec.metadata["failure_types"] = []
    rows = {r["dimension"]: r for r in coverage(spec, [], [])}
    assert rows["failure"]["total"] is None and rows["failure"]["percent"] is None
    assert rows["production"]["unknown"]
    assert rows["branch"]["covered"] == 0 and rows["branch"]["total"] == 3


def test_exclusion_does_not_shrink_observed_failure_denominator(platform):
    spec,_=platform.agent("hr-langgraph")
    observed=EvaluationCase(input="q",source="phoenix_failure_candidate",failure_type="repeated_retry",review_status="excluded")
    rows={r["dimension"]:r for r in coverage(spec,[],[],[observed])}
    assert rows["failure"]["total"]==4
    assert "repeated_retry" in rows["failure"]["missing"]


def test_gate_overrides_quality(platform):
    spec, _ = platform.agent("hr-langgraph")
    registry = EvaluatorRegistry()
    registry.register(FunctionEvaluator("permission", lambda e,r:(0, "forbidden access", {})))
    registry.register(FunctionEvaluator("quality", lambda e,r:(1, "perfect answer", {})))
    case = EvaluationCase(input="question", source="owner_manual", bindings=[
        EvaluationBinding(evaluator_id="permission", role="gate"), EvaluationBinding(evaluator_id="quality")])
    golden = {"id": "g", "version": 1, "cases": [case.model_dump()]}
    run = run_evaluation(golden, lambda q,r:AgentResult(output="great"), registry, spec)
    assert run["overall_score"] == 1 and run["decision"] == "HOLD" and not run["gate_passed"]


def test_evaluator_exception_cannot_pass(platform):
    spec, _ = platform.agent("hr-langgraph")
    registry = EvaluatorRegistry()
    registry.register(FunctionEvaluator("crash", lambda e,r: (_ for _ in ()).throw(ValueError("plugin failed"))))
    case = EvaluationCase(input="question", source="owner_manual", bindings=[EvaluationBinding(evaluator_id="crash")])
    run = run_evaluation({"id":"g","version":1,"cases":[case.model_dump()]}, lambda q,r:AgentResult(output="ok"), registry, spec)
    assert run["decision"] == "HOLD" and run["cases"][0]["evaluators"][0]["error"]


def test_tool_arguments_and_order_are_gates(platform):
    reg = platform.registry()
    case = EvaluationCase(input="q", source="owner_manual", expected=ExpectedContract(tool_calls=[{"name":"a","args":{"x":1}}, {"name":"b"}]))
    actual = AgentResult(tool_calls=[{"name":"b"}, {"name":"a","args":{"x":1}}])
    assert not reg.resolve("tool_call").evaluate(case, actual).passed
    actual.tool_calls = [{"name":"a","args":{"x":2}}, {"name":"b"}]
    assert not reg.resolve("tool_call").evaluate(case, actual).passed


def test_ordered_paths_and_forbidden_nodes(platform):
    case = EvaluationCase(input="q",source="owner_manual",expected=ExpectedContract(valid_paths=[["a","b"]],forbidden_nodes=["secret"]))
    assert not platform.registry().resolve("workflow_path").evaluate(case, AgentResult(workflow_path=["b","a"])).passed


def test_rag_recall_k_has_known_reference(platform):
    case = EvaluationCase(input="q",source="rag",expected=ExpectedContract(document_ids=["a","b"],recall_k=1))
    result = platform.registry().resolve("rag_retrieval").evaluate(case,AgentResult(documents=[{"id":"a"},{"id":"b"}]))
    assert result.score == .5 and not result.passed


def test_permission_and_schema(platform):
    case = EvaluationCase(input="q",source="owner_manual",expected=ExpectedContract(permission_denied=True,forbidden_tools=["private"]))
    assert not platform.registry().resolve("permission").evaluate(case,AgentResult(permission_denied=True,tool_calls=[{"name":"private"}])).passed
    case.expected.output_schema = {"type":"object","required":["amount"],"properties":{"amount":{"type":"number"}}}
    assert not platform.registry().resolve("output_schema").evaluate(case,AgentResult(output='{"amount":"wrong"}')).passed


def test_judge_scale_validation():
    with pytest.raises(ValidationError):
        JudgeDefinition(name="bad",criteria="test",score_min=5,score_max=1)


def test_bindings_support_dataset_case_type_capability():
    c=EvaluationCase(id="tc",input="q",source="owner_manual",capability="rag",evaluation_areas=["knowledge"])
    assert all(EvaluationBinding(evaluator_id="e",scope=s,target=t).applies(c) for s,t in
               [("dataset",None),("case","tc"),("type","knowledge"),("capability","rag")])
    assert not EvaluationBinding(evaluator_id="e",scope="case",target="other").applies(c)
