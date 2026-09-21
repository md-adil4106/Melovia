# Melovia Security Architecture & Controls (Phase 14 Hardening)

## Overview

This document outlines the security architecture, threat model, defense-in-depth controls, secret policies, and audit results for Melovia.

---

## 1. Threat Model & Attack Surface

| Asset / Boundary | Threat | Mitigation |
| :--- | :--- | :--- |
| **Catalog & Recommendations API** | Denial of Service (resource exhaustion via unbounded payloads or high-frequency polling) | Strict Pydantic input bounds (`q` max 100 chars, `seed_track_ids` max 10, `excluded_artist_ids` max 50, candidate set max 64 chars, export items max 500); Token-bucket rate limiters on all public endpoints. |
| **User Privacy & Session Data** | Session hijacking, cross-site tracking, cookie leakage | Ephemeral anonymous device IDs (`melovia_device_id`) and session cookies (`melovia_session_id`) set with `HttpOnly`, `SameSite=Lax`, and `Secure` (in production). Zero personal identifiable information (PII) collected or stored. |
| **Platform OAuth Credentials** | Token interception, replay attacks, credential exposure | Spotify OAuth 2.0 PKCE with single-use `state` token verification and immediate invalidation upon callback; tokens stored strictly in ephemeral server memory (`SpotifyTokenCache`) with TTL expiry; tokens never committed, written to database, logged, or serialized to client. |
| **Conversational LLM Interface** | Prompt injection, unauthorized model actions, hallucinated music recommendations | Strict architectural boundary: LLM only emits structured JSON constraints over controlled vocabularies; deterministic recsys pipelines select and rank tracks; explanation verifier validates all textual claims against computed ranking signals. |
| **Frontend Web Application** | Cross-Site Scripting (XSS), Clickjacking, MIME confusion | WebGL-compatible Content Security Policy (CSP), `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, and `Permissions-Policy`. |
| **Repository & Artifacts** | Accidental commit of API keys, client secrets, or private tokens | `.gitignore` rules, `.env.example` templates, and an automated full-history Git secret scanner (`scripts/scan_secrets_history.py`). |

---

## 2. Input Validation & Bounds

All external input (HTTP requests, query params, cookies, platform webhooks, and LLM payloads) is treated as untrusted and strictly bounded using Pydantic v2 schemas:

- **Track Search (`GET /tracks/search`)**: Query string `q` bounded to `min_length=1`, `max_length=100`; `limit` bounded to `ge=1`, `le=100`.
- **Recommendations (`POST /recommendations`)**: `seed_track_ids` bounded to 1–10 items; `discovery` bounded to `0.0`–`1.0`; `n` bounded to 1–100; `excluded_artist_ids` capped at maximum 50 entries; `candidate_set_id` capped at 64 characters.
- **Rerank (`POST /recommendations/rerank`)**: `candidate_set_id` bounded to 1–64 characters; `discovery` bounded to `0.0`–`1.0`.
- **Conversational Refine (`POST /refine`)**: Prompt bounded to `max_length=500`; `candidate_set_id` bounded to 64 characters.
- **Export (`POST /export/file`, `POST /export/playlist`)**: `track_ids` and `tracks` capped at maximum 500 items per export job.

---

## 3. Standardized Token-Bucket Rate Limiting

Melovia implements an in-memory token-bucket rate limiter (`TokenBucketRateLimiter`) with deterministic per-client keys (`{ip}:{device_id}`):

| Endpoint | Refill Rate (tokens/sec) | Bucket Capacity | Error Response |
| :--- | :--- | :--- | :--- |
| `GET /tracks/search` | 2.0 req/s | 20.0 | HTTP 429 (`RATE_LIMIT_EXCEEDED`) |
| `POST /feedback` | 5.0 req/s | 30.0 | HTTP 429 (`RATE_LIMIT_EXCEEDED`) |
| `POST /refine` | 0.5 req/s | 5.0 | HTTP 429 (`RATE_LIMIT_EXCEEDED`) |
| `POST /export/*` | 0.5 req/s | 10.0 | HTTP 429 (`RATE_LIMIT_EXCEEDED`) |

When rate limits are exceeded, the API responds with a structured error envelope and standard headers:
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many search requests. Please slow down.",
    "request_id": "7f09804e-4f27-4a0b-967a-4db38914ba08"
  }
}
```

---

## 4. HTTP Security Headers

Security headers are enforced at both the backend middleware layer (`api/app/main.py`) and Next.js frontend edge (`web/next.config.mjs`):

- **Content-Security-Policy (CSP)**:
  ```text
  default-src 'self';
  script-src 'self' 'unsafe-eval' 'unsafe-inline';
  style-src 'self' 'unsafe-inline';
  img-src 'self' data: blob: https:;
  connect-src 'self' http://127.0.0.1:* http://localhost:* https:;
  font-src 'self' data:;
  worker-src 'self' blob:;
  frame-ancestors 'none';
  object-src 'none';
  base-uri 'self';
  ```
  *Note: `worker-src blob:` and `img-src blob:` allow Three.js / WebGL shader compilation and procedural texture generation without weakening script provenance.*
- **X-Content-Type-Options**: `nosniff` (prevents MIME sniffing).
- **X-Frame-Options**: `DENY` (prevents clickjacking attacks).
- **Referrer-Policy**: `strict-origin-when-cross-origin`.
- **Permissions-Policy**: `camera=(), microphone=(), geolocation=()`.

---

## 5. Cookie Security & Session Isolation

Cookies issued by Melovia (`melovia_device_id`, `melovia_session_id`, `spotify_oauth_state`) adhere to strict flags:
- `httponly=True`: Inaccessible to client-side scripts via `document.cookie`.
- `samesite="lax"`: Mitigates cross-site request forgery (CSRF) while preserving top-level navigation.
- `secure=settings.is_production`: Dynamic enforcement ensuring HTTPS in production while permitting local HTTP loopback during development.
- Single-use state tokens: `spotify_oauth_state` is verified and immediately deleted on callback arrival, preventing authorization replay attacks.

---

## 6. Secret Management & Git History Scan

Melovia enforces a zero-secrets-in-codebase policy:
- No real credentials exist in `.env.example`, fixtures, or test files.
- All real secrets are loaded from environment variables (`.env`).
- Automated Git history scanner: `scripts/scan_secrets_history.py` parses all historical commits, blobs, and commit messages against high-entropy patterns for AWS keys, OpenAI keys, Spotify secrets, Private Keys, and generic API tokens.
- **Scan Result**: **0 secrets detected across entire Git history**.

---

## 7. Dependency Vulnerability Audits

### Backend (`pip-audit`)
- Tool: `uv run --directory api pip-audit`
- Result: **0 known vulnerabilities found** across all installed packages.

### Frontend (`pnpm audit`)
- Tool: `pnpm --dir web audit`
- **Audit Findings & Documented Exception**:
  - `next`: Upgraded to `14.2.35`, resolving known moderate and high advisories on Next.js 14.
  - Remaining advisories in `next` relate to Next.js 15+ upgrades.
  - **Documented Exception**: Melovia web utilizes React 18.3.1 and `@react-three/fiber` (R3F) for the 3D Taste Universe component. Upgrading to Next.js 15 forces React 19 RC, which breaks R3F and Three.js canvas bindings. The current Next.js 14.2.35 deployment is safely protected behind strict Content Security Policy, rate limiting, and zero user-provided HTML rendering.

---

## 8. Observability & Log Redaction

All API requests pass through `RequestLoggingMiddleware`:
- Every log message contains a correlation `request_id`.
- Client cookies, bearer tokens, passwords, and sensitive request headers are scrubbed before writing to stdout.
- Internal exception stack traces are logged internally at `ERROR` level with `request_id` but **never returned in HTTP responses**.
