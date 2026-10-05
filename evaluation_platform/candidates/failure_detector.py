from evaluation_platform.models import AgentResult


def detect(result: AgentResult, high_latency_ms=5000, span_status=None):
    """Only observed conditions; an unobserved interruption/retry is never inferred."""
    reasons = []
    if result.status == "timeout":
        reasons.append(("timeout", "실행 상태에 시간 초과가 명시되어 있습니다."))
    if result.error or result.status in ("error", "failed", "exception") or span_status == "ERROR":
        reasons.append(("execution_error", f"관찰된 실행 상태 / 오류: {result.status}; {result.error or span_status}"))
    if any(t.get("status") == "error" for t in result.tool_calls):
        reasons.append(("tool_failure", "Tool 호출 결과에 오류가 명시되어 있습니다."))
    if result.retrieval_attempted and not result.documents:
        reasons.append(("empty_retrieval", "RAG 검색을 수행했지만 반환된 문서가 없습니다."))
    if not result.output.strip():
        reasons.append(("empty_response", "관찰된 최종 응답이 비어 있습니다."))
    if result.latency_ms > high_latency_ms:
        reasons.append(("high_latency", f"응답 시간 {result.latency_ms:.1f}ms가 기준 {high_latency_ms}ms를 초과했습니다."))
    if result.interrupted:
        reasons.append(("workflow_interrupted", "Runtime에 Workflow 중단이 명시되어 있습니다."))
    if result.retries >= 3:
        reasons.append(("repeated_retry", f"관찰된 재시도 횟수: {result.retries}"))
    return reasons
