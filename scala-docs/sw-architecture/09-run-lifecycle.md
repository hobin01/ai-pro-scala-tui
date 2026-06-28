# 09. Run 생명주기 · 동시성 · 에러 경계

파이프라인 1회 실행(run)의 생명주기와, 단일 실행·에러 표면화 규칙을 정의한다.

## 단일 실행 (single-flight)

- 큐 시스템이 없다(`FRD`). in-flight 파이프라인은 항상 **최대 1개**.
- run 진행 중 새 `pipeline.run`이 오면 Backend는 **거부**(이미 실행 중 에러 반환). TUI는 애초에 실행 중 입력을 비활성화하므로 정상 경로에선 발생하지 않는다.
- 진행 중 사용자 입력은 **human feedback 요청 시에만** 활성(`5.human-feedback`/`02-ipc-json-rpc.md` 게이팅).

## run_id & 상태 머신

- `run_id`: `pipeline.run` 시작 시 UUID 생성. `scala_runs` 1행 생성(`status=running`, `started_at`, `selected_sources`).
- 상태 전이:

```text
running ──(정상 완료)──▶ completed   (finished_at, doc_count 기록)
   │
   └────(오류 발생)────▶ failed       (finished_at 기록, 에러 표면화)
```

- `completed` 시 `doc_count`(적재 문서 수)를 기록 → monitoring "loaded N docs"/run 집계 근거.
- `run.status` notification으로 TUI에 전이를 통지(`02-ipc-json-rpc.md`).

## 정상 흐름

1. `pipeline.run(sources)` → `scala_runs` running 생성, `run_id` 반환.
2. Connector로 원본 읽기 → per-field 매핑(캐시/RAG/검증/feedback, `03-agent-workflow-langgraph.md`).
3. finalize → Load(OpenSearch) · Caching(Redis) · Lineage(PostgreSQL).
4. 각 agent 노드가 `scala_agent_usage` 기록(`07-llm-provider-and-usage.md`).
5. Orchestrator가 결과 요약 + OpenSearch 링크 스트리밍 → `completed`.

## 에러 경계 (PoC)

프로덕션 복구·재시도 큐는 범위 밖(`AGENTS.md` 미래 목표). 다음만 보장한다.

| 실패 지점 | 표면화 |
|---|---|
| source 연결/조회 실패 | `3.data-samples` State D(연결 첫 표면화) 또는 run 중이면 run `failed` + 에러 라인 |
| OpenSearch 적재 실패 | run `failed`, 에러 표면화 |
| LLM 호출 실패 | run `failed`, 에러 표면화 |
| 필수 설정 누락 | `pipeline.run` 시작 전 검증 실패 반환(`08-config-and-secrets.md`) |

- 실패는 TUI 에러 라인(`✗`, `TUI-DESIGN.md`)으로 사용자에게 보인다.
- 부분 적재 상태의 자동 롤백/보정은 하지 않는다(범위 밖).

**부분 실패 처리 (확정 · all-or-nothing, 복구 코드 없음)**: 실패한 run은 통째로 **무효**다. run을 `failed`로 두고 에러를 표면화한 뒤 **멈춘다.** 롤백·정합 보정·재시도 같은 **복구/resilience 코드는 두지 않는다**(현재 scope 밖 — `AGENTS.md` 미래 목표). 사용자는 원인을 고쳐 **재실행**한다.

- 영속화(Load·Caching·Lineage)는 파이프라인 **마지막 단계**에 모아 수행한다(`03-agent-workflow-langgraph.md`). 따라서 매핑·검증·human feedback 등 앞 단계에서 실패하면 OpenSearch·PostgreSQL에 **아무것도 쓰이지 않아** 자연히 깔끔하다.
- 유일한 부분 적재 창은 **Load 도중**(대량 bulk 적재 중) 실패다. 이때 이미 적재된 일부 문서·부분 lineage는 **정리하지 않고 남긴다**(정리하려면 롤백 코드가 필요 — scope 밖). 재실행은 새 `run_id`로 동작하며, 깨끗한 상태가 필요하면 `docker compose`로 환경을 초기화한다(`PLANS` 12 수동 테스트 가이드와 동일).

## human feedback 중 블로킹

- feedback 대기 동안 그래프는 checkpoint에서 멈춘다(`03-agent-workflow-langgraph.md`). run은 여전히 `running`이며, TUI 입력은 그 동안만 활성.
- 사용자가 응답하면 resume. 모든 매핑 종료까지 반복.
