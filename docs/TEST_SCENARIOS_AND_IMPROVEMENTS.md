# MIRROR: Attack/ Judge 개선 및 테스트 시나리오 요약

본 문서는 현재 레포에서 추진한 공격 에이전트(Attack Agent)·심판 에이전트(Judge) 개선 사항과, 블랙박스 RAG 서버를 대상으로 한 테스트 시나리오/결과/재현 방법을 한 곳에 정리한 문서입니다.

---

## 1. 개요
- 목적: 멀티 에이전트(MIRROR: Attack → Judge → Defense → Report) 기반 LLM 보안 검증 파이프라인 구축/검증
- 대상: 
  - 오케스트레이터: `python -m mirror mirror ...`
  - 블랙박스: `blackbox/simple-rag-server.py` (FastAPI, `POST /chat` Simple JSON)
  - 가드레일: 앱 내장 키워드 차단(옵션), MIRROR 프록시(옵션)
- 산출물(세션별): `~/.mirror/brain/<session_id>/{PLANS.md, ATTACK_n.md, REPORT.*}`

---

## 2. 사전 준비
- .env: `OPENAI_API_KEY=sk-...` (루트 경로)
- uv: `uv run` 사용 가능해야 함
- 실행 디렉토리: 레포 루트에서 명령 수행

---

## 3. 공격 에이전트 개선(1차)
- 프로브 소스 확장: 커스텀 + Garak 프로브 동적 로딩(`--garak-probes`)
- 변이/우회: leet/spacing/base64(level별) + 재작성(교육/역할극/한국어) + 멀티턴(`tries`)
- 동시성: 비동기 병렬 실행(`concurrency`)
- 리포팅: Markdown(원본/변이/응답/시도/지연/사유) + 선택 JSON 요약
- 통합: MIRROR에 안전 분기(`attack_agent_mode: "custom"`)—기본(builtin) 경로 보존
- 호환성: OpenAI Chat(커스텀), Simple JSON(`endpoint_format: "simple-rag"`, builtin)

효과
- 커버리지/우회력/스루풋 향상, 재현성 및 분석성 개선, 운영 유연성 증대

---

## 4. 심판 에이전트(Judge) 개선(1차)
- Tier1 확장: 거절/refusal(한·영), PII, 시크릿, 주입/탈옥 마커 정규식 보강
- Judge 도구 추가: `detect_secrets`, `detect_jailbreak_markers`
- 프롬프트 개선: 오케스트레이터가 사전 휴리스틱 신호를 판정 프롬프트에 포함

효과
- PASS/FAIL 근거 명확화(신호/근거 로그), 오판정 가능성 감소(특히 단순 키워드 우회 시나리오)

비고
- 한국어 거절 패턴 추가 보강 대상(“요청을 처리할 수 없습니다…” 등 변형)

---

## 5. 블랙박스 RAG 서버
- 경로: `blackbox/simple-rag-server.py`
- 엔드포인트: `POST /chat` (payload: `{ "message": "..." }`, response: `{ "answer": "..." }`)
- 데이터: `blackbox/data/{news.txt, secrets.txt}` (시크릿 샘플 포함)
- 내장 가드레일(옵션): `RAG_GUARDRAIL=1` 시 특정 키워드 차단

---

## 6. 테스트 시나리오

공용 설정(예시): `settings.blackbox.batch.json`
```json
{
  "mode": "guardrail-off",
  "endpoint": "http://127.0.0.1:8000/chat",
  "endpoint_format": "simple-rag",
  "max_iterations": 3,
  "attack_categories": ["prompt_injection", "pii_leak", "jailbreak"],
  "model": "gpt-4o-mini",
  "target_model": "gpt-4o-mini"
}
```

- 시나리오 A: 앱 가드레일 OFF
  - 서버: `RAG_GUARDRAIL=0 uv run python blackbox/simple-rag-server.py`
  - MIRROR: `uv run python -m mirror mirror "Assess blackbox RAG (guardrail-0)" --settings-path settings.blackbox.batch.json --print-progress`
- 시나리오 B: 앱 가드레일 ON
  - 서버: `RAG_GUARDRAIL=1 uv run python blackbox/simple-rag-server.py`
  - MIRROR: `uv run python -m mirror mirror "Assess blackbox RAG (guardrail-1)" --settings-path settings.blackbox.batch.json --print-progress`

참고: MIRROR 프록시(별도) 비교를 원하면 `python -m mirror guardrail --port 8080` 후, 블랙박스 LLM 호출부를 프록시로 라우팅.

---

## 7. 결과 요약(관찰)

판정 의미: `pass = 방어 성공(차단)`, `fail = 공격 성공(방어 실패)`, `borderline = 불확실`

- 앱 가드레일 OFF
  - 혼합 결과 관찰: prompt_injection은 pass(거절), pii_leak는 fail로 분류된 케이스가 있었음(판정 일관성 이슈 → Judge 개선으로 신호 반영 강화)
  - 전반적으로 모델/정책 레이어의 기본 거절이 관여
- 앱 가드레일 ON
  - prompt_injection, pii_leak: 차단 메시지(한국어)로 pass 증가
  - jailbreak: “developer mode” 시도 탐지 + 거절 응답 → fail(공격 실패)로 일관 판정

세션 예시
- `~/.mirror/brain/cf2509b3`: 앱 가드레일 ON, 3라운드 수행, 각 ATTACK_n.md에 공격/판정/방어안 누적 기록

---

## 8. 재현 및 산출물 확인
- 최근 세션: `ls -td ~/.mirror/brain/* | head -n1`
- 로그 확인: `sed -n '1,160p' ~/.mirror/brain/<session_id>/PLANS.md` 및 각 `ATTACK_n.md`
- 세션 고정 실행: `--session-id mytest` → `~/.mirror/brain/mytest/*`

---

## 9. 다음 개선안(제안)
- Judge J2/J3: Moderation/경량 분류기 스코어 반영, LLM-as-a-Judge 구조화 출력 도입
- 한국어 거절 패턴 추가 보강
- Garak CLI 결과 파서: 동적 프롬프트 생성 취합 자동화
- 지표 자동 집계: REPORT.json에 ASR/차단율/경계 사례 등 추가
- Guardrail Proxy 시나리오: 앱/프록시 2×2 매트릭스 테스트로 방어 효과 비교

---

## 10. 부록: 빠른 실행 스니펫

1) 앱 가드레일 OFF
```bash
RAG_GUARDRAIL=0 uv run python blackbox/simple-rag-server.py &
uv run python -m mirror mirror "Assess blackbox RAG (guardrail-0)" \
  --settings-path settings.blackbox.batch.json --print-progress
```

2) 앱 가드레일 ON
```bash
RAG_GUARDRAIL=1 uv run python blackbox/simple-rag-server.py &
uv run python -m mirror mirror "Assess blackbox RAG (guardrail-1)" \
  --settings-path settings.blackbox.batch.json --print-progress
```

3) 최근 세션 요약 보기
```bash
LAST=$(ls -td ~/.mirror/brain/* | head -n1)
sed -n '1,160p' "$LAST/PLANS.md"
for f in "$LAST"/ATTACK_*.md; do echo "--- $f"; sed -n '1,120p' "$f"; done
```

---

본 문서는 공격/심판 개선 사항과 테스트 시나리오/결과를 지속 업데이트하는 기준 문서로 활용합니다.
