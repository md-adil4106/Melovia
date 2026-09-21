"""Feedback and Persistent Profile API router for Melovia (Phase 9).

Architecture & Security Constraints:
- Anonymous device profile (no accounts, no passwords, no PII).
- Device ID stored strictly in an httpOnly, SameSite=Lax cookie.
- Device ID is one-way hashed (SHA-256) for all log outputs.
- Session-vs-persistent separation: feedback updates live session taste only.
- Persistent profile updated strictly on explicit POST /profile/remember.
"""

import logging
import uuid
from datetime import UTC, datetime

import numpy as np
from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FeedbackEvent, Profile
from app.db.session import get_db_session
from app.errors import AppException
from app.recsys import (
    CandidatePool,
    CatalogStore,
    RecsysConfig,
    apply_feedback,
    global_candidate_cache,
    merge_modes,
    modes_from_dict,
    modes_to_dict,
    rerank_candidates,
    score_candidates,
)
from app.routers.cookies import get_or_create_device_id, get_or_create_session_id
from app.routers.recommendations import _build_response_items
from app.schemas.feedback import (
    FeedbackEventRequest,
    FeedbackResponse,
    ProfileExportResponse,
    ProfileRememberResponse,
    ProfileStatusResponse,
)
from app.session.store import TokenBucketRateLimiter, global_session_store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["feedback", "profile"])
rate_limiter = TokenBucketRateLimiter(rate=2.0, capacity=30.0)

# ==============================================================================
# Feedback Endpoints
# ==============================================================================


@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit user interaction feedback (like, dislike, skip, save)",
    description=(
        "Applies live feedback to active session taste modes. Dislikes add hard exclusions; "
        "likes shift the nearest mode toward the track vector. Persistent profile is untouched."
    ),
)
async def submit_feedback(
    request: Request,
    response: Response,
    payload: FeedbackEventRequest,
    db: AsyncSession = Depends(get_db_session),
) -> FeedbackResponse:
    catalog_store: CatalogStore | None = getattr(request.app.state, "catalog_store", None)
    if not catalog_store:
        raise AppException(
            code="CATALOG_UNAVAILABLE",
            message="Vector catalog bundle is not mounted",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    device_id, device_hash = get_or_create_device_id(request, response)
    session_id = get_or_create_session_id(request, response)

    # Rate limiting check
    if not rate_limiter.consume(f"fb_{device_hash}", tokens=1.0):
        raise AppException(
            code="RATE_LIMIT_EXCEEDED",
            message="Too many feedback interactions. Please slow down.",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    # Verify track exists in catalog
    if not catalog_store.contains_id(payload.track_id):
        raise AppException(
            code="TRACK_NOT_FOUND",
            message=f"Track ID '{payload.track_id}' not found in catalog",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    config = RecsysConfig()
    _, session_data = global_session_store.get_or_create(session_id)

    # If live_modes is not yet initialized in session, try to get from cached candidate set
    cached_set = None
    if payload.candidate_set_id:
        cached_set = global_candidate_cache.get(payload.candidate_set_id)

    if session_data.live_modes is None:
        if cached_set is not None:
            session_data.live_modes = cached_set.pool.modes
        else:
            # Fallback: build single mode from this track itself
            from app.recsys.taste import build_modes

            session_data.live_modes = build_modes([payload.track_id], catalog_store, config=config)

    # 1. Apply feedback update to live session taste modes (pure Python)
    fb_res = apply_feedback(
        event=payload.event,
        track_id=payload.track_id,
        modes=session_data.live_modes,
        negative_track_ids=session_data.negative_track_ids,
        negative_artist_ids=session_data.negative_artist_ids,
        known_track_ids=session_data.known_track_ids,
        liked_track_ids=session_data.liked_track_ids,
        catalog=catalog_store,
        config=config,
    )

    # Update session data in-memory
    session_data.live_modes = fb_res.updated_modes
    session_data.negative_track_ids = fb_res.negative_track_ids
    session_data.negative_artist_ids = fb_res.negative_artist_ids
    session_data.known_track_ids = fb_res.known_track_ids
    session_data.liked_track_ids = fb_res.liked_track_ids
    session_data.feedback_events_count += 1

    # 2. Persist anonymous feedback event to DB (with graceful memory-only fallback on DB failure)
    try:
        fb_event = FeedbackEvent(
            id=str(uuid.uuid4()),
            device_id=device_id,
            session_id=session_id,
            track_id=payload.track_id,
            event=payload.event.strip().lower(),
            created_at=datetime.now(UTC),
        )
        db.add(fb_event)
        await db.commit()
    except Exception as e:
        logger.warning(
            "Failed to persist feedback to database (degraded to memory-only): %s",
            e,
            extra={
                "request_id": getattr(request.state, "request_id", "-"),
                "event": payload.event,
                "track_id": payload.track_id,
            },
        )
        try:
            await db.rollback()
        except Exception:
            pass

    logger.info(
        "Applied feedback event: type=%s, track_id=%s, mode_idx=%d, device_hash=%s",
        payload.event,
        payload.track_id,
        fb_res.nearest_mode_idx,
        device_hash,
    )

    # 3. If candidate set is active, rerank with updated live modes and exclude negatives
    response_items = []
    if cached_set is not None:
        old_pool = cached_set.pool
        # Filter out negative tracks
        keep_mask = np.array(
            [
                catalog_store.get_id(int(idx)) not in session_data.negative_track_ids
                for idx in old_pool.track_indices
            ],
            dtype=bool,
        )
        if not np.any(keep_mask):
            # If all filtered out (unlikely), keep original
            keep_mask = np.ones(old_pool.size, dtype=bool)

        kept_indices = old_pool.track_indices[keep_mask]
        kept_raw_sims_t = old_pool.raw_sims_t[keep_mask]
        kept_raw_sims_a = old_pool.raw_sims_a[keep_mask]

        updated_pool = CandidatePool(
            track_indices=kept_indices,
            raw_sims_t=kept_raw_sims_t,
            raw_sims_a=kept_raw_sims_a,
            modes=fb_res.updated_modes,
        )

        # Re-score candidates against updated live modes
        rescored = score_candidates(updated_pool, catalog_store, config=cached_set.config)

        # Rerank candidates
        latest_items_count = (
            len(cached_set.latest_reranked.items) if cached_set.latest_reranked else 30
        )
        reranked = rerank_candidates(
            pool=updated_pool,
            scored_list=rescored,
            catalog=catalog_store,
            discovery=cached_set.discovery,
            n=latest_items_count,
            config=cached_set.config,
            session_context=session_data.context,
        )

        # Attach liked track feedback affinity signals if user liked any track
        if session_data.liked_track_ids:
            liked_indices = [
                catalog_store.get_idx(lid)
                for lid in session_data.liked_track_ids
                if catalog_store.contains_id(lid)
            ]
            if liked_indices:
                liked_vecs = catalog_store.vectors_t[liked_indices]
                for it in reranked.items:
                    cand_vec = catalog_store.vectors_t[it.track_idx]
                    sims_to_liked = np.dot(liked_vecs, cand_vec)
                    max_sim_liked = float(np.max(sims_to_liked))
                    nearest_liked_idx = liked_indices[int(np.argmax(sims_to_liked))]
                    nearest_liked_meta = catalog_store.get_track_dict(nearest_liked_idx)

                    if it.signals is not None:
                        it.signals["feedback_similarity"] = round(max_sim_liked, 4)
                        it.signals["nearest_liked_title"] = nearest_liked_meta.get("title")

        # Update cache
        assert payload.candidate_set_id is not None
        global_candidate_cache.update_reranked(
            payload.candidate_set_id,
            reranked,
            cached_set.discovery,
        )

        top_items = reranked.top_n(latest_items_count)
        response_items = _build_response_items(
            top_items=top_items,
            catalog_store=catalog_store,
            include_signals=True,
        )

    mode_shifted = abs(fb_res.cosine_to_track_after - fb_res.cosine_to_track_before) > 0.001

    return FeedbackResponse(
        status="ok",
        event=payload.event,
        track_id=payload.track_id,
        mode_shifted=mode_shifted,
        nearest_mode_idx=fb_res.nearest_mode_idx,
        cosine_shift=round(fb_res.mode_shift_cos, 4),
        candidate_set_id=payload.candidate_set_id,
        items=response_items,
        applied_negatives_count=len(session_data.negative_track_ids),
    )


# ==============================================================================
# Persistent Profile Endpoints
# ==============================================================================


@router.post(
    "/profile/remember",
    response_model=ProfileRememberResponse,
    status_code=status.HTTP_200_OK,
    summary="Merge active session taste modes into persistent profile",
    description=(
        "Explicitly merges live session modes into the persistent profile for this device. "
        "Applies strict Euclidean drift capping (max_drift=0.25) to prevent over-fitting."
    ),
)
async def remember_profile(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
) -> ProfileRememberResponse:
    device_id, device_hash = get_or_create_device_id(request, response)
    session_id = get_or_create_session_id(request, response)

    session_data = global_session_store.get(session_id)
    if not session_data or session_data.live_modes is None:
        raise AppException(
            code="NO_SESSION_MODES",
            message=(
                "No active taste modes in this session to remember. Start discovering music first."
            ),
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    config = RecsysConfig()

    # Query existing persistent profile
    stmt = select(Profile).where(Profile.device_id == device_id)
    res = await db.execute(stmt)
    profile = res.scalar_one_or_none()

    existing_modes = None
    existing_known: set[str] = set()
    if profile:
        existing_modes = modes_from_dict(profile.persistent_modes)
        existing_known = set(profile.known_track_ids or [])

    # Merge session modes into persistent profile with drift capping
    merged_modes = merge_modes(
        persistent_modes=existing_modes,
        session_modes=session_data.live_modes,
        alpha=config.merge_alpha,
        max_drift=config.max_merge_drift,
    )

    combined_known = sorted(existing_known | session_data.known_track_ids)
    modes_json = modes_to_dict(merged_modes)
    now = datetime.now(UTC)

    if profile:
        profile.persistent_modes = modes_json
        profile.known_track_ids = combined_known
        profile.updated_at = now
    else:
        profile = Profile(
            device_id=device_id,
            persistent_modes=modes_json,
            known_track_ids=combined_known,
            created_at=now,
            updated_at=now,
        )
        db.add(profile)

    await db.commit()

    logger.info(
        "Merged session taste into persistent profile: device_hash=%s, num_modes=%d, known=%d",
        device_hash,
        merged_modes.num_modes,
        len(combined_known),
    )

    return ProfileRememberResponse(
        status="ok",
        device_id_hash=device_hash,
        num_modes=merged_modes.num_modes,
        known_tracks_count=len(combined_known),
        updated_at=now,
    )


@router.get(
    "/profile",
    response_model=ProfileStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get status of anonymous persistent taste profile",
)
async def get_profile_status(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
) -> ProfileStatusResponse:
    device_id, device_hash = get_or_create_device_id(request, response)

    stmt = select(Profile).where(Profile.device_id == device_id)
    res = await db.execute(stmt)
    profile = res.scalar_one_or_none()

    if not profile:
        return ProfileStatusResponse(
            has_profile=False,
            device_id_hash=device_hash,
            num_modes=0,
            known_tracks_count=0,
            updated_at=None,
        )

    num_modes = len(profile.persistent_modes.get("weights", []))
    known_count = len(profile.known_track_ids or [])

    return ProfileStatusResponse(
        has_profile=True,
        device_id_hash=device_hash,
        num_modes=num_modes,
        known_tracks_count=known_count,
        updated_at=profile.updated_at,
    )


@router.get(
    "/profile/export",
    response_model=ProfileExportResponse,
    status_code=status.HTTP_200_OK,
    summary="Export portable JSON representation of the persistent profile",
    description="Returns full multi-modal taste representations, weights, and known tracks.",
)
async def export_profile(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
) -> ProfileExportResponse:
    device_id, device_hash = get_or_create_device_id(request, response)

    stmt = select(Profile).where(Profile.device_id == device_id)
    res = await db.execute(stmt)
    profile = res.scalar_one_or_none()

    if not profile:
        raise AppException(
            code="PROFILE_NOT_FOUND",
            message="No persistent profile found for this device to export.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return ProfileExportResponse(
        schema_version="1.0.0",
        device_id_hash=device_hash,
        persistent_modes=profile.persistent_modes,
        known_track_ids=profile.known_track_ids or [],
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.delete(
    "/profile",
    status_code=status.HTTP_200_OK,
    summary="Permanently delete persistent profile and all interaction feedback history",
)
async def delete_profile(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    device_id, device_hash = get_or_create_device_id(request, response)
    session_id = request.cookies.get("melovia_session_id")

    # 1. Delete feedback events
    await db.execute(delete(FeedbackEvent).where(FeedbackEvent.device_id == device_id))

    # 2. Delete profile
    await db.execute(delete(Profile).where(Profile.device_id == device_id))
    await db.commit()

    # 3. Clear session live feedback state if session active
    if session_id:
        sess = global_session_store.get(session_id)
        if sess:
            sess.live_modes = None
            sess.negative_track_ids.clear()
            sess.negative_artist_ids.clear()
            sess.known_track_ids.clear()
            sess.liked_track_ids.clear()

    logger.info("Deleted profile and feedback history for device_hash=%s", device_hash)

    return {
        "status": "ok",
        "message": "Persistent profile and feedback events permanently deleted.",
    }
