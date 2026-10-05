from evaluation_platform.models import AgentResult


def detect(result: AgentResult, high_latency_ms=5000, span_status=None):
    """Only observed conditions; an unobserved interruption/retry is never inferred."""
    reasons = []
    if result.status == "timeout":
        reasons.append(("timeout", "execution status explicitly reports timeout"))
    if result.error or result.status in ("error", "failed", "exception") or span_status == "ERROR":
        reasons.append(("execution_error", f"observed status/error: {result.status}; {result.error or span_status}"))
    if any(t.get("status") == "error" for t in result.tool_calls):
        reasons.append(("tool_failure", "tool call result explicitly reports error"))
    if result.retrieval_attempted and not result.documents:
        reasons.append(("empty_retrieval", "retrieval attempted, returned zero documents"))
    if not result.output.strip():
        reasons.append(("empty_response", "observed final response is empty"))
    if result.latency_ms > high_latency_ms:
        reasons.append(("high_latency", f"observed {result.latency_ms:.1f} ms exceeds {high_latency_ms} ms"))
    if result.interrupted:
        reasons.append(("workflow_interrupted", "runtime explicitly reports interrupted workflow"))
    if result.retries >= 3:
        reasons.append(("repeated_retry", f"observed retry count={result.retries}"))
    return reasons
