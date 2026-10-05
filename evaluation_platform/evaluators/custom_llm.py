from .base import BaseEvaluator
from evaluation_platform.models import EvaluatorResult


class CustomLLMEvaluator(BaseEvaluator):
    def __init__(self, definition, backend):
        self.definition, self.backend = definition, backend
        self.id, self.version = definition.id, str(definition.version)

    def evaluate(self, case, result):
        d = self.definition
        if not d.active:
            raise ValueError("evaluator is inactive")
        score, reason, details = self.backend.assess(d.criteria, case.input, result.output, case.expected.model_dump())
        scaled = d.score_min + score * (d.score_max - d.score_min)
        return EvaluatorResult(evaluator_id=self.id, score=score, passed=scaled >= d.pass_threshold,
                               reason=reason, details={**details, "scaled_score": scaled, "scale": [d.score_min, d.score_max],
                                                       "threshold": d.pass_threshold, "definition_version": d.version})
