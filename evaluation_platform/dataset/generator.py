import hashlib
from evaluation_platform.models import EvaluationCase, ExpectedContract, EvaluationBinding, AgentResult
from evaluation_platform.candidates.failure_detector import detect


def scenario(question):
    return hashlib.sha256(" ".join(question.casefold().split()).encode()).hexdigest()[:16]


def recommend(contract):
    ids = [("error_detection", "gate"), ("latency", "quality")]
    if contract.reference_output is not None:
        ids.append(("exact", "quality"))
    if contract.tool_calls or contract.forbidden_tools:
        ids.append(("tool_call", "gate"))
    if contract.required_nodes or contract.valid_paths or contract.forbidden_nodes:
        ids.append(("workflow_path", "gate"))
    if contract.document_ids:
        ids.append(("rag_retrieval", "quality"))
    if contract.reference_context:
        ids.append(("faithfulness", "quality"))
    if contract.required_output or contract.forbidden_output:
        ids.append(("behavior", "gate"))
    if contract.permission_denied is not None:
        ids.append(("permission", "gate"))
    if contract.output_schema:
        ids.append(("output_schema", "gate"))
    if contract.runtime_reference:
        ids.append(("runtime_reference", "quality"))
    return [EvaluationBinding(evaluator_id=i, role=role) for i, role in ids]


def generate(spec, production):
    cases = []
    for probe in spec.probes:
        cases.append(EvaluationCase(id="definition_" + probe.id, scenario_id=scenario(probe.input),
            input=probe.input, expected=probe.expected, source="workflow", evidence=[probe.evidence],
            confidence=probe.confidence, capability=probe.capability, evaluation_areas=[probe.capability],
            targets=probe.targets, bindings=recommend(probe.expected),
            candidate_reason="Owner-supplied integration probe mapped to discovered definition; not inferred business truth"))
    for doc in spec.knowledge_sources:
        if not doc.question or doc.reference_answer is None:
            continue
        expected = ExpectedContract(reference_output=doc.reference_answer, reference_context=[doc.content], document_ids=[doc.id])
        cases.append(EvaluationCase(id="knowledge_" + doc.id, scenario_id=scenario(doc.question),
            input=doc.question, expected=expected, source="rag", evidence=[f"knowledge unit {doc.id} from {doc.source}"],
            capability="rag", evaluation_areas=["rag"], targets={"rag": [doc.id]}, bindings=recommend(expected)))
    for trace in production:
        result = AgentResult.model_validate(trace["result"])
        sid = scenario(trace["input"])
        lineage = dict(trace_id=result.trace_id, span_id=result.span_id, original_input=trace["input"],
                       original_output=result.output, error=result.error, latency_ms=result.latency_ms)
        observed = {"production": [sid], "workflow": result.workflow_path, "branch": result.branches,
                    "tool": [t["name"] for t in result.tool_calls], "rag": [d["id"] for d in result.documents]}
        cases.append(EvaluationCase(id="trace_" + str(result.span_id), scenario_id=sid, input=trace["input"],
            source="production_trace", confidence=0.3, evidence=[trace["evidence"]], targets=observed,
            candidate_reason="Observed production input. Owner must supply expected contract; output is NOT ground truth", **lineage))
        for kind, reason in detect(result, span_status=trace.get("status_code")):
            cases.append(EvaluationCase(id="failure_" + str(result.span_id) + "_" + kind, scenario_id=sid,
                input=trace["input"], source="phoenix_failure_candidate", failure_type=kind, confidence=0.3,
                evidence=[trace["evidence"]], candidate_reason=reason, capability="failure", evaluation_areas=["failure"],
                targets={**observed, "failure": [kind]}, **lineage))
    for case in cases:
        case.sources = [case.source]
        case.input_variations = [case.input]
    return cases
