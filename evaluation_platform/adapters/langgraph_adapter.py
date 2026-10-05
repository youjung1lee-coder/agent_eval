from .base import BaseAdapter
from evaluation_platform.models import AgentResult


class LangGraphAdapter(BaseAdapter):
    def graph(self, context=None):
        module = self.trusted_module()
        _, factory = self.manifest["entry_point"].split(":", 1)
        return getattr(module, factory)(self.manifest, context)

    def analyze(self):
        graph = self.graph().get_graph()
        nodes = [n for n in graph.nodes if not n.startswith("__")]
        edges = [{"source": e.source, "target": e.target, "conditional": e.conditional} for e in graph.edges]
        branches = [f"{e.source}->{e.target}" for e in graph.edges if e.conditional]
        return self.build_spec(nodes, edges, branches)

    def execute(self, question, context):
        state = self.graph(context).invoke({"input": question, "path": [], "branches": [], "tool_calls": [],
                                             "documents": [], "status": "ok", "output": ""})
        state["workflow_path"] = state.pop("path")
        return AgentResult.model_validate(state)
