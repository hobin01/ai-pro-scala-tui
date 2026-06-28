## RDB TABLES

Postgresql에서 사용할 RDB Table들의 설계 문서이다.

## 개요

- 본 문서는 SCALA가 PostgreSQL로 관리하는 영속 데이터의 **테이블 설계**를 정의한다.
- 데이터 소유(어떤 데이터를 어디에 저장하는지)는 `FRD.md`의 `#### SCALA 데이터 관리 요구사항` 매트릭스를 기준으로 하며, 본 문서는 그중 **PostgreSQL 4개 테이블**을 상세화한다.
- 단일 사용자 로컬 PoC 기준이다. 클러스터링·샤딩·파티셔닝·복구는 범위 밖이다.
- 실제 `CREATE TABLE` 등 DDL/마이그레이션 구현은 백엔드 개발(step 9)에서 수행한다. 본 문서는 컬럼·타입·제약·관계의 **설계 명세**만 다룬다.

### 테이블 목록

| 테이블 | 용도 |
|---|---|
| `scala_settings` | 가변 설정의 단일 출처 (agent 모델·프롬프트, 모델 단가, source url·index, opensearch url·index, 웹 콘솔 URL) |
| `scala_runs` | 파이프라인 실행(run) 단위 메타데이터 |
| `scala_agent_usage` | agent별 토큰·비용·마지막 작업 이력 |
| `scala_data_lineage_metadata` | 문서 단위 원본 ↔ 정규화 추적 메타데이터 |

### RDB가 아닌 데이터 (참고)

| 데이터 | 저장 위치 |
|---|---|
| source field → OCSF 매핑 cache | Redis |
| OCSF 표준 임베딩 (RAG) | ChromaDB |
| API Key·Password, 인프라/SIEM 접속·auth token 등 secret | `.env` |

> Normalization Rule 자체는 별도 영속 요구사항이 없다. 확정된 매핑 결정은 Redis cache가 보관하므로 RDB 테이블을 만들지 않는다.

## 공통 규약

- 모든 시각 컬럼은 `TIMESTAMPTZ`로 하며 UTC로 저장한다.
- 문자 인코딩은 UTF-8.
- 대리키는 `BIGSERIAL` 또는 `UUID`를 사용한다.

## 관계

```text
scala_runs (1) ──< (N) scala_agent_usage              [run_id]
scala_runs (1) ──< (N) scala_data_lineage_metadata    [run_id]
scala_settings  : 독립 테이블 (FK 없음)
```

`scala_runs`가 부모이며, `scala_agent_usage`·`scala_data_lineage_metadata`가 `run_id`로 이를 참조한다. `scala_settings`는 어떤 테이블도 참조하지 않는 독립 설정 저장소다.

---

## 1. scala_settings

가변 설정의 **단일 출처**다. Settings 화면(`8.settings.md`)에서 보이는 모든 값과 항상 동일하며, TUI·백엔드가 공통으로 읽는다. 미래 SIEM 확장과 hot-reload(키 단위 조회)를 위해 **Key-Value(JSONB)** 구조로 둔다.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `setting_key` | TEXT | PK | 점(`.`) 구분 네임스페이스 키 |
| `setting_value` | JSONB | NOT NULL | 스칼라·배열·객체 모두 허용 |
| `updated_at` | TIMESTAMPTZ | NOT NULL | 마지막 수정 시각 |

### 키 네이밍 규약

`<그룹>.<대상>.<속성>` 형태로 둔다. 그룹 접두사(`agent.`, `source.` 등)로 Settings 화면의 그룹을 그대로 구성한다.

| 키 패턴 | 값(JSONB) 예시 | 비고 |
|---|---|---|
| `agent.<agent>.model` | `"gpt-…-mini"` | LLM agent 4종(orchestrator, schema_profiler, normalization, validator) |
| `agent.<agent>.system_prompt` | `"You are …"` | LLM agent 4종 |
| `model.<name>.price` | `{ "prompt_per_1k": 0.15, "completion_per_1k": 0.60 }` | 모델별 단가(USD/1K tokens). 개발 시 공급사 홈페이지에서 단가 조사 후 입력 |
| `source.<solution>.url` | `"https://es-prod:9201"` | solution = elasticsearch, splunk |
| `source.<solution>.indices` | `["logs-2024", "firewall-idx"]` | 선택 가능 index 목록(배열). index 추가 = 배열 갱신 |
| `output.opensearch.url` | `"https://opensearch.local:9201"` | 정규화 결과 저장 대상 |
| `output.opensearch.index` | `"scala-normalized"` | 결과 index |
| `console.<name>.url` | `"https://kibana.local:5601"` | name = kibana, splunk, opensearch (웹 콘솔, 표시·열기용) |

### 페이지 고유 규칙

- **OpenAI API key는 이 테이블에 없다.** secret이므로 `.env`에서 관리하고 Settings 화면에는 read-only로 표시만 한다.
- `agent.<agent>.model`은 **LLM agent 4종만** 존재한다. no-LLM 3종(Load·Caching·Lineage)은 model이 없다.
- `model.<name>.price`는 `prompt_per_1k`·`completion_per_1k`를 분리해 둔다. 이는 `scala_agent_usage`의 분리 저장된 토큰 컬럼과 곱해 비용을 계산하기 위함이다.
- index 추가 등 hot-reload 항목은 행 갱신 즉시 다른 화면에 반영된다.

### 초기 상태

신규 설치 시 **빈 테이블**이다. 시드/기본 행 자동 주입은 하지 않는다. 사용자가 Settings 화면에서 직접 값을 채운다. (API key 등 secret은 `.env`로 별도 설정)

---

## 2. scala_runs

파이프라인 실행 1회 = 1행. monitoring·lineage가 공통으로 참조하는 `run_id`의 출처다.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `run_id` | UUID | PK | 실행 식별자. TUI에는 `#a1b2c3`처럼 축약 표시 |
| `status` | TEXT | NOT NULL | `running` / `completed` / `failed` |
| `selected_sources` | JSONB | NOT NULL | 이 run이 선택한 `(solution, index)` 목록 스냅샷 |
| `doc_count` | INT | | 적재된 정규화 문서 수 (monitoring "loaded 2,000 docs") |
| `started_at` | TIMESTAMPTZ | NOT NULL | |
| `finished_at` | TIMESTAMPTZ | | 완료 시각 (running이면 NULL) |

> monitoring의 "37 runs · since first run"은 본 테이블의 행 수·`started_at`으로 집계한다.

---

## 3. scala_agent_usage

agent별 토큰·비용·마지막 작업 이력. monitoring 화면의 표 단위에 맞춰 **(run, agent) 1행**으로 둔다. 이 grain으로 per-run·Today·All-time 집계를 모두 단일 쿼리로 처리한다.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `id` | BIGSERIAL | PK | |
| `run_id` | UUID | FK → `scala_runs.run_id` | |
| `agent` | TEXT | NOT NULL | orchestrator / schema_profiler / normalization / validator / load / caching / lineage |
| `model` | TEXT | | 사용된 **LLM 모델 종류** (예: `gpt-…-mini`). no-LLM agent는 NULL |
| `prompt_tokens` | INT | NOT NULL, default 0 | 입력 토큰 |
| `completion_tokens` | INT | NOT NULL, default 0 | 출력 토큰 |
| `total_tokens` | INT | NOT NULL, default 0 | 합계 토큰 (별도 컬럼으로 분리 저장) |
| `cost_usd` | NUMERIC | NOT NULL, default 0 | 비용(USD) |
| `last_activity` | TEXT | | 해당 agent의 최종 작업 이력 (예: "profiled 13 fields") |
| `created_at` | TIMESTAMPTZ | NOT NULL | Today 집계 기준 시각 |

### 페이지 고유 규칙

- **7개 agent 모두 행을 기록한다.** LLM 4종은 토큰·비용이 채워지고, no-LLM 3종(Load·Caching·Lineage)은 `prompt/completion/total_tokens = 0`, `cost_usd = 0`이되 `last_activity`는 채운다(monitoring이 "loaded 2,000 docs" 등을 단일 쿼리로 표시하기 위함).
- 집계 범위 매핑:
  - **Session**(현재 프로세스) = 메모리에서 계산. (본 테이블을 쓰지 않음)
  - **Today** = `created_at`의 날짜가 오늘인 행을 agent별 합산.
  - **All-time** = 전체 행을 agent별 합산.
  - **per-run** = `run_id`로 필터.
- 비용은 `prompt_tokens × model.<name>.price.prompt_per_1k + completion_tokens × completion_per_1k`로 계산해 `cost_usd`에 저장한다. no-LLM 3종은 항상 0이다.

---

## 4. scala_data_lineage_metadata

문서 단위 추적 메타데이터. **정규화 문서 1건 = 1행.** Lineage Viewer가 OpenSearch `_id` 단건으로 조회한다.

| 컬럼 | 타입 | 제약 | 설명 |
|---|---|---|---|
| `id` | BIGSERIAL | PK | |
| `run_id` | UUID | FK → `scala_runs.run_id` | 생성 run |
| `source_solution` | TEXT | NOT NULL | 원본 solution (elasticsearch / splunk) |
| `source_index` | TEXT | NOT NULL | 원본 index |
| `source_doc_id` | TEXT | NOT NULL | 원본 raw 문서 식별자 (예: `_bkt=…::host::1234`) |
| `opensearch_index` | TEXT | NOT NULL | 정규화 문서 저장 index (예: `scala-normalized`) |
| `opensearch_id` | TEXT | NOT NULL, index | OpenSearch `_id`. 조회 키 |
| `created_at` | TIMESTAMPTZ | NOT NULL | |

### 페이지 고유 규칙

- Lineage Viewer는 `opensearch_id` 단건으로 조회하므로 해당 컬럼에 인덱스를 둔다.
- 추적에 필요한 정규화 문서의 OpenSearch URL은 본 테이블이 아니라 `scala_settings`(`output.opensearch.url`)에서 가져온다.
- 필드 단위 추적은 범위 밖이다(문서 단위만).

---

## 설정 반영 방식

- `scala_settings` 변경은 **hot-reload**로 반영된다(컨테이너 재시작 불필요). 백엔드가 각 run 시작 시점에 현재 값을 읽어 연결을 구성하기 때문이며, 인프라 접속 정보는 `.env`에서 관리해 설정 변경이 재시작을 유발하지 않는다. 런타임 반영 메커니즘 상세는 `sw-architecture/`(step 7) 문서에서 다룬다.
