"""Conversational Refinement and Session Steering Router for Melovia.

Architecture & Security Constraints:
- Untrusted LLM boundary: user utterance (max 300 chars) passed as inert data.
- Enforces token-bucket rate limiting per session and client IP.
- Guaranteed deterministic fallback to RuleBasedRefinementParser on timeout (6s) or failure.
- In-memory session store completely isolated from persistent database tables.
- Cookie-based anonymous session continuity.
"""

import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, Response, status

from app.config import get_settings
from app.llm.client import LLMClientError, LLMTimeoutError
from app.llm.rule_parser import RuleBasedRefinementParser
from app.recsys.cache import global_candidate_cache
from app.recsys.catalog import CatalogStore
from app.recsys.rerank import rerank_candidates
from app.schemas.recommendations import RecommendedTrackItem
from app.schemas.refinement import Refinement, filter_unsupported_tags
from app.schemas.session import (
    RefineRequest,
    RefineResponse,
    SessionResetResponse,
)
from app.schemas.signals import RecSignals
from app.schemas.tracks import AudioScalars, TrackDetailResponse
from app.session.store import SessionStore, global_session_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/refine", tags=["refine"])


def _extract_session_id(request: Request, explicit_id: str | None = None) -> str:
    """Extract session ID from explicit payload, cookie, or header, or create a new UUID."""
    if explicit_id and explicit_id.strip():
        return explicit_id.strip()
    cookie_id = request.cookies.get("melovia_session_id")
    if cookie_id and cookie_id.strip():
        return cookie_id.strip()
    header_id = request.headers.get("X-Session-ID")
    if header_id and header_id.strip():
        return header_id.strip()
    return f"sess_{uuid.uuid4().hex}"


def _build_response_items(
    reranked_items: list[Any], catalog_store: CatalogStore
) -> list[RecommendedTrackItem]:
    """Convert ScoredItem objects to user-facing RecommendedTrackItem models."""
    items: list[RecommendedTrackItem] = []
    for it in reranked_items:
        t_dict = catalog_store.get_track_dict(it.track_id)
        raw_scalars = t_dict.get("scalars")
        scalars_obj = AudioScalars(**raw_scalars) if raw_scalars else None

        track_resp = TrackDetailResponse(
            id=str(t_dict["id"]),
            track_idx=int(t_dict["track_idx"]),
            mbid=t_dict.get("mbid"),
            title=str(t_dict["title"]),
            artist_id=str(t_dict["artist_id"]),
            artist_name=str(t_dict.get("artist_name", "")),
            year=t_dict.get("year"),
            isrcs=t_dict.get("isrcs") or [],
            popularity_pct=float(t_dict.get("popularity_pct", 50.0)),
            has_a=bool(t_dict.get("has_a", True)),
            has_t=bool(t_dict.get("has_t", True)),
            scalars=scalars_obj,
        )

        signals_payload = it.signals or {}
        discovery_val = signals_payload.get("discovery_value")
        if discovery_val is None:
            discovery_val = signals_payload.get("discovery_score", 0.0)

        signals_obj: RecSignals | dict[str, Any] = signals_payload
        try:
            signals_obj = RecSignals(**signals_payload)
        except Exception:
            signals_obj = signals_payload

        items.append(
            RecommendedTrackItem(
                track=track_resp,
                score=round(float(it.score), 5),
                signals=signals_obj,
                discovery_value=round(float(discovery_val), 4),
            )
        )
    return items


@router.post(
    "",
    response_model=RefineResponse,
    status_code=status.HTTP_200_OK,
    summary="Refine active recommendations with natural language intent",
)
async def refine_recommendations(
    request: Request,
    response: Response,
    payload: RefineRequest,
) -> RefineResponse:
    """Process natural language refinement, apply session context, and re-rank candidate pool."""
    session_id = _extract_session_id(request, payload.session_id)
    session_store: SessionStore = getattr(request.app.state, "session_store", global_session_store)

    # 1. Rate Limiting Check
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"{session_id}:{client_ip}"
    if not session_store.check_rate_limit(rate_key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": (
                        "Too many refinement requests. Please wait a moment before refining again."
                    ),
                }
            },
        )

    # 2. Retrieve Cached Candidate Pool
    cached = global_candidate_cache.get(payload.candidate_set_id)
    if not cached:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": {
                    "code": "CANDIDATE_SET_EXPIRED",
                    "message": (
                        f"Candidate pool for '{payload.candidate_set_id}' expired or not found. "
                        "Please regenerate recommendations from your seeds."
                    ),
                }
            },
        )

    catalog_store: CatalogStore = request.app.state.catalog_store
    if not catalog_store:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": {
                    "code": "CATALOG_NOT_LOADED",
                    "message": "Catalog store is unavailable.",
                }
            },
        )

    # 3. Parse Refinement Intent (LLM or Rule-Based Fallback)
    llm_client = getattr(request.app.state, "llm_client", None)
    refinement: Refinement

    # Build controlled tag list for prompt filtering
    valid_tags = set(catalog_store.tag_vocab.get("tags", []))
    if not valid_tags and catalog_store._tracks_metadata.get("tags"):
        for t_list in catalog_store._tracks_metadata["tags"]:
            for item in t_list or []:
                if isinstance(item, str):
                    valid_tags.add(item.lower())
                elif isinstance(item, dict) and "name" in item:
                    valid_tags.add(str(item["name"]).lower())

    if llm_client is not None and getattr(llm_client, "api_key", True):
        system_prompt = (
            "You are Melovia's music discovery steering parser.\n"
            "Map the user's utterance into structured musical steering knobs, tags, and arcs.\n"
            "Allowed tags MUST be chosen from the catalog vocabulary."
        )
        try:
            raw_refinement = await llm_client.generate_structured(
                schema=Refinement,
                system_prompt=system_prompt,
                user_content=payload.utterance,
                timeout=6.0,
            )
            refinement = filter_unsupported_tags(raw_refinement, valid_tags)
        except (LLMTimeoutError, LLMClientError, Exception) as exc:
            logger.warning("LLM client failed or timed out (%s), using rule-based parser", exc)
            rule_refinement = RuleBasedRefinementParser.parse(payload.utterance)
            refinement = filter_unsupported_tags(rule_refinement, valid_tags)
    else:
        rule_refinement = RuleBasedRefinementParser.parse(payload.utterance)
        refinement = filter_unsupported_tags(rule_refinement, valid_tags)

    # 4. Apply to Session Context Store
    applied_chips = session_store.apply_refinement(session_id, refinement, payload.utterance)
    session_data = session_store.get(session_id)
    session_ctx = session_data.context if session_data else None

    # 5. Re-rank Candidate Pool using Session Context
    reranked = rerank_candidates(
        pool=cached.pool,
        scored_list=cached.scored_list,
        catalog=catalog_store,
        discovery=cached.discovery,
        n=30,
        config=cached.config,
        session_context=session_ctx,
    )

    # Update latest reranked in cache
    global_candidate_cache.update_reranked(payload.candidate_set_id, reranked, cached.discovery)

    # 6. Build and return response
    response_items = _build_response_items(reranked.items, catalog_store)

    # Set session cookie
    response.set_cookie(
        key="melovia_session_id",
        value=session_id,
        max_age=7200,
        httponly=True,
        samesite="lax",
        secure=get_settings().is_production,
    )

    return RefineResponse(
        session_id=session_id,
        candidate_set_id=payload.candidate_set_id,
        applied=applied_chips,
        unsupported=refinement.unsupported,
        items=response_items,
        clarify=refinement.clarify,
    )


@router.delete(
    "/{constraint_id}",
    response_model=RefineResponse,
    status_code=status.HTTP_200_OK,
    summary="Remove an applied constraint chip and undo its effect",
)
async def remove_constraint(
    constraint_id: str,
    request: Request,
    response: Response,
    candidate_set_id: str = Query(..., description="Active candidate set ID to re-rank"),
) -> RefineResponse:
    """Remove a specific constraint chip from session context and re-rank candidates."""
    session_id = _extract_session_id(request)
    session_store: SessionStore = getattr(request.app.state, "session_store", global_session_store)
    catalog_store: CatalogStore = request.app.state.catalog_store

    # Remove constraint
    removed = session_store.remove_constraint(session_id, constraint_id)
    if not removed:
        logger.info(
            "Constraint '%s' not found or already removed for session '%s'",
            constraint_id,
            session_id,
        )

    session_data = session_store.get(session_id)
    active_chips = session_data.constraints if session_data else []
    session_ctx = session_data.context if session_data else None

    # Re-rank if candidate set is in cache
    cached = global_candidate_cache.get(candidate_set_id)
    response_items: list[RecommendedTrackItem] = []
    if cached and catalog_store:
        reranked = rerank_candidates(
            pool=cached.pool,
            scored_list=cached.scored_list,
            catalog=catalog_store,
            discovery=cached.discovery,
            n=30,
            config=cached.config,
            session_context=session_ctx,
        )
        global_candidate_cache.update_reranked(candidate_set_id, reranked, cached.discovery)
        response_items = _build_response_items(reranked.items, catalog_store)

    return RefineResponse(
        session_id=session_id,
        candidate_set_id=candidate_set_id,
        applied=active_chips,
        unsupported=[],
        items=response_items,
        clarify=None,
    )


@router.post(
    "/session/reset",
    response_model=SessionResetResponse,
    status_code=status.HTTP_200_OK,
    summary="Reset session context and clear all applied constraints",
)
async def reset_session(
    request: Request,
) -> SessionResetResponse:
    """Clear all conversational steering constraints for this session."""
    session_id = _extract_session_id(request)
    session_store: SessionStore = getattr(request.app.state, "session_store", global_session_store)
    session_store.reset(session_id)
    return SessionResetResponse(status="ok", session_id=session_id)
