# 07. LLM Provider & 토큰/비용 회계

LLM 호출을 추상화하고, 토큰·비용을 `scala_agent_usage`에 기록하는 방식을 정의한다.

## Provider 추상화

- LLM 노드(Orchestrator·Schema Profiler·Normalization·Validator)는 `LlmProvider` 인터페이스로만 호출한다.
- 현재 구현체: `OpenAiProvider`. 미래 provider는 인터페이스 구현으로 확장.
- **모델·단가는 `scala_settings`에서 로드**한다:
  - 모델: `agent.<agent>.model`
  - 단가: `model.<name>.price` = `{ "prompt_per_1k": …, "completion_per_1k": … }` (`RDB-TABLES.md`)
- API key는 `.env`에서 로드한다(`08-…`). TUI는 모델명만 표시(read-only).

## 토큰/비용 기록

`scala_agent_usage`는 **(run, agent) 1행**이고 7개 agent 전부 기록한다(`RDB-TABLES.md`).

- **기록 주체**: 각 agent 노드가 자신의 행을 쓴다. LLM 노드는 provider 응답의 usage(prompt/completion 토큰)를 누적해 노드 완료 시 기록한다.
- **no-LLM 3종**(Load·Caching·Lineage): 토큰 0·비용 0이지만 `last_activity`는 기록한다(예: "loaded 2,000 docs"). monitoring이 단일 쿼리로 7행을 표시하기 위함.
- **토큰 컬럼**: `prompt_tokens`·`completion_tokens`·`total_tokens`를 분리 저장(`RDB-TABLES.md`).
- **비용 계산**: `cost_usd = prompt_tokens × prompt_per_1k/1000 + completion_tokens × completion_per_1k/1000`. 단가는 기록 시점의 `scala_settings` 값.

> 기록은 **노드 완료 시점에 append**한다(런 끝 일괄 X). run이 중간 실패해도 그때까지의 사용량이 all-time 집계에 반영된다.

## 집계 (7.agent-monitoring)

- **Session**(현재 프로세스): 메모리 누적(State.`usage`). PG 미사용.
- **Today**: `scala_agent_usage.created_at`이 오늘인 행을 agent별 합산.
- **All-time**: 전체 행 agent별 합산.
- monitoring은 실시간이 아니라 `monitoring.query` 호출 시점 스냅샷이다(`FRD`/`7.agent-monitoring.md`).

> ⚖️ 판단 필요 — **`model.<name>.price`의 편집 위치.** 단가는 `scala_settings`에 있으나 `8.settings.md` mockup에는 단가 입력 행이 없다. `FRD` 175는 "settings 화면에서 설정 가능한 모든 값 = scala_settings 값"이라 충돌한다. 
> ① 단가도 Settings 화면에 편집 행 추가(일관) ② 단가는 개발 시 DB에 직접 시드하는 값으로 두고 `FRD` 175에 "단가는 예외(TUI 비노출)" 명시. 택1 필요.
