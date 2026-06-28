# 04. 읽기 시나리오

agent 파이프라인을 돌리지 않는 조회 흐름이다. 모두 Backend의 **deterministic 핸들러**가 처리한다(LLM 없음). 진입은 `1.main`의 `View Results`(또는 `/`커맨드).

---

## Lineage 조회 (6.lineage-viewer)

**① 화면**: `_id` 입력 후 `enter` → 로딩 단계 표시(State D) → 원본 ↔ 정규화 결과(State B) 또는 not found(State C). 빈 입력 + `enter` → `1.main`.

**② IPC**:
```
TUI → Backend : lineage.lookup({ opensearch_id:"aZ12bQ8…" })
Backend ⇢ TUI : progress({ stage:"metadata",   status:"done" })
Backend ⇢ TUI : progress({ stage:"raw",         status:"fetching", target:"splunk·main" })
Backend ⇢ TUI : progress({ stage:"normalized",  status:"fetching" })
Backend ⇠ TUI : { found:true, metadata:{…}, raw_document:{…}, normalized_document:{…} }
```
not found이면 `{ found:false }`.

**③ 백엔드·store**: 핸들러가 `PG.scala_data_lineage_metadata`를 `opensearch_id`로 조회 → 메타의 원본 위치로 `Connector.fetch_raw_document`(ES/Splunk) → `OpenSearch`에서 정규화 문서 조회 → 셋을 합쳐 반환. **agent 미동작**. (`sw-architecture/05-data-store-access.md`)

## Agent Monitoring (7.agent-monitoring)

**① 화면**: scope(Session/Today/All-time)별 agent 표(model·last activity·tokens·cost) + 상단 Total. `←→`로 scope 전환, `enter` → main. 읽기 전용. 실시간 아님(호출 시점 스냅샷).

**② IPC**:
```
TUI → Backend : monitoring.query({ scope:"today" })
Backend ⇠ TUI : { scope:"today", as_of:"14:05",
                  total:{ tokens:842300, cost:1.94, last_run_id:"a1b2c3" },
                  agents:[ { agent:"orchestrator", model:"gpt-…", last_activity:"showed final result",
                             tokens:120400, cost:0.61 }, … ] }
```

**③ 백엔드·store**:
- `scope=session` → **Backend 메모리** 누적(현재 프로세스). PG 미사용.
- `scope=today` → `PG.scala_agent_usage`에서 `created_at`이 오늘인 행을 agent별 합산.
- `scope=all_time` → 전체 행 agent별 합산 + `scala_runs`로 run 수/first run.
- cost는 사용 기록 시점에 토큰 × `scala_settings.model.<name>.price`(백엔드 전용)로 계산돼 `scala_agent_usage.cost_usd`에 저장된다. Today/All-time은 저장된 `cost_usd`를 합산하고 Session은 메모리 누적값을 쓴다. no-LLM 3종은 0 + `last_activity`. (`sw-architecture/07-llm-provider-and-usage.md`)

> Session 정의(확정): 사용량은 LLM을 호출하는 **Backend**에 누적되므로 Session = **Backend 프로세스 기동 후**다. Backend가 상시 서비스(`sw-architecture/01-component-topology-and-stack.md` D1)라 여러 TUI 접속을 가로질러 누적되며, PoC에서 `docker compose up`으로 작업 세션을 여는 패턴이면 사실상 "이번 작업 세션"과 일치한다.

## Agent Workflow Graph 조회 (4.agent-workflow-graph · 뷰 모드)

**① 화면**: main에서 `/agent-workflow` → 흐름도 + 역할 + 모델. `enter` → main. (거의 정적)

**② IPC**: 그래프·역할은 정적이라 TUI가 자체 렌더링. **모델명만** `settings.get`의 `agents.<agent>.model`로 채운다. 별도 메서드 없음.

**③ 백엔드·store**: `settings.get` 외 없음.
