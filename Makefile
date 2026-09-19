.PHONY: all help dev check lint typecheck test clean api-check web-check api-lint api-typecheck api-test web-lint web-typecheck web-test

# Detect operating system
ifeq ($(OS),Windows_NT)
    PNPM ?= pnpm.cmd
    UV ?= uv
    PYTHON ?= python
else
    PNPM ?= pnpm
    UV ?= uv
    PYTHON ?= python3
endif

all: check

help:
	@echo "AMDE Build and Quality Targets:"
	@echo "  make check          - Run all quality checks (API + Web)"
	@echo "  make lint           - Run linting (ruff, eslint)"
	@echo "  make typecheck      - Run type checking (mypy, tsc)"
	@echo "  make test           - Run test suites (pytest, vitest)"
	@echo "  make dev            - Launch backend and frontend development servers"
	@echo "  make clean          - Remove caches and build artifacts"

check: api-check web-check
	@echo "=== All AMDE checks passed! ==="

lint: api-lint web-lint

typecheck: api-typecheck web-typecheck

test: api-test web-test

# API Targets
api-check: api-lint api-typecheck api-test

api-lint:
	$(UV) run --directory api ruff check .
	$(UV) run --directory api ruff format --check .

api-typecheck:
	$(UV) run --directory api mypy app

api-test:
	$(UV) run --directory api pytest

# Web Targets
web-check: web-lint web-typecheck web-test

web-lint:
	$(PNPM) --dir web lint

web-typecheck:
	$(PNPM) --dir web typecheck

web-test:
	$(PNPM) --dir web test

# Development servers
dev:
	@echo "Starting AMDE development servers..."
	@echo "In terminal 1 (API): cd api && uv run uvicorn app.main:app --reload --port 8000"
	@echo "In terminal 2 (Web): cd web && $(PNPM) dev"

# Clean artifacts
clean:
	rm -rf api/.pytest_cache api/.mypy_cache api/.ruff_cache
	rm -rf web/.next web/node_modules/.cache
