# Applying Real GAIA Boilerplate: gap analysis

No real GAIA boilerplate has been provided. The manifest, graph factory and Flow component names are sample integration choices. Actual A2A/config/layout are unknown.

Classify each gap: **1 unchanged**, **2 adapter/connector mapping**, **3 core extension required**. Prefer 1/2 when existing normalized contracts can express the behavior, never conceal a type-3 requirement.

| Inspect | Current integration assumption | Preferred change |
|---|---|---|
| Agent Entry Point / execution Interface | Trusted file:factory or exported Flow | 2: GAIAAdapter wraps real callable / A2A client |
| Config / auth / deployment metadata | Environment + mock manifest, no secrets in AgentSpec | 2: resolve credentials at Connector boundary |
| LangGraph Workflow location | Manifest points at factory | 2: discover actual workflow path; map actual nodes/conditional edges |
| LangFlow Flow definition | Official export + LFX 0.2.2 | 2: map actual JSON version or remote LangFlow API result |
| Node / Edge / Conditional Branch | Discovered stable IDs | 1/2: map IDs, retain unknown branch inventory if unavailable |
| Tool registration / call format | JSON schemas and normalized tool calls | 2: ToolConnector schema/name/args/result/status mapping |
| RAG implementation / Knowledge | Explicit units with stable document IDs and read-only search | 2: RAG connector supplies units, content, IDs; owner defines questions/contracts |
| S3 / OpenSearch / Milvus | MockKnowledge implementation | 2: production read-only connector, credentials via environment |
| Phoenix instrumentation | OTel project resource + `gaia.*` attributes | 2: real collector/auth/project and span attribute mapping |
| A2A code / Super Agent | No proprietary protocol assumption | 2: GAIAAdapter normalizes request/result/path/tool/retrieval |
| Multi-turn / Streaming / side effects | Single question, normalized final observation | 3 if contract or lifecycle cannot fit current schema |
| Distributed execution / hard timeout / RBAC | Local trusted code and synchronous run | 3: production runner/service extension |

## Mapping contract

Repository → `AgentSpec` (inventory, version, source evidence) and runtime → `AgentResult` (answer, observed status/error, path, branch IDs, tools, document IDs, timing, trace). Expected is an independent owner/business contract. Unknown facts must remain unknown; do not derive correct answers from previously failed outputs.

Real tracing does not need to adopt every PoC `gaia.*` attribute. Replace `PhoenixConnector.production` mapping to aggregate a root and its actual children into the same normalized observation. The PoC exports serialized normalized root results for easy demonstration; external roots without mapped fields should not claim absent retries/interruption/tool success. Redact sensitive inputs/results before emitting or importing production observations. Keep project routing `prd/evaluate` or document equivalent available project isolation.

Connector injection point is `RuntimeContext(spec, trace, tools=..., knowledge=...)`. GAIAAdapter can construct actual connectors or use an enterprise composition root. Do not add GAIA-specific node/tool names to generator, coverage, registry, runner, store or UI. Run existing schema/contract tests and a new third-agent E2E before integrating real production.
