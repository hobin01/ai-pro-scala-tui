DOCKER_COMPOSE ?= docker compose -f docker-compose.backend.yml
COUNT ?= 1000
OPENAI_SECRET_FILE ?= .scala-data/secrets/openai_api_key

.PHONY: fmt test race vet lint build run qa docker-backend-secret docker-backend-config docker-backend-build docker-backend-up docker-backend-init docker-backend-seed docker-backend-qa docker-backend-down docker-backend-clean docker-backend-logs

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
	SCALA_OPENAI_SECRET_FILE="$(OPENAI_SECRET_FILE)" $(DOCKER_COMPOSE) up -d backend kibana opensearch-dashboards

docker-backend-init: docker-backend-secret
	SCALA_OPENAI_SECRET_FILE="$(OPENAI_SECRET_FILE)" $(DOCKER_COMPOSE) run --rm backend scala-backend migrate
	SCALA_OPENAI_SECRET_FILE="$(OPENAI_SECRET_FILE)" $(DOCKER_COMPOSE) run --rm backend scala-backend seed-dev-settings
	SCALA_OPENAI_SECRET_FILE="$(OPENAI_SECRET_FILE)" $(DOCKER_COMPOSE) run --rm backend scala-backend ingest-ocsf

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
