# SCALA TUI

SCALA : Security Canonical Alignment & Lineage Automation

## Description

SCALA normalizes heterogeneous security data from Elasticsearch and Splunk into
OCSF-aligned documents, loads them into OpenSearch, and keeps lineage back to the
raw source documents. The user experience is a host-run terminal UI backed by a
Python JSON-RPC service and Docker Compose infrastructure.

## Features

- Go Bubble Tea TUI for source selection, sample review, workflow execution,
  human feedback, lineage lookup, monitoring, and settings.
- Python backend exposed over TCP JSON-RPC on `127.0.0.1:8765`.
- Docker Compose runtime for PostgreSQL, Redis, ChromaDB, OpenSearch,
  OpenSearch Dashboards, Elasticsearch, Kibana, Splunk, and the backend service.
- Development seed commands for settings, OCSF vector data, Elasticsearch
  documents, and Splunk events.

## Prerequisite & Installation

- Go 1.24+
- Docker Desktop or Docker Engine with Compose v2
- `uv`
- `tmux` for scripted TUI QA

## 사용법

처음 실행하거나 데이터가 꼬였다고 판단되면 아래 순서로 깨끗한 환경을 만든다.
`docker-backend-clean`은 이 프로젝트 Compose 컨테이너와 named volume을 삭제한다.

```bash
make docker-backend-clean
```

`.env.example`을 `.env`로 복사한 뒤 `OPENAI_API_KEY`를 설정한다. 이 값은
`make docker-backend-secret` 단계에서 git ignore된 Docker secret 파일로 복사되며,
Compose config나 git commit에 출력되지 않는다. 기본 agent 모델은
`gpt-5.4-mini`이고, agent별 비용 계산은 `.env`의 아래 per-1M token 단가를 사용한다.
다른 모델을 쓰면 두 단가도 현재 OpenAI 가격에 맞게 함께 바꾼다.

```env
SCALA_OPENAI_MODEL=gpt-5.4-mini
SCALA_OPENAI_INPUT_COST_PER_1M=0.75
SCALA_OPENAI_OUTPUT_COST_PER_1M=4.50
```

백엔드와 개발용 보안 데이터 저장소를 실행한다.

```bash
make docker-backend-build
make docker-backend-up
make docker-backend-init
make docker-backend-seed
```

각 명령의 역할은 다음과 같다.

- `docker-backend-build`: Python backend 이미지를 빌드한다.
- `docker-backend-up`: PostgreSQL, Redis, ChromaDB, OpenSearch, OpenSearch
  Dashboards, Elasticsearch, Kibana, Splunk를 실행한다.
- `docker-backend-init`: PostgreSQL schema, 개발 settings, OCSF ChromaDB index를
  준비하고 backend JSON-RPC 서비스를 시작한다.
- `docker-backend-seed`: Elasticsearch 2개 index와 Splunk 2개 index에 복잡한
  예제 데이터를 넣는다. 기본 `COUNT=1000` 기준 Elasticsearch 1000건,
  Splunk 1000건이며, OpenSearch 적재 결과는 총 2000건이 되어야 한다.

TUI를 빌드하고 실행한다.

```bash
make build
SCALA_BACKEND_ADDR=127.0.0.1:8765 ./bin/scala-tui
```

TUI에서 `Collect & Normalize`를 선택한 뒤 아래 4개 source를 선택해 pipeline을
실행한다.

- Elasticsearch `scala-es-network`
- Elasticsearch `scala-es-endpoint`
- Splunk `main`
- Splunk `security`

실행 완료 화면에는 OpenSearch Dashboards 주소와 sample lineage `_id`가 표시된다.
`Lineage Viewer`에 해당 `_id`를 넣으면 원본 source/index/doc id와 정규화 문서를
함께 확인할 수 있다. `Agent Monitoring`에서는 Orchestrator, Schema Profiler,
Normalization, Validator agent의 누적 token과 저장된 비용을 확인한다.

Docker Compose는 backend JSON-RPC를 `127.0.0.1:8765`로 노출하고, 개발 콘솔은
아래 주소로 노출한다.

- Kibana: `http://127.0.0.1:5601`
- Splunk Web: `http://127.0.0.1:8000`
- OpenSearch Dashboards: `http://127.0.0.1:5602`

자주 쓰는 명령은 다음과 같다.

```bash
make docker-backend-config
make docker-backend-logs
make docker-backend-qa
COUNT=1000 make docker-backend-seed
make docker-backend-down
make docker-backend-clean
```

backend 없이 TUI fixture 화면만 확인하려면 아래처럼 실행한다.

```bash
SCALA_TUI_MOCK=1 ./bin/scala-tui
./scripts/qa-tui.sh
```

## Configuration

Runtime settings are hot-loaded through the TUI settings screen and persisted by
the backend. Environment variables configure service endpoints and model defaults;
see `.env.example` for the supported values.
