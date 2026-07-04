# SCALA TUI

SCALA: Security Canonical Alignment & Lineage Automation

## 개요

### SCALA 

이기종 보안 데이터를 OCSF 기준 문서로 정규화하고, 결과를 OpenSearch에 적재하며, 

적재된 문서에서 원본 문서까지 추적할 수 있는 lineage를 유지한다. 

사용자는 로컬 터미널에서 실행되는 TUI를 통해 Python JSON-RPC 백엔드와 Docker Compose 기반으로 실행한다.

## 주요 기능

- 소스 선택, 샘플 검토, 워크플로우 실행, 사용자 피드백, lineage 조회, 모니터링, 설정을 처리하는 Go Bubble Tea TUI.
- `127.0.0.1:8765`에서 TCP JSON-RPC로 노출되는 Python 백엔드.
- PostgreSQL, Redis, ChromaDB, OpenSearch, OpenSearch Dashboards, Elasticsearch, Kibana, Splunk, 백엔드 서비스를 함께 실행하는 Docker Compose 런타임.
- 개발 settings, OCSF 벡터 데이터, Elasticsearch 문서, Splunk 이벤트를 준비하는 seed 명령.

## 사전 준비 및 설치

- Go 1.24+
- Docker Compose v2를 포함한 Docker Engine
- `uv`
- Python 3.12+
- 스크립트 기반 TUI QA를 위한 `tmux`

## 사용법

### 초기 세팅

처음 실행하거나 데이터가 꼬였다고 판단되면 아래 순서로 깨끗한 환경을 만든다.
`docker-backend-clean`은 이 프로젝트 Compose 컨테이너와 이름 있는 볼륨을 삭제한다.

```bash
make docker-backend-clean
```

`.env.example`을 `.env`로 복사한 뒤 `OPENAI_API_KEY`를 설정한다. 
이 값은 `make docker-backend-secret` 단계에서 git이 추적하지 않는 Docker secret 파일로 복사되며, 
`docker compose config`나 git commit에 출력되지 않는다. 
기본 에이전트 모델은 `gpt-5.4-mini`이고, 에이전트별 비용 계산은 `.env`의 아래 1M 토큰당 단가를 사용한다. 
다른 모델을 쓰면 두 단가도 현재 OpenAI 가격에 맞게 함께 바꿔야 한다.

```env
SCALA_OPENAI_MODEL=gpt-5.4-mini
SCALA_OPENAI_INPUT_COST_PER_1M=0.75
SCALA_OPENAI_OUTPUT_COST_PER_1M=4.50
```

### SCALA 백엔드 실행

백엔드와 개발용 보안 데이터 저장소를 실행한다.

```bash
make docker-backend-build
make docker-backend-up
make docker-backend-init
make docker-backend-seed
```

각 명령의 역할은 다음과 같다.

- `docker-backend-build`: Python 백엔드 이미지를 빌드한다.
- `docker-backend-up`: PostgreSQL, Redis, ChromaDB, OpenSearch, OpenSearch Dashboards, Elasticsearch, Kibana, Splunk를 실행한다.
- `docker-backend-init`: PostgreSQL schema, 개발 settings, OCSF ChromaDB index를 준비하고 백엔드 JSON-RPC 서비스를 시작한다.
- `docker-backend-seed`: Elasticsearch 2개 index와 Splunk 2개 index에 예제 데이터를 넣는다. 기본 `COUNT=1000` 기준 각 index 별 Elasticsearch 500건, Splunk 500건이며, OpenSearch 적재 결과는 총 2000건이 되어야 한다.

### SCALA TUI 실행

TUI를 빌드하고 실행한다.

```bash
make build
SCALA_BACKEND_ADDR=127.0.0.1:8765 ./bin/scala-tui
```

TUI에서 `Collect & Normalize`를 선택한 뒤 아래 4개 소스를 선택해 파이프라인을
실행한다.

- Elasticsearch `scala-es-network`
- Elasticsearch `scala-es-endpoint`
- Splunk `main`
- Splunk `security`

실행 완료 화면에는 OpenSearch Dashboards 주소와 샘플 lineage `_id`가 표시된다.
`Lineage Viewer`에 해당 `_id`를 넣으면 원본 소스, index, doc id와 정규화 문서를 함께 확인할 수 있다. 
`Agent Monitoring`에서는 Orchestrator, Schema Profiler, Normalization, Validator 에이전트의 누적 토큰과 저장된 비용을 확인한다.

Docker Compose는 백엔드 JSON-RPC를 `127.0.0.1:8765`로 노출하고, 개발 콘솔은 아래 주소로 노출한다.

- Kibana: `http://127.0.0.1:5601`
- Splunk Web: `http://127.0.0.1:8000`
- OpenSearch Dashboards: `http://127.0.0.1:5602`

백엔드 없이 TUI fixture 화면만 확인하려면 아래처럼 실행한다.

```bash
SCALA_TUI_MOCK=1 ./bin/scala-tui
./scripts/qa-tui.sh
```

## 성능 지표 측정

PLANS.md 13번의 평가 지표 측정은 개발/수동 테스트 Compose와 분리된 `docker-compose.performance.yml`을 사용한다. Compose project 이름은 `scala-performance`이고, PostgreSQL, Redis, ChromaDB, OpenSearch, OpenSearch Dashboards, Elasticsearch, Kibana, Splunk 볼륨과 host port가 기존 `docker-backend-*` 환경과 다르다.

깨끗한 cold-cache 상태에서 시작하려면 먼저 performance 환경만 삭제한다.

```bash
make docker-performance-clean
```

성능 평가용 인프라와 백엔드를 준비한다.

```bash
make docker-performance-build
make docker-performance-up
make docker-performance-init
```

정답지가 있는 평가 dataset을 생성하고 Elasticsearch/Splunk 성능 평가 index에 적재한다. 
기본 `COUNT=1000`이면 Elasticsearch 총 1000건, Splunk 총 1000건 데이터가 생성된다.

```bash
COUNT=1000 make docker-performance-seed
```

성능 평가용 TUI/backend pipeline을 실행한다. 
performance Compose 백엔드는 `127.0.0.1:8875`로 노출된다.

```bash
make build
SCALA_BACKEND_ADDR=127.0.0.1:8875 ./bin/scala-tui
```

TUI에서 `Collect & Normalize`를 선택한 뒤 아래 4개 소스를 선택한다.

- Elasticsearch `scala-perf-es-network`
- Elasticsearch `scala-perf-es-endpoint`
- Splunk `scala_perf_web`
- Splunk `scala_perf_auth`

실행이 끝나면 Redis mapping cache와 PostgreSQL lineage metadata에서 actual 결과를 추출한 뒤 평가 지표를 계산한다.

```bash
make docker-performance-export
make docker-performance-evaluate
```

성능 평가용 콘솔은 아래 주소로 노출된다.

- Kibana: `http://127.0.0.1:5611`
- Splunk Web: `http://127.0.0.1:8010`
- OpenSearch Dashboards: `http://127.0.0.1:5612`

산출물을 로컬에서 확인하려면 backend volume의 dataset을 `.scala-performance-data/dataset` 으로 복사한다. 
다른 위치가 필요하면 `LOCAL_PERFORMANCE_DATASET_DIR`를 바꿔 실행한다.
`actual_results.json`은 `make docker-performance-export` 이후에 생기고,
`metrics.json`은 `make docker-performance-evaluate` 이후에 생긴다. 
두 파일까지 로컬에 가져오려면 두 명령을 실행한 다음 복사한다.

```bash
make docker-performance-copy-results
```

계산 대상 지표는 PRD 10장의 `Field Mapping Precision`, `Field Mapping Recall`, `Lineage Traceability`다. 산출물은 performance backend volume의 `/data/performance-dataset`에 저장된다. 
같은 dataset을 성능 평가용 Elasticsearch/Splunk index에 적재하므로, 
TUI/backend pipeline도 기존 개발 환경과 분리된 조건에서 실행할 수 있다.

- `elasticsearch/*.jsonl`, `splunk/*.jsonl`: 평가용 원천 데이터
- `answer_key.json`: field mapping과 lineage 정답지
- `actual_results.json`: 실행된 pipeline에서 추출한 실제 mapping/lineage 결과
- `metrics.json`: 계산된 평가 지표

## 설정

런타임 설정은 TUI 설정 화면에서 즉시 반영되며 백엔드 저장소에 유지된다.
환경변수는 서비스 엔드포인트와 기본 모델 값을 설정한다. 지원하는 값은 `.env.example`에서 확인할 수 있다.
