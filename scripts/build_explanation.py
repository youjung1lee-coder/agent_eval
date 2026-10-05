"""Build a self-contained Korean code→case→evaluator handout from actual samples.

Read-only: analyzes adapters and reads the running demo API; never changes drafts,
Golden datasets, runs or the evaluation core. Capture screenshots with cua_repl
into artifacts/explanation before running this script.
"""
import ast
import base64
import hashlib
import json
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen

from evaluation_platform.adapters import load_adapter
from evaluation_platform.dataset.generator import generate

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/sample_evaluation_explained.html"
API = "http://127.0.0.1:8000/api"
PATHS = [
    "sample_agents/langgraph_agent/workflow.py",
    "sample_agents/langgraph_agent/eval_agent.json",
    "sample_agents/langflow_agent/components.py",
    "sample_agents/langflow_agent/eval_agent.json",
    "sample_agents/langflow_agent/flow.json",
    "scripts/build_langflow.py",
    "evaluation_platform/adapters/langgraph_adapter.py",
    "evaluation_platform/adapters/langflow_adapter.py",
    "evaluation_platform/adapters/base.py",
    "evaluation_platform/analyzer/__init__.py",
    "evaluation_platform/dataset/generator.py",
    "evaluation_platform/models/evaluation_case.py",
    "evaluation_platform/evaluators/registry.py",
    "evaluation_platform/evaluators/base.py",
    "evaluation_platform/evaluators/custom_llm.py",
    "evaluation_platform/evaluators/llm_judge.py",
    "evaluation_platform/runner/runner.py",
    "evaluation_platform/candidates/failure_detector.py",
    "evaluation_platform/coverage/__init__.py",
    "evaluation_platform/service.py",
    "evaluation_platform/connectors/runtime.py",
    "ui/app.js",
]
SOURCES = {p: (ROOT / p).read_text(encoding="utf-8") for p in PATHS}


def api(path):
    with urlopen(API + path, timeout=30) as response:
        return json.load(response)


def image_data(path):
    content = path.read_bytes()
    if content.startswith(b"\xff\xd8\xff"):
        mime = "image/jpeg"
    elif content.startswith(b"\x89PNG\r\n\x1a\n"):
        mime = "image/png"
    else:
        raise ValueError(f"Unsupported screenshot encoding: {path.name}")
    return f"data:{mime};base64," + base64.b64encode(content).decode()


def excerpt(path, symbol):
    tree = ast.parse(SOURCES[path])
    node = next(n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name == symbol)
    return {"path": path, "start": node.lineno, "end": node.end_lineno,
            "code": "\n".join(SOURCES[path].splitlines()[node.lineno - 1:node.end_lineno]), "symbol": symbol}


def lines(path, first, last, label):
    return {"path": path, "start": first, "end": last,
            "code": "\n".join(SOURCES[path].splitlines()[first - 1:last]), "symbol": label}


def manifest_excerpt(path, value):
    source = SOURCES[path].splitlines()
    marker = f'"id": "{value["id"]}"'
    index = next(i for i, line in enumerate(source) if marker in line)
    first = index - 1
    last = next(i for i in range(index + 1, len(source)) if source[i] in ("    },", "    }"))
    snippet = lines(path, first + 1, last + 1, value["id"])
    assert json.loads(snippet["code"].strip().rstrip(",")) == value
    return snippet


RULES = {
    "error_detection": ("실행 상태 / 오류", "항상 기본 추천", "expected_status (기본 ok)",
        "r.status == e.expected_status", "상태가 기대값과 같으면 1, 다르면 0. 실제 오류 문자열은 이유에 표시합니다. 기대 error/timeout도 일치하면 PASS입니다.", "gate"),
    "latency": ("응답 시간", "항상 기본 추천", "max_latency_ms (기본 5000)",
        "r.latency_ms <= e.max_latency_ms", "지연이 제한 이하면 1, 초과하면 0인 이진 점수입니다. 연속 속도 점수나 P95가 아닙니다.", "quality"),
    "exact": ("문자열 일치", "reference_output is not None", "reference_output", "platform_registry → exact lambda",
        "기준 답변과 실제 답변의 앞뒤 공백만 제거해 문자열을 비교합니다. 동의어·의역을 자동 허용하지 않습니다.", "quality"),
    "tool_call": ("Tool 호출 정확성", "tool_calls 또는 forbidden_tools 존재", "tool_calls / forbidden_tools", "tool_match(e, r)",
        "금지 Tool이 없어야 합니다. 기대 호출이 있으면 호출 수·순서·이름과 기대 args의 각 키 값을 비교합니다. 추가 인수는 허용하며 input_schema 전체 검증은 이 함수가 수행하지 않습니다.", "gate"),
    "workflow_path": ("Workflow 경로 정확성", "required_nodes / valid_paths / forbidden_nodes 존재", "required_nodes / valid_paths / forbidden_nodes", "path_match(e, r)",
        "필수 Node 포함·금지 Node 부재를 검사합니다. valid_paths가 있을 때만 실제 경로 목록 전체의 순서를 일치시킵니다. required_nodes만 있으면 전체 순서 검사는 아닙니다.", "gate"),
    "rag_retrieval": ("RAG 검색 정확성", "document_ids 존재", "document_ids / recall_k (기본 5)", "rag_recall(e, r)",
        "실제 documents의 첫 K개 ID 집합과 기준 ID의 교집합 / 기준 ID 개수 = Recall@K. FunctionEvaluator의 기본 threshold=1이므로 기준 문서가 모두 검색되어야 PASS입니다.", "quality"),
    "faithfulness": ("답변 근거 충실도", "reference_context 존재", "reference_context + 실제 답변", "CustomLLMEvaluator.evaluate → JudgeBackend.assess",
        "답변의 사실 주장이 참조 Context에 의해 지지되는지 실제 LLM에 평가시킵니다. 플랫폼 rubric과 threshold=0.5를 사용합니다. 업무 정답 전체의 완전성 보장은 아닙니다.", "quality"),
    "behavior": ("필수 / 금지 응답", "required_output 또는 forbidden_output 존재", "required_output / forbidden_output", "platform_registry → behavior lambda",
        "모든 필수 문구를 포함하고 모든 금지 문구를 포함하지 않아야 1입니다. casefold 후 부분 문자열을 검사합니다. 예외 객체나 빈 검색 자체를 직접 검사하는 함수는 아닙니다.", "gate"),
    "runtime_reference": ("Tool 결과 참조", "runtime_reference 존재", "runtime_reference", "runtime_match(e, r)",
        "tool_output.<Tool>.<field>로 실제 Tool 결과 값을 찾고 str(value)가 답변에 포함되는지 검사합니다. 현재는 부분 문자열 방식이어서 값 12가 112 안에도 매치될 수 있습니다.", "quality"),
    "permission": ("접근 권한", "permission_denied is not None", "permission_denied / forbidden_tools", "platform_registry → permission lambda",
        "실제 permission_denied와 계약을 비교하고 금지 Tool 부재를 확인합니다. 이 두 Sample의 기본 14개 사례에는 자동 배정되지 않습니다.", "gate"),
    "output_schema": ("출력 JSON Schema", "output_schema 존재", "output_schema", "schema_match(e, r)",
        "실제 응답을 JSON으로 파싱하고 jsonschema.validate를 호출합니다. Tool 입력 Schema와 구분합니다. 이 두 Sample의 기본 사례에는 자동 배정되지 않습니다.", "gate"),
}
G = "sample_agents/langgraph_agent/workflow.py"
L = "sample_agents/langflow_agent/components.py"
RUNTIME = "evaluation_platform/connectors/runtime.py"
MAPPING = {
    "hr-policy": (["intent", "knowledge"], "질문을 knowledge로 분기하고 검색 문서와 knowledge/final 경로를 반환합니다.",
        "Workflow Probe는 required_nodes와 document_ids만 요구합니다. 기준 답변/Context는 비어 있어 exact·faithfulness를 자동 추천하지 않습니다."),
    "hr-balance": (["intent", "balance"], "balance 분기에서 employee_id=demo로 balance_lookup을 호출하고 days를 답변에 넣습니다.",
        "valid_paths가 있으므로 intent→balance→final의 순서를 비교합니다. runtime_reference는 하드코딩된 12가 아니라 실제 Tool 결과의 days를 사용합니다."),
    "hr-general": (["intent", "general"], "특정 업무 키워드가 없는 질문을 general로 보내 안내 문구를 반환합니다.",
        "reference_output으로 문자열을 비교하고 general Node 포함을 확인합니다. required_nodes만 있으므로 전체 경로 순서는 보장하지 않습니다."),
    "hr-error": (["balance"], "오류 입력은 simulate_error=True를 전달하고 예외를 잡아 status=error와 안내 응답을 반환합니다.",
        "기대 상태가 error이므로 오류가 관찰되어도 이 처리 계약은 PASS할 수 있습니다. Tool의 구체적 호출·예외 종류는 이 Probe의 계약에 없습니다."),
    "hr-timeout": (["balance"], "40ms sleep 후 명시적으로 TimeoutError를 발생시키고 status=timeout으로 매핑합니다.",
        "20ms deadline을 가진 실제 비동기 취소 구현이 아닌 Simulation입니다. 기본 latency 계약은 여전히 5000ms이며 timeout 상태 검사는 error_detection이 수행합니다."),
    "hr-empty": (["intent", "knowledge"], "지식 분기에서 검색 문서가 없으면 근거 없음 안내를 반환합니다.",
        "이 Probe는 안내 문구를 검사합니다. 빈 documents나 retrieval_attempted 자체를 판정하는 별도 Evaluator는 배정하지 않습니다. 운영 Failure Detector는 두 필드를 따로 관찰합니다."),
    "support-password": (["routed", "search", "finish"], "Router가 rag 출력을 남기고 Search가 문서를 검색한 뒤 AnswerRag에서 경로를 마칩니다.",
        "Flow topology와 Owner Probe를 함께 사용합니다. required_nodes와 문서 ID를 검사하며 자동 exact·faithfulness는 없습니다."),
    "support-ticket": (["routed", "call_service", "finish"], "Router의 tool 출력이 Service로 이어지고 ticket_id=T-100으로 ticket_status를 호출합니다.",
        "TextInput→Router→Service→AnswerTool 전체 경로와 Tool 인수를 검사합니다. 실제 state 값을 runtime_reference로 비교합니다."),
    "support-help": (["routed", "help", "finish"], "일반 질문은 Help 경로에서 명시적인 안내 문구를 반환합니다.",
        "문자열 기준 답변과 Help Node 포함을 검사합니다. AnswerGeneral을 포함한 전체 순서는 이 Probe의 expected에 명시되어 있지 않습니다."),
    "support-error": (["call_service"], "오류 입력에 simulate_error=True를 전달하고 예외 처리에서 status=error와 오류 안내를 기록합니다.",
        "error 상태 일치와 필수 안내 문구를 확인합니다. 정상 복구를 기대하는 운영 회귀 계약과 다릅니다."),
    "support-missing": (["routed", "search"], "미등록 지식 질문은 rag 분기에서 검색 결과 없음 안내를 받습니다.",
        "expected_status는 기본 ok이며 안내 문구 포함만 요구합니다. 빈 검색은 운영 실패 후보가 될 수 있지만 이 명시적 fallback 테스트에서는 정상 처리입니다."),
}


def main():
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    runs = api("/runs")
    evaluators = api("/evaluators")
    data = {"captured_at": now, "sources": SOURCES, "source_hashes": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in SOURCES},
            "rules": {i: dict(zip(("name", "condition", "field", "function", "meaning", "role"), row)) for i, row in RULES.items()},
            "agents": [], "cases": [], "custom": evaluators["custom"]}
    for folder, agent_id, title in [("langgraph_agent", "hr-langgraph", "LangGraph · HR 연차 안내"),
                                   ("langflow_agent", "support-langflow", "LangFlow · 계정 / 지원 티켓")]:
        adapter = load_adapter(ROOT / "sample_agents" / folder)
        spec = adapter.analyze()
        generated = generate(spec, [])
        current = {c["id"]: c for c in api(f"/agents/{agent_id}/cases")}
        own = [r for r in runs if r["agent_id"] == agent_id and r["agent_version"] == "1.1-ko"]
        latest = max(own, key=lambda r: r["created_at"])
        run_cases = {r["case"]["id"]: r for r in latest["cases"]}
        data["agents"].append({"id": agent_id, "title": title, "spec": spec.model_dump(),
            "analysis": api(f"/agents/{agent_id}/analysis"), "run": latest,
            "base_count": len(generated), "workflow_count": len(spec.probes), "knowledge_count": len(spec.knowledge_sources)})
        for c in generated:
            doc_case = c.source == "rag"
            p = f"sample_agents/{folder}/eval_agent.json"
            if doc_case:
                index = next(i for i, d in enumerate(adapter.manifest["knowledge"]) if "knowledge_" + d["id"] == c.id)
                origin = adapter.manifest["knowledge"][index]
                pointer = f"/knowledge/{index}"
                symbols = ["knowledge"] if folder == "langgraph_agent" else ["routed", "search", "finish"]
                conclusion = "Owner가 지식 문서에 작성한 question/reference_answer/content를 읽고 기준 답변·Context·문서 ID 계약을 구성합니다."
                caveat = "동일 질문의 Workflow Probe와 독립된 사례입니다. 문서 기반 계약에는 경로 요구가 없어 workflow_path를 자동 추천하지 않습니다."
            else:
                index = next(i for i, d in enumerate(adapter.manifest["probes"]) if "definition_" + d["id"] == c.id)
                origin = adapter.manifest["probes"][index]
                pointer = f"/probes/{index}"
                symbols, conclusion, caveat = MAPPING[origin["id"]]
            code_path = G if folder == "langgraph_agent" else L
            data["cases"].append({"agent_id": agent_id, "base": c.model_dump(), "current": current.get(c.id),
                "run": run_cases.get(c.id), "origin": origin, "pointer": pointer, "manifest": p,
                "snippets": [excerpt(code_path, s) for s in symbols], "manifest_snippet": manifest_excerpt(p, origin),
                "conclusion": conclusion, "caveat": caveat})
    assert len(data["cases"]) == 14
    data["pipeline_snippets"] = [excerpt("evaluation_platform/adapters/langgraph_adapter.py", "analyze"),
        excerpt("evaluation_platform/adapters/langflow_adapter.py", "analyze"), excerpt("evaluation_platform/adapters/base.py", "build_spec"),
        excerpt("evaluation_platform/dataset/generator.py", "recommend"), excerpt("evaluation_platform/dataset/generator.py", "generate")]
    flow = json.loads(SOURCES["sample_agents/langflow_agent/flow.json"])
    component_classes = {"Router": "SupportRouter", "Search": "SupportSearch", "Service": "SupportService", "Help": "SupportGeneral",
                         "AnswerRag": "SupportFinish", "AnswerTool": "SupportFinish", "AnswerGeneral": "SupportFinish"}
    for node in flow["data"]["nodes"]:
        if node["id"] in component_classes:
            exported_code = node["data"]["node"]["template"]["code"]["value"]
            assert excerpt(L, component_classes[node["id"]])["code"] in exported_code, node["id"]
    data["flow_source_match"] = {"matched_nodes": list(component_classes), "count": len(component_classes),
        "code_pointer": "/data/nodes/<index>/data/node/template/code/value"}
    reg = "evaluation_platform/evaluators/registry.py"
    symbols = {"tool_call": "tool_match", "workflow_path": "path_match", "rag_retrieval": "rag_recall",
               "runtime_reference": "runtime_match", "output_schema": "schema_match"}
    fn_dict = next(n.value for n in ast.walk(ast.parse(SOURCES[reg])) if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == "fns" for t in n.targets))
    fn_nodes = {k.value: v for k, v in zip(fn_dict.keys, fn_dict.values)}
    for evaluator_id, definition in data["rules"].items():
        if evaluator_id in symbols:
            snippets = [excerpt(reg, symbols[evaluator_id])]
        elif evaluator_id == "faithfulness":
            snippets = [excerpt("evaluation_platform/evaluators/custom_llm.py", "evaluate")]
        else:
            fn = fn_nodes[evaluator_id]
            snippets = [lines(reg, fn.lineno, fn.end_lineno, evaluator_id + " lambda")]
        definition["snippets"] = snippets
    data["flow_projection"] = {"note": "실제 flow.json의 ID·출력·연결을 투영한 구조 요약입니다. 전체 원문은 소스 부록에서 확인합니다.", "nodes": [{"pointer": f"/data/nodes/{i}", "id": n["id"],
        "outputs": [{"name": o["name"], "group_outputs": o.get("group_outputs", False)} for o in n["data"]["node"].get("outputs", [])]} for i, n in enumerate(flow["data"]["nodes"])],
        "edges": [{"pointer": f"/data/edges/{i}", "source": e["source"], "target": e["target"]} for i, e in enumerate(flow["data"]["edges"])]}
    snapshots = [
        ("hr-generation", "LangGraph · 데이터셋 생성 / Agent 구성", "실제 graph.get_graph()에서 얻은 5개 Node와 조건부 분기 3개를 UI에서 확인합니다. 운영 후보 수는 반복 데모 실행이 누적된 현재 Draft 수입니다."),
        ("hr-review", "LangGraph · 연차 조회 Workflow 후보", "balance_lookup Probe의 생성 근거와 Tool·경로 계약입니다. 오른쪽 Evaluator 열은 UI에서 가로 스크롤해 확인할 수 있습니다."),
        ("hr-contract", "LangGraph · 계약 편집", "expected.tool_calls, valid_paths, runtime_reference를 직접 확인합니다. 검토 상태나 평가 설정을 변경하지 않고 캡처했습니다."),
        ("hr-results", "LangGraph · Tool 결과와 미복구 실패", "연차 조회는 12일을 반환하고 관련 함수가 PASS입니다. 운영 복구 사례는 expected ok인데 실제 error라 HOLD입니다."),
        ("lf-generation", "LangFlow · Flow 분석 / Coverage", "실제 Flow JSON의 8개 Node, Router의 3개 분기와 ticket_status를 표시합니다."),
        ("lf-review", "LangFlow · 티켓 조회 Workflow 후보", "Router→Service 연결에 대응하는 Probe와 Tool 호출/경로 계약입니다."),
        ("lf-rag", "LangFlow · 지식 문서 후보", "password-reset 문서의 question/reference_answer에서 별도 RAG 사례가 생성됩니다."),
        ("lf-contract", "LangFlow · RAG 계약 편집", "참조 답변, reference_context와 document_ids를 함께 확인합니다."),
        ("lf-bindings", "LangFlow · Evaluator 체크 상태", "답변 근거 충실도(Faithfulness)는 Quality로 선택되어 있습니다. 선택된 Evaluator ID/Role 전체는 사례 상세 표에서도 확인할 수 있습니다."),
        ("lf-results", "LangFlow · 문서 기반 사례 결과", "Exact와 Recall@5는 1, 실제 Faithfulness LLM 점수는 0.9/PASS입니다. 모델이 영문으로 생성한 이유는 원문 그대로 보존합니다."),
    ]
    for key, _, _ in snapshots:
        assert (ROOT / "artifacts/explanation" / f"{key}.png").is_file(), key
    data["screenshots"] = [{"id": key, "title": title, "caption": caption,
        "src": image_data(ROOT / "artifacts/explanation" / f"{key}.png")} for key, title, caption in snapshots]
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    template = (ROOT / "scripts/explanation_template.html").read_text(encoding="utf-8")
    assert "__PAYLOAD__" in template
    script = (ROOT / "scripts/explanation_ui.js").read_text(encoding="utf-8")
    OUTPUT.write_text(template.replace("__PAYLOAD__", payload).replace("__SCRIPT__", script), encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "cases": len(data["cases"]), "screenshots": len(snapshots), "bytes": OUTPUT.stat().st_size,
                      "captured_at": now, "source_files": len(SOURCES)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
