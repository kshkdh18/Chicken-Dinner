# Quickstart: Blackbox Server + Chainlit UI

이 가이드는 블랙박스 RAG 서버를 띄우고, Chainlit UI에서 MIRROR/Attack 플로우를 직접 테스트하는 방법을 정리합니다.

## 0) 사전 준비
- .env 파일에 `OPENAI_API_KEY=sk-...` 설정(루트 경로)
- uv 설치되어 있어야 함(`uv --version`)

## 1) 블랙박스 RAG 서버 실행
- 가드레일 OFF(베이스라인):
```
RAG_GUARDRAIL=0 uv run python blackbox/simple-rag-server.py
```
- 가드레일 ON(키워드 차단):
```
RAG_GUARDRAIL=1 uv run python blackbox/simple-rag-server.py
```
- 포트 변경(선택):
```
uv run uvicorn blackbox.simple-rag-server:app --port 8001
```
- 동작 확인:
```
curl -sS -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"hello"}'
```

## 2) Chainlit UI 실행
- 환경변수로 경로 설정(권장):
```
export PYTHONPATH=$(pwd)
```
- 실행:
```
uv run chainlit run chainlit_app/app.py --host 127.0.0.1 --port 8100
```
- 브라우저에서 접속: http://127.0.0.1:8100

## 3) Chainlit에서 테스트
- 첫 메시지: 목표(Goal) 입력(예: "블랙박스 RAG 보안 취약점 평가 2회")
- 모드 선택:
  - MIRROR: Endpoint에 `http://127.0.0.1:8000/chat` 입력 → 공격→판정→방어 수행 후 세션 리포트(REPORT.md) 자동 생성/표시
  - Attack Only: OpenAI Chat 호환 endpoint(예: `http://127.0.0.1:8080/v1/chat/completions`)와 전략 목록(예: `dan,prompt_injection,pii_leak`) 입력 → 공격 요약 표시

## 4) 세션 산출물(자동)
- 브레인 디렉토리: `~/.mirror/brain/<session_id>/`
  - `PLANS.md`, `ATTACK_n.md`, `REPORT.md`

## 5) 문제 해결
- 401(키 오류): `.env` 키 값 확인 또는 `export OPENAI_API_KEY=sk-...`
- ModuleNotFoundError: `export PYTHONPATH=$(pwd)` 후 재실행
- 서버 503: `blackbox/data`의 문서 존재/권한 및 OpenAI API 호출 환경 확인

## 6) 스크립트(선택)
- 빠른 실행 스크립트 이용:
```
./scripts/run_blackbox.sh on   # guardrail ON (또는 off)
./scripts/run_chainlit.sh      # Chainlit UI 실행(포트 8100)
```

