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
        return {"authorized": not any(t in s["input"].lower() for t in ("private", "비공개", "다른 사람")), "path": ["order_intake"]}

    def dispatch(s):
        action = "blocked" if not s["authorized"] else "shipment" if any(t in s["input"].lower() for t in ("track", "배송")) else "returns"
        return {"action": action, "path": s["path"] + ["dispatch"], "branches": ["dispatch->" + action]}

    def blocked(s):
        return {"permission_denied": True, "output": "접근이 거부되었습니다. 본인 소유 주문만 조회할 수 있습니다.", "path": s["path"] + ["blocked"]}

    def shipment(s):
        args = {"order_id": "ORDER-42"}
        data = context.tool("shipment_tracking", args)
        return {"tool_calls": [{"name": "shipment_tracking", "args": args, "result": data, "status": "ok"}],
                "output": f"배송 상태: {data['state']}; 도착 예정일: {data['arrival']}.", "path": s["path"] + ["shipment"]}

    def returns(s):
        docs = context.retrieve(s["input"])
        return {"documents": docs, "retrieval_attempted": True, "output": docs[0]["content"] if docs else "확인할 수 있는 반품 정책 문서가 없습니다.", "path": s["path"] + ["returns"]}

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
