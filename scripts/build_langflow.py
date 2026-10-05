"""Rebuild the committed genuine LangFlow export using official LFX components."""
import inspect
import json
from pathlib import Path
from lfx.graph import Graph
from lfx.components.input_output.text import TextInputComponent
from sample_agents.langflow_agent.components import SupportRouter, SupportSearch, SupportService, SupportGeneral, SupportFinish


def main():
    components = [("TextInput", TextInputComponent()), ("Router", SupportRouter()),
                  ("Search", SupportSearch()), ("Service", SupportService()),
                  ("Help", SupportGeneral()), ("AnswerRag", SupportFinish()),
                  ("AnswerTool", SupportFinish()), ("AnswerGeneral", SupportFinish())]
    graph = Graph()
    for name, component in components:
        # Export self-contained source exactly as LangFlow custom components expect.
        if name != "TextInput":
            component._code = "from lfx.custom.custom_component.component import Component\nfrom lfx.io import MessageTextInput, DataInput, Output\nfrom lfx.schema import Data\n\n" + inspect.getsource(component.__class__)
        graph.add_component(component, name)
    graph.add_component_edge("TextInput", ("text", "question"), "Router")
    for output, node, end in (("rag", "Search", "AnswerRag"), ("tool", "Service", "AnswerTool"), ("general", "Help", "AnswerGeneral")):
        graph.add_component_edge("Router", (output, "state"), node)
        graph.add_component_edge(node, ("result", "state"), end)
    target = Path("sample_agents/langflow_agent/flow.json")
    payload = graph.dump(name="Support Agent")
    # LFX 0.2.2 dump() serializes initialized edges; add_component_edge stores raw edges.
    payload["data"]["edges"] = graph._edges
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print("Exported LangFlow JSON:", target)


if __name__ == "__main__":
    main()
