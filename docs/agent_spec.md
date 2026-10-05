# AgentSpec

`schema_version`, `agent_id`, `version`, `framework`, `entry_point`, `workflows`, `nodes`, `branches`, `tools`, `rag_sources`, `knowledge_sources`, `capabilities`, `probes`, `phoenix_config`, `metadata`.

Nodes/edges come from adapter discovery. Tools include JSON input schemas. Knowledge units include stable IDs, content, owner-authored questions and references. Probes contain input, expected contract, capability/dependency IDs and evidence; missing probes produce uncovered inventory, not invented executable questions. Metadata identifies adapter assumptions. Fingerprint covers normalized spec and repository source digest. Config exposes no credentials.

ExpectedContract supports reference output/context, tool names/args/order, forbidden tools/nodes/output, required nodes, valid ordered paths, document IDs/recall K, expected status, latency budget, runtime tool reference, JSON schema and permission denial. Cases preserve scenario ID, variations, sources, confidence, evidence, trace/span IDs, original input/output, observed failure type/reason, and review status. EvaluationBinding separately selects evaluator ID, gate/quality role, case/type/capability/dataset scope. Golden versions snapshot cases, bindings and evaluator definitions.
