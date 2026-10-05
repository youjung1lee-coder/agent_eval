# Evaluator architecture

Runner resolves ID → `BaseEvaluator.evaluate(case, result)`. It contains no framework/sample/evaluator-type branches. Evaluator returns normalized score 0..1, passed, reason, details and optional error. Custom judge score is normalized for Quality aggregation; original scale/threshold remains in details. Gate scores never inflate or dilute quality averages. Missing/failed evaluator execution produces failure and HOLD.

Bindings are separate objects with evaluator ID, gate/quality role and scope (`dataset`, `case`, `type`, `capability`) + target. Case-level bindings are edited in the table; optional dataset/type/capability bindings are JSON in review, for example:

```json
[{"evaluator_id":"owner_example","role":"quality","scope":"capability","target":"knowledge"}]
```

Platform evaluators cover strings, paths/required/forbidden nodes, tool name/args/order, permission, schema, runtime tool reference, observed status and latency, reference document Recall@K, real LLM correctness/faithfulness and auxiliary semantic judge. Semantic evaluator uses the configured LLM, not an embedding cosine score. Rule evaluators implement exact contract semantics; free-form answers need a rubric/reference and calibrated judge.

Custom definition → actual sample inference → preview definition hash → register same definition → binding → frozen Golden → Runner. Changing any field after preview invalidates it. Update increments definition version. Disable prevents new attachments; old golden uses its frozen version. UI never runs arbitrary Python code.

## Trusted code plugin

```python
from evaluation_platform.evaluators.base import BaseEvaluator
from evaluation_platform.models import EvaluatorResult

class FinanceRule(BaseEvaluator):
    id = "finance_rule"
    version = "1.0"
    def evaluate(self, test_case, agent_result):
        ok = "currency" in agent_result.output
        return EvaluatorResult(evaluator_id=self.id, score=float(ok), passed=ok,
                               reason="Contract requires explicit currency")

# Composition root: provide this registry to run_evaluation; Runner code unchanged.
registry.register(FinanceRule())
```

PoC service uses the platform registry composition root. Enterprise plugin loading/approval can be added there; UI Python upload/execution is intentionally absent. Threshold calibration, multilingual judge accuracy and judge prompt-injection robustness require representative enterprise examples.
