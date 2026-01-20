
# MIRROR 시스템 진단 보고서

## 1. 요약

현재 MIRROR 시스템은 **핵심 루프와 주요 기능이 구현**되어 있으며, 기획서(MIRROR_PLAN.md) 대비 **약 80~85% 수준**까지 진척되었습니다.

### 현재 상태
- ✅ 기본 Plan/Worker 오케스트레이터 구현 완료
- ✅ MIRROR 멀티 에이전트 루프 (Attack → Judge → Defense → Report) 구현 완료
- ✅ LlamaIndex Workflow 기반 Planner 구현 완료
- ✅ FastAPI 기반 가드레일 프록시 구현 완료
- ✅ 시나리오 모드 (A/B/C) 분기 적용 완료
- ✅ Sub-Agent 병렬 공격 (Fan-Out/Fan-In) 구현 (fan-out 방식)
- ✅ 동적 공격 생성 엔진 구현
- ✅ 계층적 심판 시스템 구현 (Tier 1→2→3)
- ✅ 표준화 매핑 (OWASP, NIST) 구현
- ❌ 의미론적 필터/분류기 연동, 스트리밍 훅, 히트맵 등 고급 기능은 미구현

---

## 2. 기획 대비 구현 상태 분석

### 2.1 오케스트레이터 (Planner) - ✅ 대부분 구현

| 기획서 요구사항 | 구현 상태 | 비고 |
|:--|:--:|:--|
| Plan/Worker Loop 구조 | ✅ | `orchestrator.py`, `mirror_orchestrator.py` |
| PLANS.md 동적 업데이트 | ✅ | `_write_plans()` 메서드 |
| ATTACK_n.md 파일 관리 | ✅ | `brain.py` + 각 에이전트 |
| 세션 ID 기반 Brain 저장소 | ✅ | `~/.mirror/brain/{session_id}` |
| LlamaIndex Workflow 활용 | ✅ | `mirror_planner.py` |

### 2.2 공격 에이전트 (Red Team) - ⚠️ 부분 구현

| 기획서 요구사항 | 구현 상태 | 비고 |
|:--|:--:|:--|
| 정적 프로브 라이브러리 | ⚠️ | 카테고리 확장 완료, 여전히 제한적 |
| Mutation Pipeline | ✅ | base64, rot13, spacing, leetspeak |
| call_target 도구 | ✅ | OpenAI-chat + 일반 형식 |
| **동적 공격 생성 (atkgen)** | ✅ | LLM 기반 prompt generator |
| **다중 턴 공격 전략** | ✅ | Refusal 기반 follow-up |
| **Sub-Agent 병렬 공격** | ✅ | Fan-Out 실행 (동시 시도) |

### 2.3 심판 에이전트 (Judge) - ⚠️ 부분 구현

| 기획서 요구사항 | 구현 상태 | 비고 |
|:--|:--:|:--|
| Refusal 탐지 (Regex) | ✅ | `detect_refusal()` |
| PII 탐지 | ✅ | `detect_pii()` |
| **계층적 심판 (Tier 1→2→3)** | ✅ | 규칙 → 키워드 → LLM 판정 |
| **분류기 기반 판정** | ⚠️ | 키워드 리스크 점수만 적용 (모델/외부 API 미연동) |
| **LLM-as-a-Judge CoT** | ❌ | Chain-of-Thought 추론 미구현 |

### 2.4 방어 에이전트 (Blue Team) - ✅ 기본 구현

| 기획서 요구사항 | 구현 상태 | 비고 |
|:--|:--:|:--|
| 입력 필터 패턴 추가 | ✅ | `input_denylists` |
| 출력 마스킹 패턴 추가 | ✅ | `output_redact_patterns` |
| **의미론적 필터 (벡터 유사도)** | ❌ | 미구현 |
| **시스템 프롬프트 수정 (White Box)** | ⚠️ | 스캔/업데이트 지원 (대상 파일 제한) |

### 2.5 가드레일 (Proxy) - ✅ 기본 구현

| 기획서 요구사항 | 구현 상태 | 비고 |
|:--|:--:|:--|
| FastAPI 기반 프록시 | ✅ | `guardrail.py` |
| Pre-call Hook (입력 필터) | ✅ | `_matches_any()` |
| Post-call Hook (출력 정화) | ✅ | `_redact()` |
| OpenAI SDK 호환 인터페이스 | ✅ | `/v1/chat/completions` |
| **During-call Hook (스트리밍)** | ❌ | 미구현 |

### 2.6 리포트 에이전트 - ⚠️ 부분 구현

| 기획서 요구사항 | 구현 상태 | 비고 |
|:--|:--:|:--|
| 기본 보고서 생성 | ✅ | REPORT.md, JSON 출력 |
| **OWASP LLM Top 10 매핑** | ✅ | 카테고리 매핑 및 리포트 반영 |
| **NIST AI RMF 매핑** | ✅ | 카테고리 매핑 및 리포트 반영 |
| **취약점 히트맵** | ❌ | 미구현 |

### 2.7 시나리오 모드 - ⚠️ 부분 구현

| 기획서 요구사항 | 구현 상태 | 비고 |
|:--|:--:|:--|
| Guardrail-OFF 모드 (시나리오 A) | ✅ | 방어 적용 없이 권고만 수행 |
| Guardrail-ON 모드 (시나리오 B) | ✅ | 가드레일 업데이트 반영 |
| **White-Box 모드 (시나리오 C)** | ⚠️ | 코드 스캔/프롬프트 업데이트 지원 (부분) |

---

## 3. LlamaIndex 직접 구현 검토

### 3.1 현재 의존성 현황

```toml
# pyproject.toml
dependencies = [
    "openai-agents>=0.6.9",          # OpenAI Agent SDK
    "llama-index-core>=0.14.12",     # LlamaIndex Core
    "llama-index-llms-openai>=0.6.13",
    ...
]
```

현재 시스템은 **OpenAI Agents SDK + LlamaIndex 하이브리드** 구조입니다:
- **오케스트레이터/에이전트**: `openai-agents` SDK 사용
- **Planner**: LlamaIndex Workflow 사용

### 3.2 LlamaIndex 전환 가능성 분석

| 항목 | OpenAI Agents SDK | LlamaIndex 직접 구현 |
|:--|:--|:--|
| **에이전트 정의** | `Agent(name, instructions, tools)` | `FunctionCallingAgent` + `QueryPipeline` |
| **도구 정의** | `@function_tool` 데코레이터 | `FunctionTool.from_defaults()` |
| **실행** | `Runner.run_sync()` | `agent.chat()` 또는 Workflow |
| **structured output** | `output_type=Pydantic` | `output_cls` 또는 후처리 |
| **안정성** | 최신 SDK (불안정 가능성) | 0.10+ 안정화됨 |

### 3.3 전환 권장 사항

> [!IMPORTANT]
> **LlamaIndex 직접 구현 권장**

#### 전환 이유:
1. **단일 프레임워크 통일**: 현재 하이브리드 구조는 복잡성을 높임
2. **안정성**: OpenAI Agents SDK는 아직 0.x 버전으로 API 변경 가능성 존재
3. **유연성**: LlamaIndex Workflow의 Fan-Out/Fan-In이 Sub-Agent 병렬 공격에 적합
4. **벤더 종속성 감소**: OpenAI 외 다양한 LLM Provider 지원

#### 전환 범위:
- `agents.Agent` → `llama_index.core.agent.FunctionCallingAgentWorker`
- `@function_tool` → `FunctionTool.from_defaults()`
- `Runner.run_sync()` → `agent_worker.as_agent().chat()`

---

## 4. 우선순위별 구현 로드맵

### Phase 1: 안정화 
1. LlamaIndex 직접 구현으로 전환 (OpenAI Agents SDK 제거)
2. 기존 테스트 케이스 작성 및 검증

### Phase 2: 핵심 기능 완성 
1. 시나리오 모드 (A/B/C) 완전 분리 ✅
2. 계층적 심판 시스템 구현 ✅
3. 동적 공격 생성 엔진 (atkgen) 구현 ✅

### Phase 3: 고급 기능 
1. Sub-Agent 병렬 공격 (Fan-Out/Fan-In) ✅
2. 의미론적 필터 (벡터 유사도)
3. 분류기 기반 판정 모델 연동
4. During-call Hook (스트리밍 가드레일)
5. 취약점 히트맵 시각화

---

## 5. 결론

| 평가 항목 | 점수 |
|:--|:--:|
| 기획 대비 구현율 | **80~85%** |
| 코드 안정성 | **중간~높음** (핵심 기능 구현 완료) |
| LlamaIndex 전환 가능성 | **높음** |
| 예상 전환 작업량 | **중간**  |

**권장 사항**: OpenAI Agents SDK 의존 구간(Plan/Worker)을 LlamaIndex로 통일하는 방향은 여전히 유효하며, 남은 고급 기능(의미론적 필터, 분류기, 스트리밍 훅, 히트맵)을 우선순위로 추가하는 것을 권장합니다.
