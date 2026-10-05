# Executed validation — 2026-10-05 (Asia/Seoul)

Executed on Windows, Python 3.12.14, Phoenix 20.19.0, LangGraph 0.6.11, official LangFlow LFX 0.2.2, llama-cpp-python 0.3.18, Qwen2.5 0.5B Q4_K_M, Playwright 1.62.1 with installed Microsoft Edge. These are local observed results; GitHub Actions results are separate.

## Automated suite

`EVAL_REAL_E2E=1 python -m pytest -q --junitxml=artifacts/tests.xml`

**35 passed, 0 failed, 0 skipped**, 72.85s in final run. Includes 30 unit/framework/API integration checks and 5 real Phoenix/local-LLM E2Es. The unit test judge is explicitly a double; the real E2E suite requires actual Phoenix and actual weights and never substitutes that double.

| Actual full-pipeline Agent | Golden cases | Decision | Quality score |
|---|---:|---|---:|
| LangGraph HR | 8 | PASS | 99.94% |
| LangFlow Support JSON / LFX | 6 | PASS | 100.00% |
| Third Commerce, distinct intake/dispatch/permission/shipment/returns | 4 | PASS | 99.89% |

These sample Golden contracts explicitly expect graceful simulated error/timeout behavior. A separate incident-derived Golden requires successful recovery and correctly HOLDs while the deliberately broken tool remains broken. Judge scores are observations from the small local model, not a production accuracy benchmark.

## Failure / custom judge E2E

- Normal operational query and actual Phoenix `prd` read-back verified.
- Tool RuntimeError, explicit 40ms > 20ms timeout simulation, zero-document retrieval emitted and ingested from Phoenix.
- Failure detector generated observed reasons and preserved trace/span, original input/output, error and timing.
- Approval without substantive contract rejected. Owner edited recovery contract, approved failure candidate, excluded duplicate operational input, finalized immutable Golden.
- Regression executed the same failing input; error/behavior Gate failed and result was HOLD, with source trace still attached.
- Two separate owner LLM criteria ran actual samples, were registered and bound to one test case; both produced Score/Pass/Fail/Reason and raw model output.
- Runner file SHA256 unchanged before/after second custom evaluator. Positive HR portal answer passed; unrelated answer failed the same actual judge criterion.
- `prd` and `evaluate` trace ID sets were disjoint; evaluation spans and actual `judge.inference` spans read from Phoenix. No eval agent root appeared in `prd`.

## Coverage

Approved definition/knowledge coverage in full-pipeline E2Es:

| Dimension | HR | Support | Third |
|---|---|---|---|
| Feature | 4/4 | 4/4 | 3/3 |
| Workflow nodes | 5/5 | 8/8 | 6/6 |
| Branch | 3/3 | 3/3 | 3/3 |
| Tool | 1/1 | 1/1 | 1/1 |
| Knowledge units | 2/2 | 1/1 | 1/1 |
| Declared failure types | 3/3 | 2/2 | unknown |
| Edge cases | 1/1 | 1/1 | 1/1 |

Actual approved failure coverage also includes any observed types in that run's denominator; exclusion cannot erase observed failure gaps. Production future universe remains unknown. Full-pipeline definition/knowledge tests do not auto-approve operating inputs, so reviewed production coverage is lower than candidate coverage. Browser closed-loop explicitly approves an incident-derived case.

## Core independence

All Core Python files hashed before/after registering/generating/reviewing/evaluating each agent:

`e213120b6609badffc6e8965200c3eeeb85bfb0bad97ff46aca0a57d834bf5a0`

Before and after were identical in all three real E2Es, including the Third Agent. No sample node/tool/document/branch identifiers occur in Evaluation Core. The tests are reproducible and fail if Core files change during the pipeline.

## Browser validation

`tests/ui_e2e.cjs` interacted with actual running HTTP endpoints in Edge; no route mocking. It verified Source/Coverage, failure lineage display, owner contract edit/approval, manual case addition, two actual custom judge previews and registration, per-case bindings, Golden finalization and detailed run result.

Observed demo: **3 cases, 1 failed, Quality 97.14%, Gate failed → HOLD**. Both custom judge results were 0.9/PASS. Browser JavaScript errors: **0**. Screenshots inspected for generation, review and results; actual Phoenix Projects UI also showed `prd` and `evaluate`.

Local evidence (Git-excluded): `artifacts/tests.xml`, `artifacts/e2e/*.json`, `artifacts/ui/report.json`, `artifacts/ui/01-generation.png`, `02-review.png`, `03-results.png`, `04-phoenix.png`. They can be regenerated with README commands. Trace counts grow with repeated tests; candidate count is not claimed as coverage.

## Additional checks

- Python compilation, JavaScript syntax, `pip check` passed.
- Registry duplicate/missing/error behavior, gate-vs-quality decision, tool order/args, path ordering, Recall@K, permission, schema, unknown totals, review CRUD/provenance and frozen judge definitions checked.
- Deleted generated cases stay deleted on regeneration; excluded failures remain in the coverage denominator.
- Secret scan uses Git index before commits and a source allow-list in CI. `.env`, model/cache/data/artifacts/venvs excluded. Scanner reports only file/line/type, never secret values. This is a PoC detector, not a replacement for enterprise secret-scanning policy.
