"""Playlist sequencing API router for Melovia."""

import logging
from typing import Any

from fastapi import APIRouter, Request, Response, status

from app.errors import AppException
from app.recsys import (
    CatalogStore,
    RecsysConfig,
    global_candidate_cache,
    sequence_playlist,
)
from app.routers.cookies import get_or_create_device_id, get_or_create_session_id
from app.schemas.playlist import (
    ArcDataPoint,
    PlaylistSequenceRequest,
    PlaylistSequenceResponse,
    TransitionDetail,
)
from app.schemas.recommendations import RecommendedTrackItem
from app.schemas.tracks import AudioScalars, TrackDetailResponse
from app.session.store import global_session_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/playlist", tags=["playlist"])


def _build_track_detail(t_dict: dict[str, Any]) -> TrackDetailResponse:
    """Helper to convert catalog track dictionary into TrackDetailResponse schema."""
    raw_scalars = t_dict.get("scalars")
    scalars_obj = AudioScalars(**raw_scalars) if raw_scalars else None

    return TrackDetailResponse(
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


@router.post(
    "/sequence",
    response_model=PlaylistSequenceResponse,
    status_code=status.HTTP_200_OK,
    summary="Sequence candidate tracks into a coherent listening progression",
    description=(
        "Applies arc-aware greedy initialization followed by bounded 2-opt search "
        "to optimize playlist flow, transition smoothness, and artist non-adjacency."
    ),
)
async def sequence_tracks(
    req: PlaylistSequenceRequest,
    request: Request,
    response: Response,
) -> PlaylistSequenceResponse:
    """Deterministic playlist sequencing endpoint."""
    catalog_store: CatalogStore | None = getattr(request.app.state, "catalog_store", None)
    if catalog_store is None:
        raise AppException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="CATALOG_UNAVAILABLE",
            message="Vector catalog bundle is not mounted or available.",
        )

    # Manage anonymous device & session cookies
    _device_id = get_or_create_device_id(request, response)
    session_id = req.session_id or get_or_create_session_id(request, response)

    # 1. Resolve tracks to sequence
    track_dicts: list[dict[str, Any]] = []
    item_score_map: dict[str, float] = {}
    item_signals_map: dict[str, Any] = {}
    item_discovery_map: dict[str, float] = {}

    if req.candidate_set_id:
        cached = global_candidate_cache.get(req.candidate_set_id)
        if cached is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="CANDIDATE_SET_NOT_FOUND",
                message=f"Candidate set '{req.candidate_set_id}' has expired or was not found.",
            )
        # Pull top candidates (either from latest reranking or initial scoring)
        source_items = (
            cached.latest_reranked.items
            if cached.latest_reranked
            else cached.scored_list.items
        )
        for it in source_items:
            t_dict = catalog_store.get_track_dict(it.track_idx)
            tid = t_dict["id"]
            track_dicts.append(t_dict)
            item_score_map[tid] = it.score
            item_signals_map[tid] = it.signals
            disc_val = 0.0
            if it.signals:
                raw_disc = it.signals.get("discovery_value", it.signals.get("discovery_score", 0.0))
                disc_val = float(raw_disc)
            item_discovery_map[tid] = disc_val
    elif req.track_ids:
        for tid in req.track_ids:
            if catalog_store.contains_id(tid):
                idx = catalog_store.get_idx(tid)
                t_dict = catalog_store.get_track_dict(idx)
                track_dicts.append(t_dict)
                item_score_map[tid] = 1.0
                item_signals_map[tid] = {}
                item_discovery_map[tid] = 0.0

    if len(track_dicts) < 2:
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INSUFFICIENT_TRACKS",
            message=(
                f"At least 2 tracks are required to sequence a playlist (found {len(track_dicts)})."
            ),
        )

    # 2. Check session context for conversational energy deltas
    energy_delta = 0.0
    session_data = global_session_store.get(session_id)
    if session_data and session_data.context:
        energy_delta = session_data.context.knobs.get("energy", 0.0)

    # 3. Extract semantic vectors for candidate pool
    track_indices = [int(t["track_idx"]) for t in track_dicts]
    vectors_t = catalog_store.vectors_t[track_indices]

    # 4. Run deterministic sequencing
    cfg = RecsysConfig()
    result = sequence_playlist(
        tracks=track_dicts,
        arc=req.arc,
        length=req.length,
        config=cfg,
        vectors_t=vectors_t,
        energy_delta=energy_delta,
    )

    # 5. Format response items
    ordered_items: list[RecommendedTrackItem] = []
    for t_dict in result.ordered_tracks:
        tid = t_dict["id"]
        detail = _build_track_detail(t_dict)
        ordered_items.append(
            RecommendedTrackItem(
                track=detail,
                score=item_score_map.get(tid, 1.0),
                discovery_value=item_discovery_map.get(tid, 0.0),
                signals=item_signals_map.get(tid),
            )
        )

    transition_details = [
        TransitionDetail(
            from_track_id=tr.from_track_id,
            to_track_id=tr.to_track_id,
            tempo_delta=tr.tempo_delta,
            energy_delta=tr.energy_delta,
            semantic_distance=tr.semantic_distance,
            same_artist=tr.same_artist,
            cost=tr.cost,
        )
        for tr in result.transitions
    ]

    arc_points = [
        ArcDataPoint(
            position=ap.position,
            normalized_pos=ap.normalized_pos,
            target_energy=ap.target_energy,
            realized_energy=ap.realized_energy,
            track_id=ap.track_id,
        )
        for ap in result.arc_points
    ]

    logger.info(
        "Sequenced playlist successfully",
        extra={
            "session_id": session_id,
            "arc": req.arc.value if hasattr(req.arc, "value") else str(req.arc),
            "length": len(ordered_items),
            "total_cost": result.total_cost,
            "mean_transition_cost": result.mean_transition_cost,
            "arc_correlation": result.arc_correlation,
            "dropped_features": result.dropped_features,
        },
    )

    return PlaylistSequenceResponse(
        tracks=ordered_items,
        transitions=transition_details,
        arc_points=arc_points,
        total_cost=result.total_cost,
        mean_transition_cost=result.mean_transition_cost,
        arc_correlation=result.arc_correlation,
        active_weights=result.active_weights,
        dropped_features=result.dropped_features,
    )
