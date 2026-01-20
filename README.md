# 팀명
Chicken DInner

> **MIRROR**: Multi-agent Inspection & Red-team Response Orchestration Runtime system
>
> 멀티 에이전트 기반 자율 보안 검증 및 가드레일 최적화 시스템

## 데모

(데모 URL 또는 영상 링크)

## 문제 정의

생성형 AI 및 LLM의의 기업 도입이 가속화됨에 따라, GenAI가 가진 확률적이고 비결정론적인 특성으로 인한 보안 취약점(Jailbreak, Prompt Injection, PII Leak 등)이 심각한 위협으로 대두되고 있습니다.

특히 금융 및 핀테크와 같이 개인정보보호가 치명적인 산업군에서는 생성형 AI 도입에 대한 규제가 매우 엄격합니다. 금융권에서 LLM 서비스를 상용화하기 위해서는 매우 까다로운 보안 심사(Security Audit)를 통과해야만 하며, 최근 지능화된 해커들의 활동 증가와 빈번한 보안 사고는 기업들에게 실질적이고 즉각적인 위협이 되고 있습니다. 따라서 기업들은 단순한 기능 구현을 넘어 이러한 고도화된 위협에 대비해야 하는 필수적인 과제에 직면해 있습니다.

하지만 기존의 정적/동적 보안 테스트(SAST/DAST) 도구들은 LLM의 문맥 의존적인 취약점을 발견하는 데 한계가 있으며, 수동 레드티밍은 시간과 비용이 많이 소요됩니다. 또한, 발견된 취약점에 대해 실시간으로 방어 로직(Guardrail)을 수정하고 검증하는 통합된 자동화 프로세스가 부재하여 '공격-탐지-방어'의 루프가 단절되어 있는 실정입니다.



## 솔루션

**MIRROR (Multi-agent Inspection & Red-team Response Orchestration Runtime)** 는 공격, 방어, 심판, 리포트 역할을 수행하는 4종류의 전문 에이전트가 협업하여 LLM 시스템을 자동으로 진단하고 강화합니다.

1.  **지능형 공격 (Red Team)**: 오픈소스 보안 도구인 Garak의 로직을 에이전트화하여, 정적 프로브공격을 실행합니다. 또한 타겟 모델의 응답에 따라 진화하는 동적 공격(Adaptive Attack)을 수행합니다.
2.  **자율 방어 (Blue Team)**: 프록시 및 훅(Hook) 구조를 채택하여, 공격에 대응하는 입력 필터(Pre-call)와 출력 정화(Post-call) 로직을 실시간으로 생성 및 수정합니다.
3.  **객관적 심판 (Judge)**: 공격의 성공 여부를 결정론적 탐지기 및 LLM-as-a-Judge 를 통해 판정하고, 방어의 유효성을 검증합니다.
4.  **BRAIN & Iteration**: `PLANS.md`와 `ATTACK_n.md`를 통해 에이전트 간 정보를 공유하며, 시스템이 스스로 취약점을 학습하고 보안 수준을 높이는 적대적 공진화(Co-evolution)를 구현합니다.

## 조건 충족 여부

- [x] OpenAI API 사용 (공격 생성, 심판, 방어 코드 생성 등 전 에이전트 활용)
- [x] 멀티에이전트 구현 (Orchestrator, Red Team, Blue Team, Judge, Reporter)
- [X] 실행 가능한 데모 

## 아키텍처

MIRROR는 오케스트레이터의 통제 하에 4개의 에이전트가 `PLANS.md`와`ATTACK_n.md`으로 계획과 로그를 공유하고 협업하며 루프를 돕니다.

<img width="1931" height="1260" alt="mermaid-diagram-2026-01-20-175716" src="https://github.com/user-attachments/assets/20361fc0-6d57-42a3-8173-060f44f8d5a0" />

### 시나리오 모드
1.  **Mode A (가드레일 OFF)**: 순수 취약점 진단 및 리포팅
2.  **Mode B (가드레일 ON)**: 프록시 기반의 실시간 입출력 필터링 자동 적용
3.  **Mode C (White Box)**: 시스템 프롬프트 및 코드 레벨의 개선 제안
<img width="2106" height="1772" alt="mermaid-diagram-2026-01-20-175900" src="https://github.com/user-attachments/assets/b122de71-f3b4-4080-b7ba-9dfecc9e8b24" />
Mode A
<img width="2106" height="1772" alt="mermaid-diagram-2026-01-20-175941" src="https://github.com/user-attachments/assets/cf1ad27a-d358-4eb4-aea9-042311ffc81b" />
Mode B
<img width="2106" height="1772" alt="mermaid-diagram-2026-01-20-180013" src="https://github.com/user-attachments/assets/f0263b23-57ed-4979-9a4c-47be35fa63b1" />
Mode C

## 기술 스택
-   **OpenAI**: OpenAI GPT-5, OpenAI Agents SDK (Swarm)
-   **Backend**: Python, FastAPI
-   **Defense Logic**: Proxy & Hook Architecture
-   **Attack Logic**: Inspired by Garak (Probes & Detectors Logic)
-   **Workflow**: llama-index, Markdown based State Management (`PLANS.md`, `ATTACK_n.md`)

## 설치 및 실행

```bash
# uv 설치(if needed):
brew install uv

uv sync

# 타겟서버 실행
uv run python blackbox/simple-rag-server.py

# run streamlit
uv run streamlit run streamlit_app/app.py
```

## 향후 계획 
-   **공격 시스템 고도화**: 멀티모달(이미지, 오디오) 공격 및 방어 시나리오 추가, 다양한 정적 툴 추가
-   **적대적 훈련 (Adversarial Training)**: 공격 에이전트가 생성한 성공적인 탈옥 데이터를 모아 모델 미세조정(Fine-tuning)에 활용
-   시나리오 3 구현(white box)
-   proxy 고도화

## 팀원

| 이름 | 역할 |
| ---- | ---- |
| 김수호 | 프로젝트 총괄, 아키텍처 설계, 오케스트레이터 구현 |
| 김동현 | 공격(Red Team) 및 방어(Blue Team) 에이전트 로직, 프록시 서버, Streamlit 구햔 |


