from typing import TypedDict
from langgraph.graph import StateGraph, START, END


class OrderState(TypedDict, total=False):
    input: str
    path: list
    branches: list
    tool_calls: list
    documents: list
    status: str
    output: str
    authorized: bool
    action: str
    permission_denied: bool
    retrieval_attempted: bool


def build_graph(manifest, context=None):
    def intake(s):
        return {"authorized": "private" not in s["input"].lower(), "path": ["order_intake"]}

    def dispatch(s):
        action = "blocked" if not s["authorized"] else "shipment" if "track" in s["input"].lower() else "returns"
        return {"action": action, "path": s["path"] + ["dispatch"], "branches": ["dispatch->" + action]}

    def blocked(s):
        return {"permission_denied": True, "output": "Access denied: order ownership required.", "path": s["path"] + ["blocked"]}

    def shipment(s):
        args = {"order_id": "ORDER-42"}
        data = context.tool("shipment_tracking", args)
        return {"tool_calls": [{"name": "shipment_tracking", "args": args, "result": data, "status": "ok"}],
                "output": f"Shipment status: {data['state']}; arrival: {data['arrival']}.", "path": s["path"] + ["shipment"]}

    def returns(s):
        docs = context.retrieve(s["input"])
        return {"documents": docs, "retrieval_attempted": True, "output": docs[0]["content"] if docs else "Return policy unknown.", "path": s["path"] + ["returns"]}

    def receipt(s):
        return {"path": s["path"] + ["receipt"]}

    graph = StateGraph(OrderState)
    for name, fn in {"order_intake": intake, "dispatch": dispatch, "blocked": blocked, "shipment": shipment, "returns": returns, "receipt": receipt}.items():
        graph.add_node(name, fn)
    graph.add_edge(START, "order_intake")
    graph.add_edge("order_intake", "dispatch")
    graph.add_conditional_edges("dispatch", lambda s: s["action"], {"blocked": "blocked", "shipment": "shipment", "returns": "returns"})
    for name in ("blocked", "shipment", "returns"):
        graph.add_edge(name, "receipt")
    graph.add_edge("receipt", END)
    return graph.compile()
