# ADR 003: Verifier-Guarded LLM Boundary & Structured Constraints

## Status
Accepted

## Date
2026-09-20

---

## Context
Generative LLMs are frequently misapplied in recommendation systems:
1. **Metadata Invention**: LLMs hallucinate non-existent songs, artists, or misattribute releases.
2. **Ungrounded Explanations**: LLMs generate plausible-sounding justifications for why a song was chosen that have zero correlation with the underlying ranking mathematical model.
3. **Black-Box Ranking**: Direct LLM ranking suffers from severe popularity bias, inability to enforce diversity constraints (like MMR), and non-deterministic behavior.

## Decision
We establish a strict, non-negotiable architectural boundary for LLM integration (`api/app/llm/*`):
1. **Schema-Validated Structured Constraints**: LLMs may only output structured JSON matching strict Pydantic schemas (e.g. `RefineConstraints`).
2. **Controlled Vocabulary**: Any genre, mood, or instrument tag produced by the LLM must map to a pre-defined controlled catalog vocabulary; ungrounded tags are stripped.
3. **Verifier Guard**: An automated verifier validates that requested scalar target shifts (e.g. `energy_idx`, `tempo_bpm`) fall within achievable mathematical bounds.
4. **Absolute Prohibitions**:
   - The LLM **never** selects, retrieves, or ranks tracks directly.
   - The LLM **never** invents metadata or track attributes.
   - The LLM **never** writes explanations that are not derived from ranking signals.

## Consequences
### Positive
- Zero risk of LLM hallucinations corrupting the catalog or recommendation feed.
- Explanations remain 100% faithful to the underlying mathematical scoring models.
- Graceful offline fallback: if LLM services are offline or unconfigured, an in-memory deterministic rule parser handles natural language prompts without system degradation.

### Negative
- Natural-language nuance is constrained to what the controlled vocabulary and scalar modifiers can express.
- Requires maintaining Pydantic schemas and verifier rules alongside prompt engineering.
