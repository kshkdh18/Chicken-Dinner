The ultimate goal is to implement the MIRROR system.
Refer to the document/MIRROR_PLAN.md for the proposal.

# MIRROR Project: 신규 개발자 온보딩 가이드

MIRROR 시스템(자율 Red-teaming/Safety Testing) 개발 가이드문서. 
OpenAI Agents SDK 기반의 **Plan/Worker 오케스트레이터**, LlamaIndex Workflow 기반의 **MIRROR 플래너/공격·심판 엔진**을 함께 활용.

---

## 1. 시작하기

### 필수 요구 사항
- **Package Manager:** `uv`
- **Environment:** `.env` 파일에 `OPENAI_API_KEY` 설정

### 실행 방법
1. **일반 작업:** `uv run python -m mirror "목표"`
2. **MIRROR 실행:** `uv run python -m mirror mirror "목표" --settings-path settings.json`
3. **가드레일 프록시:** `uv run python -m mirror guardrail --rules-path [경로] --port 8080`

---

## 2. 핵심 개념

### Plan & Worker Loop
1. **Planner:** 목표 분석 및 `PLANS.md` 수립/업데이트.
2. **Worker:** 계획 실행 및 도구(Tools) 사용.
3. **Loop:** 단계 완료 후 Planner가 진행 상황 확인 및 재계획.

### Brain 저장소 (`~/.mirror/brain`)
- **Session ID:** 실행별 고유 ID (고정 가능).
- **주요 파일:** `PLANS.md`(계획), `ATTACK_n.md`(공격 로그), `REPORT.md`(결과), `guardrail_rules.json`(규칙).
- **주의:** 파일 접근 시 **절대 경로** 사용 권장.

---

## 3. 프로젝트 구조 (Code Map)

개발 시 주로 참고해야 할 핵심 모듈의 위치입니다.

### Core (기반 프레임워크)
*   `mirror/core/config.py`: 설정 관리 (`OrchestratorConfig`, `ApprovalMode` 등).
*   `mirror/core/orchestrator.py`: Plan/Worker 루프를 제어하는 메인 오케스트레이터.
*   `mirror/core/tools.py`: 파일 시스템 및 쉘 실행을 위한 기본 도구 모음.
*   `mirror/core/prompts.py`: 에이전트(Planner/Worker)용 시스템 프롬프트.
*   `mirror/core/models.py`: 기본 데이터 모델 정의.
*   `mirror/core/progress.py`: 진행 상황 출력 유틸리티.

### Storage (저장소 관리)
*   `mirror/storage/brain.py`: Brain 저장소 유틸리티 (`BrainStore`).
*   `mirror/storage/workspace.py`: 파일 접근 보안 및 워크스페이스 경계 관리.

### MIRROR System (Red-teaming 구현체)
*   `mirror/mirror_system/orchestrator.py`: MIRROR 에이전트 루프 진입점.
*   `mirror/mirror_system/planner.py`: LlamaIndex Workflow 기반의 특화된 플래너.
*   `mirror/mirror_system/settings.py`: MIRROR 전용 설정 로직.
*   `mirror/mirror_system/models.py`: MIRROR 데이터 모델 정의.
*   `mirror/mirror_system/tools.py`: 공격 및 로그 분석을 위한 전용 도구 (`mutate_attack_prompt`, `call_target` 등).

### Agents (에이전트)
*   `mirror/agents/attack_engine.py`: 동적 공격 생성 + Fan-Out + 다중 턴 공격 실행 엔진.
*   `mirror/agents/judge_engine.py`: Tier 1→2→3 계층 심판 파이프라인.
*   `mirror/agents/attack_library.py`: 공격 패턴 라이브러리.
*   `mirror/agents/attack_utils.py`: 공격 유틸리티 (변이, 호출 등).

### Defense (방어 시스템)
*   `mirror/defense/detectors.py`: 규칙 기반 탐지기 모음 (refusal/PII/prompt leak 등).
*   `mirror/defense/guardrail.py`: FastAPI 기반 가드레일 프록시 서버.
*   `mirror/defense/guardrail_rules.py`: 가드레일 규칙 관리.

### Analysis (분석 및 리포팅)
*   `mirror/analysis/reporting.py`: 지표 계산 및 OWASP/NIST 매핑 리포트 생성.
*   `mirror/analysis/white_box.py`: White-Box 스캔 및 시스템 프롬프트 업데이트 지원.

---

## 4. 주요 도구 (Tools)

- **기본:** `list_dir`, `read_file`, `write_file`, `edit_file`, `run_shell`
- **MIRROR:** `get_probe_prompts`, `mutate_prompt`, `call_target`, `append_attack_log`

---

## 5. 보안 정책

1. **Workspace 격리:** `workspace_root` 외부 접근 차단 (Brain 경로 제외).
2. **명령어 차단:** `rm -rf`, `sudo` 등 위험 명령 실행 거부.
3. **승인 모드:** `--approval-mode`로 작업 전 사용자 승인 강제 가능.

---

## 6. 주요 CLI 옵션

- `--print-progress`: 진행 상황 출력
- `--session-id [ID]`: 세션 고정 및 재사용
- `--model [MODEL]`: 모델 변경 (예: gpt-4o)
- `--approval-mode [MODE]`: 승인 단계 설정 (`confirm_shell` 등)

---

## 7. MIRROR settings.json 주요 옵션

- `attack_fanout`: 병렬 공격 시도 개수
- `attack_turns`: 다중 턴 공격 횟수
- `attack_variants`: 동적 공격 생성 시 후보 개수
- `dynamic_attacks`: 동적 공격 생성 활성화
- `mutation_methods`: 변이 방식 목록
- `mutation_rate`: 변이 적용 확률
- `white_box_path`: white-box 모드 시 코드 경로
