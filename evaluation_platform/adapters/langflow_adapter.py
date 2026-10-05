import asyncio
import json
from .base import BaseAdapter
from evaluation_platform.models import AgentResult


class LangFlowAdapter(BaseAdapter):
    """Runs exported JSON using the official LangFlow LFX engine, not a JSON simulator."""
    def flow(self):
        return json.loads((self.path / self.manifest["entry_point"]).read_text(encoding="utf-8"))

    def analyze(self):
        data = self.flow()["data"]
        nodes = [n["id"] for n in data["nodes"]]
        edges = [{"source": e["source"], "target": e["target"]} for e in data["edges"]]
        routers = {n["id"] for n in data["nodes"] if sum(o.get("group_outputs", False) for o in n["data"]["node"].get("outputs", [])) > 1}
        branches = [f"{e['source']}->{e['target']}" for e in data["edges"] if e["source"] in routers]
        return self.build_spec(nodes, edges, branches)

    def execute(self, question, context):
        from lfx.graph import Graph
        from evaluation_platform.connectors.runtime import active_context
        token = active_context.set(context)
        try:
            graph = Graph.from_payload(self.flow())
            result = asyncio.run(graph.arun(inputs=[{"input_value": question}], types=["text"],
                                            outputs=self.manifest.get("output_nodes", [])))
            # Shape is mapped here; framework output is never consumed by Core.
            for run in result:
                for output in run.outputs:
                    if output is None:
                        continue
                    for value in output.results.values():
                        payload = getattr(value, "data", None)
                        if payload and "output" in payload:
                            return AgentResult.model_validate(payload)
                    for value in output.outputs.values():
                        payload = value.get("message") if isinstance(value, dict) else None
                        if isinstance(payload, dict) and "output" in payload:
                            return AgentResult.model_validate(payload)
            # LFX only returns built-in Output component types in RunOutputs;
            # custom terminal Data components are obtained from executed vertices.
            for node in self.manifest.get("output_nodes", []):
                output = graph.get_vertex(node).result
                if output:
                    for artifact in output.artifacts.values():
                        payload = artifact.get("raw")
                        if isinstance(payload, dict) and "output" in payload:
                            return AgentResult.model_validate(payload)
            raise ValueError("LangFlow output has no normalized AgentResult Data")
        finally:
            active_context.reset(token)
