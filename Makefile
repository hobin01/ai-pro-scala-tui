DOCKER_COMPOSE ?= docker compose -f docker-compose.backend.yml
DOCKER_PERFORMANCE_COMPOSE ?= docker compose -p scala-performance -f docker-compose.performance.yml
COUNT ?= 1000
OPENAI_SECRET_FILE ?= .scala-data/secrets/openai_api_key
PERFORMANCE_DATASET_DIR ?= /data/performance-dataset
LOCAL_PERFORMANCE_DATASET_DIR ?= .scala-performance-data/dataset

.PHONY: fmt test race vet lint build run qa docker-backend-secret docker-backend-config docker-backend-build docker-backend-up docker-backend-init docker-backend-seed docker-backend-qa docker-backend-down docker-backend-clean docker-backend-logs docker-performance-config docker-performance-build docker-performance-up docker-performance-init docker-performance-seed docker-performance-export docker-performance-evaluate docker-performance-copy-results docker-performance-down docker-performance-clean docker-performance-logs

fmt:
	gofmt -w $$(find . -path './.git' -prune -o -name '*.go' -print)

test:
	go test ./...

race:
	go test -race ./...

vet:
	go vet ./...

lint:
	@if command -v golangci-lint >/dev/null 2>&1; then golangci-lint run ./...; else echo "golangci-lint not installed; run go vet ./... instead"; fi

build:
	mkdir -p bin
	go build -o bin/scala-tui ./cmd/scala-tui

run:
	go run ./cmd/scala-tui

qa:
	./scripts/qa-tui.sh

docker-backend-secret:
	@mkdir -p $$(dirname "$(OPENAI_SECRET_FILE)")
	@if [ -f .env ] && grep -q '^OPENAI_API_KEY=' .env; then \
		sed -n 's/^OPENAI_API_KEY=//p' .env | head -n 1 > "$(OPENAI_SECRET_FILE)"; \
	else \
		: > "$(OPENAI_SECRET_FILE)"; \
	fi
	@chmod 600 "$(OPENAI_SECRET_FILE)"

docker-backend-config: docker-backend-secret
	SCALA_OPENAI_SECRET_FILE="$(OPENAI_SECRET_FILE)" $(DOCKER_COMPOSE) config

docker-backend-build: docker-backend-secret
	SCALA_OPENAI_SECRET_FILE="$(OPENAI_SECRET_FILE)" $(DOCKER_COMPOSE) build backend

docker-backend-up: docker-backend-secret
	SCALA_OPENAI_SECRET_FILE="$(OPENAI_SECRET_FILE)" $(DOCKER_COMPOSE) up -d postgres redis chroma opensearch elasticsearch splunk kibana opensearch-dashboards

docker-backend-init: docker-backend-secret
	SCALA_OPENAI_SECRET_FILE="$(OPENAI_SECRET_FILE)" $(DOCKER_COMPOSE) run --rm backend scala-backend migrate
	SCALA_OPENAI_SECRET_FILE="$(OPENAI_SECRET_FILE)" $(DOCKER_COMPOSE) run --rm backend scala-backend seed-dev-settings
	SCALA_OPENAI_SECRET_FILE="$(OPENAI_SECRET_FILE)" $(DOCKER_COMPOSE) run --rm backend scala-backend ingest-ocsf
	SCALA_OPENAI_SECRET_FILE="$(OPENAI_SECRET_FILE)" $(DOCKER_COMPOSE) up -d backend

docker-backend-seed: docker-backend-secret
	SCALA_OPENAI_SECRET_FILE="$(OPENAI_SECRET_FILE)" $(DOCKER_COMPOSE) run --rm backend scala-backend seed-dev-data --count "$(COUNT)"

docker-backend-qa:
	uv run python scripts/qa_backend_rpc.py --addr 127.0.0.1:8765 --evidence .omo/ulw-loop/plans-10-11-impl/evidence/C002-backend-rpc.jsonl

docker-backend-down: docker-backend-secret
	SCALA_OPENAI_SECRET_FILE="$(OPENAI_SECRET_FILE)" $(DOCKER_COMPOSE) down

docker-backend-clean: docker-backend-secret
	SCALA_OPENAI_SECRET_FILE="$(OPENAI_SECRET_FILE)" $(DOCKER_COMPOSE) down -v --remove-orphans

docker-backend-logs: docker-backend-secret
	SCALA_OPENAI_SECRET_FILE="$(OPENAI_SECRET_FILE)" $(DOCKER_COMPOSE) logs -f backend

docker-performance-config: docker-backend-secret
	SCALA_OPENAI_SECRET_FILE="$(OPENAI_SECRET_FILE)" $(DOCKER_PERFORMANCE_COMPOSE) config

docker-performance-build: docker-backend-secret
	SCALA_OPENAI_SECRET_FILE="$(OPENAI_SECRET_FILE)" $(DOCKER_PERFORMANCE_COMPOSE) build backend

docker-performance-up: docker-backend-secret
	SCALA_OPENAI_SECRET_FILE="$(OPENAI_SECRET_FILE)" $(DOCKER_PERFORMANCE_COMPOSE) up -d postgres redis chroma opensearch elasticsearch splunk kibana opensearch-dashboards

docker-performance-init: docker-backend-secret
	SCALA_OPENAI_SECRET_FILE="$(OPENAI_SECRET_FILE)" $(DOCKER_PERFORMANCE_COMPOSE) run --rm backend scala-backend migrate
	SCALA_OPENAI_SECRET_FILE="$(OPENAI_SECRET_FILE)" $(DOCKER_PERFORMANCE_COMPOSE) run --rm backend scala-backend seed-performance-settings
	SCALA_OPENAI_SECRET_FILE="$(OPENAI_SECRET_FILE)" $(DOCKER_PERFORMANCE_COMPOSE) run --rm backend scala-backend ingest-ocsf
	SCALA_OPENAI_SECRET_FILE="$(OPENAI_SECRET_FILE)" $(DOCKER_PERFORMANCE_COMPOSE) up -d backend

docker-performance-seed: docker-backend-secret
	SCALA_OPENAI_SECRET_FILE="$(OPENAI_SECRET_FILE)" $(DOCKER_PERFORMANCE_COMPOSE) run --rm backend scala-backend seed-performance-data --count "$(COUNT)" --output-dir "$(PERFORMANCE_DATASET_DIR)"

docker-performance-export: docker-backend-secret
	SCALA_OPENAI_SECRET_FILE="$(OPENAI_SECRET_FILE)" $(DOCKER_PERFORMANCE_COMPOSE) run --rm backend scala-backend export-performance-results --output-dir "$(PERFORMANCE_DATASET_DIR)"

docker-performance-evaluate: docker-backend-secret
	SCALA_OPENAI_SECRET_FILE="$(OPENAI_SECRET_FILE)" $(DOCKER_PERFORMANCE_COMPOSE) run --rm backend scala-backend evaluate-performance-dataset --dataset-dir "$(PERFORMANCE_DATASET_DIR)"

docker-performance-copy-results: docker-backend-secret
	rm -rf "$(LOCAL_PERFORMANCE_DATASET_DIR)"
	mkdir -p "$(LOCAL_PERFORMANCE_DATASET_DIR)"
	SCALA_OPENAI_SECRET_FILE="$(OPENAI_SECRET_FILE)" $(DOCKER_PERFORMANCE_COMPOSE) run --rm --no-deps backend sh -c 'test -d "$(PERFORMANCE_DATASET_DIR)" && tar -C "$(PERFORMANCE_DATASET_DIR)" -cf - .' | tar -xf - -C "$(LOCAL_PERFORMANCE_DATASET_DIR)"

docker-performance-down: docker-backend-secret
	SCALA_OPENAI_SECRET_FILE="$(OPENAI_SECRET_FILE)" $(DOCKER_PERFORMANCE_COMPOSE) down

docker-performance-clean: docker-backend-secret
	SCALA_OPENAI_SECRET_FILE="$(OPENAI_SECRET_FILE)" $(DOCKER_PERFORMANCE_COMPOSE) down -v --remove-orphans

docker-performance-logs: docker-backend-secret
	SCALA_OPENAI_SECRET_FILE="$(OPENAI_SECRET_FILE)" $(DOCKER_PERFORMANCE_COMPOSE) logs -f backend
