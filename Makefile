.PHONY: fmt test race vet lint build run qa

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
