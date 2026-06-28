# 03. Agent Workflow (LangGraph)

Backend 파이프라인의 내부 구조다. `PRD.md`의 `7. 주요 워크플로우` mermaid를 LangGraph 그래프로 구현한다.

## 노드 매핑

7개 `Scala-Agent`를 그래프 노드로 둔다. LLM 노드 4개 + deterministic 노드 3개.

| 노드 | 종류 | 역할 (PRD/FRD) |
|---|---|---|
| Orchestrator | LLM | 진입/종료, 사용자 소통 중계(모든 user 채널 단독 소유) |
| Schema Profiler | LLM | 필드 프로파일 + **캐시 조회**(Redis) + 캐시 미스 시 OCSF 후보 조회(ChromaDB RAG) |
| Normalization | LLM | 매핑 Rule 생성 + 원본에 적용해 정규화 데이터 생성 |
| Validator | LLM | 정합성 검증. 미달 시 **human feedback** 유발, 수용 전 자가 재검증 |
| Load | deterministic | OpenSearch 적재, `_id`를 Lineage로 전달 |
| Caching | deterministic | 확정 매핑을 Redis에 저장 |
| Lineage | deterministic | 원본↔정규화 추적 메타데이터를 PostgreSQL에 저장 |

deterministic 3종은 LLM을 호출하지 않는다(토큰 0). 흐름·역할은 `4.agent-workflow-graph.md`·`PRD` mermaid와 일치.

## State 객체

그래프 노드 간 전달되는 공유 state(개념 스키마):

| 필드 | 내용 |
|---|---|
| `run_id` | 실행 식별자(`scala_runs`) |
| `selected_sources` | `[(solution, index)]` |
| `fields` | 원본 필드 목록(원본 source/index/doc 단위 처리에 필요한 메타 포함) |
| `profiles` | 필드별 프로파일 결과(캐시 히트 여부 포함) |
| `candidates` | 필드별 OCSF 후보(RAG 결과) |
| `mappings` | 필드별 확정 매핑(approve/keep_raw/rule) |
| `pending_feedback` | 현재 human feedback 대기 중인 필드(있으면 interrupt) |
| `normalized` | 정규화 문서들 |
| `load_result` | OpenSearch index·`_id` 목록 |
| `usage` | 노드별 토큰/비용 누적(`07-…`) |

## per-field 처리와 캐시 분기

매핑은 **필드 단위**로 처리한다. Schema Profiler가 필드별 cache key(`source_type+index+field+type`, `FRD`)로 Redis를 조회한다.

- **캐시 히트** 필드: 매핑 결정이 이미 확정 → **RAG/LLM 분석·Validator 검증·Human Feedback(PRD mermaid 4 이후 7~13)을 생략**하고 캐시된 매핑을 그대로 적용한다. (토큰 이코노미)
- **캐시 미스** 필드: RAG 후보 조회 → Normalization → Validator → (필요 시) Human Feedback → 확정.

```text
fields ─▶ Schema Profiler (per field)
            ├─ cache hit  ─────────────────────────────┐ (LLM/검증 생략)
            └─ cache miss ─▶ RAG ─▶ Normalization ─▶ Validator
                                                  │
                                      정합성 미달 ─┴─▶ Human Feedback(interrupt)
                                                  │
            확정 매핑 ◀───────────────────────────┘──────┘
              │
              ▼
        finalize rules ─▶ ┌ Load    ▶ OpenSearch
                          ├ Caching ▶ Redis (확정 매핑 저장)
                          └ Lineage ▶ PostgreSQL (_id 받아 메타 저장)
                                 └─▶ Orchestrator ▶ User (결과)
```

> 캐시 히트는 per-field 분기라 그래프에 별도 엣지로 그리지 않는다(PRD 주석과 동일). 구현상 필드 루프 안의 조건 분기다.

## Human feedback = LangGraph interrupt

- Validator가 정합성 미달로 판단하면 그래프를 **interrupt**하고, `pending_feedback`를 채운 채 checkpoint에서 멈춘다.
- Backend는 이를 `feedback.request`로 TUI에 보낸다(`02-…`). 사용자의 response(approve/keep_raw/comment)를 받아 **그래프를 resume**한다.
- `comment & re-review`는 재검토 후 갱신된 추천으로 다시 interrupt(= `feedback.request` 재발신).
- 수용 결정은 Validator가 **한 번 더 자가 검증**한 뒤 반영한다(`FRD` Validator).

## 종료 처리

- 전체 파이프라인 결과는 Load·Caching·Lineage 3종의 실행 결과를 Orchestrator가 종합해 도출한다(`FRD`).
- Orchestrator가 결과 요약 + OpenSearch 링크를 사용자에게 스트리밍(`output.chunk`).
- 실패 시 run 상태 전이·표면화는 `09-run-lifecycle.md`.
