def inventory(spec):
    return {
        "feature": spec.capabilities,
        "workflow": spec.nodes,
        "branch": spec.branches,
        "tool": [t["name"] for t in spec.tools],
        "rag": [d.id for d in spec.knowledge_sources],
        "failure": spec.metadata.get("failure_types", []),
        "edge": spec.metadata.get("edge_cases", []),
    }
