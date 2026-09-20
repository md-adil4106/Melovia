.PHONY: all help dev check lint typecheck test clean api-check web-check api-lint api-typecheck api-test web-lint web-typecheck web-test make-mock seed-mock ingest-sample ingest-full dq-report build-bundle build-bundle-mock sanity-report demo-slider eval eval-ci

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
	@echo "Melovia Build and Quality Targets:"
	@echo "  make check          - Run all quality checks (API + Web)"
	@echo "  make lint           - Run linting (ruff, eslint)"
	@echo "  make typecheck      - Run type checking (mypy, tsc)"
	@echo "  make test           - Run test suites (pytest, vitest)"
	@echo "  make make-mock      - Generate deterministic mock catalog bundle"
	@echo "  make seed-mock      - Generate mock bundle and seed database"
	@echo "  make ingest-sample  - Ingest 5k sample real-world staging catalog"
	@echo "  make ingest-full    - Ingest full (up to 50k) staging catalog"
	@echo "  make dq-report      - Generate catalog data quality report"
	@echo "  make build-bundle   - Build versioned vector bundle from real catalog"
	@echo "  make build-bundle-mock - Build versioned bundle from mock catalog"
	@echo "  make sanity-report  - Generate neighbor sanity report and plots"
	@echo "  make dev            - Launch backend and frontend development servers"
	@echo "  make clean          - Remove caches and build artifacts"

make-mock:
	$(UV) run --directory api python ../fixtures/make_mock_catalog.py

seed-mock: make-mock
	$(UV) run --directory api python ../fixtures/seed_db.py

ingest-sample:
	$(UV) run --directory api python ../pipelines/ingest_catalog.py --sample 5000

ingest-full:
	$(UV) run --directory api python ../pipelines/ingest_catalog.py --full

dq-report:
	$(UV) run --directory api python ../pipelines/dq_report.py

build-bundle:
	$(UV) run --directory api python ../pipelines/build_features.py --catalog real --version v1

build-bundle-mock:
	$(UV) run --directory api python ../pipelines/build_features.py --catalog mock --version v1

eval:
	$(UV) run --directory api python ../eval/runner.py

eval-ci:
	$(UV) run --directory api python ../eval/runner.py --ci

sanity-report:
	$(UV) run --directory api python ../pipelines/sanity_report.py --bundle-dir ../data/bundles/v1

demo-slider:
	$(UV) run --directory api python ../pipelines/demo_slider.py




check: api-check web-check eval-ci
	@echo "=== All Melovia checks passed! ==="

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
	@echo "Starting Melovia development servers..."
	@echo "In terminal 1 (API): cd api && uv run uvicorn app.main:app --reload --port 8000"
	@echo "In terminal 2 (Web): cd web && $(PNPM) dev"

# Clean artifacts
clean:
	rm -rf api/.pytest_cache api/.mypy_cache api/.ruff_cache
	rm -rf web/.next web/node_modules/.cache
