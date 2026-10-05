import hashlib
import os
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from phoenix.client import Client
from evaluation_platform.api.app import create_app
from evaluation_platform.service import Platform
from evaluation_platform.models import JudgeDefinition

pytestmark = [pytest.mark.real_e2e, pytest.mark.skipif(os.getenv("EVAL_REAL_E2E") != "1", reason="Set EVAL_REAL_E2E=1 with Phoenix running and judge downloaded")]


def wait_for(predicate):
    for _ in range(60):
        value=predicate()
        if value:
            return value
        time.sleep(.2)
    raise AssertionError("Phoenix ingestion did not complete within 12 seconds")


def test_phoenix_failure_to_golden_and_two_real_custom_judges(tmp_path):
    p=Platform(tmp_path)
    assert p.phoenix.health()["status"]=="connected"
    with TestClient(create_app(p)) as api:
        assert api.post("/api/agents",json={"path":"sample_agents/langgraph_agent"}).status_code==201
        normal=api.post("/api/agents/hr-langgraph/execute",json={"input":"What is the leave policy?"}).json()
        failure=api.post("/api/agents/hr-langgraph/execute",json={"input":"balance error"}).json()
        timeout=api.post("/api/agents/hr-langgraph/execute",json={"input":"balance timeout"}).json()
        empty=api.post("/api/agents/hr-langgraph/execute",json={"input":"knowledge missing"}).json()
        assert normal["status"]=="ok" and failure["status"]=="error" and timeout["status"]=="timeout"
        assert empty["retrieval_attempted"] and not empty["documents"]
        ids={r["span_id"] for r in (normal,failure,timeout,empty)}
        wait_for(lambda: ids <= {t["result"]["span_id"] for t in p.phoenix.production("hr-langgraph")})
        summary=api.post("/api/agents/hr-langgraph/generate").json()
        assert {"tool_failure","timeout","empty_retrieval"} <= set(summary["failure_types"])
        cases=api.get("/api/agents/hr-langgraph/cases").json()
        candidate=next(c for c in cases if c["span_id"]==failure["span_id"] and c["failure_type"]=="tool_failure")
        assert candidate["candidate_reason"] and candidate["trace_id"]==failure["trace_id"]
        assert api.patch(f"/api/agents/hr-langgraph/cases/{candidate['id']}",json={"review_status":"approved"}).status_code==422
        # The owner defines desired recovery; unchanged broken tool must fail regression.
        response=api.patch(f"/api/agents/hr-langgraph/cases/{candidate['id']}",json={"expected":{"expected_status":"ok","required_output":["Available leave"]},"review_status":"approved"})
        assert response.status_code==200,response.text
        excluded=next(c for c in cases if c["span_id"]==failure["span_id"] and c["source"]=="production_trace")
        assert api.patch(f"/api/agents/hr-langgraph/cases/{excluded['id']}",json={"review_status":"excluded"}).status_code==200
        normal_case=next(c for c in cases if c["id"]=="definition_hr-policy")
        bindings=normal_case["bindings"]
        runner_hash=hashlib.sha256(Path("evaluation_platform/runner/runner.py").read_bytes()).hexdigest()
        judge_results=[]
        for name,criteria in [("HR required information","The answer must mention applying at least 3 days in advance, the HR portal, and a manager approval document."),
                              ("HR application channel","The answer must mention the HR portal as the application method.")]:
            d=JudgeDefinition(name=name,criteria=criteria,pass_threshold=.8)
            sample=api.post("/api/evaluators/preview",json={"definition":d.model_dump(),"case":normal_case,"answer":normal["output"]})
            assert sample.status_code==200,sample.text
            sample=sample.json()
            assert sample["result"]["details"]["backend"]=="local" and sample["result"]["reason"]
            judge_results.append(sample["result"])
            assert api.post("/api/evaluators",json={"definition":d.model_dump(),"preview_id":sample["id"]}).status_code==201
            bindings.append({"evaluator_id":d.id,"role":"quality"})
        assert api.patch("/api/agents/hr-langgraph/cases/definition_hr-policy",json={"bindings":bindings,"review_status":"approved"}).status_code==200
        manual=api.post("/api/agents/hr-langgraph/cases",json={"input":"Hello","expected":{"reference_output":"I can help with leave policy and leave balance."}}).json()
        assert api.patch(f"/api/agents/hr-langgraph/cases/{manual['id']}",json={"review_status":"approved"}).status_code==200
        golden=api.post("/api/agents/hr-langgraph/golden",json={}).json()
        assert any(c["trace_id"]==failure["trace_id"] for c in golden["cases"])
        result=api.post("/api/runs",json={"dataset_id":golden["id"],"kind":"regression"})
        assert result.status_code==201,result.text
        result=result.json()
        assert result["decision"]=="HOLD" and not result["gate_passed"]
        failed=next(row for row in result["cases"] if row["case"]["id"]==candidate["id"])
        assert failed["case"]["trace_id"]==failure["trace_id"] and not failed["passed"]
        evaluated=next(row for row in result["cases"] if row["case"]["id"]==normal_case["id"])
        assert sum(e["evaluator_id"].startswith("owner_") for e in evaluated["evaluators"])==2
        assert all(e["reason"] and e["details"]["raw_response"] for e in evaluated["evaluators"] if e["evaluator_id"].startswith("owner_"))
        assert runner_hash==hashlib.sha256(Path("evaluation_platform/runner/runner.py").read_bytes()).hexdigest()
        client=Client(base_url=p.phoenix.base_url)
        eval_spans=wait_for(lambda:client.spans.get_spans(project_identifier="evaluate",limit=1000))
        prd_spans=client.spans.get_spans(project_identifier="prd",limit=1000)
        prd_ids={s["context"]["trace_id"] for s in prd_spans}
        eval_ids={s["context"]["trace_id"] for s in eval_spans}
        assert not prd_ids & eval_ids
        assert any(s["name"]=="judge.inference" for s in eval_spans)
        assert any(s["status_code"]=="ERROR" and s["context"]["trace_id"]==failure["trace_id"] for s in prd_spans)
        assert not any(row["actual"]["trace_id"] in prd_ids for row in result["cases"])
    p.phoenix.close()


def test_real_judge_positive_and_negative_rubric(tmp_path):
    p=Platform(tmp_path)
    d=JudgeDefinition(name="Portal rubric",criteria="The answer must mention the HR portal.",pass_threshold=.8)
    case={"input":"How do I apply?","source":"owner_manual"}
    yes=p.preview_judge(d.model_dump(),case,"Use the HR portal.")["result"]
    no=p.preview_judge(d.model_dump(),case,"I do not know.")["result"]
    assert yes["passed"] and not no["passed"]
    assert yes["score"]>no["score"]
    p.phoenix.close()


@pytest.mark.parametrize("path,agent_id", [("sample_agents/langgraph_agent","hr-langgraph"),
    ("sample_agents/langflow_agent","support-langflow"),("sample_agents/third_test_agent","commerce-third")])
def test_all_agents_real_pipeline(tmp_path,path,agent_id):
    import json
    from tests.test_lifecycle import core_digest
    before=core_digest()
    p=Platform(tmp_path)
    p.register(path)
    analysis=p.generate(agent_id)
    for case in p.candidates(agent_id):
        if case.source in ("workflow","rag"):
            p.save_case(agent_id,case.id,{"review_status":"approved"})
    golden=p.golden(agent_id)
    result=p.run(golden["id"],"registration")
    assert result["passed"], [(r["case"]["id"], r["actual"],r["evaluators"]) for r in result["cases"] if not r["passed"]]
    assert before==core_digest()
    artifact=Path("artifacts/e2e")
    artifact.mkdir(parents=True,exist_ok=True)
    (artifact/(agent_id+".json")).write_text(json.dumps({"agent_id":agent_id,"framework":analysis["spec"]["framework"],
        "cases":len(result["cases"]),"decision":result["decision"],"quality_score":result["overall_score"],
        "candidate_counts":analysis["counts"],"coverage":p.analysis(agent_id)["reviewed_coverage"],
        "core_sha256_before":before,"core_sha256_after":core_digest()},indent=2),encoding="utf-8")
    p.phoenix.close()
