# GAIA 평가 아키텍처

## 실행 흐름

브라우저는 동일 origin의 FastAPI에서 정적 빌드와 JSON API를 받습니다. 가져오기는 Phoenix 읽기 전용 어댑터에서 원본과 span을 수집하고 한 트랜잭션으로 커밋합니다. 중복 원본 버전은 기존 버전을 반환합니다. 같은 Trace에 연결된 서로 다른 item은 각각 유지하며 경고를 남깁니다. Dataset과 item의 원본 ID로 만든 UUID가 버전을 넘는 케이스 키입니다.

Phoenix REST는 공개 클라이언트 1.26.0의 경로와 페이징 계약을 따릅니다. 예제 metadata의 span_id 또는 trace_id가 있으면 프로젝트 span을 모아 전체 Trace를 연결합니다. 조회 실패나 참조 부재는 항목 스냅샷으로 표시합니다. 원본 입력과 구조화 출력은 JSON으로 보관합니다. 공통 OpenInference 속성에서 검색 문서, 도구 인자, root 출력을 추출하고 원래 필드를 함께 보존합니다. 예상 응답의 기본 출처는 예제 metadata.expected_output입니다.

## 영속 저장

| 엔터티 | 역할 |
|---|---|
| datasets → versions → cases | 논리 Dataset, 불변 버전, 안정적 case_id와 연결된 원본 Execution |
| executions | Phoenix 또는 신규 Agent 실행의 응답, Trace, 계측 메타데이터와 상태 |
| evaluators, mappings | family와 version으로 식별하는 정의, 해당 정의와 agent별 불변 매핑 ID |
| experiments → jobs → results | 고정 Dataset·매핑 ID 목록, 케이스 실행, 점수·판정·입력·경로·엔진 버전·Judge |
| attempts | 신규 호출 시도와 성공·실패 Execution 연결 |
| comparisons | A/B 실행의 기준·후보 Experiment 쌍. 점수차와 회귀는 저장된 결과로 계산 |

DB 마이그레이션은 Alembic이 담당합니다. Redis를 추가하는 대신 PostgreSQL의 작업 테이블과 `FOR UPDATE SKIP LOCKED`를 사용합니다. 실험 생성과 작업 등록이 한 트랜잭션에서 완료되고, Agent 호출 결과를 저장한 뒤 개별 지표를 평가합니다. 외부 호출 중에는 DB 트랜잭션을 잡지 않습니다. 소유자와 만료 시각을 검사해 재시작 후 작업을 회수합니다. 격리된 STG는 동일 Idempotency-Key를 재처리해도 부작용이 없어야 합니다.

취소는 대기 작업에 적용합니다. 케이스 재시도는 실행 성공 시 기존 응답을 재사용하며 실행 실패 시 새 시도를 기록합니다. 완료된 실험의 버전 참조는 수정되지 않습니다. 평가 오류·미실행 항목의 명시적 재시도는 해당 결과 행을 갱신합니다. 별도의 완전한 이력이 필요할 때는 새 실험으로 재평가하세요.

## 주요 API

전체 필드와 제약은 구동 중인 서버의 `/docs`에서 확인할 수 있습니다.

| 메서드·경로 | 동작 |
|---|---|
| GET /api/state | 카탈로그, Dataset 버전, 발행본, 실험 목록 |
| GET /api/sources/{source}/versions, /api/sources/{source}/preview | 원본 버전·미리보기 |
| POST /api/imports | 버전 가져오기 |
| GET /api/versions/{id}/cases | 모든 케이스와 Trace |
| PATCH /api/versions/{id}/cases/{case_id} | 편집을 새 Dataset 버전으로 발행 |
| POST /api/mapping/{preview,validate,test,publish} | 샘플 해석, 전체 검증, 실제 지표 호출, 발행 |
| POST /api/preflight, /api/experiments | 매핑 검증, 실험과 작업 생성 |
| GET /api/experiments/{id}, /api/compare?a=…&b=… | 상세, 동일 조건의 케이스별 비교 |
| POST /api/experiments/{id}/{retry,cancel} | 실패 재시도 또는 대기 작업 취소 |

## 매핑 해석

경로는 RFC 6901 JSON Pointer를 사용합니다. `/trace/spans/0/attributes/output.value`에서 마침표는 키의 일부입니다. `~1`은 슬래시, `~0`은 물결표입니다. selector는 kind, 이름 포함 여부, 속성 값으로 span을 선택합니다. unique는 복수 일치를 오류로 표시합니다. first와 last는 순서 의존성을 경고합니다. all은 배열을 보존하며 임의로 평탄화하지 않습니다. join은 지정 경로를 줄바꿈으로 연결합니다. 구조화된 원본과 지표에 전달하는 정규화 값은 별도로 표시합니다.

## STG 게이트웨이 계약

- 서버는 지정된 단일 격리 계정과 허용 에이전트만 사용합니다. 사용자별 GAIA 권한이나 SSO가 필요한 배포는 별도 위임 어댑터가 필요합니다.
- 실제 POST 전에 인증된 `GET /capabilities`에서 `{"isolated":true,"idempotency":true,"agent_id":"설정한 에이전트"}`를 확인합니다. 이 계약의 실제 안전성은 게이트웨이가 보장해야 합니다.
- `POST /run`은 input, 독립 session_id, environment, agent_id를 받습니다. 인증은 서버 환경변수의 Bearer이며, 작업 ID가 멱등 키입니다.
- 응답에 actual_output이 필수입니다. retrieval_context, tools_called, trace, metadata를 함께 전달할 수 있습니다. 버전 메타데이터가 없으면 unknown을 표시합니다.
- Mock HTTP Agent는 합성 정책 질문을 처리합니다. 실제 도구 호출, 세션 로그인, 파일 다운로드는 수행하지 않습니다.
- 알려진 인증 키·이메일 등을 마스킹하고 구조화 데이터는 텍스트로 렌더링합니다. 자유 텍스트의 모든 개인정보를 판별하는 DLP 기능은 추가 연동 대상입니다.

## 평가와 집계

DeepEval 3.1.5 Tool Correctness와 Ragas 0.2.15 Exact Match는 외부 모델 없이 실행됩니다. DeepEval Judge 어댑터는 지표가 요청한 Pydantic 스키마를 전달하고 응답을 검증합니다. Ragas는 SingleTurnSample 또는 MultiTurnSample과 LangChain 모델 래퍼를 사용합니다. 실패한 외부 응답은 점수가 없는 ERROR로 저장합니다. 빈 입력 및 잘못된 타입은 NOT_EVALUABLE, 엔진·모델 미설정은 NOT_RUN입니다. 수치가 있는 평가 결과만 평균·통과율 분모에 들어갑니다. 여러 지표를 선택하면 전체 평균은 지표 결과 단위입니다.
