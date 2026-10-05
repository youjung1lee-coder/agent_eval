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
        route = "balance" if "balance" in q else "knowledge" if "leave" in q or "knowledge" in q else "general"
        return {"route": route, "path": s["path"] + ["intent"], "branches": ["intent->" + route]}

    def knowledge(s):
        docs = context.retrieve(s["input"])
        return {"documents": docs, "retrieval_attempted": True, "path": s["path"] + ["knowledge"],
                "output": docs[0]["content"] if docs else "No supporting document found."}

    def balance(s):
        args = {"employee_id": "demo"}
        if "error" in s["input"]:
            args["simulate_error"] = True
        try:
            if "timeout" in s["input"]:
                time.sleep(0.04)
                raise TimeoutError("simulated tool deadline exceeded (40ms > 20ms budget)")
            result = context.tool("balance_lookup", args)
            return {"tool_calls": [{"name": "balance_lookup", "args": args, "result": result, "status": "ok"}],
                    "output": f"Available leave: {result['days']} days.", "path": s["path"] + ["balance"]}
        except Exception as exc:
            return {"tool_calls": [{"name": "balance_lookup", "args": args, "status": "error", "error": str(exc)}],
                    "status": "timeout" if isinstance(exc, TimeoutError) else "error", "error": str(exc),
                    "output": "The leave service is unavailable. Please retry later.", "path": s["path"] + ["balance"]}

    def general(s):
        return {"output": "I can help with leave policy and leave balance.", "path": s["path"] + ["general"]}

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
