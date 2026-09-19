# Melovia API

FastAPI backend for Melovia (explainable, user-steerable music-discovery engine).

## Development

```bash
uv sync
uv run uvicorn app.main:app --reload
```

## Checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy app
uv run pytest
```
