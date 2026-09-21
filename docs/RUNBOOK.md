# Melovia Operations Runbook

## Overview

This operations runbook details operational procedures, local deployment commands, vector bundle management, health monitoring, and incident response procedures for Melovia.

---

## 1. System Components

```
                    ┌────────────────────────┐
                    │    Next.js Frontend    │
                    │  (Port 3000 / WebGL)   │
                    └───────────┬────────────┘
                                │ HTTP / REST
                                ▼
                    ┌────────────────────────┐
                    │    FastAPI Backend     │
                    │      (Port 8000)       │
                    └───────┬─────────┬──────┘
                            │         │
          In-Memory Bundles │         │ PostgreSQL 16 (or Degraded Memory)
                            ▼         ▼
        ┌─────────────────────┐     ┌──────────────────────┐
        │ Immutable Catalog   │     │ Melovia DB           │
        │ data/bundles/v1/    │     │ (Profiles, Feedback, │
        │ (Vectors, Regions)  │     │  Staging Tracks)     │
        └─────────────────────┘     └──────────────────────┘
```

---

## 2. Startup & Development Commands

### Prerequisites
- Python 3.12+ managed via `uv`
- Node.js 20+ managed via `pnpm`

### Environment Configuration
Copy `.env.example` to `.env` in the repository root:
```bash
cp .env.example .env
```

### Backend Startup
```bash
# From repository root:
uv run --directory api uvicorn app.main:app --reload --port 8000
```
Backend runs at: `http://127.0.0.1:8000`  
Interactive OpenAPI Docs: `http://127.0.0.1:8000/docs`

### Frontend Startup
```bash
# From repository root:
pnpm --dir web dev
```
Frontend runs at: `http://localhost:3000`

---

## 3. Database & Bundle Management

### Generate Deterministic Mock Bundle
If `data/bundles/v1` is missing, generate the mock vector bundle:
```bash
uv run --directory api python ../fixtures/make_mock_catalog.py
```

### Seed Local Database
```bash
uv run --directory api python ../fixtures/seed_db.py
```

### Rebuilding Regions & 3D Projections
When new tracks or feature changes occur:
```bash
# 1. Build statistical regions & tag-lift
uv run --directory api python ../pipelines/build_regions.py --bundle-dir ../data/bundles/v1

# 2. Compute deterministic 3D/2D layouts & neighborhood trustworthiness
uv run --directory api python ../pipelines/build_layout.py --bundle-dir ../data/bundles/v1
```

---

## 4. Monitoring & Telemetry (`GET /health/details`)

Melovia exposes an unauthenticated, zero-secrets health monitoring endpoint at `GET /health/details`.

### Sample Telemetry Response
```json
{
  "status": "ok",
  "version": "0.1.0",
  "database": "connected",
  "process_memory": {
    "rss_mb": 138.4,
    "vms_mb": 672.1
  },
  "telemetry": {
    "uptime_seconds": 1245.8,
    "total_requests": 2840,
    "status_codes": {
      "200": 2835,
      "429": 5
    },
    "endpoints": {
      "/recommendations": { "count": 1200, "p50_ms": 24.2, "p95_ms": 48.6, "mean_ms": 26.1 },
      "/universe": { "count": 450, "p50_ms": 38.1, "p95_ms": 82.4, "mean_ms": 42.0 }
    }
  },
  "catalog": {
    "mounted": true,
    "version": "v1",
    "track_count": 3000,
    "dim_t": 128,
    "dim_a": 128,
    "regions_count": 24
  },
  "cache": {
    "candidate_pools_cached": 85,
    "active_sessions": 14
  }
}
```

### Health Check Alerts
- `database == "degraded"`: The application is running in memory-only fallback mode. Recommendations and session feedback function, but persistent profiles are disabled.
- `process_memory.rss_mb > 1024`: Check for excessive candidate cache retention or unclosed connections.
- `telemetry.status_codes["500"] > 0`: Inspect application logs for the corresponding `request_id`.

---

## 5. Failure Modes & Incident Response

### Failure Mode 1: Database Unavailable / Connection Refused
- **Symptoms**: Startup log warning `Database unreachable at startup... Running in memory-only degraded mode.` Health endpoint returns `"database": "degraded"`.
- **Impact**: All recommendations, steerability, 3D universe exploration, and session feedback continue functioning normally. User feedback persists in memory for the active browser session. Only "Remember this vibe" persistent database profile writes will return 503 `DATABASE_UNAVAILABLE`.
- **Resolution**:
  1. Verify PostgreSQL container / service status.
  2. Check `DATABASE_URL` in `.env`.
  3. Ensure network connectivity between backend and database host.
  4. Once database connectivity is restored, restart the backend service.

### Failure Mode 2: Catalog Bundle Missing or Corrupt
- **Symptoms**: Startup log error `CatalogNotFoundError` or `CatalogCorruptError`. Health endpoint returns `"catalog": { "mounted": false }`. Recommendation endpoints return 503 `CATALOG_UNAVAILABLE`.
- **Resolution**:
  1. Inspect directory `data/bundles/v1/`. Verify presence of `manifest.json`, `vectors_t.npy`, `vectors_a.npy`, `tracks.parquet`, and `regions.json`.
  2. Regenerate bundle from fixtures:
     ```bash
     uv run --directory api python ../fixtures/make_mock_catalog.py
     ```
  3. Verify checksum matches `manifest.json`.

### Failure Mode 3: High Rate Limiting (429) Spikes
- **Symptoms**: Clients receive HTTP 429 `RATE_LIMIT_EXCEEDED` on `/tracks/search` or `/refine`.
- **Impact**: Rapid automated search polling or script abuse is throttled.
- **Resolution**:
  1. Advise frontend clients to implement debouncing ($\ge 250\text{ ms}$).
  2. If legitimate high-traffic needs adjustment, tune rate limiter capacity in `api/app/routers/tracks.py` (`TokenBucketRateLimiter(rate=2.0, capacity=20.0)`).

### Failure Mode 4: WebGL Crash / Context Lost in 3D Universe
- **Symptoms**: Browser tab runs out of GPU memory or WebGL context crashes.
- **Impact**: Handled automatically by `UniverseErrorBoundary`.
- **Behavior**: The error boundary catches the WebGL failure without crashing the application, displays a friendly notice (`"Interactive 3D view is temporarily unavailable on your graphics device"`), and automatically presents the 2D cluster map and accessible text region summaries.
- **User Action**: The user can click "Retry 3D Map" to attempt WebGL re-initialization or continue exploring in 2D mode.

### Failure Mode 5: Platform Token Expiry or External API Outage
- **Symptoms**: Spotify playlist export returns 401 `PLATFORM_UNAUTHORIZED` or 429 `PLATFORM_RATE_LIMIT`.
- **Resolution**:
  1. Melovia automatically displays the offline file export modal (CSV, JSPF, M3U, Text) so users can immediately download their playlist offline.
  2. For Spotify token expiry, prompt the user to re-authenticate via OAuth.
