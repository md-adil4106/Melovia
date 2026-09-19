# AGENTS.md — Standing Rules (Melovia)
## Workflow
1. Inspect the repo first (tree, README, docs/, tests) and understand before changing. Use Planning mode; state a short plan; implement ONLY the requested phase.
2. Work incrementally: never rewrite working modules unnecessarily; reuse existing code; no duplicate implementations; every phase leaves the app runnable.
3. After meaningful changes run `make check`; start backend + frontend and verify integration. Never claim something works without running it.
4. Update docs touched by the phase. Small logical conventional commits. No force-push.
## Architecture boundaries
- api/app/recsys/*: pure Python (no FastAPI/DB imports), deterministic (seeded RNG, stable tie-breaks by track_id). Stages independently testable: taste, candidates, scoring, rerank, sequencing, explain.
- LLM code only in api/app/llm/*. LLM output = schema-validated structured constraints over controlled vocabularies. The LLM never selects/ranks tracks, never invents metadata, never writes explanations that are not derived from ranking signals.
- Platform code only in api/app/platforms/* behind PlatformAdapter (search_track, get_metadata, authenticate, create_playlist, add_tracks). No platform types leak into recsys.
- Catalog vectors live in an immutable, versioned, checksummed bundle (data/bundles/<version>/). Recommendation decisions use the high-dimensional vectors; 3D coordinates are visualization only.
- All external input (HTTP, LLM output, platform responses) is validated with Pydantic and treated as untrusted.
## Security & secrets
- Never hardcode or commit API keys, tokens, OAuth secrets, private keys or .env; only .env.example. Check .gitignore and scan the diff before every commit.
- No raw stack traces to users. Error envelope {error:{code,message,request_id}}. Log request_id, stage timings, counts; never tokens or personal data.
## Data & legal
- Only official APIs or openly licensed data. No scraping, no unofficial endpoints. Record each source, licence and retrieval date in docs/DATA_SOURCES.md.
## Quality
- Every algorithm gets unit tests plus a fixture-based determinism test. Budgets: POST /recommendations p95 < 400 ms and re-rank < 100 ms on the mock catalog; web first-load JS < 250 KB excluding the lazy 3D chunk. Accessibility: keyboard operable, visible focus, AA contrast, prefers-reduced-motion.
## Final report (mandatory, exact headings)
Implemented: / Changed files: / Tests run: / Validation performed: / Known issues: / Next recommended phase:
