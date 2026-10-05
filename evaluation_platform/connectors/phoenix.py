import json
import os
from contextlib import contextmanager
from datetime import datetime
import httpx
from opentelemetry.context import Context
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.trace import Status, StatusCode
from evaluation_platform.models import AgentResult


class PhoenixConnector:
    def __init__(self, base_url=None, enabled=True):
        self.base_url = (base_url or os.getenv("PHOENIX_BASE_URL", "http://127.0.0.1:6006")).rstrip("/")
        self.headers = {"Authorization": "Bearer " + os.environ["PHOENIX_API_KEY"]} if os.getenv("PHOENIX_API_KEY") else {}
        self.providers = {}
        self.enabled = enabled

    def tracer(self, project):
        if project not in self.providers:
            provider = TracerProvider(resource=Resource.create({"service.name": "gaia-evaluation", "openinference.project.name": project}))
            if self.enabled:
                provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter(endpoint=self.base_url + "/v1/traces", headers=self.headers, timeout=10)))
            self.providers[project] = provider
        return self.providers[project].get_tracer("gaia-evaluation-platform")

    def session(self, project):
        return TraceSession(self.tracer(project))

    def health(self):
        if not self.enabled:
            return {"status": "disabled"}
        try:
            response = httpx.get(self.base_url + "/healthz", headers=self.headers, timeout=5)
            response.raise_for_status()
            return {"status": "connected", "url": self.base_url}
        except Exception as exc:
            return {"status": "unavailable", "error": str(exc)}

    def production(self, agent_id):
        """Query Phoenix REST spans, never a local surrogate for production trace ingestion."""
        if not self.enabled:
            return []
        from phoenix.client import Client
        client = Client(base_url=self.base_url, api_key=os.getenv("PHOENIX_API_KEY"))
        try:
            response = client.spans.get_spans(project_identifier="prd", limit=1000)
        except Exception as exc:
            if "404" in str(exc) and "project" in str(exc).lower():
                return []
            raise
        spans = response["data"] if isinstance(response, dict) else response
        records = []
        for span in spans:
            attrs = span.get("attributes", {})
            # Phoenix returns nested OpenInference attribute objects in its REST API.
            def attr(key, default=None):
                if key in attrs:
                    return attrs[key]
                value = attrs
                for part in key.split("."):
                    if not isinstance(value, dict) or part not in value:
                        return default
                    value = value[part]
                return value
            if attr("gaia.agent_id") != agent_id or not attr("gaia.root", False):
                continue
            payload = attr("gaia.result")
            result = AgentResult.model_validate(json.loads(payload)) if payload else AgentResult(
                output=attr("output.value", ""), status=attr("gaia.status", "unknown"),
                error=span.get("status_message") if span.get("status_code") == "ERROR" else None)
            context = span.get("context", {})
            result.trace_id = context.get("trace_id") or span.get("trace_id")
            result.span_id = context.get("span_id") or span.get("span_id")
            records.append({"input": attr("input.value", ""), "result": result.model_dump(),
                            "status_code": span.get("status_code"), "events": span.get("events", []),
                            "evidence": f"Phoenix prd Span {result.span_id} · 상태: {span.get('status_code')}"})
        return records

    def close(self):
        for provider in self.providers.values():
            provider.shutdown()


class TraceSession:
    def __init__(self, tracer):
        self.tracer = tracer

    @contextmanager
    def span(self, name, kind="CHAIN", attributes=None, root=False):
        with self.tracer.start_as_current_span(name, context=Context() if root else None,
                 attributes={"openinference.span.kind": kind, **(attributes or {})}) as span:
            yield span

    @staticmethod
    def identify(span):
        context = span.get_span_context()
        return f"{context.trace_id:032x}", f"{context.span_id:016x}"

    @staticmethod
    def finish(span, result):
        span.set_attribute("output.value", result.output)
        span.set_attribute("gaia.status", result.status)
        span.set_attribute("gaia.result", result.model_dump_json())
        if result.status != "ok" or result.error:
            span.set_status(Status(StatusCode.ERROR, result.error or result.status))
        else:
            span.set_status(Status(StatusCode.OK))
