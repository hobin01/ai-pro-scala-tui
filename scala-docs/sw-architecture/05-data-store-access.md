# 05. 데이터 스토어 접근 설계

각 store를 **누가(어느 노드/핸들러)**, **언제**, **읽기/쓰기** 중 무엇으로 접근하는지 고정한다. 모든 접근은 Backend가 독점한다(TUI 직접 접근 없음).

## 접근 매트릭스

| Store | 접근 주체 | R/W | 시점 |
|---|---|---|---|
| **PostgreSQL** `scala_settings` | settings 핸들러 | R/W | `settings.get`/`settings.set` 시, run 시작 시(R) |
| `scala_runs` | run 매니저 | R/W | run 시작 시 생성, 종료 시 갱신; monitoring(R) |
| `scala_agent_usage` | 각 agent 노드(W) · monitoring 핸들러(R) | R/W | 노드 완료 시 W, `monitoring.query`(today/all-time) 시 R |
| `scala_data_lineage_metadata` | Lineage 노드(W) · lineage viewer 핸들러(R) | R/W | 적재 후 W, `lineage.lookup` 시 R |
| **Redis** cache | Schema Profiler(R) · Caching 노드(W) | R/W | 프로파일 시 조회, 정규화 확정 시 저장 |
| **ChromaDB** | 임베딩 적재기(W) · Schema Profiler(R) | R/W | 최초 1회 적재(`06-ocsf-rag-ingestion.md`), 캐시 미스 시 후보 조회(R) |
| **OpenSearch** | Load 노드(W) · lineage viewer 핸들러(R) | R/W | 적재 시 W, `lineage.lookup` 시 정규화 문서 R |
| **Elasticsearch / Splunk** | Connector(R) | R | 샘플(`3`), 파이프라인 읽기, lineage raw 조회 |

## 캐시 흐름 (Redis)

cache key = `source_type+index_name+field_name+field_type` (`FRD`, 입도 판단은 `04-siem-connector.md`).

```text
Schema Profiler ─ get(key) ─▶ Redis
   hit  → 캐시된 매핑 적용 (LLM/검증 생략)
   miss → RAG…Normalization…확정 ─ Caching 노드 ─ set(key, mapping) ─▶ Redis
```

- **조회는 Schema Profiler, 저장은 Caching 노드**로 역할이 분리된다. Normalization이 정규화를 확정한 필드만 저장한다(`FRD`).

## Lineage 흐름 (PostgreSQL ↔ OpenSearch ↔ source)

- 적재: Load 노드가 OpenSearch에 정규화 문서를 적재하고 `_id`를 Lineage 노드에 전달 → Lineage가 `scala_data_lineage_metadata` 1행/문서 저장(`source_solution/index/doc_id` ↔ `opensearch_index/_id` + `run_id`).
- 조회(`6.lineage-viewer`): 핸들러가 `opensearch_id`로 PG 메타 조회 → 메타의 원본 위치로 Connector raw 조회 → OpenSearch 정규화 문서 조회 → 셋을 함께 반환. **agent 미동작**(`FRD`).

## 일관성 / 트랜잭션 (PoC 범위)

- 단일 실행이라 동시 쓰기 경합이 없다. run 단위로 PG 쓰기를 처리한다.
- 부분 실패 시 run을 `failed`로 두고 표면화한다(복구·정합 보정은 범위 밖, `09-run-lifecycle.md`).
