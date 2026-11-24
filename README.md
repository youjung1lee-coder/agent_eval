# GAIA 에이전트 평가 플랫폼

Phoenix에서 수집한 실행을 재평가하고, 같은 질문을 에이전트에 다시 보내 버전별 회귀를 찾는 독립 웹 앱입니다. React 18 · TypeScript · Vite, FastAPI, SQLAlchemy Core, Alembic, PostgreSQL 16을 사용합니다. DeepEval과 Ragas는 백엔드 프로세스에서 라이브러리로 실행합니다.

## 빠른 시작

Docker와 Compose 2.24 이상이 필요합니다. 프로젝트 루트에서 실행하세요.

```sh
cp .env.example .env
docker compose up --build
```

브라우저에서 [GAIA 워크스페이스](http://localhost:8000)를 엽니다. [OpenAPI](http://localhost:8000/docs)와 [상태 확인](http://localhost:8000/health)도 제공합니다. 첫 기동 시 DB 마이그레이션과 합성 정책 질문 20건, 기본 Evaluator 2개의 발행이 자동으로 진행됩니다. 로컬 Demo는 로그인 없이 사용합니다. 데이터는 PostgreSQL 볼륨에 유지됩니다.

평가결과 관리 → 평가 실행 → A/B 비교 평가 → **정책 응답 정확도** → 실험 시작을 선택하세요. 완료 후 비교하기를 누르면 같은 질문 20건 중 Mock PRD가 통과하고 Mock STG가 실패한 2건이 먼저 표시됩니다.

## 개발 환경에서 실행

Python 3.12와 Node 22 이상에서 다음 명령을 사용합니다. Docker 없이 실행할 때 기본 DB는 현재 디렉터리의 SQLite입니다.

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt -r requirements-metrics.txt -r requirements-dev.txt
(cd frontend && npm ci && npm run build)
export DEMO_MODE=true
python -m backend.serve
```

런처가 Alembic 적용과 시딩 후 API, DB 큐 워커, HTTP Mock Agent를 별도 프로세스로 실행합니다. API는 8000, Mock Agent는 루프백 8101을 사용합니다. 프런트엔드 개발 서버는 별도 터미널에서 `cd frontend && npm run dev`로 실행하세요. 워커 단독 실행 명령은 `python -m backend.worker`입니다. 기본 동시성은 워커당 한 케이스입니다.

## 테스트

```sh
(cd frontend && npm ci && npm run build && npm test)
python -m playwright install chromium
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests
```

시스템 Chromium이 있으면 자동 사용합니다. 다른 실행 파일은 `CHROMIUM_PATH`로 지정하세요. 브라우저 테스트는 임시 DB, HTTP 서버 두 개, 워커를 시작합니다. Docker 없이도 실행할 수 있습니다. Chromium이 없는 서버에서 백엔드만 검증하려면 `tests/test_platform.py`를 지정하세요.

## 실서비스 연결

`.env.example`에 변수명이 있습니다. Compose가 `.env`를 읽습니다. 직접 실행할 때는 프로세스 환경변수로 전달하세요.

| 서비스 | 설정과 계약 |
|---|---|
| 인증 | 실제 연결 시 `DEMO_MODE=false`, 편집자 `GAIA_API_KEY`, 필요 시 읽기 전용 `GAIA_READ_KEY`. 브라우저 접속 화면이나 HTTP Bearer 헤더로 전달합니다. 단일 워크스페이스의 서비스 키 방식입니다. |
| Phoenix | `PHOENIX_MODE=http`, `PHOENIX_URL`(서버 루트), `PHOENIX_PROJECT`, `PHOENIX_API_KEY`. `GET /v1/datasets`, 버전 및 examples 조회, 프로젝트 span 목록 페이지네이션을 사용합니다. |
| GAIA STG | `AGENT_MODE=http`, `STG_AGENT_URL`, `STG_AGENT_TOKEN`, `STG_ALLOWED_AGENT`. 이 저장소가 정의한 격리 게이트웨이 계약을 사내 API에 맞게 구현해야 합니다. 실제 PRD는 항상 차단합니다. |
| Judge | `JUDGE_URL`(OpenAI 호환 API 베이스, 예컨대 승인된 서버의 /v1), `JUDGE_KEY`, `JUDGE_MODEL`. 모델 기반 지표는 인증 모드에서만 활성화됩니다. 실제 모델 지원 여부와 데이터 반출 권한을 확인해야 합니다. |

실제 서버와 운영 데이터로 검증한 범위는 검증 문서에 기록합니다. 데모 DB와 실제 데이터 DB는 별도로 운영하세요. 악성 코드나 임의 SQL을 실행하는 규칙은 제공하지 않습니다.

- [화면별 사용법](docs/gaia-evaluation-user-guide.md)
- [아키텍처와 연동 계약](docs/gaia-evaluation-architecture.md)
- [테스트와 인수 검증](docs/gaia-evaluation-validation.md)
- [단계별 구현 상태](docs/implementation-status.md)
- [참조 자료](docs/gaia-evaluation-reference.md)
