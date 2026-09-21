# Contributing to Melovia

Thank you for your interest in contributing to Melovia! We welcome contributions that maintain our high standards of architectural isolation, determinism, security, and user agency.

---

## Architectural Principles & Standing Rules

Before submitting a pull request, ensure your contribution respects the core architectural boundaries detailed in [`AGENTS.md`](AGENTS.md) and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md):

1. **Pure Python Recommendation Engine (`api/app/recsys/*`)**:
   - Zero imports from web frameworks (`FastAPI`, `Starlette`) or databases (`SQLAlchemy`, `psycopg`).
   - Strict determinism: all pseudo-randomness must use explicit, seeded RNG instances; stable tie-breaking on `track_id`.
   - Independent testability for each stage: `taste`, `candidates`, `scoring`, `rerank`, `sequencing`, `explain`.
2. **LLM Boundary (`api/app/llm/*`)**:
   - LLMs output strictly schema-validated constraints over controlled vocabularies.
   - The LLM **never** selects or ranks tracks directly, **never** invents metadata, and **never** writes explanations ungrounded in ranking signals.
3. **Platform Adapters (`api/app/platforms/*`)**:
   - All external platform interactions live behind `PlatformAdapter`.
   - Zero platform data models leak into recommendation logic.
   - Zero token persistence; authentication tokens exist only in ephemeral session memory.
4. **Vector Catalog & 3D Visualization**:
   - Catalog data is stored in immutable, checksummed bundles.
   - **3D coordinates are visualization only**: all recommendation decisions operate on the true high-dimensional vectors.
5. **Security & Privacy**:
   - Never commit API keys, tokens, or credentials.
   - All client responses return structured error envelopes `{error: {code, message, request_id}}`; zero raw stack traces.
   - Client taste sharing and evaluation trials collect zero PII and zero persistent telemetry.

---

## Development Workflow

### Prerequisites
- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- Node.js 20+ and [pnpm](https://pnpm.io/)
- GNU Make or `mingw32-make` (Windows)

### Getting Started
```bash
# 1. Clone repository
git clone https://github.com/md-adil4106/Melovia.git
cd Melovia

# 2. Setup environment
cp .env.example .env

# 3. Generate deterministic mock catalog bundle
make make-mock

# 4. Run full quality suite
make check
```

### Development Servers
Run the API and Frontend concurrently:
```bash
# Terminal 1: FastAPI Backend
cd api && uv run uvicorn app.main:app --reload --port 8000

# Terminal 2: Next.js Frontend
cd web && pnpm dev
```

---

## Code Quality Standards

Every pull request must pass the automated quality suite without warnings:

```bash
# Backend checks
uv run --directory api ruff check .
uv run --directory api ruff format --check .
uv run --directory api mypy app
uv run --directory api pytest

# Frontend checks
pnpm --dir web lint
pnpm --dir web typecheck
pnpm --dir web test

# Recommendation regression gates
uv run --directory api python ../eval/runner.py --ci
```

Or simply run:
```bash
make check
```

### Commit Style
We adhere to [Conventional Commits](https://www.conventionalcommits.org/):
- `feat(recsys): ...`
- `fix(web): ...`
- `docs(ml): ...`
- `test(eval): ...`
- `refactor(platforms): ...`

---

## Questions & Discussions
For bugs or feature requests, please open an issue using the relevant [issue template](.github/ISSUE_TEMPLATE/).
