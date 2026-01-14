.PHONY: install dev test verify verify-e2e build run-docker clean help

# Default target
all: help

help:
	@echo "Available commands:"
	@echo "  make install       - Install dependencies using uv"
	@echo "  make dev           - Run the Purple Agent locally (port 9009)"
	@echo "  make test          - Run unit tests with pytest"
	@echo "  make verify        - Run health check (verify_purple.py)"
	@echo "  make verify-e2e    - Run simulated End-to-End flow (verify_e2e_flow.py)"
	@echo "  make curl-test     - Run independent curl test (test_curl.sh)"
	@echo "  make build         - Build Docker image"
	@echo "  make run-docker    - Run Docker container"
	@echo "  make check         - Run all verifications (install, test, verify, verify-e2e)"

install:
	@echo "Installing dependencies..."
	uv sync --extra test

dev:
	@echo "Starting Purple Agent locally..."
	uv run src/server.py --port 9010

test:
	@echo "Running unit tests..."
	uv run tests/run_tests.py

verify:
	@echo "Running health check..."
	uv run tests/simulation/sanity_check.py

verify-e2e:
	@echo "Running E2E simulation..."
	uv run tests/simulation/e2e_flow.py

curl-test:
	@echo "Running curl test..."
	./tests/simulation/test_curl.sh

simulate:
	@echo "Simulating assessment..."
	PARTICIPANT_URL=http://purple-agent:9009 uv run tests/simulation/assessment.py

check: install test verify verify-e2e simulate
	@echo "All verifications passed!"

build:
	@echo "Building Docker image..."
	docker build -t purple-agent .

run-docker:
	@echo "Running Docker container..."
	docker run -p 9010:9009 --env-file .env purple-agent

clean:
	rm -rf .venv
	rm -rf __pycache__
