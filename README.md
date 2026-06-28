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
  Elasticsearch, Splunk, and the backend service.
- Development seed commands for settings, OCSF vector data, Elasticsearch
  documents, and Splunk events.

## Prerequisite & Installation

- Go 1.24+
- Docker Desktop or Docker Engine with Compose v2
- `uv`
- `tmux` for scripted TUI QA

## Usage

Copy `.env.example` to `.env`, then set `OPENAI_API_KEY` if you want real OpenAI
LLM and embedding calls. The key is copied into an ignored Docker secret file by
`make docker-backend-secret`; it is not committed and is not printed by Compose
config.

```bash
make docker-backend-build
make docker-backend-up
make docker-backend-init
make docker-backend-seed
make build
SCALA_BACKEND_ADDR=127.0.0.1:8765 ./bin/scala-tui
```

The TUI runs on the host terminal. Docker Compose exposes only the backend JSON-RPC
port to `127.0.0.1:8765`; inside Compose the backend uses service DNS for
PostgreSQL, Redis, ChromaDB, OpenSearch, Elasticsearch, and Splunk.

Useful commands:

```bash
make docker-backend-config
make docker-backend-logs
make docker-backend-qa
COUNT=1000 make docker-backend-seed
make docker-backend-down
```

For fixture-only TUI checks without the backend:

```bash
SCALA_TUI_MOCK=1 ./bin/scala-tui
./scripts/qa-tui.sh
```

## Configuration

Runtime settings are hot-loaded through the TUI settings screen and persisted by
the backend. Environment variables configure service endpoints and model defaults;
see `.env.example` for the supported values.
