# Melovia Production Deployment & Operations Guide

This guide provides deployment recipes for hosting Melovia across modern cloud infrastructure (Vercel, Render / Fly.io, Neon / Supabase) and for self-hosting with Docker Compose.

---

## 1. Target Hosting Topology

```mermaid
flowchart LR
    Client["User Browser"] -->|HTTPS| Web["Next.js Frontend (Vercel)"]
    Client -->|API Calls (HTTPS / CORS)| API["FastAPI Backend (Render / Fly.io Docker)"]
    API -->|SSL Connection Pool| DB["PostgreSQL 16 (Neon / Supabase)"]
    API -->|Read-Only Local Storage| Bundle["Immutable Vector Bundle (/data/bundles/v1)"]
    API -.->|Ephemeral Memory| Spotify["Spotify Web API (OAuth PKCE)"]
```

---

## 2. Component Deployment Recipes

### 2.1 Next.js Frontend on Vercel
1. **Repository Link**: Connect the Melovia GitHub repository in the Vercel Dashboard.
2. **Root Directory**: Select `web`.
3. **Build Settings**:
   - Framework Preset: **Next.js**
   - Build Command: `pnpm build`
   - Output Directory: `.next`
   - Install Command: `pnpm install`
4. **Environment Variables**:
   - `NEXT_PUBLIC_API_URL`: The production URL of your backend API (e.g. `https://api.melovia.app`).
5. **CORS & Domain Verification**: Ensure the production Vercel domain (`https://*.vercel.app` or custom domain) is registered in the API's `CORS_ORIGINS`.

---

### 2.2 FastAPI Backend on Render or Fly.io (Docker)

The backend runs inside a container using [`api/Dockerfile`](../api/Dockerfile).

#### Option A: Render (Web Service)
1. **Create New Web Service**: Connect your repository and select `api` as root directory, using Environment: **Docker**.
2. **Instance Type**: Starter / Standard (at least 1 GB RAM recommended for vector catalog in-memory operations).
3. **Health Check Path**: `/health`
4. **Startup Command**: Handled by Dockerfile CMD:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

#### Option B: Fly.io (Fly Launch)
1. Launch from the `api/` directory:
   ```bash
   fly launch --dockerfile Dockerfile --name melovia-api --region ord --vm-memory 1024
   ```
2. Configure HTTP health check:
   ```toml
   [[services.http_checks]]
     interval = 15000
     timeout = 5000
     path = "/health"
   ```

---

### 2.3 PostgreSQL Database on Neon or Supabase
1. **Provision Database**: Create a PostgreSQL 16 project on [Neon](https://neon.tech) or [Supabase](https://supabase.com).
2. **Connection String**: Copy the pooled connection string with SSL mode enabled:
   ```
   postgresql+psycopg://user:password@ep-cool-db.us-east-2.aws.neon.tech/melovia?sslmode=require
   ```
3. **Run Migrations**: Apply Alembic schema migrations during deployment:
   ```bash
   cd api && uv run alembic upgrade head
   ```

---

## 3. Vector Catalog Bundle Distribution & Startup Checksum

Because vector catalog bundles (`data/bundles/v1/`) are immutable and checksummed, production containers should **not** bloat Git history with large binary files. Instead, fetch the bundle asset at startup:

### Automated Fetcher Script (`scripts/fetch_bundle.sh`)
```bash
#!/usr/bin/env bash
set -euo pipefail

BUNDLE_DIR="${CATALOG_BUNDLE_DIR:-/app/data/bundles/v1}"
BUNDLE_VERSION="v1"
BUNDLE_URL="https://github.com/md-adil4106/Melovia/releases/download/${BUNDLE_VERSION}/bundle-${BUNDLE_VERSION}.tar.gz"

if [ ! -f "${BUNDLE_DIR}/manifest.json" ]; then
  echo "[INFO] Fetching catalog bundle from ${BUNDLE_URL}..."
  mkdir -p "${BUNDLE_DIR}"
  curl -sSL "${BUNDLE_URL}" | tar -xz -C "${BUNDLE_DIR}"
fi

# Verify checksum against settings
python -c "
from app.config import get_settings
from app.recsys.catalog import CatalogStore
settings = get_settings()
print('[INFO] Validating catalog checksum...')
catalog = CatalogStore.load(settings.CATALOG_BUNDLE_DIR)
print(f'[INFO] Catalog loaded successfully: {catalog.track_count} tracks')
"
```

---

## 4. Environment Variables Reference

| Variable Name | Default / Example | Required in Prod? | Description |
| :--- | :--- | :---: | :--- |
| `ENV` | `production` | **Yes** | Sets runtime mode (enables secure cookies, disables Swagger doc debug). |
| `DEBUG` | `false` | **Yes** | Toggles verbose error logging (must be false in production). |
| `DATABASE_URL` | `postgresql+psycopg://...` | **Yes** | SQLAlchemy 2 async/sync connection string to PostgreSQL 16. |
| `API_HOST` | `0.0.0.0` | No | Server binding host. |
| `API_PORT` | `8000` | No | Server listening port. |
| `CORS_ORIGINS` | `https://melovia.app` | **Yes** | Comma-separated allowed frontend domains. |
| `CATALOG_BUNDLE_DIR` | `/app/data/bundles/v1` | No | Directory path containing unpacked catalog bundle. |
| `CATALOG_CHECKSUM` | `sha256:...` | No | Optional verification checksum for bundle `manifest.json`. |
| `STUDY_ADMIN_TOKEN` | `secret-bearer-token` | **Yes** | Bearer token required for `GET /study/export` CSV download. |
| `SPOTIFY_CLIENT_ID` | `...` | Optional | Spotify Developer App Client ID for OAuth PKCE export. |
| `SPOTIFY_CLIENT_SECRET`| `...` | Optional | Spotify Developer App Client Secret (never committed). |
| `GEMINI_API_KEY` | `...` | Optional | Google AI Studio key for conversational steering (rule fallback if unset).|

---

## 5. Health Checks & Observability

Melovia exposes two unauthenticated observability endpoints:

1. **`GET /health`**:
   - Response: `{"status": "ok", "app": "Melovia API", "version": "1.0.0"}`
   - Use: Basic liveness probe for load balancers and orchestrators.
2. **`GET /health/details`**:
   - Response: System health diagnostics including:
     - Catalog track count and loaded status.
     - Database connection state (healthy or degraded in-memory).
     - Resident memory usage (RSS/VMS via `psutil`).
     - Real-time p50 and p95 request latencies across recommendation endpoints.
   - Use: Detailed readiness inspection and monitoring dashboards.

---

## 6. Self-Hosted Production with Docker Compose

For on-premises or single-server VPS hosting, use [`docker-compose.prod.yml`](../docker-compose.prod.yml):

```bash
# 1. Populate production secrets
cp .env.example .env
nano .env

# 2. Build and launch production containers
docker compose -f docker-compose.prod.yml up -d

# 3. Verify health
docker compose -f docker-compose.prod.yml ps
curl http://localhost:8000/health
```

---

## 7. Cloud Costs & Free-Tier Guidance (2026 Terms)

| Provider | Service | Free-Tier Allowance | Operational Caveat |
| :--- | :--- | :--- | :--- |
| **Vercel** | Frontend Hosting | 100 GB bandwidth / mo | Serverless function execution limits; 3D chunk lazy-loaded. |
| **Render** | API Web Service | 750 free instance hours / mo | Spins down after 15 min inactivity; cold starts ~50s. Upgrade to Starter ($7/mo) for 24/7 uptime. |
| **Fly.io** | API Container | Up to 3 shared-cpu VMs (256MB) | Recommend allocating 1024MB RAM to hold vector catalog matrices comfortably in memory. |
| **Neon** | Postgres DB | 0.5 GiB storage, free compute | Compute auto-suspends after 5 min; Melovia's graceful DB fallback handles auto-wake delays without crashing. |
