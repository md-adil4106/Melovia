"""In-memory Session Store and Token-Bucket Rate Limiter for Melovia Refinement.

Architecture & Security Constraints:
- In-memory store with 2-hour TTL eviction.
- Keyed by session_id (anonymous UUID).
- Completely isolated from persistent profile databases.
- Token-bucket rate limiter per session ID and client IP.
- Removing constraints deterministically replays remaining constraints to prevent state drift.
"""

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field

import numpy as np
import numpy.typing as npt

from app.recsys.catalog import CatalogStore
from app.schemas.refinement import Refinement
from app.schemas.session import AppliedConstraint

logger = logging.getLogger(__name__)


@dataclass
class SessionContext:
    """Accumulated musical steering context for an active user session."""

    knobs: dict[str, float] = field(
        default_factory=lambda: {
            "energy": 0.0,
            "valence": 0.0,
            "tempo": 0.0,
            "acousticness": 0.0,
            "danceability": 0.0,
            "novelty": 0.0,
        }
    )
    popularity_ceiling: float | None = None
    boost_tags: dict[str, float] = field(default_factory=dict)
    suppress_tags: dict[str, float] = field(default_factory=dict)
    arc: str | None = None

    def is_empty(self) -> bool:
        """Return True if no steering constraints are currently active."""
        has_knobs = any(abs(v) > 0.001 for v in self.knobs.values())
        return not (
            has_knobs
            or self.popularity_ceiling is not None
            or self.boost_tags
            or self.suppress_tags
            or self.arc
        )

    def compute_context_vector(self, catalog: CatalogStore) -> npt.NDArray[np.float32]:
        """Compute context vector C = sum(w_t * v_t) - sum(w_s * v_s)."""
        dim_t = catalog.dim_t
        c_vec = np.zeros(dim_t, dtype=np.float32)

        for tag, weight in self.boost_tags.items():
            facet_v = catalog.get_tag_facet_vector(tag)
            c_vec += float(weight) * facet_v

        for tag, weight in self.suppress_tags.items():
            facet_v = catalog.get_tag_facet_vector(tag)
            c_vec -= float(weight) * facet_v

        # Normalize if non-zero
        norm = float(np.linalg.norm(c_vec))
        if norm > 1e-12:
            return np.asarray(c_vec / norm, dtype=np.float32)
        return c_vec


@dataclass
class SessionData:
    """Data container for an active anonymous session."""

    session_id: str
    context: SessionContext = field(default_factory=SessionContext)
    constraints: list[AppliedConstraint] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)


class TokenBucketRateLimiter:
    """Thread-safe token bucket rate limiter for refinement endpoints."""

    def __init__(self, rate: float = 0.5, capacity: float = 10.0) -> None:
        # rate: tokens added per second (0.5 = 30 tokens/minute)
        # capacity: burst maximum capacity (10 tokens)
        self.rate = rate
        self.capacity = capacity
        self._buckets: dict[str, tuple[float, float]] = {}  # key -> (tokens, last_time)
        self._lock = threading.Lock()

    def consume(self, key: str, tokens: float = 1.0) -> bool:
        """Attempt to consume tokens. Returns True if permitted, False if rate limited."""
        now = time.time()
        with self._lock:
            current_tokens, last_time = self._buckets.get(key, (self.capacity, now))
            # Replenish tokens based on elapsed time
            elapsed = max(0.0, now - last_time)
            replenished = min(self.capacity, current_tokens + elapsed * self.rate)

            if replenished >= tokens:
                self._buckets[key] = (replenished - tokens, now)
                return True
            else:
                self._buckets[key] = (replenished, now)
                return False


class SessionStore:
    """Thread-safe in-memory session manager with TTL eviction and constraint replaying."""

    def __init__(self, ttl_seconds: float = 7200.0) -> None:
        self.ttl_seconds = ttl_seconds
        self._sessions: dict[str, SessionData] = {}
        self._lock = threading.Lock()
        self._rate_limiter = TokenBucketRateLimiter(rate=0.5, capacity=10.0)

    def check_rate_limit(self, client_key: str) -> bool:
        """Check if request passes token bucket rate limit."""
        return self._rate_limiter.consume(client_key)

    def get_or_create(self, session_id: str | None = None) -> tuple[str, SessionData]:
        """Retrieve existing session or create a new anonymous session."""
        now = time.time()
        with self._lock:
            # Periodic cleanup
            self._cleanup_expired_locked(now)

            if session_id and session_id in self._sessions:
                session = self._sessions[session_id]
                session.last_accessed = now
                return session_id, session

            # Generate new session ID
            new_id = (
                session_id.strip()
                if session_id and session_id.strip()
                else f"sess_{uuid.uuid4().hex}"
            )
            new_session = SessionData(session_id=new_id, created_at=now, last_accessed=now)
            self._sessions[new_id] = new_session
            return new_id, new_session

    def get(self, session_id: str) -> SessionData | None:
        """Retrieve existing session or None if not found or expired."""
        now = time.time()
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return None
            if now - session.last_accessed > self.ttl_seconds:
                del self._sessions[session_id]
                return None
            session.last_accessed = now
            return session

    def apply_refinement(
        self,
        session_id: str,
        refinement: Refinement,
        utterance: str,
    ) -> list[AppliedConstraint]:
        """Apply a Refinement to session context and return updated active constraint list."""
        now = time.time()
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                session = SessionData(session_id=session_id, created_at=now, last_accessed=now)
                self._sessions[session_id] = session

            session.last_accessed = now
            new_constraints: list[AppliedConstraint] = []

            # 1. Scalar Knob Constraints
            for knob_name, delta in refinement.knobs.model_dump().items():
                if abs(delta) > 0.001:
                    # Formulate human label
                    pct = int(round(delta * 100))
                    sign = "+" if pct > 0 else ""
                    label = f"{knob_name.replace('_', ' ').title()} {sign}{pct}%"
                    cid = f"c_knob_{knob_name}_{uuid.uuid4().hex[:6]}"
                    c = AppliedConstraint(
                        id=cid,
                        label=label,
                        type="knob",
                        value={"knob": knob_name, "delta": delta},
                        utterance=utterance,
                        created_at=now,
                    )
                    new_constraints.append(c)

            # 2. Popularity Ceiling
            if refinement.popularity_ceiling is not None:
                pct = int(round(refinement.popularity_ceiling * 100))
                cid = f"c_pop_ceil_{uuid.uuid4().hex[:6]}"
                c = AppliedConstraint(
                    id=cid,
                    label=f"Max Popularity: {pct}%",
                    type="popularity_ceiling",
                    value=refinement.popularity_ceiling,
                    utterance=utterance,
                    created_at=now,
                )
                new_constraints.append(c)

            # 3. Boost Tags
            for tw in refinement.boost_tags:
                cid = f"c_boost_{tw.tag}_{uuid.uuid4().hex[:6]}"
                c = AppliedConstraint(
                    id=cid,
                    label=f"+{tw.tag.title()}",
                    type="boost_tag",
                    value={"tag": tw.tag, "weight": tw.weight},
                    utterance=utterance,
                    created_at=now,
                )
                new_constraints.append(c)

            # 4. Suppress Tags
            for tw in refinement.suppress_tags:
                cid = f"c_suppress_{tw.tag}_{uuid.uuid4().hex[:6]}"
                c = AppliedConstraint(
                    id=cid,
                    label=f"No {tw.tag.title()}",
                    type="suppress_tag",
                    value={"tag": tw.tag, "weight": tw.weight},
                    utterance=utterance,
                    created_at=now,
                )
                new_constraints.append(c)

            # 5. Arc
            if refinement.arc is not None:
                cid = f"c_arc_{uuid.uuid4().hex[:6]}"
                c = AppliedConstraint(
                    id=cid,
                    label=f"Arc: {refinement.arc.value.replace('_', ' ').title()}",
                    type="arc",
                    value=refinement.arc.value,
                    utterance=utterance,
                    created_at=now,
                )
                new_constraints.append(c)

            session.constraints.extend(new_constraints)
            # Rebuild context from all active constraints
            self._rebuild_context_locked(session)
            return list(session.constraints)

    def remove_constraint(self, session_id: str, constraint_id: str) -> bool:
        """Remove a constraint by ID and rebuild session context. Returns True if removed."""
        now = time.time()
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return False

            session.last_accessed = now
            initial_len = len(session.constraints)
            session.constraints = [c for c in session.constraints if c.id != constraint_id]

            if len(session.constraints) != initial_len:
                self._rebuild_context_locked(session)
                return True
            return False

    def reset(self, session_id: str) -> None:
        """Reset session context and clear all active constraints."""
        now = time.time()
        with self._lock:
            if session_id in self._sessions:
                session = self._sessions[session_id]
                session.context = SessionContext()
                session.constraints = []
                session.last_accessed = now

    def _rebuild_context_locked(self, session: SessionData) -> None:
        """Replay all active constraints to construct a clean, drift-free SessionContext."""
        ctx = SessionContext()
        for c in session.constraints:
            if c.type == "knob":
                k_name = c.value.get("knob")
                delta = float(c.value.get("delta", 0.0))
                if k_name in ctx.knobs:
                    # Accumulate and clamp to [-1.0, 1.0]
                    ctx.knobs[k_name] = max(-1.0, min(1.0, ctx.knobs[k_name] + delta))
            elif c.type == "popularity_ceiling":
                ctx.popularity_ceiling = float(c.value)
            elif c.type == "boost_tag":
                tag = c.value.get("tag")
                weight = float(c.value.get("weight", 1.0))
                if tag:
                    ctx.boost_tags[tag] = max(ctx.boost_tags.get(tag, 0.0), weight)
            elif c.type == "suppress_tag":
                tag = c.value.get("tag")
                weight = float(c.value.get("weight", 1.0))
                if tag:
                    ctx.suppress_tags[tag] = max(ctx.suppress_tags.get(tag, 0.0), weight)
            elif c.type == "arc":
                ctx.arc = str(c.value)

        session.context = ctx

    def _cleanup_expired_locked(self, now: float) -> int:
        """Evict expired sessions."""
        expired = [
            sid for sid, s in self._sessions.items() if now - s.last_accessed > self.ttl_seconds
        ]
        for sid in expired:
            del self._sessions[sid]
        return len(expired)


# Global singleton instance
global_session_store = SessionStore()
