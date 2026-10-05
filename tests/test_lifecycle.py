import hashlib
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from evaluation_platform.api.app import create_app
from evaluation_platform.models import JudgeDefinition, EvaluationBinding


def core_digest():
    digest=hashlib.sha256()
    for file in sorted(Path("evaluation_platform").rglob("*.py")):
        digest.update(file.read_bytes())
    return digest.hexdigest()


def test_review_snapshots_and_crud(platform):
    platform.generate("hr-langgraph")
    case=platform.candidates("hr-langgraph")[0]
    platform.save_case("hr-langgraph",case.id,{"review_status":"approved"})
    first=platform.golden("hr-langgraph")
    platform.save_case("hr-langgraph",case.id,{"input":"changed"})
    assert platform.candidates("hr-langgraph")[0].review_status == "pending"
    assert platform.store.get("golden",first["id"])["cases"][0]["input"] == case.input
    manual=platform.add_case("hr-langgraph",{"input":"안녕하세요", "expected":{"reference_output":"연차 규정 안내와 남은 연차 조회를 도와드릴 수 있습니다."}})
    platform.save_case("hr-langgraph",manual["id"],{"review_status":"excluded"})
    platform.generate("hr-langgraph")
    assert next(c for c in platform.candidates("hr-langgraph") if c.id==manual["id"]).review_status=="excluded"
    platform.delete_case("hr-langgraph",manual["id"])
    assert all(c.id!=manual["id"] for c in platform.candidates("hr-langgraph"))
    platform.save_case("hr-langgraph",case.id,{"input":case.input,"review_status":"approved"})
    assert platform.golden("hr-langgraph")["version"] == 2


def test_no_contract_or_unknown_evaluator_can_be_approved(platform):
    case=platform.add_case("hr-langgraph",{"input":"mystery"})
    with pytest.raises(ValueError, match="substantive"):
        platform.save_case("hr-langgraph",case["id"],{"review_status":"approved"})
    with pytest.raises(ValueError, match="unknown evaluator"):
        platform.save_case("hr-langgraph",case["id"],{"expected":{"reference_output":"truth"},"bindings":[{"evaluator_id":"missing"}],"review_status":"approved"})


def test_provenance_cannot_be_overwritten(platform):
    platform.generate("hr-langgraph")
    with pytest.raises(ValueError,match="Provenance"):
        platform.save_case("hr-langgraph",platform.candidates("hr-langgraph")[0].id,{"trace_id":"fabricated"})


def test_deleted_generated_case_does_not_return(platform):
    platform.generate("hr-langgraph")
    case_id=platform.candidates("hr-langgraph")[0].id
    platform.delete_case("hr-langgraph",case_id)
    platform.generate("hr-langgraph")
    assert all(c.id!=case_id for c in platform.candidates("hr-langgraph"))


def test_two_custom_judges_and_frozen_definitions(platform):
    platform.generate("hr-langgraph")
    case=platform.candidates("hr-langgraph")[0]
    for name in ("First", "Second"):
        d=JudgeDefinition(name=name,criteria="Answer must fulfill the business rubric.")
        preview=platform.preview_judge(d.model_dump(),case.model_dump(),"sample answer")
        platform.register_judge(d.model_dump(),preview["id"])
        case.bindings.append(EvaluationBinding(evaluator_id=d.id,role="quality"))
    platform.save_case("hr-langgraph",case.id,{"bindings":[b.model_dump() if hasattr(b,'model_dump') else b for b in case.bindings],"review_status":"approved"})
    golden=platform.golden("hr-langgraph")
    run=platform.run(golden["id"])
    ids={e["evaluator_id"] for e in run["cases"][0]["evaluators"]}
    assert all(d["id"] in ids for d in golden["evaluators"])
    original=golden["evaluators"][0]
    revised={**original,"criteria":"A revised rubric","version":2,"active":False}
    preview=platform.preview_judge(revised,case.model_dump(),"sample")
    platform.register_judge(revised,preview["id"])
    rerun=platform.run(golden["id"])
    assert next(e for e in rerun["evaluator_definitions"] if e["id"]==original["id"])["version"] == 1


def test_judge_preview_definition_must_match(platform):
    platform.generate("hr-langgraph")
    d=JudgeDefinition(name="test",criteria="first rubric")
    preview=platform.preview_judge(d.model_dump(),platform.candidates("hr-langgraph")[0].model_dump(),"answer")
    with pytest.raises(ValueError,match="exact definition"):
        platform.register_judge({**d.model_dump(),"criteria":"different rubric"},preview["id"])


@pytest.mark.parametrize("path,agent_id",[("sample_agents/langgraph_agent","hr-langgraph"),("sample_agents/langflow_agent","support-langflow"),("sample_agents/third_test_agent","commerce-third")])
def test_actual_framework_full_pipeline_without_core_edit(platform,path,agent_id):
    before=core_digest()
    platform.register(path)
    platform.generate(agent_id)
    cases=platform.candidates(agent_id)
    assert {"workflow","rag"} <= {c.source for c in cases}
    for case in cases:
        platform.save_case(agent_id,case.id,{"review_status":"approved"})
    golden=platform.golden(agent_id)
    run=platform.run(golden["id"],"registration")
    assert run["passed"], [(row["case"]["id"],row["actual"],row["evaluators"]) for row in run["cases"] if not row["passed"]]
    assert before==core_digest()
    coverage=platform.analysis(agent_id)["reviewed_coverage"]
    assert all(r["percent"]==100 for r in coverage if r["dimension"] in ("feature","workflow","branch","tool","rag"))


def test_api_crud_and_origin_guard(platform):
    with TestClient(create_app(platform)) as client:
        assert client.get("/").status_code==200
        assert client.post("/api/agents",json={"path":"sample_agents/third_test_agent"},headers={"Origin":"https://malicious.invalid"}).status_code==403
        assert client.post("/api/agents/hr-langgraph/generate").status_code==200
        cases=client.get("/api/agents/hr-langgraph/cases").json()
        assert client.patch(f"/api/agents/hr-langgraph/cases/{cases[0]['id']}",json={"review_status":"approved"}).status_code==200
        golden=client.post("/api/agents/hr-langgraph/golden",json={}).json()
        result=client.post("/api/runs",json={"dataset_id":golden["id"]}).json()
        assert result["decision"]=="PASS"
        assert client.get("/api/agents/not-registered/cases").status_code==404
