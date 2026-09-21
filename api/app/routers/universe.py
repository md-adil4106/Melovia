import logging

import numpy as np
from fastapi import APIRouter, Depends, Path, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Profile
from app.db.session import get_db_session
from app.errors import AppException
from app.recsys import (
    CatalogStore,
    compute_region_3d_centroids,
    find_original_neighbors,
    place_in_universe,
    quantize_points,
)
from app.routers.cookies import get_or_create_device_id, get_or_create_session_id
from app.schemas.universe import (
    PlacedUniverseItem,
    UniverseMetrics,
    UniverseNeighborItem,
    UniverseNeighborsResponse,
    UniversePlaceRequest,
    UniversePlaceResponse,
    UniverseRegionResponse,
    UniverseResponse,
)
from app.session.store import global_session_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/universe", tags=["universe", "visualization"])

DISTORTION_DISCLAIMER = (
    "Distances in the 3D visualizer are non-linear approximations of 256-dimensional space. "
    "All Melovia recommendations and musical similarity metrics are derived strictly from "
    "high-dimensional embeddings; 3D coordinates are for spatial exploration only."
)


def _get_catalog(request: Request) -> CatalogStore:
    """Helper to retrieve mounted catalog store or raise 503."""
    catalog: CatalogStore | None = getattr(request.app.state, "catalog_store", None)
    if not catalog or catalog.layout3d is None:
        raise AppException(
            code="UNIVERSE_UNAVAILABLE",
            message="3D Universe catalog layout is not mounted or available.",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return catalog


@router.get(
    "",
    response_model=UniverseResponse,
    status_code=status.HTTP_200_OK,
    summary="Get 3D & 2D catalog points, region centroids, and layout quality metrics",
)
async def get_universe(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db_session),
) -> UniverseResponse:
    catalog = _get_catalog(request)
    assert catalog.layout3d is not None

    # 1. Determine user exposure per region from active session and persistent profile
    device_id, _ = get_or_create_device_id(request, response)
    session_id = get_or_create_session_id(request, response)
    _, session_data = global_session_store.get_or_create(session_id)

    known_ids: set[str] = set()
    known_ids.update(session_data.liked_track_ids)
    known_ids.update(session_data.known_track_ids)

    try:
        stmt = select(Profile).where(Profile.device_id == device_id)
        res = await db.execute(stmt)
        profile = res.scalar_one_or_none()
        if profile and profile.known_track_ids:
            known_ids.update(profile.known_track_ids)
    except Exception:
        profile = None

    user_exposures: dict[int, float] = {}
    if known_ids:
        region_counts: dict[int, float] = {}
        total_known = 0
        for tid in known_ids:
            if catalog.contains_id(tid):
                idx = catalog.get_idx(tid)
                reg = catalog._tracks_metadata["region_id"][idx]
                region_counts[int(reg)] = region_counts.get(int(reg), 0.0) + 1.0
                total_known += 1

        if total_known > 0:
            for r_id, count in region_counts.items():
                user_exposures[r_id] = min(1.0, count / float(total_known))

    # 2. Extract render sample points
    sample_indices = catalog.render_sample
    if sample_indices is not None and len(sample_indices) > 0:
        indices_to_render = sample_indices
    else:
        indices_to_render = list(range(catalog.track_count))

    sub_coords = catalog.layout3d[indices_to_render]
    region_col = catalog._tracks_metadata["region_id"]
    sub_regions = [region_col[idx] for idx in indices_to_render]

    # Quantize to compact Int16 representation
    flat_points = quantize_points(
        points_3d=sub_coords,
        region_indices=sub_regions,
        track_indices=indices_to_render,
    )

    # 3. Compute region centroids
    raw_regions = compute_region_3d_centroids(catalog, user_exposures=user_exposures)
    region_responses = [UniverseRegionResponse(**r) for r in raw_regions]

    # 4. Metrics from manifest
    m_dict = catalog.manifest.layout_metrics or {
        "trustworthiness_k15": 0.85,
        "continuity_k15": 0.85,
        "method_3d": "pca-3d",
        "method_2d": "pca-2d",
        "sample_count": len(indices_to_render),
    }
    metrics = UniverseMetrics(**m_dict)

    return UniverseResponse(
        points=flat_points,
        point_count=len(indices_to_render),
        scale=32767.0,
        regions=region_responses,
        metrics=metrics,
    )


@router.post(
    "/place",
    response_model=UniversePlaceResponse,
    status_code=status.HTTP_200_OK,
    summary="Place dynamic vectors (taste modes, seeds) into 3D/2D space via kNN interpolation",
)
async def place_points(
    payload: UniversePlaceRequest,
    request: Request,
) -> UniversePlaceResponse:
    catalog = _get_catalog(request)
    assert catalog.layout3d is not None
    placed_items: list[PlacedUniverseItem] = []

    # 1. Place requested track IDs
    if payload.track_ids:
        for tid in payload.track_ids:
            if catalog.contains_id(tid):
                idx = catalog.get_idx(tid)
                p3 = catalog.layout3d[idx]
                p2 = catalog.layout2d[idx] if catalog.layout2d is not None else None
                placed_items.append(
                    PlacedUniverseItem(
                        id=tid,
                        type="track",
                        position_3d=[round(float(x), 5) for x in p3],
                        position_2d=[round(float(x), 5) for x in p2] if p2 is not None else None,
                        nearest_track_ids=[tid],
                        weights=[1.0],
                    )
                )

    # 2. Place high-dimensional mode vectors via kNN interpolation
    if payload.mode_vectors:
        vectors_arr = np.array(payload.mode_vectors, dtype=np.float32)
        if len(vectors_arr) > 0:
            interp_results = place_in_universe(
                vectors=vectors_arr,
                catalog=catalog,
                k=payload.k,
            )
            for m_idx, res in enumerate(interp_results):
                placed_items.append(
                    PlacedUniverseItem(
                        id=f"mode_{m_idx}",
                        type="taste_mode",
                        position_3d=res["position_3d"],
                        position_2d=res["position_2d"],
                        nearest_track_ids=res["nearest_track_ids"],
                        weights=res["weights"],
                    )
                )

    return UniversePlaceResponse(items=placed_items)


@router.get(
    "/neighbors/{track_id}",
    response_model=UniverseNeighborsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get true nearest neighbors in original vector space with distortion disclaimer",
)
async def get_neighbors(
    track_id: str = Path(..., description="Target track ID to inspect"),
    request: Request = None,  # type: ignore
) -> UniverseNeighborsResponse:
    catalog = _get_catalog(request)

    if not catalog.contains_id(track_id):
        raise AppException(
            code="TRACK_NOT_FOUND",
            message=f"Track ID '{track_id}' was not found in the catalog.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    track_idx = catalog.get_idx(track_id)
    target_dict = catalog.get_track_dict(track_idx)

    # Compute high-dimensional nearest neighbors in original space
    raw_neighbors = find_original_neighbors(track_idx=track_idx, catalog=catalog, k=6)

    neighbor_items = [
        UniverseNeighborItem(
            track_idx=nb["track_idx"],
            track_id=nb["track_id"],
            title=nb["title"],
            artist_name=nb["artist_name"],
            region_id=nb["region_id"],
            similarity_combined=nb["similarity_combined"],
            similarity_t=nb["similarity_t"],
            similarity_a=nb["similarity_a"],
            shared_tags=nb["shared_tags"],
        )
        for nb in raw_neighbors
    ]

    return UniverseNeighborsResponse(
        target_track_id=track_id,
        target_track_title=target_dict.get("title", ""),
        target_region_id=target_dict.get("region_id"),
        neighbors=neighbor_items,
        distortion_disclaimer=DISTORTION_DISCLAIMER,
    )
