# 09. Run 생명주기 · 동시성 · 에러 경계

파이프라인 1회 실행(run)의 생명주기와, 단일 실행·에러 표면화 규칙을 정의한다.

## 단일 실행 (single-flight)

- 큐 시스템이 없다(`FRD`). in-flight 파이프라인은 항상 **최대 1개**.
- run 진행 중 새 `pipeline.run`이 오면 Backend는 **거부**(이미 실행 중 에러 반환). TUI는 애초에 실행 중 입력을 비활성화하므로 정상 경로에선 발생하지 않는다.
- 진행 중 사용자 입력은 **human feedback 요청 시에만** 활성(`5.human-feedback`/`02-…` 게이팅).

## run_id & 상태 머신

- `run_id`: `pipeline.run` 시작 시 UUID 생성. `scala_runs` 1행 생성(`status=running`, `started_at`, `selected_sources`).
- 상태 전이:

```text
running ──(정상 완료)──▶ completed   (finished_at, doc_count 기록)
   │
   └────(오류 발생)────▶ failed       (finished_at 기록, 에러 표면화)
```

- `completed` 시 `doc_count`(적재 문서 수)를 기록 → monitoring "loaded N docs"/run 집계 근거.
- `run.status` notification으로 TUI에 전이를 통지(`02-…`).

## 정상 흐름

1. `pipeline.run(sources)` → `scala_runs` running 생성, `run_id` 반환.
2. Connector로 원본 읽기 → per-field 매핑(캐시/RAG/검증/feedback, `03-…`).
3. finalize → Load(OpenSearch) · Caching(Redis) · Lineage(PostgreSQL).
4. 각 agent 노드가 `scala_agent_usage` 기록(`07-…`).
5. Orchestrator가 결과 요약 + OpenSearch 링크 스트리밍 → `completed`.

## 에러 경계 (PoC)

프로덕션 복구·재시도 큐는 범위 밖(`AGENTS.md` 미래 목표). 다음만 보장한다.

| 실패 지점 | 표면화 |
|---|---|
| source 연결/조회 실패 | `3.data-samples` State D(연결 첫 표면화) 또는 run 중이면 run `failed` + 에러 라인 |
| OpenSearch 적재 실패 | run `failed`, 에러 표면화 |
| LLM 호출 실패 | run `failed`, 에러 표면화 |
| 필수 설정 누락 | `pipeline.run` 시작 전 검증 실패 반환(`08-…`) |

- 실패는 TUI 에러 라인(`✗`, `TUI-DESIGN.md`)으로 사용자에게 보인다.
- 부분 적재 상태의 자동 롤백/보정은 하지 않는다(범위 밖).

> ⚖️ 판단 필요 — **부분 실패 처리 정책.** 적재 도중 실패 시 ① run 전체를 `failed`로 두고 사용자가 재실행(현재 가정, all-or-nothing 지향) ② 적재된 부분은 유지하고 실패만 보고. PoC 기본은 ①을 권장하나, 이미 적재된 OpenSearch 문서/부분 lineage의 처리(남김 vs 정리)는 명시 확정이 필요하다.

## human feedback 중 블로킹

- feedback 대기 동안 그래프는 checkpoint에서 멈춘다(`03-…`). run은 여전히 `running`이며, TUI 입력은 그 동안만 활성.
- 사용자가 응답하면 resume. 모든 매핑 종료까지 반복.
