"""Recommendations API router for generating and reranking recommendations."""

import uuid
from typing import Any

from fastapi import APIRouter, Request, Response, status

from app.config import get_settings
from app.errors import AppException
from app.llm.polish import LLMPolishService
from app.recsys import (
    CandidateFilters,
    CatalogStore,
    ExplanationBuilder,
    RecsysConfig,
    ScoredItem,
    SeedNotFoundError,
    build_modes,
    generate_candidates,
    global_candidate_cache,
    rerank_candidates,
    score_candidates,
)
from app.routers.cookies import get_or_create_device_id, get_or_create_session_id
from app.schemas.recommendations import (
    RecommendationRequest,
    RecommendationResponse,
    RecommendedTrackItem,
    RerankRequest,
    WhyExplanationReason,
    WhyExplanationResponse,
)
from app.schemas.signals import RecSignals
from app.schemas.tracks import AudioScalars, TrackDetailResponse

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


def _build_response_items(
    top_items: list[ScoredItem],
    catalog_store: CatalogStore,
    include_signals: bool,
    bridge_info: dict[str, Any] | None = None,
) -> list[RecommendedTrackItem]:
    """Helper to convert ScoredItems into API response schemas."""
    response_items: list[RecommendedTrackItem] = []
    for item in top_items:
        t_dict = catalog_store.get_track_dict(item.track_idx)

        raw_scalars = t_dict.get("scalars")
        scalars_obj = AudioScalars(**raw_scalars) if raw_scalars else None

        track_resp = TrackDetailResponse(
            id=t_dict["id"],
            track_idx=t_dict["track_idx"],
            mbid=t_dict.get("mbid"),
            title=t_dict["title"],
            artist_id=t_dict["artist_id"],
            artist_name=t_dict["artist_name"],
            year=t_dict.get("year"),
            isrcs=t_dict.get("isrcs") or [],
            popularity_pct=float(t_dict.get("popularity_pct", 50.0)),
            has_a=bool(t_dict.get("has_a", True)),
            has_t=bool(t_dict.get("has_t", True)),
            region_id=t_dict.get("region_id"),
            scalars=scalars_obj,
            tags=t_dict.get("tags") or [],
        )

        discovery_val = 0.0
        sig_dict = dict(item.signals) if item.signals else {}
        if bridge_info:
            sig_dict.update(bridge_info)
        if sig_dict:
            discovery_val = float(
                sig_dict.get("discovery_value", sig_dict.get("discovery_score", 0.0))
            )

        response_items.append(
            RecommendedTrackItem(
                track=track_resp,
                score=item.score,
                discovery_value=discovery_val,
                signals=sig_dict if include_signals else None,
            )
        )
    return response_items


@router.post(
    "",
    response_model=RecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate relevance-ranked recommendations from seeds",
    description=(
        "Decomposes seeds into taste modes across orthogonal channels, retrieves "
        "candidates, scores relevance, caches the candidate pool, and applies Discovery Control."
    ),
)
async def create_recommendations(
    request: Request,
    response: Response,
    payload: RecommendationRequest,
) -> RecommendationResponse:
    catalog_store: CatalogStore | None = getattr(request.app.state, "catalog_store", None)
    if not catalog_store:
        raise AppException(
            code="CATALOG_UNAVAILABLE",
            message="Vector catalog bundle is not mounted or available",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    device_id, _ = get_or_create_device_id(request, response)
    session_id = get_or_create_session_id(request, response)
    config = RecsysConfig()

    # 1. Build taste modes (from saved taste or seeds)
    if payload.use_saved_taste:
        from sqlalchemy import select

        from app.db.models import Profile
        from app.db.session import async_session_factory
        from app.recsys.feedback import modes_from_dict

        try:
            async with async_session_factory() as db:
                stmt = select(Profile).where(Profile.device_id == device_id)
                res = await db.execute(stmt)
                profile = res.scalar_one_or_none()
        except Exception as e:
            raise AppException(
                code="DATABASE_UNAVAILABLE",
                message=(
                    "Unable to retrieve saved taste profile due to a temporary database issue. "
                    "Try using seed tracks instead."
                ),
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            ) from e

        if not profile:
            raise AppException(
                code="PROFILE_NOT_FOUND",
                message=(
                    "No saved persistent taste profile found on this device. "
                    "Like some tracks and click 'Remember this vibe' first."
                ),
                status_code=status.HTTP_404_NOT_FOUND,
            )
        modes = modes_from_dict(profile.persistent_modes)
    else:
        if not payload.seed_track_ids:
            raise AppException(
                code="INVALID_SEEDS",
                message="At least 1 seed track ID must be provided when use_saved_taste is false.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        try:
            modes = build_modes(payload.seed_track_ids, catalog_store, config=config)
        except SeedNotFoundError as e:
            raise AppException(
                code="TRACK_NOT_FOUND",
                message=str(e),
                status_code=status.HTTP_404_NOT_FOUND,
            ) from e
        except ValueError as e:
            raise AppException(
                code="INVALID_SEEDS",
                message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
            ) from e

    # Initialize live modes in session
    from app.session.store import global_session_store

    _, session_data = global_session_store.get_or_create(session_id)
    session_data.live_modes = modes

    # 2. Retrieve candidates
    filters = CandidateFilters(
        excluded_artist_ids=set(payload.excluded_artist_ids),
        region_id=payload.region_id,
    )
    pool = generate_candidates(
        modes=modes,
        catalog=catalog_store,
        filters=filters,
        k_per_mode=config.k_candidates,
    )

    if pool.size == 0:
        raise AppException(
            code="EMPTY_CANDIDATES",
            message="No candidate tracks found matching the specified criteria",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    # 3. Score candidates for base multi-channel relevance
    scored_list = score_candidates(pool, catalog_store, config=config)

    # 4. Apply Discovery Control reranking
    final_list = rerank_candidates(
        pool=pool,
        scored_list=scored_list,
        catalog=catalog_store,
        discovery=payload.discovery,
        n=payload.n,
        config=config,
    )

    # 5. Cache candidate set in TTL in-process cache
    candidate_set_id = str(uuid.uuid4())
    global_candidate_cache.set(
        candidate_set_id=candidate_set_id,
        pool=pool,
        scored_list=scored_list,
        config=config,
        latest_reranked=final_list,
        discovery=payload.discovery,
    )

    # 6. Build response items with bridge info if region exploration is active
    bridge_info: dict[str, Any] | None = None
    if payload.region_id is not None:
        reg_name = f"Region {payload.region_id}"
        if catalog_store.regions:
            for r in catalog_store.regions:
                if r.get("region_id") == payload.region_id:
                    reg_name = r.get("name", reg_name)
                    break
        bridge_info = {
            "region_id": payload.region_id,
            "bridge_region_name": reg_name,
            "bridge_reason": f"Bridging your taste into {reg_name} (adjacent musical cluster).",
        }

    top_items = final_list.top_n(payload.n)
    response_items = _build_response_items(
        top_items=top_items,
        catalog_store=catalog_store,
        include_signals=payload.include_signals,
        bridge_info=bridge_info,
    )

    return RecommendationResponse(
        candidate_set_id=candidate_set_id,
        total_candidates=final_list.total_candidates,
        items=response_items,
    )


@router.post(
    "/rerank",
    response_model=RecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="Rerank cached candidate set with Discovery Control slider",
    description=(
        "Reranks an existing candidate pool using the Discovery Control slider "
        "(familiarity <-> discovery trade-off) in sub-100ms without repeating catalog retrieval."
    ),
)
async def rerank_recommendations(
    request: Request,
    payload: RerankRequest,
) -> RecommendationResponse:
    catalog_store: CatalogStore | None = getattr(request.app.state, "catalog_store", None)
    if not catalog_store:
        raise AppException(
            code="CATALOG_UNAVAILABLE",
            message="Vector catalog bundle is not mounted or available",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    cached_set = global_candidate_cache.get(payload.candidate_set_id)
    if not cached_set:
        raise AppException(
            code="CANDIDATE_SET_EXPIRED",
            message="Candidate pool expired or invalid. Please re-request recommendations.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    config = cached_set.config

    # Apply Discovery Control reranking on the cached candidate pool
    reranked_list = rerank_candidates(
        pool=cached_set.pool,
        scored_list=cached_set.scored_list,
        catalog=catalog_store,
        discovery=payload.discovery,
        n=payload.n,
        config=config,
    )

    # Update cached set with latest reranked results and discovery level
    global_candidate_cache.update_reranked(
        candidate_set_id=payload.candidate_set_id,
        latest_reranked=reranked_list,
        discovery=payload.discovery,
    )

    top_items = reranked_list.top_n(payload.n)
    response_items = _build_response_items(
        top_items=top_items,
        catalog_store=catalog_store,
        include_signals=payload.include_signals,
    )

    return RecommendationResponse(
        candidate_set_id=payload.candidate_set_id,
        total_candidates=reranked_list.total_candidates,
        items=response_items,
    )


@router.get(
    "/{candidate_set_id}/items/{track_id}/why",
    response_model=WhyExplanationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get signal-true explanation for a recommended track",
    description=(
        "Explains why a track was recommended based on real ranking signals, "
        "shared folksonomy tags, approximate scalar deltas, and discovery control level."
    ),
)
async def get_track_explanation(
    request: Request,
    candidate_set_id: str,
    track_id: str,
) -> WhyExplanationResponse:
    catalog_store: CatalogStore | None = getattr(request.app.state, "catalog_store", None)
    if not catalog_store:
        raise AppException(
            code="CATALOG_UNAVAILABLE",
            message="Vector catalog bundle is not mounted or available",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    cached_set = global_candidate_cache.get(candidate_set_id)
    if not cached_set:
        raise AppException(
            code="CANDIDATE_SET_EXPIRED",
            message="Candidate pool expired or invalid. Please re-request recommendations.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if not catalog_store.contains_id(track_id):
        raise AppException(
            code="TRACK_NOT_FOUND",
            message=f"Track ID '{track_id}' not found in catalog",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # Search for item in latest_reranked, or fallback to scored_list
    target_item: ScoredItem | None = None
    if cached_set.latest_reranked:
        target_item = next(
            (it for it in cached_set.latest_reranked.items if it.track_id == track_id),
            None,
        )

    if not target_item:
        target_item = next(
            (it for it in cached_set.scored_list.items if it.track_id == track_id),
            None,
        )

    if not target_item:
        raise AppException(
            code="TRACK_NOT_FOUND",
            message=f"Track ID '{track_id}' was not found in candidate pool '{candidate_set_id}'",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    signals_dict = dict(target_item.signals or {})
    track_meta = catalog_store.get_track_dict(target_item.track_idx)

    # Nearest seed metadata
    seed_id = str(signals_dict.get("nearest_seed_id", ""))
    seed_meta = (
        catalog_store.get_track_dict(seed_id) if catalog_store.contains_id(seed_id) else None
    )

    discovery_d = cached_set.discovery

    # Generate reasons from rule table
    reasons = ExplanationBuilder.explain(
        signals=signals_dict,
        track_meta=track_meta,
        seed_meta=seed_meta,
        discovery=discovery_d,
        max_reasons=4,
    )

    # Optional LLM polish if enabled
    settings = getattr(request.app.state, "settings", None) or get_settings()
    llm_service = getattr(request.app.state, "llm_polish_service", None)
    if not llm_service:
        llm_service = LLMPolishService(enabled=settings.EXPLAIN_LLM_POLISH)

    polished_reasons, was_polished = await llm_service.polish_reasons(reasons, signals_dict)

    # Format into response schemas
    api_reasons = [
        WhyExplanationReason(
            id=r.id,
            text=r.text,
            signal_keys=r.signal_keys,
            evidence=r.evidence,
            weight=r.weight,
        )
        for r in polished_reasons
    ]

    rec_signals = RecSignals(**signals_dict)

    return WhyExplanationResponse(
        candidate_set_id=candidate_set_id,
        track_id=track_id,
        reasons=api_reasons,
        signals=rec_signals,
        discovery_value=discovery_d,
        llm_polished=was_polished,
    )
