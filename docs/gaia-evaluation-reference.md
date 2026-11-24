# 설계 참고 자료

| 출처 | 적용 범위 |
|---|---|
| [Langfuse LLM as a Judge](https://langfuse.com/docs/evaluation/evaluation-methods/llm-as-a-judge), [코드 Evaluator](https://langfuse.com/docs/evaluation/evaluation-methods/code-evaluators) | 카탈로그에서 지표 선택 후 실제 Trace와 매핑·시험 평가를 함께 검토하는 UX |
| [LangSmith 평가 유형](https://docs.langchain.com/langsmith/evaluation-types) | 기존 실행 재평가 및 동일 케이스 페어 비교 |
| [Phoenix Python Client](https://github.com/Arize-ai/phoenix/tree/main/packages/phoenix-client) | 설치한 arize-phoenix-client 1.26.0 소스의 Dataset, DatasetVersion, examples, project spans REST 스키마 확인 |
| [DeepEval](https://deepeval.com/docs/metrics-introduction) | 설치한 3.1.5 Metric과 LLMTestCase, ToolCall, 구조화 Judge 모델 인터페이스 |
| [Ragas](https://docs.ragas.io/en/v0.2.15/concepts/metrics/available_metrics/) | 설치한 0.2.15의 SingleTurnSample, MultiTurnSample 및 지표별 비동기 평가 |
| [JSON Pointer](https://www.rfc-editor.org/rfc/rfc6901) | 웹에서 입력 가능한 필드 경로 표현 |

화면, DB 모델, 큐 워커, Fixture, 공통 레코드, 규칙 해석, 결과 비교는 이 프로젝트에서 새로 작성했습니다. 점수는 선택한 공급자의 구현 및 버전에 종속됩니다.
