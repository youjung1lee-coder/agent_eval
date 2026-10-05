import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from threading import RLock
from evaluation_platform.adapters import load_adapter
from evaluation_platform.models import AgentSpec, AgentResult, EvaluationCase, JudgeDefinition, EvaluationBinding
from evaluation_platform.connectors.runtime import RuntimeContext
from evaluation_platform.connectors.phoenix import PhoenixConnector
from evaluation_platform.storage import Store
from evaluation_platform.dataset.generator import generate, recommend, scenario
from evaluation_platform.coverage import coverage
from evaluation_platform.evaluators import platform_registry
from evaluation_platform.evaluators.custom_llm import CustomLLMEvaluator
from evaluation_platform.evaluators.llm_judge import JudgeBackend, judge_trace
from evaluation_platform.runner.runner import run_evaluation


def definition_hash(definition):
    return hashlib.sha256(json.dumps(definition.model_dump(), sort_keys=True).encode()).hexdigest()


class Platform:
    def __init__(self, data_dir="data", phoenix=None, judge=None):
        self.store = Store(Path(data_dir) / "platform.sqlite")
        self.phoenix = phoenix or PhoenixConnector()
        self.judge = judge or JudgeBackend()
        self.lock = RLock()

    def registry(self, definitions=None):
        return platform_registry(self.store.list("judges") if definitions is None else definitions, self.judge)

    def register(self, path):
        adapter = load_adapter(path)
        spec = adapter.analyze()
        with self.store.transaction() as db:
            record = {"path": str(Path(path).resolve()), "spec": spec.model_dump(), "fingerprint": spec.fingerprint()}
            self.store.put("agents", spec.agent_id, record, db)
            self.audit("register", spec.agent_id, db)
        return record

    def agent(self, agent_id):
        record = self.store.get("agents", agent_id)
        return AgentSpec.model_validate(record["spec"]), load_adapter(record["path"])

    def execute(self, agent_id, question, project="prd", run_id=None):
        spec, adapter = self.agent(agent_id)
        if adapter.source_digest() != spec.metadata["source_digest"]:
            raise ValueError("Agent repository changed; re-register to record the new version before execution")
        trace = self.phoenix.session(project)
        with trace.span("agent.execute", "AGENT", {"gaia.agent_id": agent_id, "gaia.root": True,
                "gaia.run_id": run_id or "", "input.value": question}, root=True) as span:
            context = RuntimeContext(spec, trace)
            start = time.perf_counter()
            try:
                result = adapter.execute(question, context)
            except Exception as exc:
                span.record_exception(exc)
                result = AgentResult(status="timeout" if isinstance(exc, TimeoutError) else "exception", error=str(exc))
            result.latency_ms = (time.perf_counter() - start) * 1000
            result.trace_id, result.span_id = trace.identify(span)
            trace.finish(span, result)
        # Observations can be inspected locally; candidate generation queries Phoenix itself.
        self.store.put("executions", result.span_id, {"agent_id": agent_id, "project": project, "input": question, "result": result.model_dump()})
        return result

    def candidates(self, agent_id):
        try:
            return [EvaluationCase.model_validate(c) for c in self.store.get("drafts", agent_id)["cases"]]
        except KeyError:
            self.store.get("agents", agent_id)
            return []

    def generate(self, agent_id):
        spec, _ = self.agent(agent_id)
        production = self.phoenix.production(agent_id)
        created = generate(spec, production)
        with self.lock, self.store.transaction() as db:
            try:
                previous = self.store.get("drafts", agent_id, db)
                old = previous["cases"]
                deleted_ids = set(previous.get("deleted_ids", []))
            except KeyError:
                old = []
                deleted_ids = set()
            by_id = {c["id"]: c for c in old}
            # Idempotent regeneration preserves owner edits and exclusions.
            for case in created:
                if case.id not in deleted_ids:
                    by_id.setdefault(case.id, case.model_dump())
            self.store.put("drafts", agent_id, {"cases": list(by_id.values()), "deleted_ids": sorted(deleted_ids)}, db)
            self.audit("generate", agent_id, db)
        return self.analysis(agent_id)

    def analysis(self, agent_id):
        spec, _ = self.agent(agent_id)
        cases = self.candidates(agent_id)
        prod = [c for c in cases if c.source == "production_trace"]
        counts = {source: sum(c.source == source for c in cases) for source in
                  ("workflow", "rag", "production_trace", "phoenix_failure_candidate", "owner_manual")}
        return {"spec": spec.model_dump(), "counts": counts,
                "failure_types": sorted({c.failure_type for c in cases if c.failure_type}),
                "candidate_coverage": coverage(spec, [c for c in cases if c.review_status != "excluded"], prod, cases),
                "reviewed_coverage": coverage(spec, [c for c in cases if c.review_status == "approved"], prod, cases),
                "production_trace_count": len(prod), "phoenix": self.phoenix.health()}

    def audit(self, action, target, db):
        key = uuid4().hex
        self.store.put("audit", key, {"id": key, "action": action, "target": target,
                       "owner": "local-poc-owner", "time": datetime.now(timezone.utc).isoformat()}, db)

    def validate_case(self, case, registry=None):
        if not case.expected.substantive():
            raise ValueError("Owner must provide a substantive expected contract before approval")
        registry = registry or self.registry()
        if not case.bindings:
            case.bindings = recommend(case.expected)
        for binding in case.bindings:
            registry.resolve(binding.evaluator_id)
        if not any(b.applies(case) for b in case.bindings):
            raise ValueError("No evaluator binding applies to this case")

    def save_case(self, agent_id, case_id, update):
        with self.lock, self.store.transaction() as db:
            draft = self.store.get("drafts", agent_id, db)
            current = next((c for c in draft["cases"] if c["id"] == case_id), None)
            if current is None:
                raise KeyError(case_id)
            allowed = {"input", "expected", "bindings", "review_status", "capability", "evaluation_areas", "targets", "input_variations"}
            if set(update) - allowed:
                raise ValueError("Provenance fields and IDs are immutable")
            revised = EvaluationCase.model_validate({**current, **update})
            # Editing an approved case requires fresh approval unless explicitly reviewed in same operation.
            if current["review_status"] == "approved" and set(update) - {"review_status"} and "review_status" not in update:
                revised.review_status = "pending"
            revised.scenario_id = scenario(revised.input)
            if revised.review_status == "approved":
                self.validate_case(revised, self.registry(self.store.list("judges", db)))
            draft["cases"] = [revised.model_dump() if c["id"] == case_id else c for c in draft["cases"]]
            self.store.put("drafts", agent_id, draft, db)
            self.audit("review_edit", case_id, db)
        return revised.model_dump()

    def add_case(self, agent_id, data):
        case = EvaluationCase.model_validate({**data, "source": "owner_manual", "sources": ["owner_manual"],
                  "evidence": ["Explicit local owner input"], "review_status": "pending"})
        case.scenario_id = scenario(case.input)
        if not case.bindings:
            case.bindings = recommend(case.expected)
        with self.lock, self.store.transaction() as db:
            self.store.get("agents", agent_id, db)
            try:
                draft = self.store.get("drafts", agent_id, db)
            except KeyError:
                draft = {"cases": []}
            if any(c["id"] == case.id for c in draft["cases"]):
                raise ValueError("case ID already exists")
            draft["cases"].append(case.model_dump())
            self.store.put("drafts", agent_id, draft, db)
            self.audit("owner_add", case.id, db)
        return case.model_dump()

    def delete_case(self, agent_id, case_id):
        with self.lock, self.store.transaction() as db:
            draft = self.store.get("drafts", agent_id, db)
            if not any(c["id"] == case_id for c in draft["cases"]):
                raise KeyError(case_id)
            draft["cases"] = [c for c in draft["cases"] if c["id"] != case_id]
            draft["deleted_ids"] = sorted(set(draft.get("deleted_ids", [])) | {case_id})
            self.store.put("drafts", agent_id, draft, db)
            self.audit("delete_case", case_id, db)

    def golden(self, agent_id, bindings=()):
        with self.lock, self.store.transaction() as db:
            spec = AgentSpec.model_validate(self.store.get("agents", agent_id, db)["spec"])
            cases = [EvaluationCase.model_validate(c) for c in self.store.get("drafts", agent_id, db)["cases"] if c["review_status"] == "approved"]
            if not cases:
                raise ValueError("Approve at least one case")
            definitions = self.store.list("judges", db)
            registry = self.registry(definitions)
            for case in cases:
                self.validate_case(case, registry)
            dataset_bindings = [EvaluationBinding.model_validate(b) for b in bindings]
            for binding in dataset_bindings:
                registry.resolve(binding.evaluator_id)
            versions = [g["version"] for g in self.store.list("golden", db) if g["agent_id"] == agent_id]
            golden = {"id": uuid4().hex, "agent_id": agent_id, "version": max(versions, default=0) + 1,
                      "cases": [c.model_dump() for c in cases], "bindings": [b.model_dump() for b in dataset_bindings],
                      "evaluators": definitions, "agent_fingerprint": spec.fingerprint(),
                      "created_at": datetime.now(timezone.utc).isoformat()}
            self.store.put("golden", golden["id"], golden, db, immutable=True)
            self.audit("golden_finalize", golden["id"], db)
        return golden

    def preview_judge(self, definition, case, answer):
        definition = JudgeDefinition.model_validate(definition)
        case = EvaluationCase.model_validate(case)
        trace = self.phoenix.session("evaluate")
        token = judge_trace.set(trace)
        try:
            with trace.span("evaluator.sample", "CHAIN", {"input.value": case.input}, root=True) as span:
                result = CustomLLMEvaluator(definition.model_copy(update={"active": True}), self.judge).evaluate(case, AgentResult(output=answer))
                span.set_attribute("output.value", result.model_dump_json())
        finally:
            judge_trace.reset(token)
        preview = {"id": uuid4().hex, "definition_hash": definition_hash(definition), "definition": definition.model_dump(),
                   "sample_input": case.input, "sample_answer": answer, "result": result.model_dump()}
        self.store.put("previews", preview["id"], preview)
        return preview

    def register_judge(self, definition, preview_id):
        definition = JudgeDefinition.model_validate(definition)
        preview = self.store.get("previews", preview_id)
        if preview["definition_hash"] != definition_hash(definition) or preview["result"].get("error"):
            raise ValueError("Run a successful sample evaluation with this exact definition first")
        if definition.id in platform_registry(backend=self.judge).evaluators:
            raise ValueError("Cannot replace platform evaluator")
        with self.store.transaction() as db:
            try:
                prior = self.store.get("judges", definition.id, db)
                if definition.version != prior["version"] + 1:
                    raise ValueError("Updated judge version must increment by one")
            except KeyError:
                if definition.version != 1:
                    raise ValueError("New judge version must be 1")
            self.store.put("judges", definition.id, definition.model_dump(), db)
            self.audit("register_judge", definition.id, db)
        return definition.model_dump()

    def run(self, dataset_id, kind="regression", dependency_ids=None):
        golden = self.store.get("golden", dataset_id)
        spec, _ = self.agent(golden["agent_id"])
        registry = self.registry(golden["evaluators"])
        trace = self.phoenix.session("evaluate")
        token = judge_trace.set(trace)
        try:
            with trace.span("evaluation.run", "CHAIN", {"gaia.dataset_id": dataset_id, "gaia.agent_id": spec.agent_id}, root=True) as span:
                result = run_evaluation(golden, lambda q, rid: self.execute(spec.agent_id, q, "evaluate", rid),
                                        registry, spec, kind, dependency_ids, trace)
                span.set_attribute("gaia.run_id", result["id"])
                span.set_attribute("output.value", json.dumps({"decision": result["decision"], "quality_score": result["overall_score"]}))
        finally:
            judge_trace.reset(token)
        self.store.put("runs", result["id"], result, immutable=True)
        return result
