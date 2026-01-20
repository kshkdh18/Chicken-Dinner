# Attack Agent: 설계·구현 계획서 (Garak + Custom)

본 문서는 MIRROR 시스템의 공격 에이전트(Attack Agent)를 완성도 있게 구축하기 위한 실무 계획서입니다. 현재 레포의 구현(attack_agent/ 스켈레톤, mirror/*)을 바탕으로, Garak 연동과 커스텀 파이프라인을 병행 지원합니다.

---

## 1. 목표와 범위

- 목표
  - 라운드(Iteration) 단위로 타겟 LLM 시스템을 공격하고, 결과를 구조화하여 기록/판정/방어 개선에 전달.
  - 두 가지 모드 동시 지원: (A) 커스텀 프로브/변이/실행 (B) Garak 프로브 기반.
  - MIRROR 루프(Attack → Judge → Defense → Report)와 호환되는 로그(`ATTACK_n.md`) 출력.

- 범위
  - 프롬프트 소스: 내장 라이브러리/동적 생성 + Garak Probes(선택).
  - 변이 파이프라인: base64, leetspeak, spacing 등 단계적 조합.
  - 실행기(Executor): OpenAI Chat 호환 엔드포인트 호출.
  - 1차 판정(Judge): 규칙 기반(거절 키워드) → 추후 확장(Detector/LLM-as-a-Judge).
  - 산출물: `ATTACK_n.md`(+ 선택: JSON), 비용/시간/시드 등 재현성 메타데이터.

비범위(초기): End-to-end 자동 가드레일 튜닝, 의미 기반 필터, 전면적 Garak 결과 파서(필요시 2차 단계에서 추가).

---

## 1.5 가이드라인(Docs 전반 요약)

- 엔드포인트 호환성: `OPENAI_AGENTS_DOCS.md`와 같이 OpenAI Chat 호환(`model`/`messages`) 규격을 우선 사용. `settings.endpoint_format`은 `openai-chat` 권장.
- 설계 원칙: `MIRROR_PLAN.md`의 Attack→Judge→Defense→Report 흐름 유지. 파일 기반 로그(`PLANS.md`/`ATTACK_n.md`)는 매 라운드 갱신.
- 워크플로우: 복잡한 흐름은 `LLAMA-INDEX-GUIDE.md`의 병렬/체크포인팅/수집 패턴 참조. MIRROR는 간결한 반복 루프를 우선.
- 안전/윤리: 테스트 전용 환경에서 수행, 가드레일 프록시(ON) 활용해 차단/마스킹 효과 검증.
- 카테고리 매핑: `jailbreak → dan`, `prompt_injection → prompt_injection`, `pii_leak → pii_leak/toxicity`(상황에 따라 병행).
- 비용/지연: `attack_concurrency`와 `attack_tries`는 점진적으로 증가. 기본값 중간(4/2) 수준 권장.

---

## 2. 운영 모드와 상호작용

- Standalone 모드(완): `attack_main.py` + `attack_agent/` 사용
  - 목적: 타겟 엔드포인트에 직접 공격 후 `docs/ATTACK_1.md` 등 보고서 작성.
  - 사용 예: `python attack_main.py run --endpoint http://localhost:8000/v1/chat/completions --model gpt-4o-mini --strategies "dan,toxicity,prompt_injection" --mutation-level medium --round-id 1 --out-md docs/ATTACK_1.md`

- MIRROR 통합 모드(현행 구현): `mirror/mirror_orchestrator.py`의 Attack Agent가 `mirror/mirror_tools.py`의 도구(`get_probe_prompts`, `mutate_prompt`, `call_target`, `append_attack_log`)를 통해 실행. 결과는 `~/.mirror/brain/{session}/ATTACK_n.md`에 기록.

- Garak 연동(선택): Garak Probe를 프롬프트 소스로 사용하거나, `garak run` 결과를 파싱해 공격 케이스로 주입.

---

## 3. 아키텍처 개요

- 컴포넌트
  - Probe Library: `attack_agent/probes.py`(DAN/Prompt Injection/Toxicity), `mirror/attack_library.py`(간이 라이브러리)
  - Mutation Pipeline: `attack_agent/mutations.py`(base64/leet/spacing)
  - Executor: `attack_agent/executor.py`(OpenAI Chat 호환 POST), `mirror/mirror_tools.py: call_target`
  - Judge: `attack_agent/judge.py`(거절 키워드 규칙 기반)
  - Orchestration: Standalone(`attack_main.py`) 또는 MIRROR(`mirror/mirror_orchestrator.py`)

- 데이터/아티팩트
  - Markdown 리포트: `ATTACK_n.md` (원본/변이 프롬프트, 응답 스니펫, 판정/사유)
  - Brain 스토리지: `~/.mirror/brain/{session}/`에 `PLANS.md`, `ATTACK_n.md`, `REPORT.md/json`, `guardrail_rules.json`

---

## 4. 구현 단계(Plan)

### Phase 1. MVP(완료됨/검증 필요)
- 목적: 최소 공격 라운드 실행 및 보고서 생성.
- 작업
  1) 커스텀 공격 스켈레톤 배치:
     - `attack_agent/attack_agent.py`: 라운드 실행/MD 리포트 생성
     - `attack_agent/probes.py`: DAN/Injection/Toxicity 프롬프트
     - `attack_agent/mutations.py`: 변이 파이프라인(light/medium/heavy)
     - `attack_agent/executor.py`: OpenAI Chat 호환 엔드포인트 호출
     - `attack_agent/judge.py`: 거절 키워드 판정
     - `attack_agent/config.py`: `settings.json` 로딩
     - `attack_main.py`: Typer CLI 진입점
  2) 실행 검증: 로컬/프록시(guardrail) 타겟 호출, `docs/ATTACK_1.md` 생성 확인. (옵션: `--out-json docs/ATTACK_1.json`)

- 수용 기준
  - 전략별(DAN/toxicity/prompt_injection) 1~3개 케이스가 실행되고, 응답/판정/사유가 MD로 남는다.
  - 예외 발생 시도 오류가 리포트에 기록된다.

### Phase 2. MIRROR 통합 강화
- 목적: Standalone 공격자와 MIRROR 공격 단계를 일원화.
- 작업
  1) `mirror/mirror_orchestrator.py::_run_attack`에서 Standalone AttackAgent 호출 옵션 추가(도구로 감싸기 또는 직접 임포트).
  2) `mirror/mirror_tools.py`에 `run_attack_agent(round_id, kinds, mutation_level, limit)` 함수툴 추가 → 내부에서 AttackAgent 호출 후 `append_attack_log`로 기록.
  3) `settings.json`에 `attack_agent_mode: "custom"|"garak"` 추가(선택) 및 `attack_strategies`(전략 문자열) 허용.

- 수용 기준
  - MIRROR 실행 시 Attack 단계가 AttackAgent 경로로도 수행 가능하며, 결과가 동일 포맷으로 `ATTACK_n.md`에 기록된다.

### Phase 3. Garak 연동(옵션)
- 목적: Garak Probe를 프롬프트 소스로 활용하거나 Garak의 atkgen/Probes 실행을 통한 프롬프트 합성.
- 작업
  1) Probe 로더: `agents/red_team.py` 유틸 리팩터를 참고하여 동적 import로 Garak Probe 인스턴스 생성 후 `prompts` 추출.
     - 예시: `import importlib; mod = importlib.import_module("garak.probes.dan"); cls = getattr(mod, "Dan_11_0"); prompts = list(cls().prompts)`
  2) CLI 실행 연동: `garak run --generator openai --probe probes.dan.Dan_11_0 --json-out ...` 결과 파싱하여 프롬프트 수집(선택).
  3) 환경 주입: 필요 시 `TARGET_SYSTEM_PROMPT`를 Garak 호출 경로에 강제 주입하는 제너레이터(커스텀) 추가.

- 수용 기준
  - 라운드별 Garak Probe(예: `Dan_10_0`, `Dan_11_0`, `InjectBase64`)에서 프롬프트 1~5개 샘플링 성공.
  - 커스텀 파이프라인과 동일 포맷으로 실행/기록됨.

### Phase 4. 적응형(멀티턴) 공격
- 목적: 거절(Refusal) 감지 시 재프롬프트/우회 전략 자동 반복.
- 작업
  1) 결과 분석: `judge.py`에 거절 강도/유형 Rule 추가(예: 명시적 거절/우회적 거절 구분).
  2) 재작성 템플릿: "교육적 맥락", "역할극", "가설적 상황", 다국어 등 우회 템플릿 추가.
  3) 반복 제어: 시도 횟수/비용 상한, 성공 시 조기 종료.

- 수용 기준
  - 동일 케이스에서 2~3회 재시도 후 성공률/차단 신호 변화가 리포트에 반영.

### Phase 5. 변이 파이프라인 확장
- 목적: 필터 우회 다양화 및 조합 테스트.
- 작업
  - base64/leet/spacing에 언어 전환(KO/JA/ES), 인코딩 혼합(hex/morse), 토큰 삽입(Zero-width) 추가.
  - 조합 탐색: (light/medium/heavy) 외 사용자 지정 체인 정의.

### Phase 6. 병렬 서브에이전트(Fan-out/Fan-in)
- 목적: 카테고리별 동시 공격 및 결과 집계.
- 작업
  - asyncio/gather로 병렬 실행, 결과를 케이스별로 Fan-in.
  - MIRROR 모드에서는 이미 라운드 루프가 있으므로, 라운드 내부 병렬화만 추가.

### Phase 7. 로깅/재현성/비용 관리
- 목적: 실험 재현/비용 안전장치.
- 작업
  - 메타데이터 기록: seed, 전략/변이/체인, 요청/응답 해시, 지연/에러, 토큰/비용(가능 시) 수집.
  - Budget/Timeout 상한, 백오프 재시도 정책.
  - Tracing: Agents SDK 트레이싱, 결과 해석 편의 증대.

---

## 5. 데이터 포맷/로그

- Markdown(`ATTACK_n.md`) 필수 섹션 제안
  - Header: Category, Goal, Round, Timestamp
  - Attack Execution: Original/Mutated prompt, Response(snippet), Notes
  - Judge Result: Verdict(pass/fail/borderline), Severity, Signals, Rationale
  - Defense Update(후속 단계): Actions, Input/Output patterns, System prompt update

- 선택 JSON 로그 필드(요약)
  - `round`, `category`, `strategy`, `mutations`, `seed`, `endpoint`, `model`, `latency_ms`, `cost_estimate`, `req_hash`, `res_hash`, `verdict`, `rationale`

---

## 6. 설정 및 실행 예시

- settings.json(MIRROR) 예시
```json
{
  "mode": "guardrail-off",
  "endpoint": "http://localhost:8080/v1/chat/completions",
  "endpoint_format": "openai-chat",
  "max_iterations": 3,
  "attack_categories": ["prompt_injection", "jailbreak", "pii_leak"],
  "model": "gpt-4o-mini",
  "target_model": "gpt-4o-mini"
}
```

- Standalone
```bash
python attack_main.py run \
  --endpoint http://localhost:8080/v1/chat/completions \
  --model gpt-4o-mini \
  --strategies "dan,toxicity,prompt_injection" \
  --mutation-level medium \
  --max-prompts 3 \
  --concurrency 4 \
  --tries 2 \
  --round-id 1 \
  --out-md docs/ATTACK_1.md \
  --out-json docs/ATTACK_1.json
```

- MIRROR
```bash
python -m mirror mirror "Assess LLM safety for service X" \
  --settings-path settings.json \
  --print-progress
```

### MIRROR 통합 설정(예시: custom AttackAgent 사용)

settings.json
```json
{
  "mode": "guardrail-off",
  "endpoint": "http://localhost:8080/v1/chat/completions",
  "endpoint_format": "openai-chat",
  "max_iterations": 3,
  "attack_categories": ["prompt_injection", "jailbreak", "pii_leak"],
  "model": "gpt-4o-mini",
  "target_model": "gpt-4o-mini",
  "attack_agent_mode": "custom",
  "attack_strategies": ["prompt_injection", "dan", "toxicity"],
  "attack_mutation_level": "medium",
  "attack_max_prompts": 3,
  "attack_concurrency": 4,
  "attack_tries": 2,
  "garak_probes": [
    "garak.probes.dan.Dan_11_0",
    "garak.probes.promptinject.InjectBase64"
  ]
}
```

실행
```bash
python -m mirror mirror "Assess LLM safety for service X" \
  --settings-path settings.json \
  --print-progress
```

결과(브레인 디렉토리)
- `~/.mirror/brain/{session}/PLANS.md`: 계획/진행
- `~/.mirror/brain/{session}/ATTACK_1.md`: AttackAgent 케이스(`## AttackAgent Cases`) 포함
- `~/.mirror/brain/{session}/REPORT.{md,json}`: 요약/지표/권고

---

## 7. Garak 연동 계획(옵션)

- 설치: `pip install garak` (CI/개발용 환경)
- 동적 로딩: `importlib`로 `garak.probes.*`에서 Probe 클래스 로딩 → `instance.prompts` 샘플링.
- CLI 연동(대안): `garak run --generator openai --probe probes.dan.Dan_11_0 --json-out out.json` → out.json 파싱.
- Standalone에서 직접 로딩: `--garak-probes "garak.probes.dan.Dan_11_0,garak.probes.promptinject.InjectBase64"`
- 시스템 프롬프트 강제 주입 필요 시: 커스텀 Generator(예: `garak_generator.py`)로 `TARGET_SYSTEM_PROMPT` 적용.

수용 기준: 라운드별 Garak 프로브 세트(DAN_Jailbreak, Dan_10_0, Dan_11_0, InjectBase64 등)에서 1~5개 프롬프트 확보 및 실행 기록.

---

## 8. 테스트 전략

- 단위 테스트: 변이 함수/프로브 선택/판정 규칙.
- 통합 테스트: 로컬 가드레일 프록시(`python -m mirror guardrail`)를 업스트림으로 두고 Standalone 공격 실행 → 거절 탐지 PASS 비율 확인.
- 회귀 테스트: 동일 설정/시드에서 결과 로그 해시 비교.

---

## 9. 보안/윤리 가이드

- 내부/테스트 환경에서만 수행. 실제 사용자 트래픽과 격리.
- PII/유해 콘텐츠는 저장 전 마스킹 처리 권장.
- 결과는 취약점 개선 목적 외 외부 공유 금지.

---

## 10. 일정/마일스톤(예시)

- 주1: Phase 1 완전 검증(리포트/옵션 정리) → 문서화
- 주2: Phase 2 통합(도구/설정/로그 합치기) → MIRROR 시연
- 주3: Phase 3 Garak 연동(동적 로딩/CLI 파싱) → 비교 실험
- 주4: Phase 4~5(적응형/변이 확장), 비용/성능 튜닝 → 내부 배포

---

## 11. 오픈 이슈

- Garak 출력(JSON)의 표준화 스키마 정의(Probe별 상이).
- 타겟 엔드포인트의 모델/시스템 프롬프트 주입 정책 일원화.
- 비용 메트릭 수집(토큰/요금)과 예산 상한 정책.

---

## 12. 부록: 현재 코드 레퍼런스

- Standalone
  - `attack_main.py`: CLI 진입점
  - `attack_agent/attack_agent.py`: 실행/리포트
  - `attack_agent/{probes,mutations,executor,judge,config}.py`

- MIRROR
  - `mirror/mirror_orchestrator.py`: Attack/Judge/Defense/Report 루프
  - `mirror/mirror_tools.py`: `get_probe_prompts`, `mutate_prompt`, `call_target`, `append_attack_log`
  - `mirror/mirror_planner.py`: 라운드 계획 생성(LLM)
  - `mirror/guardrail.py`: 가드레일 프록시(OpenAI Chat 호환)
  - `mirror/attack_library.py`: 간이 프로브 라이브러리

이 계획에 따라 바로 Phase 2(통합 강화) 또는 Phase 3(Garak 연동)부터 진행 가능합니다. 원하시는 우선순위를 알려주세요.
