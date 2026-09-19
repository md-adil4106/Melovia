# MELOVIA

> **Melovia** is an explainable, user-steerable music-discovery engine.

## Stack Overview

- **Backend API**: FastAPI (Python 3.12, `uv`, Pydantic v2, SQLAlchemy 2, Alembic)
- **Database**: PostgreSQL 16 (*No Redis, no pgvector*)
- **Frontend Web**: Next.js 14+ (App Router, TypeScript, Tailwind CSS, `pnpm`)
- **Quality & Tooling**: `ruff`, `mypy`, `pytest` (API); `eslint`, `tsc`, `vitest` (Web); `pre-commit` (ruff + gitleaks); GitHub Actions CI

## Repository Layout

```
.
├── api/                  # FastAPI backend
│   ├── alembic/          # Database migrations
│   ├── app/              # Application logic
│   │   ├── config.py     # Pydantic-settings (DATABASE, LLM, PLATFORM, CATALOG, ENV)
│   │   ├── db/           # SQLAlchemy session and models
│   │   ├── errors.py     # Exception handlers returning {error: {code, message, request_id}}
│   │   ├── llm/          # Schema-validated constraints (no ranking/metadata invention)
│   │   ├── logging.py    # Structured JSON logging with request_id and latency
│   │   ├── main.py       # FastAPI application entrypoint
│   │   ├── platforms/    # External platform adapters (PlatformAdapter)
│   │   ├── recsys/       # Pure Python deterministic recsys pipeline
│   │   ├── routers/      # API endpoints (e.g. /health)
│   │   ├── schemas/      # Pydantic schemas
│   │   └── services/     # Business logic
│   └── tests/            # Pytest test suite
├── web/                  # Next.js App Router frontend
├── pipelines/            # Offline data pipelines
├── eval/                 # Evaluation scripts and benchmarks
├── fixtures/             # Test and determinism fixtures
├── data/                 # Immutable vector bundles (gitignored except data/README.md)
├── docs/                 # Documentation (ARCHITECTURE.md, DATA_SOURCES.md, ADRs)
├── docker-compose.yml    # PostgreSQL 16, api, and web definitions
├── Makefile              # Unified task runner (make check, make dev)
└── AGENTS.md             # Repository standing rules
```

## Quickstart

### Prerequisites

- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Node.js 20+ and [pnpm](https://pnpm.io/)
- Docker & Docker Compose (optional for PostgreSQL 16)
- GNU Make (or `mingw32-make` on Windows)

### 1. Setup Environment

```bash
cp .env.example .env
```

### 2. Run Checks

```bash
make check
```

This runs linting (`ruff`, `eslint`), typechecking (`mypy`, `tsc`), and test suites (`pytest`, `vitest`).

### 3. Run Development Servers

```bash
make dev
```

- API runs on [http://localhost:8000](http://localhost:8000) (Health check: `http://localhost:8000/health`)
- Web runs on [http://localhost:3000](http://localhost:3000)

## Architectural Guidelines

Refer to [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [AGENTS.md](AGENTS.md) for strict architectural boundaries, determinism requirements, and security guidelines.
