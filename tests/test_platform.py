from unittest.mock import patch
from backend.adapters import clean, PhoenixHTTP
from backend.db import engine
from backend.experiments import process_one
from backend.metrics import extract


def setup(c):
    st = c.get("/api/state").json()
    v = st["datasets"][0]["versions"][0]["id"]
    cases = c.get("/api/versions/" + v + "/cases").json()
    return v, cases, st["mappings"]


def submit(c, v, ms, mode="historical", key="job"):
    r = c.post(
        "/api/experiments",
        json=dict(
            version=v,
            mode=mode,
            name="실험",
            selection=[m["id"] for m in ms],
            environment="STG",
            request_id=key,
        ),
    )
    assert r.status_code == 200, r.text
    return r.json()


def drain():
    while process_one():
        pass


def get(c, e):
    return c.get("/api/experiments/" + e).json()


def test_import_and_immutable_edits(client):
    v, cases, _ = setup(client)
    assert len(cases) == 20 and len({x["case_id"] for x in cases}) == 20
    assert len(cases[1]["record"]["trace"]["spans"]) == 2
    assert cases[-1]["data"]["warnings"]
    assert client.post(
        "/api/imports", json={"source": "policy", "version": "fixture-v1"}
    ).json() == {"version": v, "duplicate": True}
    url = "/api/versions/" + v + "/cases/" + cases[0]["case_id"]
    new = client.patch(url, json={"expected_output": "새 버전"}).json()["version"]
    after = client.get("/api/versions/" + new + "/cases").json()[0]
    assert (
        after["case_id"] == cases[0]["case_id"]
        and after["execution"] == cases[0]["execution"]
    )
    assert client.patch(url, json={"expected_output": "old"}).status_code == 409
    assert (
        client.get("/api/versions/" + v + "/cases").json()[0]["data"]["expected_output"]
        != "새 버전"
    )


def test_selectors_and_missing_values(client):
    v, cs, ms = setup(client)
    rule = {
        "selector": {"kind": "RETRIEVER", "attributes": {"operation": "search"}},
        "path": "/attributes/documents",
        "policy": "first",
    }
    for x in cs[1:3]:
        val, path, warn = extract(x["record"], rule)
        assert val == x["record"]["retrieval_context"] and path.startswith(
            "/trace/spans/1"
        )
    body = dict(
        version=v,
        sample=cs[0]["id"],
        spec={"metric": "faith", "name": "근거성"},
        rules={
            "input": {"path": "/input/text"},
            "actual_output": {"path": "/actual_output/text"},
            "retrieval_context": rule,
        },
    )
    detail = client.post("/api/mapping/validate", json=body).json()
    assert detail["total"] == 20 and detail["valid"] == 15
    result = client.post("/api/mapping/test", json=body).json()
    assert result["status"] == "NOT_EVALUABLE" and result["score"] is None
    body["sample"] = cs[1]["id"]
    assert client.post("/api/mapping/test", json=body).json()["status"] == "NOT_RUN"
    assert client.post("/api/mapping/publish", json=body).is_success


def test_historical_engines_and_published_versions(client):
    v, cs, ms = setup(client)
    with patch("backend.experiments.HTTPAgent.run") as runner:
        e = submit(client, v, ms)["id"]
        assert submit(client, v, ms)["id"] == e
        drain()
        runner.assert_not_called()
    old = get(client, e)
    assert old["status"] == "DONE" and old["summary"]["scored"] == 40
    assert old["summary"]["statuses"] == {"PASSED": 36, "FAILED": 4}
    assert all(x["execution"] for x in old["cases"])
    m = ms[0]
    b = dict(
        version=v,
        sample=cs[1]["id"],
        family=m["definition"]["family"],
        spec=m["definition"]["spec"],
        rules={**m["rules"], "expected_output": {"fixed": "different"}},
    )
    new = client.post("/api/mapping/publish", json=b).json()["mapping"]
    assert new != m["id"] and get(client, e) == old
    other = submit(client, v, [{"id": new}], key="new")["id"]
    assert client.get("/api/compare", params={"a": e, "b": other}).status_code == 409


def test_http_ab_and_regressions(client, agent_url):
    v, cs, ms = setup(client)
    r = submit(client, v, ms[:1], "ab")
    drain()
    pair = client.get("/api/compare", params={"a": r["baseline"], "b": r["id"]}).json()
    assert len(pair["pairs"]) == 20 and pair["counts"]["regression"] == 2
    assert pair["pairs"][0]["label"] == "regression"
    for p in pair["pairs"]:
        assert p["a"]["case_id"] == p["b"]["case_id"]
        assert p["a"]["execution"] != p["b"]["execution"]
        assert (
            p["a"]["record"]["trace"]["trace_id"]
            != p["b"]["record"]["trace"]["trace_id"]
        )
    assert get(client, r["id"])["environment"] == "STG"


def test_worker_retry_cancel_and_restart(client, agent_url):
    from backend import schema_v1 as s

    v, cs, ms = setup(client)
    e = submit(client, v, ms[:1], "single")["id"]
    with patch("backend.experiments.HTTPAgent.run", side_effect=TimeoutError):
        assert process_one()
    drain()
    result = get(client, e)
    assert result["status"] == "PARTIAL" and result["summary"]["scored"] == 19
    j = next(x for x in result["cases"] if x["error"])
    assert (
        client.post(f"/api/experiments/{e}/retry?job=" + j["id"]).json()["affected"]
        == 1
    )
    with engine.begin() as c:
        c.execute(
            s.jobs.update()
            .where(s.jobs.c.id == j["id"])
            .values(status="RUNNING", lease="2000", owner="offline")
        )
    drain()
    assert get(client, e)["status"] == "DONE"
    e = submit(client, v, ms[:1], key="cancel")["id"]
    assert client.post("/api/experiments/" + e + "/cancel").json()["affected"] == 20
    assert get(client, e)["status"] == "CANCELLED"


def test_permissions_and_real_prd_block(client, monkeypatch):
    v, cs, ms = setup(client)
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("GAIA_API_KEY", "unit-editor")
    monkeypatch.setenv("GAIA_READ_KEY", "unit-reader")
    monkeypatch.setenv("AGENT_MODE", "real")
    assert client.get("/api/versions/" + v + "/cases").status_code == 401
    client.headers["Authorization"] = "Bearer unit-reader"
    assert client.get("/api/state").status_code == 200
    assert client.post("/api/imports", json={}).status_code == 403
    client.headers["Authorization"] = "Bearer unit-editor"
    payload = dict(
        version=v,
        mode="single",
        environment="PRD",
        name="blocked",
        selection=[ms[0]["id"]],
        request_id="blocked",
    )
    assert client.post("/api/experiments", json=payload).status_code == 403
    assert (
        clean({"metadata": {"api_key": "example"}})["metadata"]["api_key"] == "[마스킹]"
    )


def test_phoenix_rest_contract(monkeypatch):
    client = PhoenixHTTP()

    def get(path, **params):
        if path == "datasets/d/versions":
            return {"data": [{"version_id": "v"}]}
        if path == "datasets/d/examples":
            assert params["version_id"] == "v"
            return {
                "data": {
                    "examples": [
                        {
                            "id": "item",
                            "input": {"text": "q"},
                            "metadata": {"span_id": "child"},
                        }
                    ]
                }
            }
        assert path == "projects/default/spans"
        return {
            "data": [
                {"context": {"span_id": "child", "trace_id": "t"}},
                {"context": {"span_id": "root", "trace_id": "t"}},
            ]
        }

    monkeypatch.setattr(client, "get", get)
    assert client.versions("d")[0]["id"] == "v"
    item = client.load("d", "v")[0]
    assert len(item["spans"]) == 2 and item["metadata"]["trace_id"] == "t"


def test_reuse_single_run_without_agent(client, agent_url):
    v, cs, ms = setup(client)
    first = submit(client, v, ms[:1], "single")["id"]
    drain()
    ids = {j["case_id"]: j["execution"] for j in get(client, first)["cases"]}
    with patch("backend.experiments.HTTPAgent.run") as runner:
        payload = dict(
            version=v,
            mode="historical",
            name="reuse",
            selection=[ms[1]["id"]],
            request_id="reuse",
            baseline=first,
        )
        new = client.post("/api/experiments", json=payload).json()["id"]
        drain()
        runner.assert_not_called()
    assert {j["case_id"]: j["execution"] for j in get(client, new)["cases"]} == ids


def test_openinference_raw_normalization():
    from backend.datasets import convert

    data, rec = convert(
        "d",
        {
            "id": "i",
            "input": {"image": {"mime": "image/png"}},
            "output": {"text": "dataset"},
            "spans": [
                {"context": {"span_id": "r"}, "attributes": {"output.value": "actual"}},
                {
                    "context": {"span_id": "s"},
                    "parent_id": "r",
                    "attributes": {
                        "retrieval.documents": [
                            {"document.content": "chunk", "document.id": "d"}
                        ]
                    },
                },
                {
                    "context": {"span_id": "t"},
                    "parent_id": "r",
                    "attributes": {
                        "tool.name": "search",
                        "tool.parameters": '{"limit":3}',
                    },
                },
            ],
        },
    )
    assert (
        rec["actual_output"]["text"] == "actual" and rec["trace"]["root_span_id"] == "r"
    )
    assert rec["retrieval_context"][0]["content"] == "chunk" and rec["tools_called"][0][
        "arguments"
    ] == {"limit": 3}
    assert rec["original_item"]["output"] == {"text": "dataset"}


def test_deepeval_relevancy_with_stub_judge(monkeypatch):
    from backend.metrics import run_metric
    from backend.judge import StructuredJudge

    async def stub(self, prompt, schema=None):
        responses = {
            "Statements": {"statements": ["policy"]},
            "Verdicts": {"verdicts": [{"verdict": "yes"}]},
            "Reason": {"reason": "관련성 확인"},
        }
        return schema.model_validate(responses[schema.__name__])

    monkeypatch.setattr(StructuredJudge, "a_generate", stub)
    score, reason = run_metric(
        "relevancy",
        {"input": "policy?", "actual_output": "policy"},
        {"model": "stub", "threshold": 0.5},
    )
    assert score == 1 and reason == "관련성 확인"


def test_custom_judge_schema_and_unknown_variables(monkeypatch):
    import httpx
    from backend.metrics import evaluate

    monkeypatch.setenv("DEMO_MODE", "false")
    for key in ("JUDGE_MODEL", "JUDGE_KEY", "JUDGE_URL"):
        monkeypatch.setenv(key, "unit-test")
    spec = dict(
        metric="judge",
        threshold=0.5,
        prompt="{{input}} {{criteria}}",
        rubric="test",
        score_type="category",
        categories={"good": 0.9},
    )
    rules = {"input": {"fixed": "q"}, "actual_output": {"fixed": "a"}}
    assert evaluate({}, spec, rules)["status"] == "NOT_EVALUABLE"
    rules["criteria"] = {"fixed": "accuracy"}
    response = httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": '{"score":"good","reason":"aligned"}'}}]
        },
        request=httpx.Request("POST", "https://fixture.invalid"),
    )
    with patch("backend.metrics.httpx.post", return_value=response):
        result = evaluate({}, spec, rules)
    assert result["status"] == "PASSED" and result["score"] == 0.9
