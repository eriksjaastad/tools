.PHONY: build test lint clean

build:
	go build -o bin/claude-mcp-go ./cmd/server

test:
	go test ./...

lint:
	golangci-lint run

clean:
	rm -rf bin/
