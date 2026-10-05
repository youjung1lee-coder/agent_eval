# 한국어 데이터셋 / UI 적용 검증

2026-10-05, Sample Agent 버전 `1.1-ko`.

## 적용 범위

- 세 Sample의 질문, 문서 내용, 기준 답변, 응답 문구, 생성 근거와 실패 추천 이유를 한국어로 작성했습니다.
- 한국어 질문이 실제 LangGraph/LFX의 RAG·Tool·일반·오류·권한 분기로 전달됩니다. Mock Tool 업무 값도 한국어입니다.
- UI의 메뉴·버튼·필터·검토 상태·Evaluator 이름·설명·실행 이력·결과 이유를 한국어로 표시합니다. Schema 필드, 식별자, Trace ID와 익숙한 기술 용어는 유지합니다.
- 한국어 검토 상태의 표시와 API enum 값(`pending/approved/excluded`)을 분리했습니다.
- Custom Judge 정의를 실제 Sample 평가 후 버전을 올려 등록했으며, 실제 추론에도 한국어 이유를 요청합니다. 소형 모델 점수는 미보정 PoC 값입니다.
- 과거 Golden/Result를 다시 쓰지 않습니다. 운영 Trace의 원문과 관찰된 오류는 번역하지 않습니다. 평가용 질문만 번역해도 원본 Trace 연결을 보존합니다.

## 실제 검증

- 전체 Python Suite **36 passed, 0 failed, 0 skipped**, 74.89s. 실제 Phoenix/LLM E2E 5개 포함.
- 새 Migration 테스트가 과거 Golden, 원본 Trace 입력·응답·오류·ID 보존과 운영 후보 Pending 유지를 확인합니다.
- 세 Agent의 한국어 정의/문서 Golden 전체 평가: HR 8개 PASS/99.35%, LangFlow 6개 PASS/99.17%, Third 4개 PASS/99.89%.
- 기존 로컬 Demo를 변환한 후 HR Golden v3 11개 HOLD/98.73%(미복구 운영 실패 1개), LangFlow v2 6개 PASS/99.17%, Third v2 4개 PASS/99.89%.
- Custom Judge 4개: 실제 한국어 응답에 0.9 또는 0.99/PASS. 실제 모델 이유를 원문 그대로 보존합니다.
- 현재 로컬 후보의 질문에 영문만 있는 사례는 0개입니다. 이전 Golden 버전의 영문 사례는 이력으로 유지합니다.
- 실제 앱 브라우저에서 한국어 Source 필터, 검토 모달, 승인 저장과 한국어 결과 화면을 확인했습니다.

Git-excluded 증거: `artifacts/tests-ko.xml`, `artifacts/e2e/*.json`, `artifacts/live_demo_results.json`, `artifacts/ko_review.png`, `artifacts/ko_results.png`, `data/platform-before-ko-*.sqlite`.

기존 데모 변환 도구는 Sample Integration 계층의 유지보수 도구이며, 임의 Agent나 임의 영문 질문의 자동 번역 기능은 아닙니다. 처음 설치할 때에는 한국어 Manifest와 seed_demo를 바로 사용합니다.
