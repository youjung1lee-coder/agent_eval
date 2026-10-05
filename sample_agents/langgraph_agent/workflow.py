import time
from typing import TypedDict
from langgraph.graph import StateGraph, START, END


class State(TypedDict, total=False):
    input: str
    route: str
    output: str
    status: str
    error: str
    path: list
    branches: list
    tool_calls: list
    documents: list
    retrieval_attempted: bool
    retries: int
    interrupted: bool


def build_graph(manifest, context=None):
    def intent(s):
        q = s["input"].lower()
        route = "balance" if "balance" in q or "연차 조회" in q or "남은 연차" in q else "knowledge" if any(t in q for t in ("leave", "knowledge", "연차", "지식")) else "general"
        return {"route": route, "path": s["path"] + ["intent"], "branches": ["intent->" + route]}

    def knowledge(s):
        docs = context.retrieve(s["input"])
        return {"documents": docs, "retrieval_attempted": True, "path": s["path"] + ["knowledge"],
                "output": docs[0]["content"] if docs else "근거 문서를 찾지 못했습니다. 확인된 규정에 대해서만 안내할 수 있습니다."}

    def balance(s):
        args = {"employee_id": "demo"}
        if "error" in s["input"] or "오류" in s["input"]:
            args["simulate_error"] = True
        try:
            if "timeout" in s["input"] or "시간 초과" in s["input"]:
                time.sleep(0.04)
                raise TimeoutError("simulated tool deadline exceeded (40ms > 20ms budget)")
            result = context.tool("balance_lookup", args)
            return {"tool_calls": [{"name": "balance_lookup", "args": args, "result": result, "status": "ok"}],
                    "output": f"남은 연차는 {result['days']}일입니다.", "path": s["path"] + ["balance"]}
        except Exception as exc:
            return {"tool_calls": [{"name": "balance_lookup", "args": args, "status": "error", "error": str(exc)}],
                    "status": "timeout" if isinstance(exc, TimeoutError) else "error", "error": str(exc),
                    "output": "현재 연차 조회 서비스를 이용할 수 없습니다. 잠시 후 다시 시도해 주세요.", "path": s["path"] + ["balance"]}

    def general(s):
        return {"output": "연차 규정 안내와 남은 연차 조회를 도와드릴 수 있습니다.", "path": s["path"] + ["general"]}

    def final(s):
        if context:
            with context.trace.span("final", "CHAIN", {"output.value": s["output"]}):
                pass
        return {"path": s["path"] + ["final"]}

    graph = StateGraph(State)
    for name, fn in {"intent": intent, "knowledge": knowledge, "balance": balance, "general": general, "final": final}.items():
        graph.add_node(name, fn)
    graph.add_edge(START, "intent")
    graph.add_conditional_edges("intent", lambda s: s["route"], {"knowledge": "knowledge", "balance": "balance", "general": "general"})
    for name in ("knowledge", "balance", "general"):
        graph.add_edge(name, "final")
    graph.add_edge("final", END)
    return graph.compile()
