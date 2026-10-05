from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, DataInput, Output
from lfx.schema import Data


class SupportRouter(Component):
    display_name = "Support Intent"
    name = "SupportRouter"
    inputs = [MessageTextInput(name="question", required=True)]
    outputs = [Output(name="rag", method="rag", group_outputs=True),
               Output(name="tool", method="tool", group_outputs=True),
               Output(name="general", method="general", group_outputs=True)]

    def routed(self, requested: str) -> Data:
        question = self.question.lower()
        route = "tool" if any(t in question for t in ("ticket", "티켓")) else "rag" if any(t in question for t in ("password", "knowledge", "비밀번호", "지식")) else "general"
        for other in ("rag", "tool", "general"):
            if other != route:
                self.stop(other)
                self.graph.exclude_branch_conditionally(self._id, output_name=other)
        return Data(data={"input": self.question, "route": route, "status": "ok", "workflow_path": ["TextInput", "Router"]})

    def rag(self) -> Data:
        return self.routed("rag")

    def tool(self) -> Data:
        return self.routed("tool")

    def general(self) -> Data:
        return self.routed("general")


class SupportSearch(Component):
    display_name = "Support Knowledge"
    name = "SupportSearch"
    inputs = [DataInput(name="state", required=True)]
    outputs = [Output(name="result", method="search")]

    def search(self) -> Data:
        from evaluation_platform.connectors.runtime import active_context
        ctx = active_context.get()
        state = dict(self.state.data)
        documents = ctx.retrieve(state["input"])
        state.update(documents=documents, retrieval_attempted=True,
                     output=documents[0]["content"] if documents else "지원 문서를 찾지 못했습니다. 확인된 문서를 기준으로 질문해 주세요.",
                     workflow_path=state["workflow_path"] + ["Search"], branches=["Router->Search"])
        return Data(data=state)


class SupportService(Component):
    display_name = "Ticket Service"
    name = "SupportService"
    inputs = [DataInput(name="state", required=True)]
    outputs = [Output(name="result", method="call_service")]

    def call_service(self) -> Data:
        from evaluation_platform.connectors.runtime import active_context
        ctx = active_context.get()
        state = dict(self.state.data)
        args = {"ticket_id": "T-100"}
        if "error" in state["input"] or "오류" in state["input"]:
            args["simulate_error"] = True
        try:
            result = ctx.tool("ticket_status", args)
            state.update(tool_calls=[{"name": "ticket_status", "args": args, "result": result, "status": "ok"}],
                         output="지원 티켓 처리 상태: " + result["state"])
        except Exception as exc:
            state.update(status="error", error=str(exc), output="현재 지원 티켓 조회 서비스를 이용할 수 없습니다.",
                         tool_calls=[{"name": "ticket_status", "args": args, "status": "error", "error": str(exc)}])
        state.update(workflow_path=state["workflow_path"] + ["Service"], branches=["Router->Service"])
        return Data(data=state)


class SupportGeneral(Component):
    display_name = "Support Help"
    name = "SupportGeneral"
    inputs = [DataInput(name="state", required=True)]
    outputs = [Output(name="result", method="help")]

    def help(self) -> Data:
        state = dict(self.state.data)
        state.update(output="비밀번호 재설정과 지원 티켓 조회를 도와드릴 수 있습니다.",
                     workflow_path=state["workflow_path"] + ["Help"], branches=["Router->Help"])
        return Data(data=state)


class SupportFinish(Component):
    display_name = "Support Answer"
    name = "SupportFinish"
    inputs = [DataInput(name="state", required=True)]
    outputs = [Output(name="result", method="finish")]

    def finish(self) -> Data:
        state = dict(self.state.data)
        state["workflow_path"] = state["workflow_path"] + [self._id]
        return Data(data=state)
