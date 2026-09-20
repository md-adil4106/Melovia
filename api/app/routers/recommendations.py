"""Recommendations API router for generating and reranking recommendations."""

import uuid

from fastapi import APIRouter, Request, status

from app.errors import AppException
from app.recsys import (
    CandidateFilters,
    CatalogStore,
    RecsysConfig,
    ScoredItem,
    SeedNotFoundError,
    build_modes,
    generate_candidates,
    global_candidate_cache,
    rerank_candidates,
    score_candidates,
)
from app.schemas.recommendations import (
    RecommendationRequest,
    RecommendationResponse,
    RecommendedTrackItem,
    RerankRequest,
)
from app.schemas.tracks import AudioScalars, TrackDetailResponse

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


def _build_response_items(
    top_items: list[ScoredItem],
    catalog_store: CatalogStore,
    include_signals: bool,
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

        response_items.append(
            RecommendedTrackItem(
                track=track_resp,
                score=item.score,
                signals=item.signals if include_signals else None,
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
    payload: RecommendationRequest,
) -> RecommendationResponse:
    catalog_store: CatalogStore | None = getattr(request.app.state, "catalog_store", None)
    if not catalog_store:
        raise AppException(
            code="CATALOG_UNAVAILABLE",
            message="Vector catalog bundle is not mounted or available",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    config = RecsysConfig()

    # 1. Build taste modes (validating seeds exist)
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

    # 2. Retrieve candidates
    filters = CandidateFilters(
        excluded_artist_ids=set(payload.excluded_artist_ids),
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

    # 4. Cache candidate set in TTL in-process cache
    candidate_set_id = str(uuid.uuid4())
    global_candidate_cache.set(candidate_set_id, pool, scored_list, config)

    # 5. Apply Discovery Control reranking
    final_list = rerank_candidates(
        pool=pool,
        scored_list=scored_list,
        catalog=catalog_store,
        discovery=payload.discovery,
        n=payload.n,
        config=config,
    )

    # 6. Build response items
    top_items = final_list.top_n(payload.n)
    response_items = _build_response_items(
        top_items=top_items,
        catalog_store=catalog_store,
        include_signals=payload.include_signals,
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
