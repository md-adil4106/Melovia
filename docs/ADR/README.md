# Architectural Decision Records (ADRs)

This directory records all major architectural decisions made in the Melovia project.

## Index of Decisions

- [ADR 001: Catalog Architecture Plan (Plan A vs Plan B Gate)](001-catalog-plan.md) — Accepted
- [ADR 002: Dual-Channel Orthogonal Representations (Semantic vs Acoustic)](002-dual-channel-recsys.md) — Accepted
- [ADR 003: Verifier-Guarded LLM Boundary & Structured Constraints](003-llm-verifier-guard.md) — Accepted
- [ADR 004: Framework-Agnostic Deterministic Recsys Core](004-pure-python-recsys.md) — Accepted
- [ADR 005: Client-Side Privacy, Ephemeral Sessions & Zero PII](005-client-privacy.md) — Accepted

---

## ADR Template

Each new record should follow this structure:

```markdown
# ADR [Number]: [Title]

## Status
[Proposed | Accepted | Superseded | Deprecated]

## Date
YYYY-MM-DD

## Context
What was the problem or motivation? What options were considered?

## Decision
What was decided and why?

## Consequences
What are the trade-offs, advantages, and risks of this decision?
```
