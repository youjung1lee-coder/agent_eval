"""Metric catalog, structured selectors and isolated provider adapters."""

import asyncio
import importlib
import json
import math
import os
import re
from importlib.metadata import version, PackageNotFoundError
import httpx
from .adapters import clean, demo, setting

os.environ["DEEPEVAL_TELEMETRY_OPT_OUT"] = "YES"
os.environ["RAGAS_DO_NOT_TRACK"] = "true"
os.environ["DEEPEVAL_UPDATE_WARNING_OPT_IN"] = "NO"


def metric(key, provider, title, description, category, fields, impl, model=False):
    try:
        ver = version(provider.lower()) if provider != "Custom" else "1"
    except PackageNotFoundError:
        ver = "unavailable"
    ready = ver != "unavailable" and (
        not model
        or (
            not demo()
            and all(setting(k) for k in ("JUDGE_URL", "JUDGE_MODEL", "JUDGE_KEY"))
        )
    )
    return dict(
        metric_id=key,
        provider=provider,
        provider_version=ver,
        display_name=title,
        description=description,
        category=category,
        scope="Session"
        if key == "goal"
        else "Trace"
        if category == "Tool" or key == "task"
        else "응답",
        required_inputs=fields.split(),
        optional_inputs=[],
        supported_output_type=["text", "json"],
        score_schema="0–1",
        default_threshold=0.5,
        model_requirement=model,
        implementation_ref=impl,
        available=bool(ready),
        docs={
            "DeepEval": "https://deepeval.com/docs/metrics-tool-correctness",
            "Ragas": "https://docs.ragas.io/en/v0.2.15/concepts/metrics/available_metrics/",
            "Custom": "#evaluators",
        }[provider],
    )


DEEP = {
    "relevancy": "AnswerRelevancyMetric",
    "deep_faith": "FaithfulnessMetric",
    "precision": "ContextualPrecisionMetric",
    "recall": "ContextualRecallMetric",
    "task": "TaskCompletionMetric",
}


def catalog():
    return {
        m["metric_id"]: m
        for m in [
            metric(
                "exact",
                "Ragas",
                "Exact Match",
                "기대 응답과 실제 응답의 문자열이 일치하는지 평가합니다.",
                "Task",
                "actual_output expected_output",
                "ragas.metrics.ExactMatch",
            ),
            metric(
                "tools",
                "DeepEval",
                "Tool Correctness",
                "기대 도구 목록과 실제 호출 도구의 이름을 비교합니다.",
                "Tool",
                "input actual_output tools_called expected_tools",
                "deepeval.metrics.ToolCorrectnessMetric",
            ),
            metric(
                "faith",
                "Ragas",
                "Faithfulness",
                "응답의 주장을 검색 문서로 뒷받침할 수 있는지 Judge로 평가합니다.",
                "RAG",
                "input actual_output retrieval_context",
                "ragas.metrics.Faithfulness",
                True,
            ),
            metric(
                "relevancy",
                "DeepEval",
                "Answer Relevancy",
                "응답 문장이 질문에 관련되는지 판단합니다.",
                "General",
                "input actual_output",
                "deepeval.metrics.AnswerRelevancyMetric",
                True,
            ),
            metric(
                "deep_faith",
                "DeepEval",
                "Faithfulness",
                "추출한 답변 주장과 검색 근거의 모순을 판정합니다. Ragas와 판정 절차가 다릅니다.",
                "RAG",
                "input actual_output retrieval_context",
                "deepeval.metrics.FaithfulnessMetric",
                True,
            ),
            metric(
                "precision",
                "DeepEval",
                "Contextual Precision",
                "관련 문서가 검색 결과 앞에 정렬됐는지 평가합니다.",
                "RAG",
                "input actual_output expected_output retrieval_context",
                "deepeval.metrics.ContextualPrecisionMetric",
                True,
            ),
            metric(
                "recall",
                "DeepEval",
                "Contextual Recall",
                "검색 근거가 기대 응답을 얼마나 포괄하는지 평가합니다.",
                "RAG",
                "input actual_output expected_output retrieval_context",
                "deepeval.metrics.ContextualRecallMetric",
                True,
            ),
            metric(
                "task",
                "DeepEval",
                "Task Completion",
                "도구 실행 기록과 응답을 바탕으로 요청의 완수 여부를 판단합니다.",
                "Task",
                "input actual_output tools_called",
                "deepeval.metrics.TaskCompletionMetric",
                True,
            ),
            metric(
                "goal",
                "Ragas",
                "Goal Accuracy",
                "순서가 보존된 대화 턴과 기준 목표로 세션 완수 여부를 평가합니다.",
                "Workflow",
                "turns expected_output",
                "ragas.metrics.AgentGoalAccuracyWithReference",
                True,
            ),
            metric(
                "present",
                "Custom",
                "Field Presence",
                "선택한 필드에 값이 있는지 확인합니다.",
                "General",
                "value",
                "presence",
            ),
            metric(
                "numeric",
                "Custom",
                "Numeric Comparison",
                "숫자가 지정한 최솟값 이상인지 확인합니다.",
                "Workflow",
                "value minimum",
                "greater_equal",
            ),
            metric(
                "judge",
                "Custom",
                "Rubric Judge",
                "설정한 프롬프트와 기준으로 응답의 품질을 채점합니다.",
                "Task",
                "input actual_output",
                "openai-compatible",
                True,
            ),
        ]
    }


def pointer(obj, path):
    if path == "":
        return obj
    if not isinstance(path, str) or not path.startswith("/"):
        raise ValueError("경로는 JSON Pointer 형식이어야 합니다")
    for token in path[1:].split("/"):
        key = token.replace("~1", "/").replace("~0", "~")
        if isinstance(obj, list):
            if not key.isdecimal():
                raise ValueError("배열 인덱스 오류")
            obj = obj[int(key)]
        else:
            obj = obj[key]
    return obj


def extract(rec, rule):
    if "fixed" in rule:
        return rule["fixed"], "고정값", []
    if "join" in rule:
        return "\n".join(str(pointer(rec, p)) for p in rule["join"]), rule["join"], []
    path = rule["path"]
    if "selector" not in rule:
        return pointer(rec, path), path, []
    selector = rule["selector"]
    hits = []
    for i, span in enumerate(rec["trace"]["spans"]):
        if (
            selector.get("kind")
            and (span.get("kind") or span.get("span_kind")) != selector["kind"]
        ):
            continue
        if selector.get("name_contains", "") not in span.get("name", ""):
            continue
        if any(
            span.get("attributes", {}).get(k) != v
            for k, v in selector.get("attributes", {}).items()
        ):
            continue
        hits.append((pointer(span, path), f"/trace/spans/{i}" + path))
    if not hits:
        raise KeyError("selector")
    policy = rule.get("policy", "unique")
    warn = ["복수 span 일치"] if len(hits) > 1 else []
    if policy == "all":
        return [v for v, _ in hits], [p for _, p in hits], warn
    if policy not in ("unique", "first", "last") or (
        len(hits) > 1 and policy == "unique"
    ):
        raise ValueError("복수 일치 · 선택 정책 필요")
    value, p = hits[-1 if policy == "last" else 0]
    return value, p, warn + (["span 순서에 의존"] if policy != "unique" else [])


def recommend(rec, metric_id):
    fields = catalog()[metric_id]["required_inputs"]
    out = {}
    for key in fields:
        path = "/" + key
        if isinstance(rec.get(key), dict) and "text" in rec[key]:
            path += "/text"
        if key == "value":
            path = "/actual_output"
        out[key] = {"fixed": 0} if key == "minimum" else {"path": path}
    return out


def preview(rec, spec, rules):
    result = {}
    required = list(catalog()[spec["metric"]]["required_inputs"])
    if spec["metric"] == "judge":
        required = list(
            dict.fromkeys(required + re.findall(r"\{\{(\w+)\}\}", spec["prompt"]))
        )
    for name in required:
        item = {"rule": rules.get(name), "ok": False}
        try:
            raw, path, warnings = extract(rec, rules[name])
            item.update(
                raw=raw,
                path=path,
                type=type(raw).__name__,
                length=len(raw) if isinstance(raw, (str, list, dict)) else None,
                warnings=warnings,
            )
            val = raw
            if raw is None or raw == "" or raw == []:
                raise ValueError(
                    "null" if raw is None else "빈 배열" if raw == [] else "빈 문자열"
                )
            if name in ("input", "actual_output", "expected_output"):
                val = raw.get("text") if isinstance(raw, dict) else raw
                if not isinstance(val, str) or not val.strip():
                    raise ValueError("타입 불일치 · 텍스트 필요")
            if name == "turns" and (
                not isinstance(raw, list)
                or not all(
                    isinstance(x, dict) and x.get("type") in ("human", "ai", "tool")
                    for x in raw
                )
            ):
                raise ValueError("타입 불일치 · 순서가 있는 Ragas 메시지 배열 필요")
            if name in ("expected_tools", "tools_called", "retrieval_context"):
                if not isinstance(raw, list):
                    raise ValueError("타입 불일치 · 배열 필요")
                if name == "retrieval_context":
                    val = [x.get("content") if isinstance(x, dict) else x for x in raw]
                    if not all(isinstance(x, str) and x.strip() for x in val):
                        raise ValueError("문서 content 타입 불일치")
                elif not all(
                    isinstance(x, dict) and isinstance(x.get("name"), str) for x in raw
                ):
                    raise ValueError("도구 name 타입 불일치")
            if spec["metric"] == "numeric" and (
                type(raw) not in (float, int) or not math.isfinite(raw)
            ):
                raise ValueError("타입 불일치 · 유한한 숫자 필요")
            item.update(ok=True, value=val)
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            item["error"] = (
                str(exc) if isinstance(exc, ValueError) else "경로 또는 매핑 누락"
            )
        result[name] = item
    return result


def run_metric(k, v, spec):
    if k == "present":
        return 1.0, "필드 값 확인"
    if k == "numeric":
        return float(v["value"] >= v["minimum"]), "최솟값 비교"
    if k == "tools":
        from deepeval.metrics import ToolCorrectnessMetric
        from deepeval.test_case import LLMTestCase, ToolCall

        calls = lambda key: [
            ToolCall(name=x["name"], input_parameters=x.get("arguments"))
            for x in v[key]
        ]
        metric = ToolCorrectnessMetric()
        score = metric.measure(
            LLMTestCase(
                input=v["input"],
                actual_output=v["actual_output"],
                tools_called=calls("tools_called"),
                expected_tools=calls("expected_tools"),
            )
        )
        return score, metric.reason
    if k in DEEP:
        from .judge import StructuredJudge
        from deepeval.test_case import LLMTestCase, ToolCall

        args = dict(v)
        if "tools_called" in args:
            args["tools_called"] = [
                ToolCall(name=t["name"], input_parameters=t.get("arguments"))
                for t in args["tools_called"]
            ]
        metric_class = getattr(importlib.import_module("deepeval.metrics"), DEEP[k])
        metric = metric_class(
            model=StructuredJudge(spec.get("model") or setting("JUDGE_MODEL")),
            threshold=spec["threshold"],
        )
        score = asyncio.run(
            asyncio.wait_for(
                metric.a_measure(LLMTestCase(**args)), timeout=spec.get("timeout", 60)
            )
        )
        return score, clean(metric.reason)
    if k in ("exact", "faith", "goal"):
        from ragas import SingleTurnSample
        from ragas.metrics import ExactMatch, Faithfulness

        if k == "exact":
            metric = ExactMatch()
            sample = SingleTurnSample(
                response=v["actual_output"], reference=v["expected_output"]
            )
        else:
            from langchain_openai import ChatOpenAI
            from ragas.llms import LangchainLLMWrapper

            llm = LangchainLLMWrapper(
                ChatOpenAI(
                    model=spec.get("model") or setting("JUDGE_MODEL"),
                    api_key=setting("JUDGE_KEY"),
                    base_url=setting("JUDGE_URL"),
                    timeout=25,
                    max_retries=1,
                )
            )
            if k == "goal":
                from ragas import MultiTurnSample
                from ragas.metrics import AgentGoalAccuracyWithReference

                metric = AgentGoalAccuracyWithReference(llm=llm)
                sample = MultiTurnSample(
                    user_input=v["turns"], reference=v["expected_output"]
                )
                score = asyncio.run(
                    asyncio.wait_for(
                        metric.multi_turn_ascore(sample),
                        timeout=spec.get("timeout", 60),
                    )
                )
                return score, "기대 목표와 관찰 결과의 일치 여부"
            metric = Faithfulness(llm=llm)
            sample = SingleTurnSample(
                user_input=v["input"],
                response=v["actual_output"],
                retrieved_contexts=v["retrieval_context"],
            )
        score = asyncio.run(
            asyncio.wait_for(
                metric.single_turn_ascore(sample), timeout=spec.get("timeout", 60)
            )
        )
        return score, (
            "문자열 일치" if score else "문자열 불일치"
        ) if k == "exact" else "Ragas Faithfulness 주장 지지 비율"
    if k == "judge":
        prompt = re.sub(r"\{\{(\w+)\}\}", lambda m: str(v[m[1]]), spec["prompt"])
        kind = spec.get("score_type", "number")
        schema = {
            "number": "number in [0,1]",
            "boolean": "boolean true or false",
            "category": "one of " + json.dumps(list(spec.get("categories", {}))),
        }[kind]
        r = httpx.post(
            setting("JUDGE_URL").rstrip("/") + "/chat/completions",
            headers={"Authorization": "Bearer " + setting("JUDGE_KEY")},
            json={
                "model": spec.get("model") or setting("JUDGE_MODEL"),
                "temperature": spec.get("temperature", 0),
                "messages": [
                    {
                        "role": "system",
                        "content": spec["rubric"]
                        + " Return JSON with score ("
                        + schema
                        + ") and reason.",
                    },
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=spec.get("timeout", 30),
        )
        r.raise_for_status()
        obj = json.loads(r.json()["choices"][0]["message"]["content"])
        raw = obj["score"]
        if kind == "boolean" and type(raw) is not bool:
            raise ValueError("Judge boolean schema")
        if kind == "number" and type(raw) not in (float, int):
            raise ValueError("Judge numeric schema")
        score = spec["categories"][raw] if kind == "category" else float(raw)
        return score, clean(str(obj["reason"]))
    raise ValueError("지원하지 않는 Metric")


def evaluate(rec, spec, rules):
    k = spec["metric"]
    m = catalog()[k]
    inputs = preview(rec, spec, rules)
    base = dict(
        metric_id=k,
        metric_version=m["provider_version"],
        inputs=inputs,
        score=None,
        passed=None,
        error_code=None,
        judge_model=(spec.get("model") or setting("JUDGE_MODEL"))
        if m["model_requirement"]
        else None,
        raw_result=None,
    )
    missing = [key for key, x in inputs.items() if not x["ok"]]
    if missing:
        return dict(
            base,
            status="NOT_EVALUABLE",
            reason="매핑 확인 필요 · " + ", ".join(missing),
            error_code="INPUT",
        )
    if not m["available"]:
        return dict(
            base,
            status="NOT_RUN",
            reason="라이브러리 또는 Judge 설정 필요",
            error_code="UNAVAILABLE",
        )
    try:
        for attempt in range(spec.get("retries", 0) + 1):
            try:
                score, reason = run_metric(
                    k, {key: x["value"] for key, x in inputs.items()}, spec
                )
                break
            except (TimeoutError, httpx.TimeoutException, httpx.ConnectError):
                if attempt >= spec.get("retries", 0):
                    raise
        score = float(score)
        if not 0 <= score <= 1:
            raise ValueError("score")
        passed = score >= spec["threshold"]
        return {
            **base,
            "score": score,
            "passed": passed,
            "reason": reason,
            "raw_result": {"score": score, "reason": reason},
            "status": "PASSED" if passed else "FAILED",
        }
    except Exception as exc:
        return {
            **base,
            "status": "ERROR",
            "error_code": type(exc).__name__,
            "reason": "평가 엔진 호출 오류",
        }
