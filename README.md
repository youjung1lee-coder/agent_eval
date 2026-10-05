# GAIA Agent Evaluation Platform

로컬에서 실행하는 재사용 가능한 Agent 평가 PoC입니다. Repository를 Adapter로 표준화하고, 정의·Knowledge·실제 운영 Trace·운영 실패·Owner 지식에서 평가 후보를 만든 뒤 리뷰와 Golden 버전을 거쳐 회귀평가합니다. 실제 GAIA Boilerplate는 아직 제공되지 않았습니다. `eval_agent.json`과 Sample 구조는 **PoC의 Integration Contract이며 실제 GAIA 구조에 대한 주장과 다릅니다.**

## Project Overview

동일한 Golden Dataset을 등록평가, Agent 변경 회귀평가, 플랫폼 품질평가에 재사용합니다. Gate 실패는 Quality 점수와 무관하게 `HOLD`입니다. 운영 실패는 원본 Trace와 함께 후보가 되며, Owner가 의도한 정상 Contract를 작성해야 Golden에 들어갑니다. 원본 실패 답변을 정답으로 자동 승인하지 않습니다.

기준 문서 [에이전트_성능평가_v1.md](에이전트_성능평가_v1.md)를 보존했습니다. 구현 전 정리한 요구사항, 차이, 범위, 가정은 [docs/requirements.md](docs/requirements.md)를 참고하세요.

[Sample 코드 → 평가 사례 → Evaluator 설명자료](docs/sample_evaluation_explained.html)는 두 Sample의 기본 14개 사례, 실제 코드 줄 번호, 평가 함수 배정 조건과 결과, UI 스냅샷 10개를 함께 보여주는 단일 HTML입니다. 파일을 다운로드해 브라우저로 열면 오프라인에서도 사례 전환·검색·이미지 확대를 사용할 수 있습니다.

회사 PC에서 코드와 설명자료를 확인하려면 GitHub에서 `feat/gaia-evaluation-platform` 브랜치를 선택하세요. `Code → Download ZIP`으로 내려받아 압축을 풀고 `docs/sample_evaluation_explained.html`을 Chrome 또는 Edge로 여세요. 설명자료 열람에는 Python 설치나 서버 실행이 필요하지 않습니다. GitHub 파일 화면은 HTML을 웹페이지로 실행하지 않으므로 다운로드한 파일을 여는 방법을 권장합니다. 비공개 저장소는 접근 권한이 있는 GitHub 계정으로 로그인해야 합니다.

## Architecture

```text
Repository → Framework Adapter → AgentSpec → Analyzer → Candidates → Coverage
                                                             ↓
Production → Phoenix prd → Failure Detector ───────────→ Owner Review
                                                             ↓
                                                    Golden version
                                                             ↓
Platform / Owner / Python plugins → Evaluator Registry → Runner → Result Store → UI
                                                             ↓
                                                      Phoenix evaluate
```

FastAPI + Python Core + SQLite + HTML/JavaScript UI입니다. 프런트엔드 빌드 과정 없이 한 프로세스로 실행할 수 있도록 `ui/`를 정적 파일로 구성했습니다. Phoenix 서버는 Windows 호환성과 LFX 의존성 충돌을 피하기 위해 별도 가상환경을 사용합니다. [상세 설계](docs/architecture.md).

## AgentSpec

Adapter는 Framework 구조를 `AgentSpec`으로 변환합니다. 주요 필드는 `schema_version`, `agent_id`, `version`, `framework`, `entry_point`, `workflows`, `nodes`, `branches`, `tools`, `rag_sources`, `knowledge_sources`, `capabilities`, `probes`, `phoenix_config`, `metadata`입니다. 실제 Graph/JSON에서 Node와 Branch를 발견하고, 코드만으로 알 수 없는 업무 질문·정답은 명시적 Integration Probe로 제공합니다. Probe가 없는 기능은 Coverage Gap으로 남습니다. [Schema와 Expected Contract](docs/agent_spec.md).

## Quick Start

Python **3.12**, Git이 필요합니다. CPU와 로컬 디스크 약 3GB 이상을 권장합니다. 공개 모델 다운로드는 약 491MB이며 API Key는 필요하지 않습니다. 아래 명령은 **Repository 루트**에서 실행합니다.

```powershell
git clone https://github.com/youjung1lee-coder/agent_eval.git
cd agent_eval
# PR merge 전에는 구현 브랜치를 사용합니다.
git switch feat/gaia-evaluation-platform
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-cache-dir -r requirements.txt
python -m venv .phoenix-venv
.\.phoenix-venv\Scripts\python.exe -m pip install --no-cache-dir -r requirements-phoenix.txt
.\.venv\Scripts\python.exe -m scripts.download_judge
```

터미널 1 — 실제 Phoenix 서버:

```powershell
$env:PYTHONUTF8='1'
.\.phoenix-venv\Scripts\python.exe -m scripts.start_phoenix
```

터미널 2 — Agent 등록, 정상/실패 운영 Trace 생성, Pending Candidate 생성:

```powershell
$env:PYTHONUTF8='1'
.\.venv\Scripts\python.exe -m scripts.seed_demo
.\.venv\Scripts\python.exe -m evaluation_platform serve
```

평가 UI: [http://127.0.0.1:8000](http://127.0.0.1:8000). Phoenix: [http://127.0.0.1:6006](http://127.0.0.1:6006). API 문서: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). 서버 종료는 각 터미널에서 Ctrl+C입니다. 데이터는 `data/`, 공개 모델은 `.cache/`에 저장되며 Git에서 제외합니다. `.env.example`을 `.env`로 복사하면 CLI가 환경설정을 로드합니다. Secret을 파일에 저장했다면 Commit하지 마세요.

Linux/macOS에서는 `python3 -m venv`와 `.venv/bin/python`, `.phoenix-venv/bin/python`으로 경로를 바꿉니다. 서버는 Loopback에만 바인딩합니다. Remote Repository와 Flow의 Custom Component는 신뢰한 코드만 등록합니다. PoC에는 사내 인증과 Python Sandbox가 없습니다.

Ubuntu/glibc에서는 0.3.18 CPU 휠의 musl 의존성을 피하기 위해 requirements 설치 후 아래 명령으로 같은 버전을 소스 빌드합니다. C/C++ Compiler와 CMake가 필요하며 CI도 이 방식으로 검증합니다. [공식 소스 설치 설명](https://github.com/abetlen/llama-cpp-python#installation).

```bash
CMAKE_ARGS="-DGGML_NATIVE=OFF" CMAKE_BUILD_PARALLEL_LEVEL=2 .venv/bin/python -m pip install --force-reinstall --no-cache-dir --no-deps --no-binary=llama-cpp-python --index-url https://pypi.org/simple llama-cpp-python==0.3.18
.venv/bin/python -c "from llama_cpp import Llama; print('Judge runtime loaded')"
```

## Sample Agents

| Agent | 실제 실행 엔진 | 구조 |
|---|---|---|
| `hr-langgraph` | LangGraph StateGraph | Intent → Knowledge / Leave Tool / General → Final, Error·Timeout·Empty Retrieval |
| `support-langflow` | 공식 LangFlow LFX 0.2.2, `flow.json` | Text Input → 3개 Group Output Router → Search / Ticket Service / Help → 각 Answer |
| `commerce-third` | LangGraph StateGraph | Order Intake → Dispatch → Shipment / Returns / Permission Block → Receipt |

LangFlow는 JSON을 자체 Interpreter로 흉내 내지 않습니다. 실제 `lfx.graph.Graph.from_payload(...).arun(...)`을 사용합니다. 커밋된 JSON을 재생성하려면 `python -m scripts.build_langflow`를 실행하고 Agent를 재등록합니다. LFX 0.2.2의 Export/분기 중단/출력 형태에 대한 호환 처리는 Builder와 Adapter에 격리했습니다. [공식 LFX 설명](https://docs.langflow.org/lfx-run).

## Phoenix

실제 Phoenix **20.19.0** 서버에 OTLP HTTP `/v1/traces`로 Span을 보냅니다. 별도의 OTel Provider Resource에 `openinference.project.name=prd` 또는 `evaluate`를 지정합니다. 두 프로젝트 간 Trace ID가 섞이지 않는 것을 실제 테스트합니다. Candidate 수집은 Phoenix REST `/v1/projects/prd/spans`를 조회하며 SQLite의 실행 로그를 대체 원천으로 쓰지 않습니다. Agent / Retrieval / Tool / Evaluation / 실제 Judge LLM Span을 기록합니다. Sample Agent의 최종 답변은 결정적 Mock이며 이를 LLM Span으로 표시하지 않습니다.

Phoenix Native Dataset/Experiment API에 의존하지 않고 Golden과 Registry를 GAIA 계층에 구현합니다. Trace UI 링크는 Phoenix를 열어 표시된 Trace ID로 찾는 방식입니다. [Phoenix SDK 공식 설명](https://arize.com/docs/phoenix/resources/python-api).

## Dataset Generation

| UI Source | 정보 역할 | 후보 근거 |
|---|---|---|
| Workflow | Agent Definition | 실제 Node/Branch + Owner Integration Probe의 Expected Contract |
| RAG / Knowledge | Knowledge Source | Knowledge Unit 질문·원문·Reference Answer |
| Production Trace | Execution Trace | 실제 Phoenix 입력, 응답, Path, Tool, Retrieval, Latency, Status |
| Failure Candidate | Execution Trace | 관찰된 Timeout/Error/Tool Failure/Empty Retrieval/Empty Response/지연/중단/Retry |
| Owner Manual | Owner Input | Owner가 직접 작성한 질문·Contract·Evaluator |

모든 후보는 Pending으로 시작합니다. Confidence와 Evidence를 표시합니다. 정규화된 동일 입력에 Scenario ID를 부여하고 Variations를 보존하지만, Semantic Clustering과 자동 최소집합 최적화는 제외했습니다. 기존 리뷰 수정·제외는 재생성해도 유지됩니다. [Lifecycle](docs/evaluation_flow.md).

## Failure Candidate

1. `연차 조회 오류를 재현해 주세요.`, `연차 조회 시간 초과를 재현해 주세요.`, `미등록 지식 XYZ-404를 찾아주세요.`를 운영 질문으로 실행합니다.
2. `prd`의 실제 Trace가 수집된 후 Candidate를 생성합니다.
3. `실패 후보` 필터에서 `trace_id`, `span_id`, `failure_type`, `original_input/output`, `error`, `latency`, `candidate_reason`을 확인합니다.
4. Owner가 기대하는 복구 동작을 Contract로 작성하고 승인 또는 제외합니다.
5. Golden에 포함하고 Regression을 실행합니다. 고장난 Tool이 계속 실패하면 Gate가 실패하고 HOLD가 됩니다.

Status/Exception/Tool 결과/빈 Retrieval/Latency/명시적 중단·Retry만 탐지합니다. Trace에 없는 실패는 추론하지 않습니다. Phoenix 수집은 비동기이므로 전송 직후 조회 시점에 아직 없는 Span은 이후 Generate에서 가져옵니다. 수집 창은 최근 최대 1000 Span이며 미래 운영 질문 전체 Coverage를 주장하지 않습니다.

## Coverage

Feature, Workflow Node, Conditional Branch, Tool, Knowledge Unit, 관찰된 Production Scenario, Failure Type, Edge Case의 **안정적인 ID 집합**을 분모로 사용합니다. Candidate Coverage와 Approved Coverage를 구분합니다. 알려진 Inventory가 없으면 `total=null`, `unknown=true`, `percent=null`로 표시합니다. Production 분모는 관찰 창이며 향후 전체 사용량은 unknown입니다. Coverage는 테스트 설계 범위이며, 실제 통과율은 Evaluation 결과입니다.

## Evaluator Architecture

Registry에 등록된 `BaseEvaluator.evaluate(case, result)`를 Runner가 ID로 조회합니다. 기본 제공: Exact, Tool/Args/Order, Workflow/Path, RAG Document Match/Recall@K, Latency, Error, Required/Forbidden Behavior, Permission, JSON Schema, Runtime Tool Reference, LLM Correctness Judge, LLM 기반 Auxiliary Semantic Judge, LLM Faithfulness. String/Similarity만으로 자유형 정확성을 확정하지 않습니다. [Registry와 Plugin 예제](docs/evaluator_architecture.md).

Gate와 Quality를 분리합니다. Overall Score는 Quality만 평균합니다. Gate 또는 적용된 Evaluator 오류/실패가 있으면 HOLD입니다. 오류 난 Evaluator를 자동 PASS로 처리하지 않습니다. Latency 예산과 Quality 기준은 Contract/정의에서 조정해야 합니다.

## Custom Evaluator

UI의 `＋ 사용자 정의 Evaluator`에서 이름, 설명, 평가 기준, 점수 범위, 통과 기준, 적용 범위/대상, 활성 상태를 설정합니다. 한국어 Sample 질문/응답으로 **실제 LLM 평가**를 실행하고 점수·통과 여부·이유를 확인한 다음 등록합니다. Sample 이후 정의가 바뀌면 재평가해야 합니다. 기존 정의를 수정하면 Version을 증가시켜 다시 Sample을 실행합니다. Inactive Judge는 새 Golden의 Binding에 연결할 수 없습니다. 이미 확정한 Golden은 이전 정의를 재현하기 위해 스냅샷을 유지합니다.

Case Review에서 Platform Evaluator, 기존 Custom Evaluator 또는 새 Custom Evaluator를 선택합니다. Dataset Binding JSON은 전체, Type, Capability Scope를 지원합니다. 하나의 Case에 여러 Evaluator를 연결할 수 있습니다.

기본 Judge는 실제 **Qwen2.5 0.5B Instruct GGUF Q4_K_M**를 CPU에서 실행하며 Mock 점수 함수가 아닙니다. 작은 모델의 정확도·한국어 Rubric·Prompt Injection 방어는 운영 수준으로 검증되지 않았습니다. 사내 Judge 서비스 연결은 `JUDGE_BACKEND=compatible`, `JUDGE_BASE_URL` (예: `.../v1`), `JUDGE_MODEL`, `JUDGE_API_KEY` 환경변수로 교체합니다. [CPU Runtime 문서](https://github.com/abetlen/llama-cpp-python), [모델](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF).

## UI

1. **데이터셋 생성 · Coverage:** Repository 등록, 발견한 Node/Branch/Tool/Knowledge, 출처별 후보 수, 운영 질문 실행, 실패 유형, 전체/승인 후보 Coverage Gap.
2. **Owner 검토:** 출처/검토 상태/검색 필터, 한국어 질문·기대 응답·Contract·Evaluator 편집, 생성 근거·Trace·추천 이유, 추가·삭제·승인·제외, Golden Version 확정.
3. **평가 결과:** Golden Version·평가 종류 선택, Quality Score와 Gate/HOLD, 사례별 기대/실제 응답, Workflow/Tool/RAG/Latency, Platform/Custom 점수·이유, 실패 필터와 실행 이력.

Sample Agent `1.1-ko`의 질문·문서·기대 응답과 후보 설명은 한국어입니다. UI는 한국어를 기본으로 하되 AgentSpec, Golden Dataset, Evaluator, Trace ID, Gate, Quality, PASS/FAIL/HOLD 등 기술 용어와 API/Schema 식별자는 유지합니다. Judge에는 한국어 이유를 요청하지만 외부 모델의 언어·정확성은 모델 특성에 따라 달라질 수 있습니다.

기존 영문 데모를 사용했다면 **seed_demo 재실행 / Agent 재등록 전에** 다음 명령으로 변환합니다. SQLite 백업을 생성하고 이전 Golden/실행 이력 및 원본 Trace 입력·응답은 보존합니다. 알려진 Sample 후보의 질문·기대 응답만 변환하며, 운영 후보를 새로 자동 승인하지 않습니다. `--approve-sample-contracts`는 명시된 Sample Workflow/RAG 계약만 승인하고 `--finalize`는 새 Golden 버전을 만듭니다.

```powershell
.\.venv\Scripts\python.exe -m scripts.localize_demo --approve-sample-contracts --finalize
```

이미 Agent를 재등록했다면 `--source-backup data/platform-before-ko-<timestamp>.sqlite`로 변환 이전 AgentSpec이 있는 백업을 지정할 수 있습니다. 새 Clone에서는 변환 없이 Quick Start를 실행하면 한국어 후보가 생성됩니다. [한국어 적용 검증](docs/korean_localization.md).

Golden에는 Case, Binding, Custom Evaluator 정의, Agent Fingerprint를 저장합니다. 결과에는 현재 Agent Snapshot/Fingerprint, Dataset Version, Evaluator Version/정의, Judge 모델 SHA256과 실제 응답을 남깁니다. SQLite 파일을 보관하면 재시작 후에도 조회할 수 있습니다.

## Testing

```powershell
# Unit + framework/API integration (실제 LangGraph/LFX, Judge는 명시적 테스트 Double)
.\.venv\Scripts\python.exe -m pytest -q -m 'not real_e2e'
# 실제 Phoenix와 실제 로컬 Judge를 사용하는 E2E
$env:EVAL_REAL_E2E='1'
.\.venv\Scripts\python.exe -m pytest -q
# 실제 브라우저 E2E: 플랫폼 실행 + seed_demo 완료 후
npm install
# Windows 기본은 설치된 Edge; 다른 환경은 BROWSER_CHANNEL 설정
npm run test:ui
# Git에 들어갈 파일의 Secret 검사
.\.venv\Scripts\python.exe -m scripts.secret_scan
```

실제 E2E는 Phoenix 프로젝트 격리, 정상·Tool Error·Timeout·Empty Retrieval, Trace→Failure Candidate→Owner Review→Golden→회귀 HOLD, Custom Judge 2개와 실제 Sample 결과, Runner 수정 없음, Judge Positive/Negative를 확인합니다. Browser E2E는 UI에서 편집·수동 추가·승인·Custom 2개 Sample/등록/Case 적용·Golden/결과를 확인하고 `artifacts/ui/`에 Screenshot과 JSON을 생성합니다. Third Agent 테스트는 Core 파일의 SHA256을 전/후 비교합니다. [검증 보고서](docs/validation.md).

## Adding a New Agent

```powershell
.\.venv\Scripts\python.exe -m evaluation_platform register --agent-path C:\trusted\new-agent
.\.venv\Scripts\python.exe -m evaluation_platform execute new-agent-id 'A production question'
.\.venv\Scripts\python.exe -m evaluation_platform generate new-agent-id
```

1. 신뢰한 Repository에 `eval_agent.json`을 제공하거나, 실제 Repository 구조를 발견하는 별도 Adapter를 등록합니다.
2. LangGraph는 Graph Factory Entry Point가 `(manifest, runtime_context)`를 받아 Compiled Graph를 반환합니다. LangFlow는 Exported JSON과 Output Node ID를 Mapping합니다.
3. Tool Schema, Knowledge Unit, 업무 Probe/Expected Contract/Dependency ID를 Mapping합니다. 알 수 없는 부분은 명시적으로 unknown/gap으로 남깁니다.
4. Runtime 결과를 `AgentResult`로 변환합니다. 실제 서비스는 Knowledge/Tool Protocol 구현으로 주입합니다.
5. UI에서 Pending 후보를 리뷰하고 Golden을 확정해 실행합니다. Framework 런타임/Output 구조 차이는 Adapter에서 흡수합니다. Dataset Generator, Coverage, Golden, Registry, Runner, Result Store, UI에 Agent 이름을 추가하지 않습니다.

## Applying Real GAIA Boilerplate

**현재 제공된 기능을 AgentSpec/AgentResult/ExpectedContract로 표현할 수 있다면 Evaluation Core는 변경하지 않습니다.**

1. Entry Point, Config, LangGraph 위치, LangFlow Export, Node/Edge/Conditional, Tool 등록/호출, RAG/Knowledge, S3/OpenSearch/Milvus, Phoenix Instrumentation, A2A Request/Response, 실행 Interface를 비교합니다.
2. 실제 Repository 발견·실행을 담당하는 `GAIAAdapter`를 추가하고 `adapters.ADAPTERS`에 등록합니다. 현재 Sample Manifest 경로를 GAIA 사실로 사용하지 않습니다.
3. Workflow·Capability·Tool Schema·Knowledge·Probe를 AgentSpec에 Mapping하고, 실행 Observation을 AgentResult에 Mapping합니다.
4. Phoenix Connector의 환경변수·Auth·Project Routing·Attribute Mapping·Read Window를 실제 Instrumentation에 맞춥니다. 운영 데이터의 개인정보/민감정보는 Connector에서 수집 전 Redaction해야 합니다.
5. KnowledgeConnector를 실제 S3/OpenSearch/Milvus Read-only 검색 구현으로, ToolConnector를 실제 GAIA/A2A Tool 호출 구조로 교체합니다.
6. 기존 생성·Coverage·리뷰·Golden·Registry·Runner·Store·UI를 그대로 실행하고 Contract Tests/Third Agent E2E를 반복합니다.
7. 멀티턴/Streaming Contract, 새 Observation 타입, 데이터 규모에 따른 분산 Runner, 운영 RBAC 같은 **현재 Schema나 실행 모델로 표현할 수 없는 요구**가 나오면 Core 확장이 필요합니다. 이를 Adapter 수정이라고 숨기지 않고 Schema Version Migration과 Gap으로 기록합니다.

[Gap Analysis 체크리스트와 Mapping 지침](docs/real_gaia_integration.md).

## Limitations

Knowledge Document/Search/Business Tool은 Mock입니다. 실제 S3/OpenSearch/Milvus/MyAccess/Jenkins/회사 인증/A2A Super Agent는 연결하지 않았습니다. Sample Agent 응답 생성은 결정적이며 Judge는 실제 로컬 LLM입니다. Repository 분석은 실행 가능한 Graph와 명시적 업무 Probe를 이용하며 임의 코드에서 업무 정답을 완전히 추론하지 않습니다. 운영 Trace 수집은 공통 Attribute Mapping이 필요합니다. 런너는 로컬 동기 실행이며 Sample Timeout은 명시적 Simulation입니다. 임의 Agent 프로세스를 강제 종료하는 Sandbox/분산 Timeout은 제외했습니다. [제한사항 전체](docs/limitations.md).

## Main files

`evaluation_platform/adapters/`, `models/`, `analyzer/`, `dataset/generator.py`, `candidates/failure_detector.py`, `coverage/`, `evaluators/`, `runner/runner.py`, `storage/store.py`, `service.py`, `api/app.py`, `ui/`, `sample_agents/`, `tests/`, `scripts/`. 실제 서비스별 변경은 Adapter/Connector에서 시작합니다.
