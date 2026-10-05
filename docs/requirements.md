# Implementation decisions before coding

Baseline: `에이전트_성능평가_v1.md`, preserved verbatim. The request adds an executable closed loop, three agents, real Phoenix and custom LLM judges.

1. **Requirements:** registration, regression and platform-quality runs share reviewed/versioned datasets. Production incidents improve candidates, never auto-approve. Gates override quality averages.
2. **Lifecycle:** repository → trusted adapter → AgentSpec → discovery → candidates → coverage → owner review → immutable golden version → registry → runner → persisted results. Production → Phoenix `prd` → observed failure → review → regression.
3. **Components:** FastAPI + local HTML/JS UI, SQLite repository, two framework adapters, pluggable runtime/knowledge/tool/trace/judge interfaces, analyzer, generator, detector, coverage, registry, runner.
4. **Models:** AgentSpec with versioned capability inventory and probes; ExpectedContract; candidate provenance and confidence; evaluator bindings separate from test content; golden snapshots; result with runtime/evaluator/model versions and gate/quality decisions.
5. **Generation:** agent-definition probes with evidence; knowledge questions with references; actual Phoenix production spans; observed failure reasons; owner manual. No fabricated expected output for production responses. Exact normalized inputs form scenario groups, with variations retained; semantic clustering deferred.
6. **Evaluators:** deterministic contracts first (tools/arguments/order, paths, permissions, schema, runtime tool reference, latency/errors); lexical similarity explicitly auxiliary. Real local CPU LLM judge by default, optional OpenAI-compatible backend. Custom Python registration is trusted developer plugin only, never UI code execution.
7. **UI:** generation/inventory/coverage; editable/filterable review with lineage and evaluator selection; custom judge sample-before-registration; golden version selector and runs with case-level diagnosis.
8. **Scope:** executable actual LangGraph, LangFlow JSON via official LFX engine, a structurally different third agent; Phoenix server/export/query; failure and two custom-judge E2Es; CLI, API, browser tests; GitHub branch/PR.
9. **Excluded:** real enterprise auth/MyAccess, Jenkins deployment, proprietary A2A implementation, real S3/OpenSearch/Milvus, distributed job scheduling, semantic production clustering and calibrated production-grade local judge accuracy. Interfaces and gaps documented.
10. **Assumptions:** repository layout and metadata are a PoC integration contract, not GAIA facts. Isolate manifest discovery, graph/flow mapping and runtime import in adapters; knowledge/tool in connectors; Phoenix attributes in trace connector. Core consumes only normalized models.

## Reconciliation with baseline

The prompt's “RAG source” is the UI label for **Knowledge Source**; RAG is a capability, not an information source. Phoenix is an Execution Trace connector. Preserve scenario/variation, confidence, permissions, forbidden behavior, runtime references and gate/quality from the baseline. Deployment is a HOLD/PASS decision recorded locally, not actual Jenkins deployment. Three run kinds record registration/regression/platform-quality intent. Impact-based selection uses case dependency IDs; automatic code diff impact inference is deferred. Exact input clustering is transparent and does not claim semantic optimization.

## Trust boundary

Only an owner-reviewed case can enter an immutable golden snapshot. Trace-derived cases without expected contracts cannot be approved until the owner supplies one. A failed production answer is evidence, never ground truth. Repository Python and LangFlow custom components are executable trusted code; local-only registration is explicit trust, not sandboxing. Secrets use environment variables; data/traces/model cache excluded from Git. Production redaction must be supplied by enterprise connector before real data ingestion.
