"""Interpret common OpenInference attributes without requiring a particular span name."""

import json


def attribute(attrs, key):
    if key in attrs:
        return attrs[key]
    node = attrs
    for part in key.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


def decoded(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            pass
    return value


def normalize(spans):
    documents, tools, roots = [], [], []
    for span in spans:
        attrs = span.get("attributes") or {}
        sid = (span.get("context") or {}).get("span_id") or span.get("id")
        if not span.get("parent_id"):
            roots.append(span)
        for doc in attribute(attrs, "retrieval.documents") or []:
            if isinstance(doc, dict):
                documents.append(
                    {
                        "content": attribute(doc, "document.content"),
                        "document_id": attribute(doc, "document.id"),
                        "source_span_id": sid,
                        "raw": doc,
                    }
                )
        name = attribute(attrs, "tool.name")
        if name:
            tools.append(
                {
                    "name": name,
                    "arguments": decoded(attribute(attrs, "tool.parameters")),
                    "status": span.get("status_code", "unknown"),
                    "source_span_id": sid,
                }
            )
    root = roots[0] if len(roots) == 1 else {}
    return {
        "root_span_id": (root.get("context") or {}).get("span_id") or root.get("id"),
        "output": decoded(attribute(root.get("attributes") or {}, "output.value")),
        "documents": documents,
        "tools": tools,
    }
