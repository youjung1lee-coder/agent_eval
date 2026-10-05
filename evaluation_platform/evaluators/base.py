from abc import ABC, abstractmethod
from evaluation_platform.models import EvaluationCase, AgentResult, EvaluatorResult


class BaseEvaluator(ABC):
    id: str
    version: str = "1.0"

    @abstractmethod
    def evaluate(self, test_case: EvaluationCase, agent_result: AgentResult) -> EvaluatorResult: ...


class FunctionEvaluator(BaseEvaluator):
    def __init__(self, evaluator_id, function, threshold=1):
        self.id, self.function, self.threshold = evaluator_id, function, threshold

    def evaluate(self, case, result):
        score, reason, details = self.function(case.expected, result)
        return EvaluatorResult(evaluator_id=self.id, score=score, passed=score >= self.threshold,
                               reason=reason, details=details)
