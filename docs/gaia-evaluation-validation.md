# 실행 검증 기록

2026-11-24 UTC에 합성 데이터로 확인했습니다.

| 검증 | 결과 |
|---|---|
| TypeScript 및 Vite 프로덕션 빌드 | 성공 |
| 프런트엔드 상태 로직 | 페이지 범위, 오류·미채점·0점 구분, Tool·검색 필터 3개 통과 |
| pytest | 백엔드·통합 11개와 Chromium E2E 1개, 총 12개 통과. 외부 라이브러리의 deprecation 경고 6개 |
| Docker | Python 3.12 / Node 기반 다단계 이미지 빌드 성공. PostgreSQL 16과 앱 모두 healthy. HTTP /health 성공 |
| 마이그레이션 | 빈 SQLite와 Compose PostgreSQL에 Alembic 적용, Fixture 20건과 기본 Evaluator 2개 생성 |
| 브라우저 | React 정적 빌드에서 import, 미리보기, 전체 검증, 시험 평가, 버전 발행, A/B 실행, 회귀 필터, 모바일 폭 검증 |
| Compose 브라우저 추가 확인 | 서로 다른 두 Trace에서 필드 클릭 → 매핑 미리보기 성공. 사용 가이드의 화면은 실제 배포에서 캡처 |

## Compose 실험 기록

동일 Dataset v1의 20건에 정책 응답 정확도(Ragas Exact Match)와 정책 검색 도구 호출(DeepEval Tool Correctness)을 적용했습니다. 아래 건수는 케이스·지표 조합 단위입니다.

| 실행 | Agent 호출 | 점수 | 통과 | 실패 |
|---|---:|---:|---:|---:|
| 기존 Phoenix Fixture Trace | 0 | 40 | 36 | 4 |
| Mock PRD | 20 | 40 | 38 | 2 |
| Mock STG | 20 | 40 | 37 | 3 |

기준 PRD와 후보 STG의 40쌍 중 회귀 2개, 개선 1개, 동률 37개였습니다. 회귀는 기준 통과 및 후보 실패를 의미합니다. 두 환경은 실제 HTTP를 통해 별도 세션으로 실행했습니다.

## 자동 검증 근거

- 20개 안정 ID, 원본 응답·Trace 및 미연결 경고, 중복 import, 편집 시 새 버전과 기존 Execution 참조 유지.
- 다른 이름의 검색 span에서 selector 적용, 빈 문서·누락 데이터의 NOT_EVALUABLE, Judge가 없는 경우 NOT_RUN.
- 두 실제 라이브러리의 결정론적 점수 및 reason 저장. 구조화 스텁 Judge를 DeepEval Answer Relevancy에 연결. Custom 범주형 Judge의 응답 스키마와 추가 변수 검증.
- 기존 및 신규 실행 재평가에서 AgentRunner 호출 0회. 버전 발행 후 과거 실험 결과 불변. 기준이 다른 비교 HTTP 409.
- 실제 HTTP Mock Agent 기반 A/B 케이스 매칭, 오류 격리와 단일 건 재시도, 워커 lease 만료 후 복구, 대기 건 취소.
- 인증 없는 접근 HTTP 401, 읽기 권한으로 변경 HTTP 403, 실제 PRD 호출 차단, 민감 키 마스킹.
- Phoenix REST 응답 스텁으로 버전 식별자·항목·참조 span에서 전체 Trace 연계, OpenInference 속성 정규화.

## 환경 제약

이 환경의 Docker 빌더는 TLS 검사 프록시를 사용합니다. 로컬 CA 번들을 BuildKit의 선택적 `build_ca` secret으로 제공해 빌드했습니다. 인증서나 자격증명은 이미지·저장소에 포함하지 않습니다. Docker의 VFS 드라이버 공간 제약으로 중간 빌드 캐시를 정리한 후 생성된 이미지에 `docker compose up --no-build --wait`를 실행했습니다.

실제 Phoenix·사내 GAIA STG·Judge 모델 접속 정보는 제공되지 않았습니다. 외부 실서버 통합, 실제 모델의 평가 품질과 비용, 사내 사용자별 권한 위임, 대용량 부하 성능은 확인 대상입니다. 실제 PRD 테스트는 수행하지 않았습니다.
