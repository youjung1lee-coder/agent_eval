from .langgraph_adapter import LangGraphAdapter
from .langflow_adapter import LangFlowAdapter

ADAPTERS = {"langgraph": LangGraphAdapter, "langflow": LangFlowAdapter}


def load_adapter(path):
    from .base import read_manifest
    manifest = read_manifest(path)
    if manifest["framework"] not in ADAPTERS:
        raise ValueError("unsupported framework; register an adapter in ADAPTERS")
    return ADAPTERS[manifest["framework"]](path)
