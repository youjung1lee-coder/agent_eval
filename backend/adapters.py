import os
import re
from collections import defaultdict
from typing import Protocol
from urllib.parse import quote
import httpx
from .mock_agent import policies


def setting(name, default=""):
    return os.getenv(name, default)


def demo():
    return setting("DEMO_MODE").lower() == "true"


def clean(value):
    if isinstance(value, list):
        return [clean(v) for v in value]
    if isinstance(value, dict):
        return {
            k: "[마스킹]"
            if re.search(
                r"token|authorization|cookie|password|api.?key|employee.?id|사번|secret",
                k,
                re.I,
            )
            else clean(v)
            for k, v in value.items()
        }
    if isinstance(value, str):
        value = re.sub(r"(?i)Bearer\s+[\w.~/+=-]+", "[마스킹]", value)
        return re.sub(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}", "[이메일]", value)
    return value


class PhoenixDatasetClient(Protocol):
    def list(self): ...
    def versions(self, dataset): ...
    def load(self, dataset, version): ...


class FixtureClient:
    def list(self):
        return [{"id": "policy", "name": "사내 정책 도우미", "example_count": 20}]

    def versions(self, dataset):
        if dataset != "policy":
            raise ValueError("알 수 없는 Fixture Dataset")
        return [{"id": "fixture-v1"}]

    def load(self, dataset, version):
        if version != self.versions(dataset)[0]["id"]:
            raise ValueError("알 수 없는 Fixture 버전")
        items = []
        for i, p in enumerate(policies):
            text = p["topic"] + " 방법을 알려주세요."
            answer = p["answer"] if i % 6 else "확인이 필요합니다."
            docs = [p["answer"]] if i % 5 else []
            trace_id = f"trace-{i}" if i != 19 else None
            root = {
                "id": "r",
                "parent_id": None,
                "kind": "CHAIN",
                "attributes": {"input.value": text, "output.value": answer},
            }
            search = {
                "id": "s",
                "parent_id": "r",
                "name": "search_policy" if i % 2 else "knowledge_lookup",
                "kind": "RETRIEVER",
                "attributes": {"operation": "search", "documents": docs},
            }
            tools = [{"name": "policy_search", "arguments": {"topic": p["topic"]}}]
            items.append(
                {
                    "id": f"item-{i:02}",
                    "input": {"text": text},
                    "output": {"text": answer},
                    "metadata": {
                        "expected_output": p["answer"],
                        "expected_tools": tools,
                        "tools_called": tools,
                        "retrieval_context": docs,
                        "trace_id": trace_id,
                        "span_id": "s" if trace_id else None,
                    },
                    "spans": [root, search] if trace_id else [],
                }
            )
        return items


class PhoenixHTTP:
    def get(self, path, **params):
        headers = (
            {"Authorization": "Bearer " + setting("PHOENIX_API_KEY")}
            if setting("PHOENIX_API_KEY")
            else {}
        )
        with httpx.Client(
            timeout=15, transport=httpx.HTTPTransport(retries=2)
        ) as client:
            r = client.get(
                setting("PHOENIX_URL").rstrip("/") + "/v1/" + path,
                params=params,
                headers=headers,
            )
            r.raise_for_status()
            return r.json()

    def pages(self, path):
        result, params = [], {}
        while True:
            page = self.get(path, **params)
            result.extend(page["data"])
            if not page.get("next_cursor"):
                return result
            params = {"cursor": page["next_cursor"]}

    def list(self):
        return self.pages("datasets")

    def versions(self, dataset):
        return [
            {**v, "id": v["version_id"]}
            for v in self.pages("datasets/" + quote(dataset, safe="") + "/versions")
        ]

    def load(self, dataset, version):
        body = self.get(
            "datasets/" + quote(dataset, safe="") + "/examples", version_id=version
        )["data"]
        examples = body["examples"]
        grouped, by_span = defaultdict(list), {}
        if any(
            (x.get("metadata") or {}).get(k)
            for x in examples
            for k in ("span_id", "trace_id")
        ):
            try:
                spans = self.pages(
                    "projects/"
                    + quote(setting("PHOENIX_PROJECT", "default"), safe="")
                    + "/spans"
                )
                for span in spans:
                    ctx = span.get("context", {})
                    grouped[ctx.get("trace_id")].append(span)
                    by_span[ctx.get("span_id")] = ctx.get("trace_id")
            except httpx.HTTPError:
                pass  # item-only snapshot is marked by importer
        for x in examples:
            meta = x.get("metadata") or {}
            trace = meta.get("trace_id") or by_span.get(meta.get("span_id"))
            x["spans"] = grouped.get(trace, []) if trace else []
            x["metadata"] = {**meta, "trace_id": trace}
        return examples


def phoenix():
    if setting("PHOENIX_MODE", "fixture") == "fixture":
        return FixtureClient()
    if demo() or not setting("PHOENIX_URL"):
        raise ValueError("실제 Phoenix에는 인증 모드와 URL이 필요합니다")
    return PhoenixHTTP()


class AgentRunner(Protocol):
    def run(self, sample, environment, agent, request_id): ...


class HTTPAgent:
    def run(self, sample, environment, agent, request_id):
        mock = setting("AGENT_MODE", "mock") == "mock"
        if not mock and (
            demo()
            or environment == "PRD"
            or agent != setting("STG_ALLOWED_AGENT")
            or not setting("STG_AGENT_TOKEN")
        ):
            raise ValueError("실제 실행 권한 또는 격리된 STG 계약 미설정")
        url = (
            setting("MOCK_AGENT_URL", "http://127.0.0.1:8101")
            if mock
            else setting("STG_AGENT_URL")
        )
        headers = {"Idempotency-Key": request_id}
        if not mock:
            headers["Authorization"] = "Bearer " + setting("STG_AGENT_TOKEN")
        if not mock:
            check = httpx.get(
                url.rstrip("/") + "/capabilities", headers=headers, timeout=5
            )
            check.raise_for_status()
            caps = check.json()
            if (
                caps.get("isolated") is not True
                or caps.get("idempotency") is not True
                or caps.get("agent_id") != agent
            ):
                raise ValueError(
                    "격리 및 멱등성을 보장하는 STG 게이트웨이가 필요합니다"
                )
        response = httpx.post(
            url.rstrip("/") + "/run",
            json={
                "input": sample["input"],
                "session_id": request_id,
                "environment": environment,
                "agent_id": agent,
            },
            headers=headers,
            timeout=20,
        )
        response.raise_for_status()
        record = clean(response.json())
        if not isinstance(record, dict) or "actual_output" not in record:
            raise ValueError("Agent 응답 계약 오류")
        return record
